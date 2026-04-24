from cerrarpestanias import cerrar_pestanas_firefox
from utils import *
from pausa import pausa
from sap_connection import obtener_session_sap
from constantes import CANCEL

def principal(tipo):

    if tipo not in("fotos","pdf"):
        print("Tipo invalido, usa 'fotos' o 'pdf'.")
        return
    
    session = obtener_session_sap()
    if session is None:
        return  # Esto termina la función
    ingreso_a_came(session)

    # Crear carpeta acta con el nombre del Texto Breve
    carpeta_acta = crear_carpeta_acta(datos.get("Texto Breve", "sin_nombre"))
    if not carpeta_acta:
        print("No se pudo crear la carpeta, script cancelado.")
        return

    if tipo == "fotos":
        ver_fotos_en_came(session,"fotos")
        mover_y_renombrar_archivos_sap(carpeta_acta, "CAME")
    elif tipo == "pdf":
        ver_fotos_en_came(session,"pdf")
        mover_y_renombrar_archivos_sap(carpeta_acta, "CAME")

    entrar_a_care(session)
    ver_fotos_en_care(session)

    mover_y_renombrar_archivos_sap(carpeta_acta, "CARE")

    entrar_a_aviso(session)
    aceptar_g02(session)
    aceptar_itemizado(session)
    mostrar_datos(carpeta_acta)

    # Manejar la pausa y el comportamiento según la respuesta del usuario
    exit_code = pausa()
    if exit_code == CANCEL:  # Usuario presionó ESC
        salir(session)
        cerrar_pestanas_firefox()
    else:  # Usuario presionó ENTER (exit_code == 0)
        cgi(session)
        cerrar_pestanas_firefox()