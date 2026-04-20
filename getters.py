import win32com.client
from constantes import RUTAS_SAP

def _get_sap_field(session, ruta, nombre_campo="", caret_position=None):
    try:
        elemento = session.findById(ruta)

        if caret_position is not None:
            elemento.setFocus()
            elemento.caretPosition = caret_position

        return elemento.text
    
    except Exception as e:
        print(f"Error al obtener {nombre_campo}: {e}")
        return None
    
def get_textoBreve(session):
    return _get_sap_field(session, RUTAS_SAP["textoBreve"],"Texto Breve")

def get_claseActividad(session):
    return _get_sap_field(session, RUTAS_SAP["claseActividad"],"Clase de actividad")

def get_UT(session):
    return _get_sap_field(session, RUTAS_SAP["UT"],"UT")

def get_textoBreveCare(session):
    return _get_sap_field(session, RUTAS_SAP["textoBreveCare"],"Texto Care")

def get_aviso_tipo(session):
    return _get_sap_field(session, RUTAS_SAP["aviso_tipo"],"Tipo de aviso")
    
def get_aviso_autor(session):
    return _get_sap_field(session, RUTAS_SAP["aviso_autor"],"Autor del aviso",caret_position=5)
    
def get_aviso_fecha(session):
    return _get_sap_field(session, RUTAS_SAP["aviso_fecha"],"Fecha del aviso",caret_position=5)
        
def get_aviso_servicio(session):
    return _get_sap_field(session, RUTAS_SAP["aviso_servicio"],"Tipo de aviso",caret_position=23)

def getter_care(session):
    """Obtiene todos los valores válidos de los campos LTXA1 y ARBEI de la operación actual y los devuelve en formato tabla ordenado."""
    ltxa1_list = []
    arbei_list = []
    row = 0
    
    # Recopilar datos
    while True:
        try:
            ltxa1 = session.findById(f"wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpVGUE/ssubSUB_AUFTRAG:SAPLCOVG:3010/tblSAPLCOVGTCTRL_3010/txtAFVGD-LTXA1[7,{row}]").text
            arbei = session.findById(f"wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpVGUE/ssubSUB_AUFTRAG:SAPLCOVG:3010/tblSAPLCOVGTCTRL_3010/txtAFVGD-ARBEI[10,{row}]").text
            if ltxa1.strip() and not ltxa1.startswith("_") and ltxa1 != "":
                ltxa1_list.append(ltxa1)
                arbei_list.append(arbei)
            row += 1
        except Exception:
            break
    
    # Si no hay datos, devolver string vacío
    if not ltxa1_list:
        return ""
    
    # Combinar y ordenar por TRABAJO (alfabéticamente)
    combined_data = list(zip(ltxa1_list, arbei_list))
    combined_data.sort(key=lambda x: x[0].lower())
    
    # Calcular anchos máximos para justificación
    max_trabajo_width = max(len("TRABAJO"), max(len(trabajo) for trabajo, _ in combined_data))
    max_itemizado_width = max(len("ITEMIZADO"), max(len(itemizado) for _, itemizado in combined_data))
    
    # Crear tabla formateada
    separator = "+" + "-" * (max_trabajo_width + 2) + "+" + "-" * (max_itemizado_width + 2) + "+"
    header = f"| {'TRABAJO'.ljust(max_trabajo_width)} | {'ITEMIZADO'.ljust(max_itemizado_width)} |"
    
    result = [separator, header, separator]
    
    # Agregar datos sin subtotales
    for trabajo, itemizado in combined_data:
        row = f"| {trabajo.ljust(max_trabajo_width)} | {itemizado.ljust(max_itemizado_width)} |"
        result.append(row)
    
    result.append(separator)
    
    # Total general
    try:
        all_itemizados = [float(itemizado.replace(',', '.')) for _, itemizado in combined_data if itemizado.strip()]
        total_value = sum(all_itemizados)
        total_text = f"TOTAL GENERAL: {total_value:.2f}"
    except (ValueError, TypeError):
        total_text = f"TOTAL GENERAL: {len(combined_data)} item(s)"
    
    total_row = f"| {total_text.ljust(max_trabajo_width + max_itemizado_width + 3)} |"
    result.append(total_row)
    result.append(separator)
    
    return "\n".join(result)

