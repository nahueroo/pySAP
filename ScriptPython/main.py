from scripts import *
from pausa import limpiar_consola
from globales import datos

def mostrar_menu():
    print("\n---MENU ---")
    print("1. General")
    print("2. Tecnovias")
    print("3. Salir")

def main():

    while True:
        limpiar_consola()
        mostrar_menu()
        opcion = input("Opcion?\n")

        if opcion == "g" or opcion == "1":
            flujo_general()
        elif opcion == "t" or opcion == "2":
            flujo_tecnovias()
        elif opcion == "3" or opcion == "salir":
            print("Saliendo...")
            break
        else:
            print("es 1 o 2, pelotudo")
            

if __name__ == "__main__": 
    main()
