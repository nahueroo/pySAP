import win32com.client
    
def get_textoBreve(session):
    ruta =  "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/" \
            "ssubSUB_LEVEL:SAPLCOIH:1100/" \
            "subSUB_KOPF:SAPLCOIH:1102/txtCAUFVD-KTEXT"
    try:
        return session.findById(ruta).text
    except Exception:
        return None
    
def get_gPlanificador(session):
    ruta =  "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/" \
            "ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/" \
            "ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/" \
            "ctxtCAUFVD-INGPR"
    try:
        return session.findById(ruta).text
    except Exception:
        return None

def get_claseActividad(session):
    ruta =  "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/" \
            "ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/" \
            "ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/" \
            "ctxtCAUFVD-ILART"
    try:
        return session.findById(ruta).text
    except Exception:
        return None
    
def get_care(session):
    ruta =  "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/" \
            "ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/" \
            "ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/" \
            "subMAINORDER:SAPLCOIH:0152/ctxtCAUFVD-MAUFNR"
    try:
        return session.findById(ruta).text
    except Exception:
        return None

def get_UT(session):
    ruta = (
        "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/"
        "ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/"
        "ssubSUB_AUFTRAG:SAPLCOIH:1120/subOBJECT:SAPLCOIH:7100/"
        "txtRIOT-PLTXT"
    )
    try:
        return session.findById(ruta).text
    except Exception:
        return None
    
def get_aviso(session):
    ruta =  "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/" \
            "ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/" \
            "ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/" \
            "txtCAUFVD-QMNUM"
    try:
        return session.findById(ruta).text
    except Exception:
        return None

def get_textoBreveCare(session):
    ruta =  "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/" \
            "ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/" \
            "ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/" \
            "subMAINORDER:SAPLCOIH:0152/txtCAUFVD_MOR-KTEXT"
    try:
        return session.findById(ruta).text
    except Exception:
        return None
    

def get_aviso_tipo(session):
    ruta = (
        "wnd[0]/usr/subSCREEN_1:SAPLIQS0:1050/"
        "subNOTIF_TYPE:SAPLIQS0:1051/ctxtVIQMEL-QMART"
    )
    try:
        return session.findById(ruta).text
    except Exception:
        return None
    
def get_aviso_autor(session):
    ruta =  r"wnd[0]/usr/tabsTAB_GROUP_10/tabp10\TAB01/ssubSUB_GROUP_10:SAPLIQS0:7235/" \
            r"subCUSTOM_SCREEN:SAPLIQS0:7212/subSUBSCREEN_1:SAPLIQS0:7326/ctxtVIQMEL-QMNAM"
    try:
        campo = session.findById(ruta)
        campo.setFocus()
        campo.caretPosition = 5
        # Si necesitas enviar sendVKey para activar algo, puedes hacerlo fuera del getter
        return campo.text
    except Exception as e:
        print(f"[ERROR] Nombre solicitante: {e}")
        return None
    
def get_aviso_fecha(session):
    ruta =  r"wnd[0]/usr/tabsTAB_GROUP_10/tabp10\TAB01/ssubSUB_GROUP_10:SAPLIQS0:7235/" \
            r"subCUSTOM_SCREEN:SAPLIQS0:7212/subSUBSCREEN_1:SAPLIQS0:7326/ctxtVIQMEL-QMDAT"
    try:
        campo = session.findById(ruta)
        campo.setFocus()
        campo.caretPosition = 5
        return campo.text
    except Exception as e:
        print(f"[ERROR] Fecha de notificación: {e}")
        return None
        
def get_aviso_servicio(session):
    ruta =  r"wnd[0]/usr/tabsTAB_GROUP_10/tabp10\TAB01/ssubSUB_GROUP_10:SAPLIQS0:7235/" \
            r"subCUSTOM_SCREEN:SAPLIQS0:7212/subSUBSCREEN_3:SAPLIQS0:7324/txtVIQMFE-FETXT"
    try:
        campo = session.findById(ruta)
        campo.setFocus()
        campo.caretPosition = 23
        return campo.text
    except Exception as e:
        print(f"[ERROR] Texto aviso: {e}")
        return None

def getter_care(session):
    """Obtiene todos los valores válidos de los campos LTXA1 y ARBEI de la operación actual."""
    ltxa1_list = []
    arbei_list = []
    row = 0
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
    return ltxa1_list, arbei_list

def getter_came(session):
    """Obtiene todos los valores válidos de los campos LTXA1 y DAUNO de la operación actual."""
    ltxa1_list = []
    dauno_list = []
    row = 0
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
    return ltxa1_list, dauno_list