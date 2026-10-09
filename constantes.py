import os

# Codigos de retorno

CONTINUE = 0
CANCEL = 1

# Teclas

ENTER = b'\r'
ESCAPE = b'\x1b'

# Nombres Pestañas
PESTANAS = ["image.html","data.pdf", "Microsoft Word"]

# Campos CARE y CAME

GRUPOPLANIFICACION = "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/ctxtCAUFVD-INGPR"
DATOSCABECERA = "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpIHKZ"

#Ambas usan LTXA1
LTXA1 = "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpVGUE/ssubSUB_AUFTRAG:SAPLCOVG:3010/tblSAPLCOVGTCTRL_3010/txtAFVGD-LTXA1"

#CAME usa DAUNO
DAUNO = "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpVGUE/ssubSUB_AUFTRAG:SAPLCOVG:3010/tblSAPLCOVGTCTRL_3010/txtAFVGD-DAUNO"

#CARE usa ARBEI
ARBEI = "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpVGUE/ssubSUB_AUFTRAG:SAPLCOVG:3010/tblSAPLCOVGTCTRL_3010/txtAFVGD-ARBEI"
MAUFNR = "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/subMAINORDER:SAPLCOIH:0152/ctxtCAUFVD-MAUFNR"
AVISO = "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/btnICON_NTF"

# BOTONES

F2 = 2
F3 = 3
SHIFTF3 = 15
GUARDAR = "wnd[0]/tbar[0]/btn[11]"


# RUTA_SAP_DESCARGAS = r"C:\Users\nahue\Documents\SAP\SAP GUI"
RUTA_SAP_DESCARGAS = os.path.join(
    os.path.expanduser("~"),
    "Documents",
    "SAP",
    "SAP Gui"
)

OPERTAB = "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE"

RUTAS_SAP = {

        "textoBreve": "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/" \
                        "ssubSUB_LEVEL:SAPLCOIH:1100/" \
                        "subSUB_KOPF:SAPLCOIH:1102/txtCAUFVD-KTEXT",
        "claseActividad":"wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/" \
                "ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/" \
                "ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/" \
                "ctxtCAUFVD-ILART",
        "UT": "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/"
                "ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/"
                "ssubSUB_AUFTRAG:SAPLCOIH:1120/subOBJECT:SAPLCOIH:7100/"
                "txtRIOT-PLTXT",
        "textoBreveCare": "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/" \
                "ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/" \
                "ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/" \
                "subMAINORDER:SAPLCOIH:0152/txtCAUFVD_MOR-KTEXT",
        "aviso_tipo": "wnd[0]/usr/subSCREEN_1:SAPLIQS0:1050/"\
        "subNOTIF_TYPE:SAPLIQS0:1051/ctxtVIQMEL-QMART", 
        "aviso_autor": r"wnd[0]/usr/tabsTAB_GROUP_10/tabp10\TAB01/ssubSUB_GROUP_10:SAPLIQS0:7235/" \
                r"subCUSTOM_SCREEN:SAPLIQS0:7212/subSUBSCREEN_1:SAPLIQS0:7326/ctxtVIQMEL-QMNAM",
        "aviso_fecha": r"wnd[0]/usr/tabsTAB_GROUP_10/tabp10\TAB01/ssubSUB_GROUP_10:SAPLIQS0:7235/" \
                r"subCUSTOM_SCREEN:SAPLIQS0:7212/subSUBSCREEN_1:SAPLIQS0:7326/ctxtVIQMEL-QMDAT",
        "aviso_servicio": r"wnd[0]/usr/tabsTAB_GROUP_10/tabp10\TAB01/ssubSUB_GROUP_10:SAPLIQS0:7235/" \
                r"subCUSTOM_SCREEN:SAPLIQS0:7212/subSUBSCREEN_3:SAPLIQS0:7324/txtVIQMFE-FETXT"
}