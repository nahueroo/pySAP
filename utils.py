import time
import pyautogui
import json
import os
import ctypes
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
                grid = session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell")
                
                # Obtener el número total de filas en la grid
                row_count = grid.RowCount
                
                # Iterar a través de todas las filas
                for row_index in range(row_count):
                    try:
                        # Seleccionar la fila actual
                        grid.currentCellRow = row_index
                        grid.currentCellColumn = "NOMBRE"
                        
                        # Verificar si la celda tiene contenido
                        cell_value = grid.getCellValue(row_index, "NOMBRE")
                        
                        # Si la celda está vacía, terminar el bucle
                        if not cell_value or cell_value.strip() == "":
                            break
                        
                        # Hacer doble clic en la celda con contenido
                        grid.doubleClickCurrentCell()
                        
                        # Pequeña pausa entre selecciones para estabilidad
                        time.sleep(0.5)
                        
                    except Exception as e:
                        # Si hay error al acceder a una fila, probablemente llegamos al final
                        print(f"Error al procesar fila {row_index}: {e}")
                        break
                
                # Cerrar las ventanas después de procesar todas las filas
                session.findById("wnd[1]").close()
                session.findById("wnd[0]/shellcont").close()

def ver_fotos_en_came_tecno(session):
    session.findById("wnd[0]/titl/shellcont/shell").pressButton("%GOS_TOOLBOX")
    session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_DOC")
    
    # Espera a que aparezca la ventana con la grid
    if esperar_elemento(session, "wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell", timeout=3):
        grid = session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell")
        
        # Obtener el número total de filas en la grid
        row_count = grid.RowCount
        
        # Iterar a través de todas las filas
        for row_index in range(row_count):
            try:
                # Seleccionar la fila actual
                grid.currentCellRow = row_index
                grid.currentCellColumn = "NOMBRE"
                
                # Verificar si la celda tiene contenido
                cell_value = grid.getCellValue(row_index, "NOMBRE")
                
                # Si la celda está vacía, terminar el bucle
                if not cell_value or cell_value.strip() == "":
                    break
                
                # Hacer doble clic en la celda con contenido
                grid.doubleClickCurrentCell()
                
                # Pequeña pausa entre selecciones para estabilidad
                time.sleep(0.5)
                
            except Exception as e:
                # Si hay error al acceder a una fila, probablemente llegamos al final
                print(f"Error al procesar fila {row_index}: {e}")
                break
        
        # Cerrar las ventanas después de procesar todas las filas
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
    fotos_encontradas_row0a = True
    fotos_encontradas_row0b = True
    fotos_encontradas_row1a = True
    fotos_encontradas_row1b = True
    
    # Primera fila (row 0) - exactamente como antes
    session.findById("wnd[0]/titl/shellcont[1]/shell").pressButton("%GOS_TOOLBOX")

    session.findById("wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL").getAbsoluteRow(0).selected = True
    session.findById("wnd[1]").sendVKey(0)

    # Espera a que se procese la selección
    if esperar_elemento(session, "wnd[0]/shellcont/shell", timeout=3):
        session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_IMAG")

    if session.Children.Count > 1:
        # presiona el botón Aceptar en el popup
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        fotos_encontradas_row0a = False
        
        # abre lista de documentos
        session.findById("wnd[0]/shellcont/shell").pressButton("DOC_LIST")

        if session.Children.Count > 1:
            # presiona el botón Aceptar en el popup
            session.findById("wnd[1]/tbar[0]/btn[0]").press()
            fotos_encontradas_row0b = False

    # Segunda fila (row 1) - exactamente como antes
    session.findById("wnd[0]/titl/shellcont[1]/shell").pressButton("%GOS_TOOLBOX")

    session.findById("wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL").getAbsoluteRow(1).selected = True
    session.findById("wnd[1]").sendVKey(0)
    session.findById("wnd[0]/shellcont[1]/shell").pressButton("VIEW_IMAG")
    
    # Espera inteligente a que aparezca el popup
    if session.Children.Count > 1:
        # presiona el botón Aceptar en el popup
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        fotos_encontradas_row1a = False

        # abre Lista de documentos
        session.findById("wnd[0]/shellcont[1]/shell").pressButton("DOC_LIST")
        
        # Espera inteligente a que aparezca el popup
        if esperar_popup(session, timeout=3):
            # presiona el botón Aceptar en el popup
            session.findById("wnd[1]/tbar[0]/btn[0]").press()
            fotos_encontradas_row1b = False

    fotos_encontradas = fotos_encontradas_row0a or fotos_encontradas_row0b or fotos_encontradas_row1a or fotos_encontradas_row1b
    
    # Si no se encontraron fotos en ninguna de las dos filas, acceder directamente a documentos
    if not fotos_encontradas:
        print("No se encontraron fotos. Accediendo directamente a documentos...")
        
        # Seguir exactamente la secuencia del Script2.vbs
        session.findById("wnd[0]/titl/shellcont[1]/shell").pressButton("%GOS_TOOLBOX")
        
        # Esperar a que aparezca la ventana GOS_TOOLBOX
        if esperar_elemento(session, "wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL", timeout=3):
            # Seleccionar la fila 1 y hacer foco en el campo específico como en Script2.vbs
            #session.findById("wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL/txtSWLOBJTDYN-DEF_ATTRIB[1,1]").setFocus()
            #session.findById("wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL/txtSWLOBJTDYN-DEF_ATTRIB[1,1]").caretPosition = 4
            session.findById("wnd[1]").sendVKey(2)
            
            # Intentar diferentes ubicaciones para VIEW_DOC
            try:
                # Primero intentar como en Script2.vbs
                session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_DOC")
            except:
                try:
                    # Si no funciona, intentar con shellcont[1] como en el resto de la función
                    session.findById("wnd[0]/shellcont[1]/shell").pressButton("VIEW_DOC")
                except:
                    return
        
        # Procesar todos los documentos en la grid (adaptado de ver_fotos_en_came)
        if esperar_elemento(session, "wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell", timeout=3):
            grid = session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell")
            
            # Obtener el número total de filas en la grid
            row_count = grid.RowCount
            
            # Iterar a través de todas las filas
            for row_index in range(row_count):
                try:
                    # Seleccionar la fila actual
                    grid.currentCellRow = row_index
                    grid.currentCellColumn = "NOMBRE"
                    
                    # Verificar si la celda tiene contenido
                    cell_value = grid.getCellValue(row_index, "NOMBRE")
                    
                    # Si la celda está vacía, terminar el bucle
                    if not cell_value or cell_value.strip() == "":
                        break
                    
                    # Hacer doble clic en la celda con contenido
                    grid.doubleClickCurrentCell()
                    
                    # Pequeña pausa entre selecciones para estabilidad
                    time.sleep(0.5)
                    
                except Exception as e:
                    # Si hay error al acceder a una fila, probablemente llegamos al final
                    print(f"Error al procesar fila {row_index}: {e}")
                    break
            
            # Cerrar las ventanas después de procesar todas las filas
            try:
                session.findById("wnd[1]").close()
            except:
                pass
            
            try:
                session.findById("wnd[0]/shellcont[1]").close()
            except:
                try:
                    session.findById("wnd[0]/shellcont").close()
                except:
                    pass

