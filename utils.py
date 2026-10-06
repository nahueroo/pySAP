import time
import pyautogui
import json
import os
import shutil
import csv
from sap_connection import *
from pausa import traer_consola_al_frente 
from getters import *
from globales import datos, esperar_elemento, esperar_popup
from constantes import RUTA_SAP_DESCARGAS, MAUFNR, AVISO,ESPERAR,ESPERARLARGO

def ingreso_a_came(session,fila)->str:
    came = selectCell(session,fila)
    
    came.doubleClickCurrentCell()

    datos["Texto Breve"] = get_textoBreve(session)
    datos["Clase de actividad"] = get_claseActividad(session)
    datos["Ubicacion Tecnica"] = get_UT(session)

    return came

def ver_fotos_en_came(session,carpeta_destino,sufijo):
    
    get_came_toolbox(session)
    
    hayfotos = abrir_fotos_came(session,carpeta_destino,sufijo)
    if not hayfotos:
        time.sleep(ESPERAR)
        abrir_pdf_came(session,carpeta_destino,sufijo)

def entrar_a_care(session):
    get_care_field(session)
    time.sleep(ESPERAR)
    get_care_field(session)
    
    datos["Ubicacion Aviso"] = get_textoBreveCare(session)
    datos["Clase de actividad aviso"] =  get_claseActividad(session)
    
    session.findById("wnd[0]").sendVKey(2) #F2

def ver_fotos_en_care(session,carpeta_destino,sufijo):
    docsAviso = docsOrden = imagenesOrden = imagenesAviso = False
    
    get_care_toolbox(session)
    select_first_row(session)

    session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_IMAG")
    time.sleep(ESPERARLARGO)
    if session.Children.Count > 1:
        print("No hay imagenes en ORDEN DE MANTENIMIENTO")
        session.findById("wnd[1]/tbar[0]/btn[0]").press()        
    else:
        imagenesOrden = True
        mover_y_renombrar_archivos_sap(carpeta_destino,sufijo)
        print("Imagenes encontradas en ORDEN DE MANTENIMIENTO")

    session.findById("wnd[0]/shellcont/shell").pressButton("DOC_LIST")
    time.sleep(ESPERARLARGO)
    if session.Children.Count > 1:
        print("No hay docs en ORDEN DE MANTENIMIENTO")
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
    else:
        docsOrden = True
        mover_y_renombrar_archivos_sap(carpeta_destino,sufijo)
        print("Documentos encontrados en ORDEN DE MANTENIMIENTO")

    # Segunda fila
    session.findById("wnd[0]/titl/shellcont[1]/shell").pressButton("%GOS_TOOLBOX")

    session.findById("wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL").getAbsoluteRow(1).selected = True
    session.findById("wnd[1]").sendVKey(0)
    
    session.findById("wnd[0]/shellcont[1]/shell").pressButton("VIEW_IMAG")
    time.sleep(ESPERARLARGO)
    if session.Children.Count > 1:
        print("No hay imagenes en AVISO")
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
    else:
        imagenesAviso = True
        mover_y_renombrar_archivos_sap(carpeta_destino,sufijo)
        print("Imagenes encontradas en AVISO")

    session.findById("wnd[0]/shellcont[1]/shell").pressButton("DOC_LIST")
    time.sleep(ESPERARLARGO)
    if esperar_popup(session, timeout=3):
        print("No hay docs en AVISO")
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
    else:
        docsAviso = True
        mover_y_renombrar_archivos_sap(carpeta_destino,sufijo)
        print("Documentos encontrados en AVISO")
    
    fotosEncontradas = docsAviso or docsOrden or imagenesAviso or imagenesOrden 

def entrar_a_aviso(session):
    # Cerrar ventanas adicionales que puedan estar abiertas
    while session.Children.Count > 1:
        try:
            session.Children(session.Children.Count-1).close()
        except Exception as e:
            break
    
    session.findById(AVISO).press()
    
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
        texto_largo = get_texto_aviso(session)
        if texto_largo:
            # Convertir saltos de línea a espacios para que quede en una sola línea
            datos["Aviso"] = texto_largo.replace('\n', ' ').replace('\r', ' ')
        else:
            datos["Aviso"] = "Sin texto disponible"

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

