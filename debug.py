from sap_connection import obtener_session_sap

def debug_ubicacion_tecnica(session):
    ruta =  "wnd[0]/usr/tabsTAB_GROUP_10/tabp10/TAB01/" \
            "ssubSUB_GROUP_10:SAPLIQS0:7235/subCUSTOM_SCREEN:SAPLIQS0:7212/" \
                "subSUBSCREEN_3:SAPLIQS0:7322/subOBJEKT:SAPLIWO1:0100/" \
            "ctxtRIWO1-TPLNR"
    try:
        campo = session.findById(ruta)
        print("Tipo:", campo.Type)
        print("ID:", campo.Id)
        print("Name:", campo.Name)
        print("ClassName:", campo.ClassName)
        print("Text:", getattr(campo, "Text", None))
        print("text:", getattr(campo, "text", None))
        print("Value:", getattr(campo, "Value", None))
        print("tooltip:", getattr(campo, "tooltip", None))
    except Exception as e:
        print(f"[ERROR] Debug Ubicación Técnica: {e}")
