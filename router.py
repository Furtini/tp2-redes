#  UFMG - DCC - Redes de Computadores
#  TP2 - DCCRIP
#
#  Lucas Furtini Veado - 2013007609

import sys, socket, struct, json, time
import argparse, threading
from random import randint

PORT = 55151

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
            self.handleLine(line)

    # Read a command line, break it and do the respective action (add, del, trace)
    def handleLine(self, commandLine):

        line = commandLine.split()

        # line[0] = command
        # line[1] = ip
        # line[2] = weight
        if line[0] == "q" or line[0] == "Q":
            exit()

        elif line[0] == "add":
            neighborsTable[line[1]] = line[2]
            #routerTable[line[1]] = [[line[2], line[1], time.time()]]

        elif line[0] == "del":
            neighborsTable.pop(line[1], None)
            #routerTable.pop(line[1], None)

        elif line[0] == "trace":
            self.sendTrace(line[1])

        else:
            print("Unknow command. Try again.")

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

            data = json.loads(data)
            
            messageType = data["type"]
            sourceIP = data["source"]
            destinationIP = data["destination"]

            # Update Message
            if messageType == "update":
                
                # Update time stamps
                
                # Save the distances received from update from neighbor              
                new_distances = data["distances"]

                # Weight to the neighbor where the message came from
                weightToNeighbor = int(neighborsTable[sourceIP])

                # Loop through list of distances received                
                # Checking if each IP are on the router table
                for ip, dist in new_distances.items():
                   
                    newWeight = int(dist[0]) + weightToNeighbor

                    # If IP read is not on the router table, add it with current time stamp
                    if ip not in routerTable:
                        
                        # Add ip to the route
                        routerTable[ip] = [[newWeight, sourceIP, time.time()]]
                    
                    # New ip already in router table
                    # Check if new weight is lower then new one
                    else:
                        # Since we can have multiple routes with the same weight to the same destination
                        # We need to check all of then
                        
                        # All routes known of the ip received
                        numberOfKnownRoutes = len(routerTable[ip])
                        
                        # Oold weight save in the router table
                        oldWeight = int(routerTable[ip][0][0])

                        # New weight is lower then current weight
                        # Replace with new weight
                        if newWeight < oldWeight:

                            # Loop through all known routes to to the ip to update values
                            for i in range(numberOfKnownRoutes):
                                routerTable[ip][i][0] = newWeight
                                routerTable[ip][i][1] = sourceIP
                                routerTable[ip][i][2] = time.time()

                        # We need to save the routes with the same weight and nexHop to the IP
                        # Same weight, add route to list
                        elif newWeight == oldWeight:
                            
                            # Check if nextHop already on list
                            for sublist in routerTable[ip]:
                                # If next hop is already on the list, do nothing                                
                                if sublist[1] == sourceIP:
                                    break
                            # if the next hopis not on the list, add new route to the same ip.
                            else:
                                routerTable[ip].append([newWeight,sourceIP, time.time()])
                        
                        # If new weight is bigger then current one
                        else:

                            nextHop = routerTable[ip][0][1]

                            # Check if next hop is current neighbord, update weight
                            if nextHop == sourceIP:
                                for i in range(numberOfKnownRoutes):
                                    routerTable[ip][i][0] = newWeight
                                    routerTable[ip][i][2] = time.time()
                    
            # Trace Message
            if messageType == "trace":

                # Check if is destination, case true: send data message to source with hops list
                if destinationIP == self.host:
                    # Get next hop
                    nextHop = routerTable[sourceIP][0][1]
                    
                    # Send   hops list from trace message.
                    self.sendData(data["hops"], sourceIP, nextHop)
                
                # If its not destination, send to next known address
                else:

                    # Initialize neighbor connection
                    nextIP = self.initNeighborSocket()
                    
                    # Append IP to Hops list
                    data["hops"].append(self.host)
                    
                    # Check if next hop has more then one route
                    if len(routerTable[destinationIP]) > 1:

                        # Get next hop through load balance algorith
                        nextHop = self.loadBalance(routerTable[destinationIP])

                        # Send message
                        data = json.dumps(data)
                        nextIP.sendto(data.encode('UTF-8'), (nextHop, 55151))

                    else:
                        # Get next hop
                        nextHop = routerTable[destinationIP][0][1]

                        # Send message
                        data = json.dumps(data)
                        nextIP.sendto(data.encode('UTF-8'), (nextHop, 55151))

            # Data Message
            if messageType == "data":
                
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
                        nextIP.sendto(data.encode('UTF-8'), (nextHop, 55151))

                    # If only one route to destination
                    else:
                        # Get next hop
                        nextHop = routerTable[destinationIP][0][1]
                        
                        # Send message
                        data = json.dumps(data)
                        nextIP.sendto(data.encode('UTF-8'), (nextHop, 55151))

    # Send periodic update messagens
    #   - Time period read from input parameter
    #   - Send update message to all neighbors (Split Horizon optimization)
    def sendUpdate(self, period):
        
        # Setting up distances table to send in the update messages
        # Format: {ip: distance}
        distanceTable = {}
        if len(routerTable) == 0:
            for ip in neighborsTable:
                distanceTable[ip] = neighborsTable[ip]
        else:
            for ip in list(routerTable):
                distanceTable[ip] = routerTable[ip][0][0]
            

        while True:
            # Sleep thread until "period", send update after
            time.sleep(period)
           
            # Loop through all neighbors
            for ip in neighborsTable:

                # Split Horizon
                # Remove the route that goes to the neighbor of the message to the neighbor
                if ip in list(routerTable):
                    # Remove the knowing route to neighbor
                    removedRoute = distanceTable.pop(ip)

                    # Beggin socket connection to send trace to next hop
                    neighbor = self.initNeighborSocket()

                    # Create Message
                    updateMessage = self.createMessage("update", ip, distanceTable) 
                    
                    # Send menssage
                    neighbor.sendto(updateMessage.encode('UTF-8'), (ip, 55151))
                    
                    # Re add revomed route to router table
                    distanceTable[ip] = removedRoute

                # Ip is not on router table
                else:
                    # Beggin socket connection to send trace to next hop
                    neighbor = self.initNeighborSocket()

                    # Create message
                    updateMessage = self.createMessage("update", ip, distanceTable)

                    # send message
                    neighbor.sendto(updateMessage.encode('UTF-8'), (ip, 55151))

    # Send trace message to destination
    def sendTrace(self, dest):

        # Get list of known routes to destination
        destRoutes = routerTable[dest]

        # Check for the number of routes
        # If more then 1, check for distances values
        if len(destRoutes) > 1:
            
            # Get next hop through load balance algorithm
            routerToSendIP = self.loadBalance(destRoutes)

            # Beggin socket connection to send trace to next hop
            neighbor = self.initNeighborSocket()

            
            # Create message
            hops = [self.host]
            traceMessage = self.createMessage("trace", dest, hops)
            
            # Send message            
            neighbor.sendto(traceMessage.encode('UTF-8'), (routerToSendIP, 55151))

        # Ip is not on router table
        else:
            # Beggin socket connection to send trace to next hop
            neighbor = self.initNeighborSocket()

            # Create message
            hops = [self.host]
            traceMessage = self.createMessage("trace", dest, hops)
            
            # Get next hop
            nextHop = routerTable[dest][0][1]
            # Send message
            neighbor.sendto(traceMessage.encode('UTF-8'), (nextHop, 55151))

    # Send data message back to the destination required
    def sendData(self, hops, dest, nextHop):
       
        # Get the list of routes to destination
        destRoutes = routerTable[dest]
        
        # Check for the number of routes
        # If more then 1, check for distances values
        if len(destRoutes) > 1:

            # Get next hop through load balance algorithm
            routerToSendIP = self.loadBalance(destRoutes)

            # Beggin socket connection to send trace to next hop
            neighbor = self.initNeighborSocket()

            # Create message
            dataMessage = self.createMessage("data", dest, hops)
            
            # Send message
            # Check if router is neighbor
            if nextHop == "":  # is neighbor
                neighbor.sendto(dataMessage.encode('UTF-8'), (dest, 55151))
            else:
                neighbor.sendto(dataMessage.encode('UTF-8'), (routerToSendIP, 55151))

        # If only one route, send to id
        else:
            # Beggin socket connection to send trace to next hop
            neighbor = self.initNeighborSocket()
            
            # Create message
            dataMessage = self.createMessage("data", dest, hops)
            
            # Send message
            # Check if router is neighbor 
            if nextHop == "": # is neighbor
                neighbor.sendto(dataMessage.encode('UTF-8'), (dest, 55151))
            else:
                neighbor.sendto(dataMessage.encode('UTF-8'), (nextHop, 55151))

    # Delete routes after 4 pi times passed
    def deleteRoutes(self, period):

        # Keep cheking the router list looking for routers that passed 4 * period without atualization
        # If the time withou update pass 4*pi remove route from table.
       """
        while True:

            timeToLive = (period * 4)
            currentTime = time.time()

            # Loop through router list
            for ip in list(routerTable):
                #list of all routes known by current ip
                routes = routerTable[ip]

                # check for more than 1 route
                if len(routes) > 1:
                    for index in range(len(routes)):
                        if (currentTime - routes[index][2]) >= timeToLive:
                            routerTable[ip].remove[index]
                        else:
                            continue

                else:
                    if (currentTime - routes[0][2]) >= timeToLive:
                        routerTable.pop(ip, None)
                    else:
                        continue            
        """
    # Calculate the load balance for a given list of routes and distances
    # Input: list of routes to a given IP
    # Input Model: [[weight, nextHop, timeStamo], [weight, nextHop, timeStamo], ...]
    # Output: an address to send the next message
    def loadBalance(self, destRoutes):
        
        # Get list os distances!!! ACHO Q NAO PRECISA, TESTAR!
        #distances = [int(i[0]) for i in destRoutes]

        # Se nao precisar, counter = len
        #counter = collections.Counter(distances)

        # Get the number of repeated routes for the smaller route
        numberReapetedRoutes = len(destRoutes)

        # int that represents the ID of the router to send
        routerToSend = randint(0, numberReapetedRoutes-1)

        # Get the ip to the next route
        routerToSendIP = destRoutes[routerToSend][1]

        return routerToSendIP

    # Read input commands from file passed as parameter
    # Call handleLine to break the lines and do the respective action
    def readFile(self, inputFile):

        with open(inputFile) as fp:
            for line in fp:
                self.handleLine(line)

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