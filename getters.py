import win32com.client
from constantes import RUTAS_SAP, LTXA1,DAUNO,ARBEI

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
    return _get_sap_field(session, RUTAS_SAP["textoBreve"],nombre_campo="Texto Breve")

def get_claseActividad(session):
    return _get_sap_field(session, RUTAS_SAP["claseActividad"],nombre_campo="Clase de actividad")

def get_UT(session):
    return _get_sap_field(session, RUTAS_SAP["UT"],nombre_campo="UT")

def get_textoBreveCare(session):
    return _get_sap_field(session, RUTAS_SAP["textoBreveCare"],nombre_campo="Texto Care")

def get_aviso_tipo(session):
    return _get_sap_field(session, RUTAS_SAP["aviso_tipo"],nombre_campo="Tipo de aviso")
    
def get_aviso_autor(session):
    return _get_sap_field(session, RUTAS_SAP["aviso_autor"],nombre_campo="Autor del aviso",caret_position=5)
    
def get_aviso_fecha(session):
    return _get_sap_field(session, RUTAS_SAP["aviso_fecha"],nombre_campo="Fecha del aviso",caret_position=5)
        
def get_aviso_servicio(session):
    return _get_sap_field(session, RUTAS_SAP["aviso_servicio"],nombre_campo="Tipo de aviso",caret_position=23)

def getter_care(session):
    return get_operaciones(session,"care")

def getter_came(session):
    return get_operaciones(session, "came")

def _es_fila_valida(texto):
    """Valida si una fila tiene contenido válido"""
    return texto.strip() and not texto.startswith("_")

def _calcular_anchos_tabla(headers, datos):
    """Calcula los anchos máximos para alineación"""
    anchos = [len(h) for h in headers]
    for fila in datos:
        for i, valor in enumerate(fila):
            anchos[i] = max(anchos[i], len(str(valor)))
    return anchos

def _crear_separador(anchos):
    """Crea separador de tabla"""
    return "+" + "+".join("-" * (a + 2) for a in anchos) + "+"

def _crear_header(headers, anchos):
    """Crea header de tabla"""
    return "|" + "|".join(f" {h.ljust(a)} " for h, a in zip(headers, anchos)) + "|"

def _crear_fila_tabla(valores, anchos):
    """Crea una fila de tabla"""
    return "|" + "|".join(f" {str(v).ljust(a)} " for v, a in zip(valores, anchos)) + "|"

def get_operaciones(session,orden):

    ltxa1_list = []
    orden_list = []
    row = 0

    # Mapeo de orden -> (campo,indice)
    config_orden = {
        "care": (ARBEI, 10),
        "came": (DAUNO, 13)
    }
    if orden not in config_orden:
        return ""
    
    campo,index = config_orden[orden]

    # Recopilar datos
    while True:
        try:
            ltxa1 = session.findById(f"{LTXA1}[7,{row}]").text
            valor = session.findById(f"{campo}[{index},{row}]").text
            if _es_fila_valida(ltxa1):
                ltxa1_list.append(ltxa1)
                orden_list.append(valor)
            row += 1
        except Exception:
            break

    # Si no hay datos, devolver string vacio
    if not ltxa1_list:
        return ""

    # Combinar y ordenar por Trabajo (alfabeticamente)
    combined_data = list(zip(ltxa1_list, orden_list))
    combined_data.sort(key=lambda x: x[0].lower())

    # Headers y columnas
    headers = ["TRABAJO", "CANTIDAD" if orden == "came" else "ITEMIZADO"]
    anchos = _calcular_anchos_tabla(headers, combined_data)

    result = [_crear_separador(anchos), _crear_header(headers, anchos), _crear_separador(anchos)]

    if orden == "came":
        # Agrupar por trabajo para subtotales
        from collections import defaultdict
        grouped_data = defaultdict(list)
        for trabajo, cantidad in combined_data:
            grouped_data[trabajo].append(cantidad)

        # Agregar datos agrupados con subtotales
        for trabajo in sorted(grouped_data.keys(), key=str.lower):
            cantidades = grouped_data[trabajo]

            # Primera fila del grupo
            result.append(_crear_fila_tabla([trabajo, cantidades[0]], anchos))

            # Filas adicionales del groupo(trabajo vacio)
            for cantidad in cantidades[1:]:
                result.append(_crear_fila_tabla(["", cantidad], anchos))

            # Calcular el subtotal numerico si las cantidades son numeros
            try:
                numeric = [float(c.replace(',', '.')) for c in cantidades if c.strip()]
                subtotal_text = f"Subtotal: {sum(numeric):.2f}"
            except (ValueError, TypeError):
                subtotal_text = f"Subtotal: {len(cantidades)} item(s)"

            result.append(_crear_separador(anchos))
            result.append(_crear_fila_tabla([subtotal_text, ""], anchos))
            result.append(_crear_separador(anchos))
    
    else: # orden == "care"
        for trabajo, itemizado in combined_data:
            result.append(_crear_fila_tabla([trabajo, itemizado], anchos))
        
        result.append(_crear_separador(anchos))
        
        # Calcular total general
        try:
            numeric = [float(v.replace(',', '.')) for _, v in combined_data if v.strip()]
            total_text = f"TOTAL GENERAL: {sum(numeric):.2f}"
        except (ValueError, TypeError):
            total_text = f"TOTAL GENERAL: {len(combined_data)} item(s)"
        
        result.append(_crear_fila_tabla([total_text, ""], anchos))
        result.append(_crear_separador(anchos))
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
        estrategia_usada = None
        
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

        if lineas_ordenadas:
            estrategia_usada = "Principal (scroll directo)"
        
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
            lineas_previas = len(lineas_ordenadas)
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

            if len(lineas_ordenadas) > lineas_previas:
                estrategia_usada = "Alternativa (firstVisibleRow)"
        
        # ESTRATEGIA DE RESPALDO: Acceso directo por índices
        if len(lineas_ordenadas) < 2:  # Si aún tenemos muy poco contenido
            lineas_previas = len(lineas_ordenadas)
            # Resetear tabla
            try:
                if hasattr(tabla, 'verticalScrollbar'):
                    tabla.verticalScrollbar.position = 0
            except:
                pass

            if len(lineas_ordenadas) > lineas_previas:
                estrategia_usada = "Respaldo (acceso directo)"
            
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
            print(f"[get_texto_largo_aviso] No se obtuvieron líneas")
            return None
        
        # Unir todas las líneas preservando saltos de línea
        texto_completo = "\n".join(lineas_ordenadas)
        print(f"[get_texto_largo_aviso] Estrategia exitosa: {estrategia_usada} | Líneas obtenidas: {len(lineas_ordenadas)}")
        return texto_completo if texto_completo.strip() else None
        
    except Exception as e:
        print(f"[get_texto_largo_aviso] Error general: {e}")
        return None





