import time
import pyautogui
import json
import os
import csv
from sap_connection import *
from pausa import traer_consola_al_frente 
from getters import *
from globales import datos, esperar_elemento

def ingreso_a_came(session,fila=None)->str:
    
    if fila is not None:
        came = selectCell(session,fila)
    else:
        came = get_grid(session)
    
    came.doubleClickCurrentCell()

    datos["Texto Breve"] = get_textoBreve(session)
    datos["Clase de actividad"] = get_claseActividad(session)
    datos["Ubicacion Tecnica"] = get_UT(session)

    return came

def ver_fotos_en_came(session,carpeta_destino,sufijo):

    # "DOC_LIST" O "VIEW_IMAG"
    
    get_came_toolbox(session)
    hayfotos = fotosCame(session, carpeta_destino,sufijo)
    if not hayfotos:
        time.sleep(0.3)
        pdfCame(session,carpeta_destino,sufijo)

def entrar_a_care(session):
    get_care_field(session)
    time.sleep(0.4)
    get_care_field(session)
    
    datos["Ubicacion Aviso"] = get_textoBreveCare(session)
    datos["Clase de actividad aviso"] =  get_claseActividad(session)
    
    sendKey(session, F2)

def ver_fotos_en_care(session,carpeta_destino,sufijo):

    # row == 0 es orden, row == 1 es aviso

    row = 0
    while row < 2:

        if row == 0:
            sufijo = "CARE - ORDEN DE MANTENIMIENTO"
        if row == 1:
            sufijo = "CARE - AVISO"
    
        get_care_toolbox(session)
        select_row(session,row)
    
        verfotosCARE(session,row,"VIEW_IMAG")
        time.sleep(0.3)
        download_fotos(session,carpeta_destino,sufijo)

        verfotosCARE(session,row,"DOC_LIST")
        time.sleep(0.3)
        download_fotos(session,carpeta_destino,sufijo)

        row += 1

    cerrar_ventanas_extra(session)

def entrar_a_aviso(session):
    
    get_aviso_field(session)
    time.sleep(0.3)
    
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

def volveryGuardarOperaciones(session,orden):
    
    volver(session)
    selectOperTab(session)
    guardar_itemizado(session,orden)
    guardar_datos_ultimo()

def cgi(session):
    session.findById(DATOSCABECERA).select()
    session.findById(GRUPOPLANIFICACION).text = "Cgi"
    session.findById(GUARDAR).press()

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