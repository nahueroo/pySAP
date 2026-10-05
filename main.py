from scripts import principal
from sap_connection import obtener_session_sap
from utils import mostrar_ultimo_guardado, traer_consola_al_frente,obtener_acta_actual
from pausa import limpiar_consola
from datetime import datetime
import os

def mostrar_menu():

    print("\n---MENU ---\b\b")
    print("1. Corregir un acta")
    print("2. Mostrar ultima guardada")
    print("3. Bajar fotos")
    print("4. Correccion DH")
    print("5. Salir")

def main():
    # Crear carpeta actas al inicio
    os.makedirs("actas", exist_ok=True)

    while True:
        limpiar_consola()
        traer_consola_al_frente()  # Traer consola al frente cada vez que se muestra el menú
        
        mostrar_menu()
        opcion = input("Opcion?\n")

        if opcion == "1":
            principal("corregir")
        elif opcion == "2":
            mostrar_ultimo_guardado()
            input("\nPresiona ENTER para continuar...")
        elif opcion == "3":
            acta = input("Hasta que acta[copiar texto breve completo]: ")
            session = obtener_session_sap()
            actaActual = obtener_acta_actual(session)
            while acta != actaActual:
                principal("descarga")
        elif opcion == "4":
            acta = input("Hasta que acta[copiar texto breve completo]: ")
            actaActual = obtener_acta_actual(session)
            while acta != actaActual:
                principal("dh")
        elif opcion == "5":
            print("Saliendo...")
            break
        else:
            print("Opcion invalida, las opciones son [1],[2],[3] y [4]")


if __name__ == "__main__":
    main()