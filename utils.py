import time
import pyautogui
from pausa import pausaPorConsola
from getters import *
from globales import datos, esperar_elemento, esperar_popup

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
    
    # Espera inteligente a que aparezca el popup
    if esperar_popup(session, timeout=3):
        # presiona el botón Aceptar en el popup
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        
        # abre Lista de documentos
        session.findById("wnd[0]/shellcont/shell").pressButton("DOC_LIST")
        
        # Espera inteligente a que aparezca el popup
        if esperar_popup(session, timeout=3):
            # presiona el botón Aceptar en el popup
            session.findById("wnd[1]/tbar[0]/btn[0]").press()

            session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_DOC")
            
            # Espera a que aparezca la ventana con la grid
            if esperar_elemento(session, "wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell", timeout=3):
                session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell").currentCellColumn = "NOMBRE"
                session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell").doubleClickCurrentCell()
                session.findById("wnd[1]").close()
                session.findById("wnd[0]/shellcont").close()

def ver_fotos_en_came_tecno(session):
    session.findById("wnd[0]/titl/shellcont/shell").pressButton("%GOS_TOOLBOX")
    session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_DOC")
    
    # Espera a que aparezca la ventana con la grid
    if esperar_elemento(session, "wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell", timeout=3):
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

    # Espera a que se procese la selección
    if esperar_elemento(session, "wnd[0]/shellcont/shell", timeout=3):
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
    
    # Espera inteligente a que aparezca el popup
    if esperar_popup(session, timeout=3):
        # presiona el botón Aceptar en el popup
        session.findById("wnd[1]/tbar[0]/btn[0]").press()

        # abre Lista de documentos
        session.findById("wnd[0]/shellcont[1]/shell").pressButton("DOC_LIST")
        
        # Espera inteligente a que aparezca el popup
        if esperar_popup(session, timeout=3):
            # presiona el botón Aceptar en el popup
            session.findById("wnd[1]/tbar[0]/btn[0]").press()

def entrar_a_aviso(session):
    session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/btnICON_NTF").press()
    
    # Espera a que se abra el aviso
    if esperar_elemento(session, "wnd[0]/usr/subSCREEN_1:SAPLIQS0:1050/subNOTIF_TYPE:SAPLIQS0:1051/ctxtVIQMEL-QMART", timeout=3):
        datos["Tipo Aviso"] = get_aviso_tipo(session)
        datos["Autor Aviso"] = get_aviso_autor(session)
        datos["Fecha Aviso"] = get_aviso_fecha(session)
        datos["Servicio"] = get_aviso_servicio(session)
        
        # Obtener texto largo del aviso en una sola línea
        texto_largo = get_texto_largo_aviso(session)
        if texto_largo:
            # Convertir saltos de línea a espacios para que quede en una sola línea
            datos["Aviso"] = texto_largo.replace('\n', ' ').replace('\r', ' ')
        else:
            datos["Aviso"] = "Sin texto largo disponible"

def aceptar_g02(session):
    session.findById("wnd[0]/tbar[0]/btn[3]").press()
    
    # Espera a que se procese y luego selecciona la pestaña
    if esperar_elemento(session, "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE", timeout=3):
        session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE").select()
        care_table = getter_care(session)
        if care_table:
            print("\n\nItemizado:")
            print(care_table)
        else:
            print("No se encontraron datos CARE válidos.")

def pausa():
    exit_code = pausaPorConsola()
    if exit_code == 0:
        print("")
        return 0  # Continúa normalmente
    elif exit_code == 1:
        print("")
        return 1  # Indica que se presionó ESC
    else:
        print(f"Codigo de salida inesperado: {exit_code}")
        exit(exit_code)

def aceptar_itemizado(session):
    session.findById("wnd[0]/tbar[0]/btn[3]").press()
    
    # Espera a que se procese y luego selecciona la pestaña
    if esperar_elemento(session, "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE", timeout=3):
        session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE").select()
        # Espera adicional para que se cargue completamente
        esperar_elemento(session, "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE", timeout=2)
        came_table = getter_came(session)
        if came_table:
            print("\n\nCargado:")
            print(came_table)
        else:
            print("No se encontraron datos CAME válidos.")

