from cerrarpestanias import cerrar_pestanas_chrome
from utils import *
from sap_connection import obtener_session_sap

def flujo_base(tipo_flujo):
    session = obtener_session_sap()
    if session is None:
        print("Error: No se pudo conectar a SAP")
        return  # Esto termina la función   
    ingreso_a_came(session)
    if tipo_flujo == "general":     
        ver_fotos_en_came(session)
    elif tipo_flujo == "tecnovias":
        ver_fotos_en_came_tecno(session)
    entrar_a_care(session)
    ver_fotos_en_care(session)
    entrar_a_aviso(session)
    mostrar_datos()
    pausa()
    aceptar_g02(session)
    pausa()
    aceptar_itemizado(session)
    pausa()
    aceptar_medicion(session)
    cgi(session)
    cerrar_pestanas_chrome()

def flujo_general():
    flujo_base("general")

def flujo_tecnovias():
    flujo_base("tecnovias")