#  UFMG - DCC - Redes de Computadores
#  TP2 - DCCRIP
#
#  Lucas Furtini Veado - 2013007609

import sys, socket, struct, json, time
import argparse, threading
from random import randint

PORT = 55151

# Time to leave
ttl = 0

# Global tables use by the current router
# neighbors Table layout:
# {"ip": distance}
neighborsTable = {}

# Router table layout: 
# {"ip": [[distance, nextHop, timeStamp], [distance, nextHop, timeStamp], ...]}
routerTable = {}

lock = threading.Lock()

class Router():

    # Constructor
    def __init__(self, host, port, period):
        self.host = host
        self.port = port
        self.period = period

    # Initialize UDP socket 
    def initSocket(self):
        
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp.bind((self.host, self.port))
        return self.udp

    # Initialize neighbor socket
    def initNeighborSocket(self):
      
        self.udpNeighbor = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        self.udpNeighbor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return self.udpNeighbor

    # Handle user input
    #   - "add ip cost" : add new router to topology
    #   - "del ip"      : remove ip from topology
    #   - "trace ip"    : calculate hops to the ip destination
    #   - Ctrl+c        : terminate the program
    def handleUserInput(self):
        while True:
            line = input("")
            self.handleCommand(line)

    # Read a command line, break it and do the respective action (add, del, trace)
    def handleCommand(self, commandLine):

        line = commandLine.split()

        # line[0] = command
        # line[1] = ip
        # line[2] = distance
        if line[0] == "q" or line[0] == "Q":
            exit()

        elif line[0] == "add": self.handleAdd(line[1], line[2])

        elif line[0] == "del":
            neighborsTable.pop(line[1], None)

        elif line[0] == "trace":
            self.sendTrace(line[1])

        elif line[0] == "v":
            print("---------")
            print("VIZINHOS: {}".format(neighborsTable))
            print("---------")
            print("ROTEADOR: {}".format(routerTable))

        else:
            print("Unknow command. Try again.")

    # handle add command
    def handleAdd(self, ip, distance):
        
        global period

        if ip == self.host:
            return

        if ip not in neighborsTable:
            neighborsTable[ip] = distance

        if ip not in routerTable:
            routerTable[ip] = [[distance, ip, (4 *  period)]]

    # Create JSON message to send
    def createMessage(self, messageType, destination, data):

        message = {}
        message["type"] = messageType
        message["source"] = self.host
        message["destination"] = destination

        if messageType == "trace":
            message["hops"] = data
        elif messageType == "update":
            message["distances"] = data
        elif messageType == "data":
            message["payload"] = data

        message = json.dumps(message)

        return message

    # Receive messagens
    #  - update messages: update router table
    #  - trace messages: check if is destination:
    #       case true - send back data message
    #       case false - add ip to hops list, send message to shortest path to destination
    def receive(self):

        while True:
            
            data, conn = self.udp.recvfrom(10000)
            conn = conn # ignorar warning

            data = json.loads(data)
            
            messageType = data["type"]

            # Update Message
            if messageType == "update": self.receivedUpdate(data)
                
            # Trace Message
            if messageType == "trace": self.receivedTrace(data)
                
            # Data Message
            if messageType == "data": self.receiveData(data)

    # Deal with received update
    def receivedUpdate(self, data):

        # Save the distances received from update from neighbor              
        sourceIP = data["source"]
        
        newDistances = data["distances"]

        if sourceIP in neighborsTable: 
            neighborDist = neighborsTable[sourceIP] 

        # Loop through list of distances received                
        # Checking if each IP are on the router table
        for ip, dist in newDistances.items():

            if ip not in routerTable:
                newDist = int(dist) + int(neighborDist)
                # Add ip to the route
                routerTable[ip] = [[str(newDist), sourceIP, ttl]]
            
            else:
                routes = routerTable[ip]

                oldDistance = routes[0][0]


    # Deal with received trace     
    def receivedTrace(self, data):

        data["hops"].append(self.host)
        
        sourceIP = data["source"]
        destinationIP = data["destination"]

        # Check if is destination, case true: send data message to source with hops list
        if destinationIP == self.host:

            self.sendData(data["hops"], sourceIP)

        # If its not destination, send to next known address
        else:

            nextIP = self.initNeighborSocket()
            
            if destinationIP in neighborsTable:
                nextHop = destinationIP
            
            else:
                # Check if next hop has more then one route
                if len(routerTable[destinationIP]) > 1:

                    # Get next hop through load balance algorith
                    nextHop = self.loadBalance(routerTable[destinationIP])

                else:
                    # Get next hop
                    nextHop = routerTable[destinationIP][0][1]

            # Send message
            data = json.dumps(data)
            nextIP.sendto(data.encode('UTF-8'), (nextHop, PORT))

    # Deal with received data message
    def receiveData(self, data):

        destinationIP = data["destination"]

        #Current router is the destination
        if destinationIP == self.host:
            # Print payload field on message
            print(data["payload"])

        # Current router is not the destination
        else:

            # Beggin socket connection to send trace to next hop
            nextIP = self.initNeighborSocket()

            # Check if next hop has more then one route
            if len(routerTable[destinationIP]) > 1:

                # Get next hop through load balance algorith
                nextHop = self.loadBalance(routerTable[destinationIP])

                # Send message
                data = json.dumps(data)
                nextIP.sendto(data.encode('UTF-8'), (nextHop, PORT))

            # If only one route to destination
            else:
                # Get next hop
                nextHop = routerTable[destinationIP][0][1]
                
                # Send message
                data = json.dumps(data)
                nextIP.sendto(data.encode('UTF-8'), (nextHop, PORT))

    # Send periodic update messagens
    #   - Time period read from input parameter
    #   - Send update message to all neighbors (Split Horizon optimization)
    def sendUpdate(self, period):
        
        while True:
            # Sleep thread until "period", send update after
            time.sleep(period)
         
            # No neighbors
            if not neighborsTable:
                continue
            
            # Loop through all neighbors
            for ip in neighborsTable:

                distanceTable = self.buildDistanceTable(ip)
               
                # Split Horizon
                # Remove the route that goes to the neighbor of the message to the neighbor
                
                neighbor = self.initNeighborSocket()

                updateMessage = self.createMessage("update", ip, distanceTable) 
                
                neighbor.sendto(updateMessage.encode('UTF-8'), (ip, PORT))
                
    # Send trace message to destination
    def sendTrace(self, dest):

        neighbor = self.initNeighborSocket()

        # Check if destination is neighbor
        if dest in neighborsTable:
            nextHop = dest
 
        else:
            destRoutes = routerTable[dest]

            # Check for the number of routes
            # If more then 1, check for distances values
            if len(destRoutes) > 1:
                # Get next hop through load balance algorithm
                nextHop = self.loadBalance(destRoutes)
                
            # Ip is not on router table
            else:
                nextHop = routerTable[dest][0][1]

        hops = [self.host]

        traceMessage = self.createMessage("trace", dest, hops)
        neighbor.sendto(traceMessage.encode('UTF-8'), (nextHop, PORT))

    # Send data message back to the destination required
    def sendData(self, hops, dest):

        neighbor = self.initNeighborSocket()

        if dest in neighborsTable:
            nextHop = dest        
        
        else:
            # Get the list of routes to destination
            destRoutes = routerTable[dest]
        
            # Check for the number of routes
            # If more then 1, check for distances values
            if len(destRoutes) > 1:
                # Get next hop through load balance algorithm
                nextHop = self.loadBalance(destRoutes)

            # If only one route, send to id
            else:
                nextHop = routerTable[dest][0][1]
            
        dataMessage = self.createMessage("data", dest, hops)
        neighbor.sendto(dataMessage.encode('UTF-8'), (nextHop, PORT))

    # Delete routes after 4 pi times passed
    def deleteRoutes(self, period):

        # Keep cheking the router list looking for routers that passed 4 * period without atualization
        # If the time withou update pass 4*pi remove route from table.
        while True:

            time.sleep(period)

            lock.acquire()
            # Loop through router list
            for ip, routes in routerTable.items():
                
                # check for more than 1 route
                if len(routes) > 1:
                    for index in range(len(routes)):
                        routes[index][2] -= 1
                        
                        if routes[index][2] <= 0 : routes.pop(index)
                else:
                    routes[0][2] -= 1      
                    if routes[0][2] <= 0 : routerTable.pop(ip)

            lock.release()

    # Build disntance table to send across the network
    def buildDistanceTable(self, destination):

        distanceTable = {}

        if routerTable:
            for ip, routes in routerTable.items():
                if ip != destination:
                    distanceTable[ip] = routes[0][0]

        distanceTable[self.host] = "0"

        return distanceTable

    # Calculate the load balance for a given list of routes and distances
    # Input: list of routes to a given IP
    # Input Model: [[distance, nextHop, timeStamo], [distance, nextHop, timeStamo], ...]
    # Output: an address to send the next message
    def loadBalance(self, destRoutes):
        
        # Get the number of repeated routes for the smaller route
        numberReapetedRoutes = len(destRoutes)

        # int that represents the ID of the router to send
        routerToSend = randint(0, numberReapetedRoutes-1)

        # Get the ip to the next route
        routerToSendIP = destRoutes[routerToSend][1]

        return routerToSendIP

    # Read input commands from file passed as parameter
    # Call handleCommand to break the lines and do the respective action
    def readFile(self, inputFile):
        with open(inputFile) as fp:
            for line in fp:
                self.handleCommand(line)

