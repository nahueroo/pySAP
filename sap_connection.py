import win32com.client

def obtener_session_sap():
    """Obtener sesion de SAP
    
    Returns: Objeto de sesion de SAP

    Exception: Captura errores de conexion
    """
    try:
        SapGuiAuto  = win32com.client.GetObject("SAPGUI")
        application = SapGuiAuto.GetScriptingEngine
        connection = application.Children(0)
        session = connection.Children(0)
        if session is None:
            print("Error: No se pudo obtener sesion SAP valida")
            return None
        
        return session
    
    except AttributeError as e:
        print(f"Error: SAP no esta abierto o no esta disponible: {e}")
        return None
    except IndexError as e:
        print(f"Error: No hay conexion o sesion activa: {e}")
        return None
    except Exception as e:
        print(f"Error inesperado al conectar con SAP: {e}")
        return None