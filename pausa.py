import msvcrt
import os

def limpiar_consola():
    os.system("cls")

def pausaPorConsola():
    print("")

    while True:
        key = msvcrt.getch()
        if key == b'\r': #ENTER
            print("ok...")
            return 0
        elif key == b'\x1b': #ESC
            print("")
            return 1
        else:
            print("")