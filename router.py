#  UFMG - DCC - Redes de Computadores
#  TP2 - DCCRIP
#
#  Lucas Furtini Veado - 2013007609
#  Caio Augusto Ferreira Godoy -

import sys
import socket
import struct
import json
import time
import argparse
import threading
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
    def __init__(self, host, port, period):
        self.host = host
        self.port = port
        self.period = period

    def initSocket(self):
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp.bind((self.host, self.port))
        return self.udp

    def initNeighborSocket(self):
        self.udpNeighbor = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        self.udpNeighbor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return self.udpNeighbor

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
        if not line:
            return

        if line[0] == "q" or line[0] == "Q":
            exit()

        elif line[0] == "add":
            self.handleAddCommand(line[1], line[2])

        elif line[0] == "del":
            self.handleDelCommand(line[1])

        elif line[0] == "trace":
            self.sendTrace(line[1])

        elif line[0] == "v":
            print("---------")
            print("VIZINHOS: {}".format(neighborsTable))
            print("---------")
            print("ROTEADOR: {}".format(routerTable))

        elif line[0] == "f":
            self.sendUpdate()

        else:
            print("Unknow command. Try again.")
            return

    def handleAddCommand(self, ip, distance):
        if ip == self.host:
            return

        if ip not in neighborsTable:
            neighborsTable[ip] = distance

        if ip not in routerTable:
            routerTable[ip] = [[distance, ip, time.time()]]

    def handleDelCommand(self, ip):
        neighborsTable.pop(ip)

        for ip, dist in routerTable.copy().items():
            if dist[1] == ip:
                routerTable[ip].remove(dist)

    def createMessage(self, messageType, destination, data):
        # Create JSON message to send
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

    def receive(self):
        while True:
            data, conn = self.udp.recvfrom(10000)
            conn = conn  # ignorar warning

            data = json.loads(data)

            messageType = data["type"]

            lock.acquire()
            # Update Message
            if messageType == "update":
                self.receivedUpdate(data)

            # Trace Message
            if messageType == "trace":
                self.receivedTrace(data)

            # Data Message
            if messageType == "data":
                self.receiveData(data)

            lock.release()

    def receivedUpdate(self, data):
        # Save the distances received from update from neighbor
        sourceIP = data["source"]

        newDistances = data["distances"]

        if sourceIP not in neighborsTable:
            return

        nextHop = sourceIP
        neighborDistance = int(neighborsTable[sourceIP])

        # Loop through list of distances received
        # Checking if each IP are on the router table
        for ip, dist in newDistances.items():
            if ip not in routerTable:
                routerTable[ip] = []
                for route in dist:
                    newDist = int(route[0]) + neighborDistance
                    routerTable[ip].append(
                        [str(newDist), nextHop, time.time()])
            else:
                for newRoute in dist:
                    newDist = int(newRoute[0]) + neighborDistance

                    for oldRoute in routerTable[ip]:
                        if oldRoute[1] == sourceIP:
                            oldRoute[2] = time.time()
                            break
                        elif oldRoute[1] != sourceIP:
                            if newDist <= int(oldRoute[0]):
                                novo = [[str(newDist), sourceIP, time.time()]]
                                routerTable[ip] = novo + routerTable[ip]
                            else:
                                # if oldRoute[1] != sourceIP:
                                novo = [[str(newDist), sourceIP, time.time()]]
                                routerTable[ip] = routerTable[ip] + novo
        self.fixRoutes()

    def fixRoutes(self):
        # Fix routes on router table, removing duplicates and ordering by small distance
        for ip, dist in routerTable.items():

            seen = set()
            # Remove duplicates on router based on nextHop value
            dist = [x for x in dist if x[1] not in seen and not seen.add(x[1])]
            dist = sorted(dist, key=lambda x: int(x[0]))
            routerTable[ip] = dist

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

    def receiveData(self, data):
        destinationIP = data["destination"]

        # Current router is the destination
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

    def sendUpdate(self):
        # No neighbors
        if not neighborsTable:
            return

        # print("Enviando Update")
        # Loop through all neighbors
        for ip in neighborsTable.copy():
            distanceTable = self.buildDistanceTable(ip)

            # Split Horizon
            # Remove the route that goes to the neighbor of the message to the neighbor
            neighbor = self.initNeighborSocket()

            updateMessage = self.createMessage("update", ip, distanceTable)
            # print(updateMessage)
            neighbor.sendto(updateMessage.encode('UTF-8'), (ip, PORT))

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

    def deleteRoutes(self):
        # Loop through router list
        for ip, routes in routerTable.copy().items():
            for route in routes:
                if time.time() - route[2] >= ttl:
                    routes.remove(route)
            if not routerTable[ip]:
                neighborsTable.pop(ip, None)
                routerTable.pop(ip, None)

    # Build disntance table to send across the network
    def buildDistanceTable(self, destination):
        distanceTable = {}

        if routerTable:
            for ip, routes in routerTable.items():
                if ip == destination:
                    continue
                else:
                    distanceTable[ip] = []
                    for route in routes:
                        if route[1] == destination:
                            continue
                        else:
                            distanceTable[ip].append(route)

        distanceTable[self.host] = "0"
        return distanceTable

    def loadBalance(self, destRoutes):
        
        repeatedRoutes = []

        distance = int(destRoutes[0][0])
        repeatedRoutes.append(destRoutes[0][1])

        for route in destRoutes:
            if int(route[0]) == distance:
                repeatedRoutes.append(route[1]) 
        
        # Get the number of repeated routes for the smaller route
        numberReapetedRoutes = len(repeatedRoutes)

        # int that represents the ID of the router to send
        routerToSend = randint(0, numberReapetedRoutes-1)

        # Get the ip to the next route
        routerToSendIP = repeatedRoutes[routerToSend]

        return routerToSendIP

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

# Helper function that simulates js setInterval
def set_interval(func, sec):
    def func_wrapper():
        set_interval(func, sec)
        func()
    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t

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

    ttl = 4 * period

    # Optional startup commands parameter
    if args.startup_commands:
        router.readFile(args.startup_commands)

    router.initSocket()

    # Initialize Threads
    inputThread = threading.Thread(target=router.handleUserInput, args=())

    updateThread = set_interval(router.sendUpdate, period)

    deleteThread = set_interval(router.deleteRoutes, period)

    receiveThread = threading.Thread(target=router.receive, args=())
    receiveThread.daemon = True

    inputThread.start()
    receiveThread.start()
    