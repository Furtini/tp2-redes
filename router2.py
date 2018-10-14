# UFMG - DCC - Redes de Computadores
#
#  TP2 - DCCRIP
#
# Lucas Furtini Veado - 2013007609
# 
# 

import sys, socket, struct, json, time
import argparse, threading

# Tabela de vizinhos global usado por roteador
# Layout: {"ip": "distancia"}
tabelaVizinhos = {}

# Tabela de roteador
# Layout: {"ip": [[distancia, proximoPulo, tempo], ...]}
tabelaRoteador = {}

lock = threading.Lock()

# Inicializa, da bind e retorna um socket UDP
def inicializarSocket(host, port):

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind((host, port))
    return udp

# Inicializar e retorna um socket UDP
def inicializarSockVizinho():

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return udp

def lerArquivo(arquivoComandos):

    with open(arquivoComandos) as fp:
        for linha in fp:
            tratarLinha(linha)

# Define os parametros recebidos ao executar
def definirParametros():
    
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

# Verifica qual o tipo de comando e executa o comando apropriado
def tratarLinha(linhaComando):

    comandos = linhaComando.split()

    # Finalizar execucao
    if comandos[0] == "q" or comandos[0] == "quit":
        exit()

    elif comandos[0] == "add":
        print("add")
        tabelaVizinhos[comandos[1]] = comandos[2]
        print(tabelaVizinhos)
        return "add"

    elif comandos[0] == "del":
        print("del")
        tabelaVizinhos.pop(comandos[1], None)
        print(tabelaVizinhos)
        return "del"

    elif comandos[0] == "trace":
        print("trace")
        return "trace"
    
    else:
        print("Comando desconhecido")
        return "desconhecido"

# Funcoes executadas nas threads
# Lida com os inputs do Usuario durante execucao
def lidarComandoUsuario():
    
    while True:
        comando = input("")
        tratarLinha(comando)

# Enviar mensagens de Update periodicamente
def enviarUpdate(periodo):

    while True:

        time.sleep(periodo)
        print("Mensagem de update")

        for ip in tabelaVizinhos:
            
            # Split Horizon
            print("Vizinho: {}".format(tabelaVizinhos[ip]))

# Execucao principal
if __name__ == '__main__':

    args = definirParametros()

    host = args.hostIP
    periodo = args.timePeriod

    # Opcionais
    if args.addr:
        host = args.addr
    if args.update_period:
        periodo = args.timePeriod
    if args.startup_commands:
        lerArquivo(args.startup_commands)

    # Inicializando Threads
    inputThread = threading.Thread(target=lidarComandoUsuario, args=())
    updateThread = threading.Thread(target=enviarUpdate, args=(periodo, ))    
        
    try:
        # Thread principal
        inputThread.start()

        updateThread.daemon = True
        updateThread.start()
    
    except KeyboardInterrupt:
        inputThread.join()
        updateThread.join()