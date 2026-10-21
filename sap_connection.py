import win32com.client
import shutil
from constantes import *
from getters import *
from globales import *
from copy import deepcopy
import re
import time

def get_session():
        
    SapGuiAuto  = win32com.client.GetObject("SAPGUI")
    application = SapGuiAuto.GetScriptingEngine
    connection = application.Children(0)
    return connection.Children(0)

# GLOBAL

def sendKey(session, key):
    session.findById("wnd[0]").sendVKey(key)

def volver(session):
    sendKey(session,F3)

def get_data_came(session, fila=None):
    
    grid = get_grid(session)

    if fila is not None:
        grid.CurrentCellRow = fila

    datos_came = {}

    for i in range(grid.ColumnCount):
        campo = grid.ColumnOrder[i]

        try:
            valor = grid.GetCellValue(grid.CurrentCellRow, campo)
        except:
            valor = None

        # TRADUCE NOMBRE TECNICO A COLOQUIAL
        nombre = campos_ordenes.get(campo,campo)
        datos_came[nombre] = valor

    orden = datos_came.get("Orden")

    # CHEQUEA SI LA CAME ES VALIDA Y EXISTE
    if orden:
        if orden not in datos["came"]:
            datos["came"][orden] = deepcopy(came)

    datos["came"][orden].update(datos_came)

    return datos_came

def get_data_iw(session,tipo,fila=None):
    
    tipos = {
        "aviso": ("aviso",aviso,"Numero de aviso"),
        "care": ("care",care,"Orden"), 
        "came": ("came",came,"Orden"), 
    }

    nombre_diccionario,plantilla,key = tipos[tipo]

    grid = get_grid(session)

    if fila is not None:
        grid.CurrentCellRow = fila

    actualRow = grid.CurrentCellRow
    equivalencias_tipo = equivalencias[tipo]

    registro = {}

    for i in range(grid.ColumnCount):
        campo = grid.ColumnOrder[i]

        try:
            valor = grid.GetCellValue(actualRow,campo)
        except Exception:
            continue

        nombre_campo = equivalencias_tipo.get(campo,campo)
        registro[nombre_campo] = valor

    identificador = registro.get(key)

    if tipo == "aviso":
        objeto = registro.get("OBJETO")

        if objeto:
            identificador = str(objeto).strip().lstrip("0")

    if not identificador:
        return registro

    if identificador not in datos[nombre_diccionario]:
        datos[nombre_diccionario][identificador] = deepcopy(plantilla)

    registro_guardado = datos[nombre_diccionario][identificador]

    if tipo == "aviso":
        agregar_texto_aviso(
            registro_guardado,
            registro.get("TEXTO")
    )

    campos_operacion = set(operaciones.values())

    datos_cabecera = {}
    datos_operacion = {}

    for campo,valor in registro.items():

        if campo in campos_operacion:
            datos_operacion[campo] = valor

        elif campo in registro_guardado:
            datos_cabecera[campo] = valor

    registro_guardado.update(datos_cabecera)

    numero_operacion = datos_operacion.get("Operacion")

    if numero_operacion:
        operacion_existente = registro_guardado["operaciones"].setdefault(
            numero_operacion,
            {}
    )
        operacion_existente.update(datos_operacion)

    return registro_guardado

def agregar_texto_aviso(aviso, texto):
    if texto:
        aviso.setdefault("Texto", []).append(texto)


def __debug_data_iw(session, fila=None):
    grid = get_grid(session)

    if fila is not None:
        grid.CurrentCellRow = fila

    actualRow = grid.CurrentCellRow

    for i in range(grid.ColumnCount):
        clave = grid.ColumnOrder[i]

        try:
            valor = grid.GetCellValue(actualRow,clave)
        except Exception as error:
            print(f"{clave}: no disponible({error})")
            continue

        print(f"{clave}: {valor}")
    input("\nPresiona ENTER para volver al menú...")

# IW38 TOOLS

def get_grid(session):
    return session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell")

def get_grid2(session):
    return session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell")

def get_columns(session):
    grid = get_grid(session)

    for i in range(grid.ColumnCount):
        print(i, grid.ColumnOrder[i])

def selectCell(session, fila):
    grid = get_grid(session)
    grid.CurrentCellRow = fila
    grid.SetCurrentCell(fila, "KTEXT")
    return grid

def selectRow(session,row):
    grid = get_grid(session)
    grid.CurrentCellRow = row
    return grid