def getter_came(session):
    """Obtiene todos los valores válidos de los campos LTXA1 y DAUNO de la operación actual y los devuelve en formato tabla ordenado con subtotales."""
    ltxa1_list = []
    dauno_list = []
    row = 0
    
    # Recopilar datos
    while True:
        try:
            ltxa1 = session.findById(f"wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpVGUE/ssubSUB_AUFTRAG:SAPLCOVG:3010/tblSAPLCOVGTCTRL_3010/txtAFVGD-LTXA1[7,{row}]").text
            dauno = session.findById(f"wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpVGUE/ssubSUB_AUFTRAG:SAPLCOVG:3010/tblSAPLCOVGTCTRL_3010/txtAFVGD-DAUNO[13,{row}]").text
            if ltxa1.strip() and not ltxa1.startswith("_") and ltxa1 != "":
                ltxa1_list.append(ltxa1)
                dauno_list.append(dauno)
            row += 1
        except Exception:
            break
    
    # Si no hay datos, devolver string vacío
    if not ltxa1_list:
        return ""
    
    # Combinar y ordenar por TRABAJO (alfabéticamente)
    combined_data = list(zip(ltxa1_list, dauno_list))
    combined_data.sort(key=lambda x: x[0].lower())
    
    # Agrupar por trabajo para subtotales
    from collections import defaultdict
    grouped_data = defaultdict(list)
    for trabajo, cantidad in combined_data:
        grouped_data[trabajo].append(cantidad)
    
    # Calcular anchos máximos para justificación
    max_trabajo_width = max(len("TRABAJO"), max(len(trabajo) for trabajo in grouped_data.keys()))
    max_cantidad_width = max(len("CANTIDAD"), max(len(item) for sublist in grouped_data.values() for item in sublist))
    
    # Crear tabla formateada
    separator = "+" + "-" * (max_trabajo_width + 2) + "+" + "-" * (max_cantidad_width + 2) + "+"
    header = f"| {'TRABAJO'.ljust(max_trabajo_width)} | {'CANTIDAD'.ljust(max_cantidad_width)} |"
    
    result = [separator, header, separator]
    
    # Agregar datos agrupados con subtotales
    for trabajo in sorted(grouped_data.keys(), key=str.lower):
        cantidades = grouped_data[trabajo]
        
        # Primera fila del grupo
        first_row = f"| {trabajo.ljust(max_trabajo_width)} | {cantidades[0].ljust(max_cantidad_width)} |"
        result.append(first_row)
        
        # Filas adicionales del grupo (trabajo vacío)
        for cantidad in cantidades[1:]:
            additional_row = f"| {' '.ljust(max_trabajo_width)} | {cantidad.ljust(max_cantidad_width)} |"
            result.append(additional_row)
        
        # Calcular subtotal numérico si las cantidades son números
        try:
            numeric_cantidades = [float(c.replace(',', '.')) for c in cantidades if c.strip()]
            subtotal_value = sum(numeric_cantidades)
            subtotal_text = f"Subtotal: {subtotal_value:.2f}"
        except (ValueError, TypeError):
            subtotal_text = f"Subtotal: {len(cantidades)} item(s)"
        
        # Subtotal del grupo
        subtotal_separator = "+" + "-" * (max_trabajo_width + 2) + "+" + "-" * (max_cantidad_width + 2) + "+"
        subtotal_row = f"| {subtotal_text.ljust(max_trabajo_width + max_cantidad_width + 3)} |"
        result.append(subtotal_separator)
        result.append(subtotal_row)
        result.append(separator)
    
    return "\n".join(result)