def entrar_a_aviso(session):
    # Cerrar ventanas adicionales que puedan estar abiertas
    while session.Children.Count > 1:
        try:
            session.Children(session.Children.Count-1).close()
        except Exception as e:
            break
    
    # Verificar estado de la ventana antes de presionar el botón
    try:
        boton_aviso = session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/btnICON_NTF")
    except Exception as e:
        return
    
    session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/btnICON_NTF").press()
    
    # Dar más tiempo para que se abra el aviso
    time.sleep(2)
    
    # Espera a que se abra el aviso
    elemento_esperado = "wnd[0]/usr/subSCREEN_1:SAPLIQS0:1050/subNOTIF_TYPE:SAPLIQS0:1051/ctxtVIQMEL-QMART"
    if esperar_elemento(session, elemento_esperado, timeout=5):
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
    else:
        # Intentar listar las ventanas disponibles
        try:
            for i in range(session.Children.Count):
                ventana = session.Children(i)
        except Exception as e:
            pass

def aceptar_g02(session):
    session.findById("wnd[0]/tbar[0]/btn[3]").press()
    
    # Espera a que se procese y luego selecciona la pestaña
    if esperar_elemento(session, "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE", timeout=3):
        session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE").select()
        care_table = getter_care(session)
        if care_table:
            print("\n\nItemizado:")
            print(care_table)
            # Guardar los datos CARE en el diccionario global
            datos["Datos CARE"] = care_table
            # Guardar inmediatamente en el archivo JSON
            guardar_datos_ultimo()
        else:
            print("No se encontraron datos CARE válidos.")
            datos["Datos CARE"] = "No se encontraron datos CARE válidos."
            # Guardar inmediatamente en el archivo JSON
            guardar_datos_ultimo()

def pausa():
    traer_consola_al_frente()  # Traer consola al frente antes de la pausa
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
            # Guardar los datos CAME en el diccionario global
            datos["Datos CAME"] = came_table
            # Guardar inmediatamente en el archivo JSON
            guardar_datos_ultimo()
        else:
            print("No se encontraron datos CAME válidos.")
            datos["Datos CAME"] = "No se encontraron datos CAME válidos."
            # Guardar inmediatamente en el archivo JSON
            guardar_datos_ultimo()

