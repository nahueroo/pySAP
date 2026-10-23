import time
import pyautogui
import json
import os
import csv
from sap_connection import *
from globales import *

def ingreso_a_came(session,fila=None)->str:

    datos = get_data_came(session,fila)
    
    if fila is not None:
        came = selectCell(session,fila)
    else:
        came = get_grid(session)
    
    came.doubleClickCurrentCell()

    return came,datos

def ver_fotos_en_came(session,carpeta_destino,sufijo,numero_came):

    with open("cames.json", "r", encoding="utf-8") as archivo:
        cames = json.load(archivo)
    came = cames.get(str(numero_came).strip())
    if came.get("Tiene foto") != "G-Anexo SAP":
        return
    
    # "DOC_LIST" O "VIEW_IMAG"
    
    get_came_toolbox(session)
    hayfotos = fotosCame(session, carpeta_destino,sufijo)
    if not hayfotos:
        time.sleep(0.3)
        pdfCame(session,carpeta_destino,sufijo)

def entrar_a_care(session):
    get_care_field(session)
    time.sleep(0.4)
    get_care_field(session)
    
    sendKey(session, F2)

def ver_fotos_en_care(session,carpeta_destino,sufijo,numero_care):

    aviso = False

    with open("cares.json", "r", encoding="utf-8") as archivo:
        cares = json.load(archivo)

    care = cares.get(str(numero_care).strip())

    row = 0 if care.get("Tiene foto") == "G-Anexo SAP" else 1
    # row == 0 es orden, row == 1 es aviso

    if row == 1:
        aviso = True    

    while row < 2:

        if row == 0:
            sufijo = "CARE - ORDEN DE MANTENIMIENTO"
        if row == 1:
            sufijo = "CARE - AVISO"
    
        get_care_toolbox(session)
        select_row(session,row)
    
        verfotosCARE(session,row,aviso,"VIEW_IMAG")
        time.sleep(0.3)
        download_fotos(session,carpeta_destino,sufijo)

        verfotosCARE(session,row,aviso,"DOC_LIST")
        time.sleep(0.3)
        download_fotos(session,carpeta_destino,sufijo)

        row += 1

    cerrar_ventanas_extra(session)

def cargar_lectura(tipo):
    nombres_archivo = {
        "came": "cames.json",
        "care": "cares.json",
        "aviso": "avisos.json",
    }

    nombre_archivo = nombres_archivo[tipo]

    try:
        with open(nombre_archivo, "r", encoding="utf-8") as archivo:
            datos[tipo] = json.load(archivo)

    except FileNotFoundError:
        datos[tipo] = {}

        # Crea el archivo aunque todavía no tenga registros
        guardar_lectura(tipo)

def guardar_lectura(tipo):
    nombres_archivo = {
        "came": "cames.json",
        "care": "cares.json",
        "aviso": "avisos.json",
    }

    with open(nombres_archivo[tipo], "w", encoding="utf-8") as archivo:
        json.dump(datos[tipo], archivo, ensure_ascii=False, indent=4)