def get_texto_largo_aviso(session):
    """
    Obtiene todo el contenido de texto largo de un aviso en SAP.
    Versión que combina acceso directo e inteligente navegación con scroll.
    
    Args:
        session: Sesión activa de SAP GUI
    
    Returns:
        str: Texto completo del aviso concatenado, o None si hay error
    """
    try:
        # Maximizar ventana para asegurar visibilidad completa
        session.findById("wnd[0]").maximize()
        
        # Ruta base para la tabla de texto largo
        base_ruta = (r"wnd[0]/usr/tabsTAB_GROUP_10/tabp10\TAB01/"
                     r"ssubSUB_GROUP_10:SAPLIQS0:7235/"
                     r"subCUSTOM_SCREEN:SAPLIQS0:7212/"
                     r"subSUBSCREEN_1:SAPLIQS0:7710/")
        
        tabla_ruta = base_ruta + "tblSAPLIQS0TEXT"
        
        # Set para evitar duplicados exactos
        lineas_unicas = set()
        lineas_ordenadas = []
        
        # Obtener referencia a la tabla
        tabla = session.findById(tabla_ruta)
        
        # Obtener información básica de la tabla
        try:
            filas_visibles = tabla.visibleRowCount
            total_filas = tabla.rowCount
        except:
            filas_visibles = 4
            total_filas = 20
        
        # Resetear scroll al inicio
        try:
            if hasattr(tabla, 'verticalScrollbar'):
                tabla.verticalScrollbar.position = 0
            if hasattr(tabla, 'firstVisibleRow'):
                tabla.firstVisibleRow = 0
        except:
            pass
        
        # ESTRATEGIA PRINCIPAL: Navegación sistemática con scroll
        # Primero: explorar contenido visible inicial
        for fila in range(filas_visibles):
            try:
                celda = session.findById(f"{tabla_ruta}/txtLTXTTAB2-TLINE[0,{fila}]")
                texto = celda.text
                
                if texto and texto.strip():
                    if texto not in lineas_unicas:
                        lineas_unicas.add(texto)
                        lineas_ordenadas.append(texto)
                        
            except:
                continue
        
        # Segundo: navegar con scroll si hay más filas
        if total_filas > filas_visibles:
            # Calcular cuántas posiciones de scroll necesitamos
            posiciones_scroll = range(1, total_filas - filas_visibles + 2)
            
            for pos_scroll in posiciones_scroll:
                try:
                    # Intentar mover scroll
                    if hasattr(tabla, 'verticalScrollbar'):
                        tabla.verticalScrollbar.position = pos_scroll
                    
                    # Leer filas visibles en esta posición
                    for fila in range(filas_visibles):
                        try:
                            celda = session.findById(f"{tabla_ruta}/txtLTXTTAB2-TLINE[0,{fila}]")
                            texto = celda.text
                            
                            if texto and texto.strip():
                                if texto not in lineas_unicas:
                                    lineas_unicas.add(texto)
                                    lineas_ordenadas.append(texto)
                                    
                        except:
                            continue
                            
                except:
                    continue
        
        # ESTRATEGIA ALTERNATIVA: Si lo anterior no funcionó bien, usar firstVisibleRow
        if len(lineas_ordenadas) < 3:  # Si obtuvimos muy poco contenido
            try:
                # Resetear
                tabla.firstVisibleRow = 0
                
                # Navegar por firstVisibleRow
                for start_row in range(0, total_filas, max(1, filas_visibles - 1)):
                    try:
                        tabla.firstVisibleRow = start_row
                        
                        # Leer filas visibles
                        for fila in range(filas_visibles):
                            try:
                                celda = session.findById(f"{tabla_ruta}/txtLTXTTAB2-TLINE[0,{fila}]")
                                texto = celda.text
                                
                                if texto and texto.strip():
                                    if texto not in lineas_unicas:
                                        lineas_unicas.add(texto)
                                        lineas_ordenadas.append(texto)
                                        
                            except:
                                continue
                                
                    except:
                        continue
                        
            except:
                pass
        
        # ESTRATEGIA DE RESPALDO: Acceso directo por índices
        if len(lineas_ordenadas) < 2:  # Si aún tenemos muy poco contenido
            # Resetear tabla
            try:
                if hasattr(tabla, 'verticalScrollbar'):
                    tabla.verticalScrollbar.position = 0
            except:
                pass
            
            # Intentar acceso directo
            for indice in range(min(100, total_filas * 2)):
                try:
                    celda = session.findById(f"{tabla_ruta}/txtLTXTTAB2-TLINE[0,{indice}]")
                    texto = celda.text
                    
                    if texto and texto.strip():
                        if texto not in lineas_unicas:
                            lineas_unicas.add(texto)
                            lineas_ordenadas.append(texto)
                            
                except:
                    continue
        
        # Construir resultado final
        if not lineas_ordenadas:
            return None
        
        # Unir todas las líneas preservando saltos de línea
        texto_completo = "\n".join(lineas_ordenadas)
        
        return texto_completo if texto_completo.strip() else None
        
    except Exception as e:
        return None





