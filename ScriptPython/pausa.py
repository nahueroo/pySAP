import msvcrt
import os

def limpiar_consola():
    os.system("cls")

def pausaPorConsola():
    print("Presiona ENTER para continuar, o ESC para salir...")

    while True:
        key = msvcrt.getch()
        if key == b'\r': #ENTER
            print("Continuando...")
            return 0
        elif key == b'\x1b': #ESC
            print("Detenido por ESC")
            return 1
        else:
            print("Tecla no valida. Usa ENTER o ESC")