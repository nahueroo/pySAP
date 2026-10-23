from scripts import principal,debug,getter
from utils import guardar_lectura,cargar_lectura
from pausa import limpiar_consola, traer_consola_al_frente
from vincular import vincular
import os

def mostrar_menu():

    print("\n---MENU ---\b\b")
    print("1. Bajar fotos de todas las cames y cares")
    print("2. Solo cames (DH)")
    print("3. Obtener toda la grilla")
    print("4. Vincular")
    print("5. Salir")

def mostrar_debug_menu():
    print("\n---MENU DEBUG---\b\b")
    print("1. Inspeccionar celdas")

def main():
    # Crear carpeta actas al inicio
    os.makedirs("actas", exist_ok=True)
    while True:
        limpiar_consola()
        traer_consola_al_frente()  # Traer consola al frente cada vez que se muestra el menú
        
        mostrar_menu()
        opcion = input("Opcion?\n")

        if opcion == "1":
                principal()     
        elif opcion == "2":
                principal(0,"solofotos")
        elif opcion == "3":
                modo = input("\n1: cames, 2: cares, 3:avisos")

                tipos = {
                    "came": "came",
                    "care": "care",
                    "aviso": "aviso",
                }
                tipo = tipos.get(modo)
                if tipo:
                    cargar_lectura(tipo)
                    getter(tipo, 0)
                    guardar_lectura(tipo)
                else:
                     print("Opcion invalida")
        elif opcion == "4":
             siono = input("\nEsta seguro que ya estan cames,cares y avisos cargados? Reponda si/no")
             if siono == "si":
                vincular()      
             else:
                break
        elif opcion == "5":
            print("Saliendo...")
            break
        elif opcion == "6":
            while True:
                limpiar_consola()
                traer_consola_al_frente()  # Traer consola al frente cada vez que se muestra el menú      
                mostrar_debug_menu()
                opcion = input("Opcion?\n")
                if opcion == "1":
                    debug(1)
                elif opcion == "2":
                    print("Saliendo...")
                    break
                    
        else:
            print("Opcion invalida, las opciones son [1],[2],[3] y [4]")

if __name__ == "__main__":
    main()