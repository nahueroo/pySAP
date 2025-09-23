from scripts import flujo_general, flujo_tecnovias
from utils import mostrar_ultimo_guardado, traer_consola_al_frente
from pausa import limpiar_consola
import win32com.client

def mostrar_menu():
    print("\n---MENU ---")
    print("1. General")
    print("2. Tecnovias")
    print("3. Mostrar ultimo guardado")
    print("4. Salir")

def main():

    while True:
        limpiar_consola()
        traer_consola_al_frente()  # Traer consola al frente cada vez que se muestra el menú
        mostrar_menu()
        opcion = input("Opcion?\n")

        if opcion == "g" or opcion == "1":
            flujo_general()
        elif opcion == "t" or opcion == "2":
            flujo_tecnovias()
        elif opcion == "3":
            mostrar_ultimo_guardado()
            input("\nPresiona ENTER para continuar...")
        elif opcion == "4" or opcion == "salir":
            print("Saliendo...")
            break
        else:
            print("Opcion invalida")
            

if __name__ == "__main__": 
    main()
