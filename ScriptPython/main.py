from cerrarpestanias import cerrar_pestanas_chrome
from utils import *
from sap_connection import obtener_session_sap

def main():\

    session = obtener_session_sap()
    ingreso_a_came(session)
    ver_fotos_en_came(session)
    entrar_a_care(session)
    ver_fotos_en_care(session)
    entrar_a_aviso(session)
    pausa()
    aceptar_g02(session)
    pausa()
    aceptar_itemizado(session)
    pausa()
    aceptar_medicion(session)
    cgi(session)
    cerrar_pestanas_chrome()

if __name__ == "__main__": 
    main()
