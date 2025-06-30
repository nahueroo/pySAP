import win32com.client

try:
    def obtener_session_sap():
        SapGuiAuto  = win32com.client.GetObject("SAPGUI")
        application = SapGuiAuto.GetScriptingEngine
        connection = application.Children(0)
        session = connection.Children(0)
        return session
except:
    None