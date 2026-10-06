import win32com.client
from constantes import *

def get_session():
        
    SapGuiAuto  = win32com.client.GetObject("SAPGUI")
    application = SapGuiAuto.GetScriptingEngine
    connection = application.Children(0)
    session = connection.Children(0)

    if session is None:
        raise RuntimeError("No se pudo obtener una sesion SAP")

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

def get_numero_de_acta(session,ktext)->int:
    came = selectCell(session,ktext)
    return int(came.split("ACTA_")[1])

def get_came_toolbox(session):
    session.findById("wnd[0]/titl/shellcont/shell").pressButton("%GOS_TOOLBOX")

def get_care_toolbox(session):
    session.findById("wnd[0]/titl/shellcont[1]/shell").pressButton("%GOS_TOOLBOX")

def get_care_field(session):
    campo = session.findById(MAUFNR)
    campo.setFocus()
    campo.caretPosition = 7

def select_first_row(session):
    session.findById("wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL").getAbsoluteRow(0).selected = True
    session.findById("wnd[1]").sendVKey(0) # enter