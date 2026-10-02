from scripts import principal,solofotos
from utils import mostrar_ultimo_guardado, traer_consola_al_frente
import os, pyautogui

def mostrar_menu():

    print("\n---MENU ---\b\b")
    print("1. Fotos/PDF")
    print("2. Directo PDF")
    print("3. Solo bajar fotos")
    print("4. Mostrar ultimo guardado")
    print("5. Salir")

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
            for _ in range(3):
                solofotos("fotos")
        elif opcion == "4":
            mostrar_ultimo_guardado()
            input("\nPresiona ENTER para continuar...")
        elif opcion == "5":
            print("Saliendo...")
            break
        else:
            print("Opcion invalida, las opciones son [1],[2],[3] y [4]")


if __name__ == "__main__":
    main()