def defineParameters():
    
    # Control for requiered and optional paramethers
    parser = argparse.ArgumentParser()
    # Requiered
    parser.add_argument("hostIP")
    parser.add_argument("timePeriod", type=int)
    # Optional
    parser.add_argument("--addr")
    parser.add_argument("--update-period")
    parser.add_argument("--startup-commands")

    return parser.parse_args()

# Main execution
if __name__ == '__main__':

    global period

    args = defineParameters()

    host = args.hostIP
    period = args.timePeriod

    # Optional IP add parameter
    if args.addr:
        host = args.addr
    # Optional update period parameter
    if args.update_period:
        period = args.timePeriod

    router = Router(host, PORT, period)
    
    ttl = 4 * period

    # Optional startup commands parameter
    if args.startup_commands:
        router.readFile(args.startup_commands) 

    router.initSocket()

    # Initialize Threads
    inputThread   = threading.Thread(target = router.handleUserInput, args = ())
    
    updateThread  = threading.Thread(target = router.sendUpdate, args = (period,))
    updateThread.daemon = True
    receiveThread = threading.Thread(target = router.receive, args = ())
    receiveThread.daemon = True
    deleteThread  = threading.Thread(target = router.deleteRoutes, args = (period,))
    deleteThread.daemon = True

    try:
        inputThread.start()
        updateThread.start()
        receiveThread.start()
        deleteThread.start()

    except KeyboardInterrupt:
        updateThread.join()