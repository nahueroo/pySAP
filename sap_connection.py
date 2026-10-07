import win32com.client
import shutil
from constantes import *

def get_session():
        
    SapGuiAuto  = win32com.client.GetObject("SAPGUI")
    application = SapGuiAuto.GetScriptingEngine
    connection = application.Children(0)
    return connection.Children(0)

# GLOBAL

def sendKey(session, key):
    session.findById("wnd[0]").sendVKey(key)

def volver(session):
    sendKey(session,15)

# IW38 TOOLS

def get_grid(session):
    return session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell")

def get_columns(session):
    grid = get_grid(session)

    for i in range(grid.ColumnCount):
        print(i, grid.ColumnOrder[i])

def selectCell(session, fila):
    grid = get_grid(session)
    grid.CurrentCellRow = fila
    grid.SetCurrentCell(fila, "KTEXT")
    return grid

def get_numero_de_acta(session,ktext)->int:
    came = selectCell(session,ktext)
    return int(came.split("ACTA_")[1])

# CAME TOOLS

def get_came_toolbox(session):
    session.findById("wnd[0]/titl/shellcont/shell").pressButton("%GOS_TOOLBOX")

def get_care_field(session):
    # revisar y comparar con aviso field
    campo = session.findById(MAUFNR)
    campo.setFocus()
    campo.caretPosition = 7

# CARE TOOLS

def get_care_toolbox(session):
    session.findById("wnd[0]/titl/shellcont[1]/shell").pressButton("%GOS_TOOLBOX")

def select_row(session,row):
    session.findById("wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL").getAbsoluteRow(row).selected = True
    session.findById("wnd[1]").sendVKey(0) # enter

def verfotos(session,row,tecla):
    if row == 0:
        session.findById("wnd[0]/shellcont/shell").pressButton(tecla)
    if row == 1:
        session.findById("wnd[0]/shellcont[1]/shell").pressButton(tecla)

def get_aviso_field(session):
    session.findById(AVISO).press()

def press_button(session):
    session.findById("wnd[1]/tbar[0]/btn[0]").press()

def cerrar_ventanas_extra(session):
    while session.Children.Count > 1:
        try:
            session.Children(session.Children.Count-1).close()
        except Exception as e:
            break

# AVISO TOOLS

# DESCARGA DE ARCHIVOS

def download_fotos(session,carpeta_destino,sufijo):
    if session.Children.Count > 1:
        press_button(session)      
    else:
        mover_y_renombrar_archivos_sap(carpeta_destino,sufijo)

def mover_y_renombrar_archivos_sap(carpeta_destino, sufijo):
    """
    Mueve las fotos a la carpeta creada.
    Los renombra agregando CAME o CARE de acuerdo a de donde son.

    Args:
        carpeta_destino: Ruta donde mover los archivos
        sufijo: Sufijo a agregar al nombre ("CAME", "CARE")
    """
    try:
        ruta_sap = RUTA_SAP_DESCARGAS

        # Verificar si la carpeta de origen existe
        if not os.path.exists(ruta_sap):
            print(f"Carpeta SAP no encontrada: {ruta_sap}")
            return False

        # Obtener lista de archivos
        archivos = os.listdir(ruta_sap)

        if not archivos:
            print(f"No hay archivos en la carpeta SAP GUI para {sufijo}")
            return False

        contador = 0
        for archivo in archivos:
            ruta_origen = os.path.join(ruta_sap, archivo)

            # Solo procesar archivos, no carpetas
            if os.path.isfile(ruta_origen):
                # Separar nombre y extensión
                nombre_base, extension = os.path.splitext(archivo)

                # Crear nuevo nombre con sufijo
                nuevo_nombre = f"{nombre_base}_{sufijo}{extension}"
                ruta_destino = os.path.join(carpeta_destino, nuevo_nombre)

                contador_nombre = 1
                
                while os.path.exists(ruta_destino):
                    nuevo_nombre = f"{nombre_base}_{sufijo} ({contador_nombre}){extension}"
                    ruta_destino = os.path.join(carpeta_destino, nuevo_nombre)
                    contador_nombre += 1

                try:
                    shutil.move(ruta_origen, ruta_destino)
                    contador += 1
                except Exception as e:
                    print(f"Error moviendo {archivo}: {e}")

        if contador > 0:
            print(f"Se movieron {contador} archivo(s) con sufijo _{sufijo} a {carpeta_destino}")

        return True
    except Exception as e:
        print(f"Error al mover archivos SAP: {e}")
        return False