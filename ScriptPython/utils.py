import time
import pyautogui
from pausa import pausaPorConsola
from getters import *
from globales import datos

#entrar a came seleccionada desde IW38

def ingreso_a_came(session):
    session.findById("wnd[0]").maximize()
    session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").doubleClickCurrentCell()
    datos["Texto Breve"] = get_textoBreve(session)
    datos["Clase de actividad"] = get_claseActividad(session)
    datos["Ubicacion Tecnica"] = get_UT(session)


def ver_fotos_en_came(session):
    session.findById("wnd[0]/titl/shellcont/shell").pressButton("%GOS_TOOLBOX")
    
    #Abre Visualizar imagenes
    session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_IMAG")
    time.sleep(0.5)

    if session.Children.Count > 1:
        # presiona el botón Aceptar en el popup
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        
        # abre Lista de documentos
        session.findById("wnd[0]/shellcont/shell").pressButton("DOC_LIST")
        time.sleep(0.3)

        if session.Children.Count > 1:
            # presiona el botón Aceptar en el popup
            session.findById("wnd[1]/tbar[0]/btn[0]").press()

            session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_DOC")
            time.sleep(0.3)

            session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell").currentCellColumn = "NOMBRE"

            session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell").doubleClickCurrentCell()

            session.findById("wnd[1]").close()
            session.findById("wnd[0]/shellcont").close()

def ver_fotos_en_came_tecno(session):
    session.findById("wnd[0]/titl/shellcont/shell").pressButton("%GOS_TOOLBOX")
    session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_DOC")
    time.sleep(0.3)
    session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell").currentCellColumn = "NOMBRE"
    session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell").doubleClickCurrentCell()
    session.findById("wnd[1]").close()
    session.findById("wnd[0]/shellcont").close()

def entrar_a_care(session):
    campo = session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/subMAINORDER:SAPLCOIH:0152/ctxtCAUFVD-MAUFNR")
    campo.setFocus()
    campo.caretPosition = 7
    datos["Ubicacion Aviso"] = get_textoBreveCare(session)
    datos["Clase de actividad aviso"] =  get_claseActividad(session)
    session.findById("wnd[0]").sendVKey(2)

def ver_fotos_en_care(session):
    session.findById("wnd[0]/titl/shellcont[1]/shell").pressButton("%GOS_TOOLBOX")

    session.findById("wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL").getAbsoluteRow(0).selected = True
    session.findById("wnd[1]").sendVKey(0)

    time.sleep(0.3)

    session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_IMAG")

    if session.Children.Count > 1:
        # presiona el botón Aceptar en el popup
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        # abre lista de documentos
        session.findById("wnd[0]/shellcont/shell").pressButton("DOC_LIST")

        if session.Children.Count > 1:
            # presiona el botón Aceptar en el popup
            session.findById("wnd[1]/tbar[0]/btn[0]").press()

    session.findById("wnd[0]/titl/shellcont[1]/shell").pressButton("%GOS_TOOLBOX")

    session.findById("wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL").getAbsoluteRow(1).selected = True
    session.findById("wnd[1]").sendVKey(0)
    session.findById("wnd[0]/shellcont[1]/shell").pressButton("VIEW_IMAG")
    time.sleep(0.3)

    if session.Children.Count > 1:
        # presiona el botón Aceptar en el popup
        session.findById("wnd[1]/tbar[0]/btn[0]").press()

        # abre Lista de documentos
        session.findById("wnd[0]/shellcont[1]/shell").pressButton("DOC_LIST")
        time.sleep(0.3)

        if session.Children.Count > 1:
            # presiona el botón Aceptar en el popup
            session.findById("wnd[1]/tbar[0]/btn[0]").press()

def entrar_a_aviso(session):
    session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/btnICON_NTF").press()
    time.sleep(0.5)
    datos["Tipo Aviso"] = get_aviso_tipo(session)
    datos["Autor Aviso"] = get_aviso_autor(session)
    datos["Fecha Aviso"] = get_aviso_fecha(session)
    datos["Servicio"] = get_aviso_servicio(session)

def aceptar_g02(session):
    session.findById("wnd[0]/tbar[0]/btn[3]").press()
    time.sleep(0.5)

    session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE").select()

def pausa():
    exit_code = pausaPorConsola()
    if exit_code == 0:
        print("Pausa termino con 0, continuando")
    elif exit_code == 1:
        print("Pausa termino con 1, deteniendo")
        exit(1)
    else:
        print("Codigo de salida inesperado: {exit_code}")
        exit(exit_code)

def aceptar_itemizado(session):
    session.findById("wnd[0]/tbar[0]/btn[3]").press()
    time.sleep(0.5)

    session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE").select()
    time.sleep(2)

def aceptar_medicion(session):
    session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpIHKZ").select()
    time.sleep(0.25)

def cgi(session):
    session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/ctxtCAUFVD-INGPR").text = "Cgi"
    session.findById("wnd[0]/tbar[0]/btn[11]").press()
    time.sleep(0.5)
    pyautogui.press('down')

def mostrar_datos():
    print("\n-----CAME-----\n")
    print(f"Texto Breve:  {datos['Texto Breve']}")

    print("\n-----Ubicacion-----\n")
    print(f"Ubicación Aviso:  {datos['Ubicacion Aviso']}")
    print(f"UT:  {datos['Ubicacion Tecnica']}")

    print("\n-----Clase de Actividad-----\n")
    print(f"Clase de actividad:  {datos['Clase de actividad']}")
    print(f"Clase de actividad aviso:  {datos['Clase de actividad aviso']}")
    
    print("\n-----AVISO-----\n")
    print(f"Tipo:  {datos['Tipo Aviso']}")
    print(f"Autor:  {datos['Autor Aviso']}")
    print(f"Fecha:  {datos['Fecha Aviso']}")
    print(f"Servicio:  {datos['Servicio']}")