# UFMG - DCC - Redes de Computadores
#
#  TP2 - DCCRIP
#
# Lucas Furtini Veado - 2013007609
# 

import sys, socket, struct, json, time
import argparse, threading

PORTA = 55151

# Tabela de vizinhos global usado por roteador
# Layout: {"ip": "distancia"}
tabelaVizinhos = {}

# Tabela de roteador
# Layout: {"ip": [[distancia, proximoPulo, tempo], ...]}
tabelaRoteador = {}

lock = threading.Lock()

def inicializarSocket(host, port):

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind((host, port))
    return udp

def inicializarSockVizinho():

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return udp

def lerArquivo(arquivoComandos):
    with open(arquivoComandos) as fp:
        for linha in fp:
            tratarLinhaDeComando(linha)

def construirParametros():
    
    # Controla os parametros Obrigatorios e Opcionais
    parser = argparse.ArgumentParser()

    # Obrigatorios
    parser.add_argument("hostIP")
    parser.add_argument("timePeriod", type=int)
    # Opcionais
    parser.add_argument("--addr")
    parser.add_argument("--update-period")
    parser.add_argument("--startup-commands")

    return parser.parse_args()

def tratarLinhaDeComando(linhaComando):

    comandos = linhaComando.split()

    # Finalizar execucao
    if comandos[0] == "q" or comandos[0] == "quit":
        exit()

    elif comandos[0] == "add":
        tabelaVizinhos[comandos[1]] = comandos[2]

    elif comandos[0] == "del":
        tabelaVizinhos.pop(comandos[1], None)

    elif comandos[0] == "trace":
        enviarMensagemTrace(comandos[1])
    else:
        print("Comando desconhecido")

# Montar tabela de distancias para enviar nos updates
def montarTabelaDistancia():

    global host

    tabelaDistancias = {}
    tabelaDistancias[host] = "0"
    
    if len(tabelaRoteador) == 0:
        for ip, distancia in tabelaVizinhos.items():
            tabelaDistancias[ip] = distancia
    else:
        for ip, distancia in tabelaRoteador.items():
            tabelaDistancias[ip] = distancia[ip][0]
    
    return tabelaDistancias

# Montar mensagem de update
def montarMensagem(tipo, origem, destino, dados):

    mensagem = {}
    mensagem["type"] = tipo
    mensagem["source"] = origem
    mensagem["destination"] = destino

    if tipo == "trace":
        mensagem["hops"] = dados

    elif tipo == "update":
        mensagem["distances"] = dados
    
    elif tipo == "data":
        mensagem["payload"] = dados

    return mensagem

# Enviar mensagem de dados
def enviarMensagemDados(origem, destino, payload):

    mensagemDado = montarMensagem("data", origem, destino, payload)

    # mensagem = json.dumps(mensagemDado)
    print(mensagemDado)

# Enviar mensagem de trace
def enviarMensagemTrace(destino):

    global host

    rotasDestino = tabelaRoteador[destino]

    if len(rotasDestino) > 1:

        roteadorDestino = rotasDestino[0][1]

        hops = []
        hops.append(host)
        
        mensagemTrace = montarMensagem("trace", host, destino, hops)

        print(mensagemTrace)
        print(roteadorDestino)

# Trata mensagem de update recebida
def tratarMensagemUpdate(data):

    origem = data["source"]
    
    rotasRecebidas = data["distances"]

    pesoRecebido = int(tabelaVizinhos[origem])
    print("Peso Recebido: {}".format(pesoRecebido))

    print("Rotas recebidas: {}".format(rotasRecebidas))
    for ip, distancia in rotasRecebidas.items():

        print(ip)
        print(distancia)
        if ip not in tabelaRoteador:

            novoPeso = pesoRecebido + int(distancia)
            tabelaRoteador[ip] = [[novoPeso, origem]]

    print("----")
    print(tabelaRoteador)




# Funcoes executadas nas threads
# Lida com os inputs do Usuario durante execucao
def lidarComandoUsuario():
    while True:
        comando = input("")
        tratarLinhaDeComando(comando)

# Enviar mensagens de Update periodicamente
def enviarMensagemUpdate(periodo):

    global host

    while True:

        time.sleep(periodo)
        print("Mensagem de update")

        # Montar tabela de distancia
        # Layout: {"ip": distancia}
        tabelaDistancias = montarTabelaDistancia()

        for ip in tabelaVizinhos:
            
            vizinho = inicializarSockVizinho()
            # Split Horizon
            #print("Vizinho: {}".format(ip))

            mensagem = montarMensagem("update", host, ip, tabelaDistancias)

            mensagem = json.dumps(mensagem)

            vizinho.sendto(mensagem.encode('UTF-8'), (ip, PORTA))

# Recebe mensagens de roteadores vizinhos e processa de acordo com cada uma
def receberMensagens(udp):

    while True:

        data, conn = udp.recvfrom(10000)
        data = json.loads(data)

        conn = conn

        tipo = data["type"]

        if tipo == "update":
            tratarMensagemUpdate(data)

# Execucao principal
if __name__ == '__main__':

    global host

    args = construirParametros()

    host = args.hostIP
    periodo = args.timePeriod

    # Opcionais
    if args.addr:
        host = args.addr
    if args.update_period:
        periodo = args.timePeriod
    if args.startup_commands:
        lerArquivo(args.startup_commands)

    udp = inicializarSocket(host, PORTA)

    # Inicializando Threads
    inputThread   = threading.Thread(target=lidarComandoUsuario, args=())
    updateThread  = threading.Thread(target=enviarMensagemUpdate, args=(periodo, ))    
    receiveThread = threading.Thread(target=receberMensagens, args=(udp,))

    try:
        # Thread principal
        inputThread.start()

        updateThread.daemon = True
        updateThread.start()
        receiveThread.daemon = True
        receiveThread.start()
    
    except KeyboardInterrupt:
        inputThread.join()
        updateThread.join()
        receiveThread.join()