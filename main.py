from scripts import principal,debug
from utils import mostrar_ultimo_guardado, traer_consola_al_frente
from pausa import limpiar_consola
import os

def mostrar_menu():

    print("\n---MENU ---\b\b")
    print("1. Corregir un acta")
    print("2. Mostrar ultima guardada")
    print("3. Bajar data de todas las cames")
    print("4. Bajar fotos de todas las cames")
    print("5. Correccion DH")
    print("6. Salir")

def mostrar_debug_menu():
    print("\n---MENU DEBUG---\b\b")
    print("1. Inspeccionar ventana")
    print("2. Inspeccionar textos")
    print("3. Inspeccionar tipos")
    print("4. Salir")

def main():
    # Crear carpeta actas al inicio
    os.makedirs("actas", exist_ok=True)

    while True:
        limpiar_consola()
        traer_consola_al_frente()  # Traer consola al frente cada vez que se muestra el menú
        
        mostrar_menu()
        opcion = input("Opcion?\n")

        if opcion == "1":
            principal("corregir",0)
        elif opcion == "2":
            mostrar_ultimo_guardado()
            input("\nPresiona ENTER para continuar...")
        elif opcion == "3":
                principal("descarga",0)
        elif opcion == "4":
                principal("descargarfotos",0)        
        elif opcion == "5":
                principal("dh",0)
        elif opcion == "6":
            print("Saliendo...")
            break
        elif opcion == "7":
            while True:
                limpiar_consola()
                traer_consola_al_frente()  # Traer consola al frente cada vez que se muestra el menú      
                mostrar_debug_menu()
                opcion = input("Opcion?\n")
                if opcion == "1":
                    debug(1)
                elif opcion == "2":
                    debug(2)
                elif opcion == "3":
                    debug(3)
                elif opcion == "4":
                    print("Saliendo...")
                    break
        else:
            print("Opcion invalida, las opciones son [1],[2],[3] y [4]")


if __name__ == "__main__":
    main()