def cgi(session):
    session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpIHKZ").select()
    session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/ctxtCAUFVD-INGPR").text = "Cgi"
    session.findById("wnd[0]/tbar[0]/btn[11]").press()
    
    # Espera un poco antes de enviar la tecla
    if esperar_elemento(session, "wnd[0]", timeout=2):
        pyautogui.press('down')

def mostrar_datos():
    # Guardar los datos actuales antes de mostrarlos
    guardar_datos_ultimo()
    
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

def guardar_datos_ultimo():
    """Guarda los datos actuales en un archivo JSON"""
    try:
        # Crear copia de los datos actuales incluyendo timestamp
        datos_a_guardar = datos.copy()
        datos_a_guardar["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Guardar en archivo JSON
        with open("ultimo_guardado.json", "w", encoding="utf-8") as archivo:
            json.dump(datos_a_guardar, archivo, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error al guardar los datos: {e}")

def mostrar_ultimo_guardado():
    """Muestra los datos del último guardado desde el archivo JSON"""
    try:
        # Verificar si existe el archivo
        if not os.path.exists("ultimo_guardado.json"):
            print("\nNo hay datos guardados anteriormente.")
            return
        
        # Cargar datos del archivo
        with open("ultimo_guardado.json", "r", encoding="utf-8") as archivo:
            datos_guardados = json.load(archivo)
        
        # Mostrar timestamp si existe
        if "timestamp" in datos_guardados:
            print(f"\nÚltimos datos guardados el: {datos_guardados['timestamp']}")
        
        # Calcular el ancho máximo para alinear columnas
        max_key_width = max(len("Clase de actividad aviso"), len("Ubicacion Tecnica"), len("Texto Breve"))
        max_value_width = 50
        
        # Crear separador
        separator = "+" + "-" * (max_key_width + 2) + "+" + "-" * (max_value_width + 2) + "+"
        
        print("\n" + separator)
        
        # Texto Breve
        print(f"| {'Texto Breve'.ljust(max_key_width)} | {str(datos_guardados.get('Texto Breve', '') or '').ljust(max_value_width)} |")
        print(separator)
        
        # Ubicaciones
        print(f"| {'Ubicacion Tecnica'.ljust(max_key_width)} | {str(datos_guardados.get('Ubicacion Tecnica', '') or '').ljust(max_value_width)} |")
        print(f"| {'Ubicacion Aviso'.ljust(max_key_width)} | {str(datos_guardados.get('Ubicacion Aviso', '') or '').ljust(max_value_width)} |")
        print(separator)
        
        # Clases de Actividad
        print(f"| {'Clase de actividad'.ljust(max_key_width)} | {str(datos_guardados.get('Clase de actividad', '') or '').ljust(max_value_width)} |")
        print(f"| {'Clase de actividad aviso'.ljust(max_key_width)} | {str(datos_guardados.get('Clase de actividad aviso', '') or '').ljust(max_value_width)} |")
        print(separator)
        
        # Datos del Aviso
        print(f"| {'Tipo Aviso'.ljust(max_key_width)} | {str(datos_guardados.get('Tipo Aviso', '') or '').ljust(max_value_width)} |")
        print(f"| {'Servicio'.ljust(max_key_width)} | {str(datos_guardados.get('Servicio', '') or '').ljust(max_value_width)} |")
        print(separator)
        
        # Texto del aviso completo - dividir en líneas si es muy largo
        aviso_text = str(datos_guardados.get('Aviso', '') or '')
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
        
        # Mostrar datos CARE (Itemizado) si están disponibles
        if datos_guardados.get("Datos CARE"):
            print("\n\nDatos CARE (Itemizado):")
            print(datos_guardados["Datos CARE"])
        
        # Mostrar datos CAME (Cargado) si están disponibles
        if datos_guardados.get("Datos CAME"):
            print("\n\nDatos CAME (Cargado):")
            print(datos_guardados["Datos CAME"])
        
    except Exception as e:
        print(f"Error al cargar los datos guardados: {e}")

def traer_consola_al_frente():
    """Trae la ventana de la consola al frente"""
    try:
        # Obtener el handle de la ventana de la consola
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        
        # Obtener el handle de la ventana de la consola actual
        console_window = kernel32.GetConsoleWindow()
        
        if console_window:
            # Traer la ventana al frente
            user32.SetForegroundWindow(console_window)
            # Asegurar que la ventana esté visible y no minimizada
            user32.ShowWindow(console_window, 9)  # SW_RESTORE
        else:
            print("No se pudo obtener el handle de la consola")
    except Exception as e:
        print(f"Error al traer la consola al frente: {e}")