def aceptar_medicion(session):
    # Espera a que la pestaña esté disponible y la selecciona
    if esperar_elemento(session, "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpIHKZ", timeout=3):
        session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpIHKZ").select()

def cgi(session):
    session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/ctxtCAUFVD-INGPR").text = "Cgi"
    session.findById("wnd[0]/tbar[0]/btn[11]").press()
    
    # Espera un poco antes de enviar la tecla
    if esperar_elemento(session, "wnd[0]", timeout=2):
        pyautogui.press('down')

def mostrar_datos():
    # Calcular el ancho máximo para alinear columnas
    max_key_width = max(len("Clase de actividad aviso"), len("Ubicacion Tecnica"), len("Texto Breve"))
    max_value_width = 50
    
    # Crear separador
    separator = "+" + "-" * (max_key_width + 2) + "+" + "-" * (max_value_width + 2) + "+"
    
    print("\n" + separator)
    
    # Texto Breve
    print(f"| {'Texto Breve'.ljust(max_key_width)} | {str(datos['Texto Breve'] or '').ljust(max_value_width)} |")
    print(separator)
    
    # Ubicaciones
    print(f"| {'Ubicacion Tecnica'.ljust(max_key_width)} | {str(datos['Ubicacion Tecnica'] or '').ljust(max_value_width)} |")
    print(f"| {'Ubicacion Aviso'.ljust(max_key_width)} | {str(datos['Ubicacion Aviso'] or '').ljust(max_value_width)} |")
    print(separator)
    
    # Clases de Actividad
    print(f"| {'Clase de actividad'.ljust(max_key_width)} | {str(datos['Clase de actividad'] or '').ljust(max_value_width)} |")
    print(f"| {'Clase de actividad aviso'.ljust(max_key_width)} | {str(datos['Clase de actividad aviso'] or '').ljust(max_value_width)} |")
    print(separator)
    
    # Datos del Aviso
    print(f"| {'Tipo Aviso'.ljust(max_key_width)} | {str(datos['Tipo Aviso'] or '').ljust(max_value_width)} |")
    print(f"| {'Servicio'.ljust(max_key_width)} | {str(datos['Servicio'] or '').ljust(max_value_width)} |")
    print(separator)
    
    # Texto del aviso completo - dividir en líneas si es muy largo
    aviso_text = str(datos['Aviso'] or '')
    if len(aviso_text) <= max_value_width:
        # Si cabe en una línea, mostrar normalmente
        print(f"| {'Aviso'.ljust(max_key_width)} | {aviso_text.ljust(max_value_width)} |")
    else:
        # Si es muy largo, dividir en múltiples líneas
        words = aviso_text.split()
        lines = []
        current_line = ""
        
        for word in words:
            # Si agregar la palabra no excede el límite
            if len(current_line + " " + word if current_line else word) <= max_value_width:
                current_line = current_line + " " + word if current_line else word
            else:
                # Si la línea actual no está vacía, guardarla
                if current_line:
                    lines.append(current_line)
                # Si la palabra sola es más larga que el ancho máximo, cortarla
                if len(word) > max_value_width:
                    while len(word) > max_value_width:
                        lines.append(word[:max_value_width])
                        word = word[max_value_width:]
                    current_line = word if word else ""
                else:
                    current_line = word
        
        # Agregar la última línea si no está vacía
        if current_line:
            lines.append(current_line)
        
        # Mostrar la primera línea con la etiqueta "Aviso"
        if lines:
            print(f"| {'Aviso'.ljust(max_key_width)} | {lines[0].ljust(max_value_width)} |")
            # Mostrar las líneas restantes con etiqueta vacía
            for line in lines[1:]:
                print(f"| {' '.ljust(max_key_width)} | {line.ljust(max_value_width)} |")
        else:
            print(f"| {'Aviso'.ljust(max_key_width)} | {' '.ljust(max_value_width)} |")
    
    print(separator)

def salir(session):
    """Simula presionar F3 y luego ENTER para salir"""
    # Usar SAP GUI directamente en lugar de pyautogui
    session.findById("wnd[0]").sendVKey(15)  # F3 en SAP
    time.sleep(0.5)
    session.findById("wnd[0]").sendVKey(0)   # ENTER en SAP