def mostrar_datos(carpeta_acta=None):
    # Guardar los datos actuales antes de mostrarlos
    guardar_datos_ultimo()
    _mostrar_tabla_datos(datos)

    # Si se proporcionó carpeta_acta, guardar archivos relacionados (pero NO mover)
    if carpeta_acta:
        # Guardar datos en archivo txt
        guardar_datos_txt(carpeta_acta, datos)
        # Agregar datos al CSV histórico
        agregar_datos_csv(carpeta_acta)
        print(f"\nDatos guardados en: {carpeta_acta}")

def _formatear_texto_largo(aviso_text,max_value_width):
        """Divide un texto largo en lineas de maximo max_value_width"""
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

        return lines

def salir(session):
    """Simula presionar F3 y luego ENTER para salir"""
    # Usar SAP GUI directamente en lugar de pyautogui
    session.findById("wnd[0]").sendVKey(15)  # F3 en SAP
    time.sleep(ESPERARLARGO)
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
        # Verificar si existe el archivo
    if not os.path.exists("ultimo_guardado.json"):
        print("\nNo hay datos guardados anteriormente.")
        return
    try:
        # Cargar datos del archivo
        with open("ultimo_guardado.json", "r", encoding="utf-8") as archivo:
            datos_guardados = json.load(archivo)
    except FileNotFoundError:
        print("\nNo hay datos guardados anteriormente.")
        return
    except json.JSONDecodeError:
        print("\nEl archivo de ultimo guardado esta corrupto.")
        return
    except OSError as e:
        print(f"\nNo se pudo leer ultimo_guardado.json: {e}")
        return
    
    # Mostrar timestamp si existe
    if "timestamp" in datos_guardados:
        print(f"\nÚltimos datos guardados el: {datos_guardados['timestamp']}")
        
    _mostrar_tabla_datos(datos_guardados)

def sanitizar_nombre_carpeta(texto):
    """Convierte un texto en un nombre de carpeta válido"""
    if not texto:
        return "sin_nombre"
    # Reemplazar caracteres inválidos para nombres de carpeta
    invalidos = '<>:"/\\|?*'
    for char in invalidos:
        texto = texto.replace(char, '_')
    # Remover espacios al inicio/final y limitar longitud
    return texto.strip()[:100]

def crear_carpeta_acta(texto_breve):
    """
    Crea una carpeta dentro de 'actas' con el nombre del texto breve
    Retorna la ruta de la carpeta creada
    """
    try:
        # Crear carpeta principal actas si no existe
        os.makedirs("actas", exist_ok=True)

        # Sanitizar el nombre del texto breve
        nombre_carpeta = sanitizar_nombre_carpeta(texto_breve)

        # Crear ruta completa
        carpeta_acta = os.path.join("actas", nombre_carpeta)

        # Crear carpeta acta
        os.makedirs(carpeta_acta, exist_ok=True)

        return carpeta_acta
    except Exception as e:
        print(f"Error al crear carpeta acta: {e}")
        return None

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

