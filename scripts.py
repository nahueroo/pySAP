from cerrarpestanias import cerrar_pestanas
from utils import *
from pausa import pausa
from sap_connection import obtener_session_sap
from constantes import CANCEL
import win32gui

def principal(modo):
    
    session = obtener_session_sap()
    if session is None:
        return

    hwnd = session.findById("wnd[0]").Handle

    ingreso_a_came(session)

    # Crear carpeta acta con el nombre del Texto Breve
    carpeta_acta = crear_carpeta_acta(datos.get("Texto Breve", "sin_nombre"))
    if not carpeta_acta:
        print("No se pudo crear la carpeta, proceso cancelado.")
        return

    ver_fotos_en_came(session,carpeta_acta, "CAME")
    entrar_a_care(session)
    ver_fotos_en_care(session,carpeta_acta, "CARE")

    entrar_a_aviso(session)
    aceptar_g02(session)
    aceptar_itemizado(session)
    mostrar_datos(carpeta_acta)

    if modo == "corregir":
        # El final del proceso lo define el usuario con ESC o ENTER
        exit_code = pausa()
        if exit_code == CANCEL:  # ESC
            cerrar_pestanas()
            salir(session)
        else:  # ENTER
            cerrar_pestanas()
            cgi(session)
    else:
        cerrar_pestanas()
        salir(session)

    win32gui.SetForegroundWindow(hwnd)

    time.sleep(0.3)
    pyautogui.press('down')      