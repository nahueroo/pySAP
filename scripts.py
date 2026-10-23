from utils import *
from sap_connection import get_session, __debug_data_iw
import json


def principal(fila=0,modo=None)->str:
    
    session = get_session()
    if session is None:
        print("Session not NONE")
        return

    grid = get_grid(session)
    ultimaFila = grid.RowCount
    if fila >= ultimaFila:
        return

    _, datos = ingreso_a_came(session,fila)

    numero_came = str(datos["Orden"]).strip()

    with open("cames.json", "r", encoding="utf-8") as archivo:
        cames = json.load(archivo)

    came = cames.get(numero_came)

    numero_care = str(came.get("CARE Asociada") or "").strip()

    # Crear carpeta acta con el nombre del Texto Breve
    carpeta_acta = crear_carpeta_acta(datos["Texto Breve"])
    if not carpeta_acta:
        print("No se pudo crear la carpeta, proceso cancelado.")
        return

    ver_fotos_en_came(session,carpeta_acta, "CAME",numero_came)
    if modo == "solofotos":
        volver(session)
        fila += 1
        return principal(fila,modo)
    
    entrar_a_care(session)
    ver_fotos_en_care(session,carpeta_acta, "CARE",numero_care)
    volver(session)
    volver(session)

    time.sleep(0.3)
    fila+=1

    time.sleep(0.6)
    if fila < ultimaFila:
        return principal(fila,modo)
    else:
        return

def getter(tipo,fila):
    
    session = get_session()
    
    if session is None:
        print("Session not NONE")
        return

    grid = get_grid(session)
    ultimaFila = grid.RowCount
    
    if fila >= ultimaFila:
        return
   
    get_data_iw(session,tipo, fila)
    fila+=1

    return getter(tipo,fila)

def debug(func):
    
    session = get_session()
    if session is None:
        print("session not NONE")
        return

    if func == 1:
        __debug_data_iw(session)