def get_data_acta(session,ktext,dato):
    came = selectCell(session,ktext)
    partes = came.split("_")
    if dato == "certificado":
        return int(partes[5])
    if dato == "acta":
        return int(partes[7])
    if dato == "renglon":
        return partes[3]

def selectOperTab(session):
    session.findById(OPERTAB).select()

# CAME TOOLS

def get_came_toolbox(session):
    session.findById("wnd[0]/titl/shellcont/shell").pressButton("%GOS_TOOLBOX")

def selectDocSource(session, source):
    if source == "fotos":
        session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_IMAG")
    elif source == "docs":
        session.findById("wnd[0]/shellcont/shell").pressButton("DOC_LIST")
    elif source == "pdf":
        session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_DOC")

def fotosCame(session,carpeta_destino,sufijo):
    selectDocSource(session,"fotos")
    fotos = download_fotos(session,carpeta_destino,sufijo)
    return fotos

def pdfCame(session,carpeta_destino, sufijo):
    selectDocSource(session,"pdf")
    download_pdf(session,carpeta_destino, sufijo)

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

def verfotosCARE(session,row,aviso,tecla):
    if row == 0 or aviso:
        session.findById("wnd[0]/shellcont/shell").pressButton(tecla)
    if row == 1 and not aviso:
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

def crear_carpeta_acta(texto_breve):
    
    try:
        carpeta_acta = os.path.join("actas", texto_breve)

        if os.path.exists(carpeta_acta):
            shutil.rmtree(carpeta_acta)

        os.makedirs(carpeta_acta)
        
        return carpeta_acta
    
    except OSError as e:
        print(f"Error al crear carpeta acta: {e}")
        return None

def validar_nombre_acta(nombre):
    patron = r"^P\d+_\d+_Z\d+_R\d+_CERT_\d+_ACTA_\d+$"
    return bool(re.fullmatch(patron, nombre))

def download_fotos(session,carpeta_destino,sufijo)->bool:
    if session.Children.Count > 1:
        press_button(session)
    else:
        mover_y_renombrar_archivos_sap(carpeta_destino,sufijo)
        return True

def download_pdf(session,carpeta_destino,sufijo):
    
    if session.Children.Count > 1:
        try:
            press_button(session)
        except Exception:
            pass

    time.sleep(0.8)
    grid = session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell")

    documentos = grid.RowCount
    for documento in range(documentos):
        try:
            grid.currentCellRow = documento
            grid.currentCellColumn = "NOMBRE"
                
            # Verificar si la celda tiene contenido
            name = grid.getCellValue(documento, "NOMBRE")
                
            if not name or name.strip() == "":
                break

            grid.doubleClickCurrentCell()
                
            # Pequeña pausa entre selecciones para estabilidad
            time.sleep(0.6)
            mover_y_renombrar_archivos_sap(carpeta_destino,sufijo)
                
        except Exception as e:
            # Si hay error al acceder a una fila, probablemente llegamos al final
            print(f"Error al procesar fila {documento}: {e}")
            break
        
    # Cerrar las ventanas después de procesar todas las filas
    session.findById("wnd[1]").close()
    session.findById("wnd[0]/shellcont").close()

def mover_y_renombrar_archivos_sap(carpeta_destino, sufijo):

    try:
        ruta_sap = RUTA_SAP_DESCARGAS

        if not os.path.exists(ruta_sap):
            return False

        archivos = os.listdir(ruta_sap)

        if not archivos:
            return False

        contador = 0

        for archivo in archivos:
            ruta_origen = os.path.join(ruta_sap, archivo)

            if not os.path.isfile(ruta_origen):
                continue

            nombre_base, extension = os.path.splitext(archivo)
            nuevo_nombre = f"{nombre_base}_{sufijo}{extension}"
            ruta_destino = os.path.join(carpeta_destino, nuevo_nombre)
            
            shutil.move(ruta_origen,ruta_destino)
            contador += 1

        return True
    
    except OSError as e:
        print(f"Error al mover archivos SAP: {e}")
        return False

def guardar_itemizado(session,orden):

    if orden == "came":
        operaciones = getter_came(session)
        orden = "DATOS CAME"
        texto = "\n\nCargado:"
    elif orden == "care":
        operaciones = getter_care(session)
        orden = "DATOS CARE"
        texto = "\n\nItemizado:"
    
    if operaciones:
        print(texto)
        print(operaciones)
        datos[orden] = operaciones
    else:
        datos[orden] = "No se encontraron datos válidos."