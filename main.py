from scripts import principal,solofotos
from utils import mostrar_ultimo_guardado, traer_consola_al_frente
import os, pyautogui

def mostrar_menu():

    print("\n---MENU ---\b\b")
    print("1. Corregir un acta")
    print("2. Mostrar ultima guardada")
    print("3. Bajar fotos")
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
            principal()
        elif opcion == "2":
            mostrar_ultimo_guardado()
            input("\nPresiona ENTER para continuar...")
        elif opcion == "3":
            cantidad = int(input("Ingresar cantidad de actas: "))
            for _ in range(cantidad):
                solofotos("fotos")
        elif opcion == "4":
            print("Saliendo...")
            break
        else:
            print("Opcion invalida, las opciones son [1],[2],[3] y [4]")


if __name__ == "__main__":
    main()