from cerrarpestanias import cerrar_pestanas
from utils import *
from pausa import pausa
from sap_connection import get_session
from debugtools import *

def principal(modo,fila)->str:
    
    session = get_session()
    if session is None:
        print("Session not NONE")
        return

    grid = get_grid(session)
    ultimaFila = grid.RowCount
    if fila >= ultimaFila:
        return

    if modo == "corregir":
        ingreso_a_came(session)
    else:
        ingreso_a_came(session,fila)

    # Crear carpeta acta con el nombre del Texto Breve
    carpeta_acta = crear_carpeta_acta(datos.get("Texto Breve", "sin_nombre"))
    if not carpeta_acta:
        print("No se pudo crear la carpeta, proceso cancelado.")
        return

    ver_fotos_en_came(session,carpeta_acta, "CAME")
    if modo == "dh":
        volver(session)
        fila += 1
        return principal(modo,fila)
    
    entrar_a_care(session)
    ver_fotos_en_care(session,carpeta_acta, "CARE")
    if modo == "descargarfotos":
        volver(session)
        volver(session)
        fila += 1
        return principal(modo,fila)

    entrar_a_aviso(session)
    volveryGuardarOperaciones(session,"care")
    volveryGuardarOperaciones(session,"came")
    mostrar_datos(carpeta_acta)

    # El final del proceso lo define el usuario con ESC o ENTER
    if modo == "corregir":
        exit_code = pausa()
        if exit_code == CONTINUE:  # ESC
            cgi(session)

    cerrar_pestanas()
    time.sleep(0.3)
    volver(session)

    time.sleep(0.3)
    fila+=1

    time.sleep(0.6)
    if fila < ultimaFila and (modo == "descarga" or modo == "dh"):
        return principal(modo,fila)
    else:
        return

def debug(func):
    
    session = get_session()
    if session is None:
        print("session not NONE")
        return
        
    if func == 1:
        debug_window(session)
        input("ok?")
    if func == 2:
        inspect_object(session)
        input("ok?")