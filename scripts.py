from cerrarpestanias import cerrar_pestanas_firefox
from utils import *
from sap_connection import obtener_session_sap

def flujo_base(tipo_flujo):
    session = obtener_session_sap()
    if session is None:
        return  # Esto termina la función
    ingreso_a_came(session)

    # Crear carpeta acta con el nombre del Texto Breve
    carpeta_acta = crear_carpeta_acta(datos.get("Texto Breve", "sin_nombre"))

    if tipo_flujo == "general":
        ver_fotos_en_came(session)
        # Mover archivos CAME después de ver fotos en CAME
        mover_y_renombrar_archivos_sap(carpeta_acta, "CAME")
    elif tipo_flujo == "tecnovias":
        ver_fotos_en_came_tecno(session)
        # Mover archivos CAME después de ver fotos en CAME
        mover_y_renombrar_archivos_sap(carpeta_acta, "CAME")

    entrar_a_care(session)
    ver_fotos_en_care(session)
    # Mover archivos CARE después de ver fotos en CARE
    mover_y_renombrar_archivos_sap(carpeta_acta, "CARE")

    entrar_a_aviso(session)
    aceptar_g02(session)
    aceptar_itemizado(session)
    mostrar_datos(carpeta_acta)

    # Manejar la pausa y el comportamiento según la respuesta del usuario
    exit_code = pausa()
    if exit_code == 1:  # Usuario presionó ESC
        salir(session)
        cerrar_pestanas_firefox()
    else:  # Usuario presionó ENTER (exit_code == 0)
        cgi(session)
        cerrar_pestanas_firefox()

def flujo_general():
    flujo_base("general")

def flujo_tecnovias():
    flujo_base("tecnovias")