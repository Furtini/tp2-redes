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

def tratarLinha(linhaComando):

    linha = linhaComando.spli()

    if linha[0] == "add":
        print("add")
        tabelaVizinhos[linha[1]] = linha[2]
        print(tabelaVizinhos)

    elif linha[0] == "del":
        print("del")
        tabelaVizinhos.pop(linha[1], None)
        print(tabelaVizinhos)

    elif linha[0] == "trace":
        print("trace")
        print(tabelaVizinhos)
    
    else:
        print("Comando desconhecido")


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
        arquivoComandos = args.startup_commands