def guardar_datos_txt(carpeta_destino, datos_dict):
    """
    Guarda los datos formateados en un archivo .txt dentro de la carpeta destino
    """
    try:
        # Crear el contenido formateado como se muestra en pantalla
        max_key_width = max(len("Clase de actividad aviso"), len("Ubicacion Tecnica"), len("Texto Breve"))
        max_value_width = 50

        # Crear separador
        separator = "+" + "-" * (max_key_width + 2) + "+" + "-" * (max_value_width + 2) + "+"

        lineas = ["\n" + separator]

        # Texto Breve
        lineas.append(f"| {'Texto Breve'.ljust(max_key_width)} | {str(datos_dict.get('Texto Breve', '') or '').ljust(max_value_width)} |")
        lineas.append(separator)

        # Ubicaciones
        lineas.append(f"| {'Ubicacion Tecnica'.ljust(max_key_width)} | {str(datos_dict.get('Ubicacion Tecnica', '') or '').ljust(max_value_width)} |")
        lineas.append(f"| {'Ubicacion Aviso'.ljust(max_key_width)} | {str(datos_dict.get('Ubicacion Aviso', '') or '').ljust(max_value_width)} |")
        lineas.append(separator)

        # Clases de Actividad
        lineas.append(f"| {'Clase de actividad'.ljust(max_key_width)} | {str(datos_dict.get('Clase de actividad', '') or '').ljust(max_value_width)} |")
        lineas.append(f"| {'Clase de actividad aviso'.ljust(max_key_width)} | {str(datos_dict.get('Clase de actividad aviso', '') or '').ljust(max_value_width)} |")
        lineas.append(separator)

        # Datos del Aviso
        lineas.append(f"| {'Tipo Aviso'.ljust(max_key_width)} | {str(datos_dict.get('Tipo Aviso', '') or '').ljust(max_value_width)} |")
        lineas.append(f"| {'Servicio'.ljust(max_key_width)} | {str(datos_dict.get('Servicio', '') or '').ljust(max_value_width)} |")
        lineas.append(separator)

        # Texto del aviso completo - dividir en líneas si es muy largo
        aviso_text = str(datos_dict.get('Aviso', '') or '')
        if len(aviso_text) <= max_value_width:
            lineas.append(f"| {'Aviso'.ljust(max_key_width)} | {aviso_text.ljust(max_value_width)} |")
        else:

            lines = _formatear_texto_largo(aviso_text, max_value_width)

            if lines:
                lineas.append(f"| {'Aviso'.ljust(max_key_width)} | {lines[0].ljust(max_value_width)} |")
                for line in lines[1:]:
                    lineas.append(f"| {' '.ljust(max_key_width)} | {line.ljust(max_value_width)} |")
            else:
                lineas.append(f"| {'Aviso'.ljust(max_key_width)} | {' '.ljust(max_value_width)} |")

        lineas.append(separator)

        # Agregar datos CARE si existen
        if datos_dict.get("Datos CARE"):
            lineas.append("\n\nDatos CARE (Itemizado):")
            lineas.append(datos_dict["Datos CARE"])

        # Agregar datos CAME si existen
        if datos_dict.get("Datos CAME"):
            lineas.append("\n\nDatos CAME (Cargado):")
            lineas.append(datos_dict["Datos CAME"])

        # Agregar timestamp
        lineas.append(f"\n\nGenerado: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Guardar archivo
        ruta_txt = os.path.join(carpeta_destino, "datos.txt")
        with open(ruta_txt, "w", encoding="utf-8") as archivo:
            archivo.write("\n".join(lineas))

        return ruta_txt
    except Exception as e:
        print(f"Error al guardar archivo txt: {e}")
        return None

def agregar_datos_csv(carpeta_destino):
    """
    Agrega los datos actuales a un archivo CSV histórico
    """
    try:
        ruta_csv = "historico_actas.csv"

        # Preparar datos para CSV
        fila = {
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'Texto Breve': datos.get('Texto Breve', ''),
            'Clase de actividad': datos.get('Clase de actividad', ''),
            'Ubicacion Tecnica': datos.get('Ubicacion Tecnica', ''),
            'Ubicacion Aviso': datos.get('Ubicacion Aviso', ''),
            'Clase de actividad aviso': datos.get('Clase de actividad aviso', ''),
            'Tipo Aviso': datos.get('Tipo Aviso', ''),
            'Autor Aviso': datos.get('Autor Aviso', ''),
            'Fecha Aviso': datos.get('Fecha Aviso', ''),
            'Servicio': datos.get('Servicio', ''),
            'Aviso': str(datos.get('Aviso', ''))[:100] if datos.get('Aviso') else '',
            'Ruta carpeta': carpeta_destino
        }

        # Nombres de columnas en orden
        columnas = [
            'timestamp', 'Texto Breve', 'Clase de actividad', 'Ubicacion Tecnica',
            'Ubicacion Aviso', 'Clase de actividad aviso', 'Tipo Aviso', 'Autor Aviso',
            'Fecha Aviso', 'Servicio', 'Aviso', 'Ruta carpeta'
        ]

        # Verificar si el archivo ya existe
        archivo_existe = os.path.exists(ruta_csv)

        # Escribir/Agregar al CSV
        with open(ruta_csv, 'a' if archivo_existe else 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columnas)

            # Si es la primera vez, escribir encabezado
            if not archivo_existe:
                writer.writeheader()

            # Escribir fila de datos
            writer.writerow(fila)

        return ruta_csv
    except Exception as e:
        print(f"Error al agregar datos a CSV: {e}")
        return None

def _mostrar_tabla_datos(datos_dict):

    # Calcular el ancho máximo para alinear columnas
    max_key_width = max(len("Clase de actividad aviso"), len("Ubicacion Tecnica"), len("Texto Breve"))
    max_value_width = 50

    # Crear separador
    separator = "+" + "-" * (max_key_width + 2) + "+" + "-" * (max_value_width + 2) + "+"

    print("\n" + separator)

    # Texto Breve
    print(f"| {'Texto Breve'.ljust(max_key_width)} | {str(datos_dict.get('Texto Breve') or '').ljust(max_value_width)} |")
    print(separator)

    # Ubicaciones
    print(f"| {'Ubicacion Tecnica'.ljust(max_key_width)} | {str(datos_dict.get('Ubicacion Tecnica') or '').ljust(max_value_width)} |")
    print(f"| {'Ubicacion Aviso'.ljust(max_key_width)} | {str(datos_dict.get('Ubicacion Aviso') or '').ljust(max_value_width)} |")
    print(separator)

    # Clases de Actividad
    print(f"| {'Clase de actividad'.ljust(max_key_width)} | {str(datos_dict.get('Clase de actividad') or '').ljust(max_value_width)} |")
    print(f"| {'Clase de actividad aviso'.ljust(max_key_width)} | {str(datos_dict.get('Clase de actividad aviso') or '').ljust(max_value_width)} |")
    print(separator)

    # Datos del Aviso
    print(f"| {'Tipo Aviso'.ljust(max_key_width)} | {str(datos_dict.get('Tipo Aviso') or '').ljust(max_value_width)} |")
    print(f"| {'Servicio'.ljust(max_key_width)} | {str(datos_dict.get('Servicio') or '').ljust(max_value_width)} |")
    print(separator)

    # Texto del aviso completo - dividir en líneas si es muy largo
    aviso_text = str(datos['Aviso'] or '')
    if len(aviso_text) <= max_value_width:
        # Si cabe en una línea, mostrar normalmente
        print(f"| {'Aviso'.ljust(max_key_width)} | {aviso_text.ljust(max_value_width)} |")
    else:

        lines = _formatear_texto_largo(aviso_text, max_value_width)

        # Mostrar la primera línea con la etiqueta "Aviso"
        if lines:
            print(f"| {'Aviso'.ljust(max_key_width)} | {lines[0].ljust(max_value_width)} |")
            # Mostrar las líneas restantes con etiqueta vacía
            for line in lines[1:]:
                print(f"| {' '.ljust(max_key_width)} | {line.ljust(max_value_width)} |")
        else:
            print(f"| {'Aviso'.ljust(max_key_width)} | {' '.ljust(max_value_width)} |")

    print(separator)

    # FUNCIONES AUXILIARES

def abrir_fotos_came(session,carpeta_destino,sufijo):
    
    #Abre Visualizar imagenes
    session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_IMAG")
    
    # Espera a que aparezca el popup
    if esperar_popup(session, timeout=3):
        # presiona el botón Aceptar en el popup
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        return False
    
    mover_y_renombrar_archivos_sap(carpeta_destino,sufijo)
    return True

def abrir_doc_list_came(session,carpeta_destino, sufijo):
    
    # abre Lista de documentos
    session.findById("wnd[0]/shellcont/shell").pressButton("DOC_LIST")
    
    # Espera a que aparezca el popup
    if esperar_popup(session, timeout=3):
        # presiona el botón Aceptar en el popup
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        return False
    
    mover_y_renombrar_archivos_sap(carpeta_destino,sufijo)
    return True

def abrir_pdf_came(session,carpeta_destino, sufijo):

    session.findById("wnd[0]/shellcont/shell").pressButton("VIEW_DOC")

    # Espera a que aparezca el popup
    popup = esperar_popup(session, timeout=3)
    if popup:
        # presiona el botón Aceptar en el popup
        try:
            boton = session.findById("wnd[1]/tbar[0]/btn[0]")
            boton.press()
        except Exception:
            print("No apareció el popup o no existe el botón Aceptar.")
    
    
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
                time.sleep(ESPERARLARGO)
                mover_y_renombrar_archivos_sap(carpeta_destino,sufijo)
                
            except Exception as e:
                # Si hay error al acceder a una fila, probablemente llegamos al final
                print(f"Error al procesar fila {row_index}: {e}")
                break
        
        # Cerrar las ventanas después de procesar todas las filas
        session.findById("wnd[1]").close()
        session.findById("wnd[0]/shellcont").close()
