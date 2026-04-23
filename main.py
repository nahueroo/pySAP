from scripts import principal
from utils import mostrar_ultimo_guardado, traer_consola_al_frente
import os

def mostrar_menu():
    print("\n---MENU ---\b\b")
    print("1. Fotos/PDF")
    print("2. Directo PDF")
    print("3. Mostrar ultimo guardado")
    print("4. Salir")

def main():
    # Crear carpeta actas al inicio
    os.makedirs("actas", exist_ok=True)

    while True:
        os.system("cls")
        traer_consola_al_frente()  # Traer consola al frente cada vez que se muestra el menú
        mostrar_menu()
        opcion = input("Opcion?\n")

        if opcion == "1":
            principal("fotos")
        elif opcion == "2":
            principal("pdf")
        elif opcion == "3":
            mostrar_ultimo_guardado()
            input("\nPresiona ENTER para continuar...")
        elif opcion == "4":
            print("Saliendo...")
            break
        else:
            print("Opcion invalida, las opciones son [1],[2],[3] y [4]")


if __name__ == "__main__":
    main()
