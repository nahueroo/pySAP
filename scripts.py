from cerrarpestanias import cerrar_pestanas_chrome
from utils import *
from sap_connection import obtener_session_sap

def flujo_base(tipo_flujo):
    session = obtener_session_sap()
    if session is None:
        return  # Esto termina la función   
    ingreso_a_came(session)
    if tipo_flujo == "general":     
        ver_fotos_en_came(session)
    elif tipo_flujo == "tecnovias":
        ver_fotos_en_came_tecno(session)
    entrar_a_care(session)
    ver_fotos_en_care(session)
    entrar_a_aviso(session)
    pausa()
    mostrar_datos()
    aceptar_g02(session)
    pausa()
    aceptar_itemizado(session)
    aceptar_medicion(session)
    
    # Manejar la pausa y el comportamiento según la respuesta del usuario
    exit_code = pausa()
    if exit_code == 1:  # Usuario presionó ESC
        salir(session)
        cerrar_pestanas_chrome()
    else:  # Usuario presionó ENTER (exit_code == 0)
        cgi(session)
        cerrar_pestanas_chrome()

def flujo_general():
    flujo_base("general")

def flujo_tecnovias():
    flujo_base("tecnovias")