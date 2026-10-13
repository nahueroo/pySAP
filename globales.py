
datos = {
    "cames": {},
    "cares": {},
    "avisos": {}
}

came = {
    "Orden": None,
    "Texto Breve" : None,
    "Fecha creacion": None,
    "Puesto de trabajo": None,
    "Clase de actividad" : None,
    "Área de empresa": None,
    "Fecha inicio": None,
    "Fecha fin": None,
    "Orden superior": None,
    "Ubicacion Tecnica" : None,
    "Descripción ubicación técnica": None,
    "Status sistema": None,
    "Calle": None,
    "Fecha modificación": None,
    "Modificado por": None,
    "operaciones": {}
}

care = {
    "Orden": None,
    "Clase de orden": None,
    "Fecha creación": None,
    "Aviso asociado": None,  # Aviso asociado
    "Puesto de trabajo": None,
    "Grupo planificador": None,
    "Fecha inicio(care)": None,
    "Fecha fin": None,
    "Fin programado": None,
    "Área de empresa": None,
    "Ubicación técnica": None,
    "Texto breve": None,
    "Descripción ubicación técnica": None,
    "Calle": None,
    "Fecha modificación": None,
    "Modificado por": None,
    "Creado por": None,
    "operaciones": {},
    "CAME asociada": None
}

aviso = {
    "Número de aviso": None,
    "Área de empresa": None,
    "Autor del aviso": None,
    "Calle": None,
    "Canal": None,
    "Clase de aviso": None,
    "Prioridad aviso": None,
    "Código": None,
    "Fecha creación": None,
    "Creado por": None,
    "Descripción ubicación técnica": None,
    "Descripción": None,
    "Fecha de aviso": None,
    "Fin deseado": None,
    "Grupo códigos": None,
    "Grupo planificación": None,
    "Inicio avería": None,
    "Local": None,
    "Fecha modificación": None,
    "Modificado por": None,
    "Dirección": None,
    "Objeto": None,
    "Orden CARE": None,
    "Prioridad": None,
    "Puesto de trabajo responsable": None,
    "Status usuario": None,
    "Status sistema": None,
    "Tipo": None,
    "Texto para prioridad": None,
    "Ubicación técnica afectada": None
}

operaciones = {
    "KTSCH": "Clave de control",
    "STEUS": "Clave de control operación",
    "VORNR": "Operación",
    "LTXA1": "Texto breve operación",
    "DAUNO": "Duración normal",
}


# EQUIVALENCIAS
campos_ordenes = {
    "PM_SELECTED": "Seleccionado",
    "AUFNR": "Orden",
    "AUART": "Clase de orden",
    "ERDAT": "Fecha creación",
    "KTEXT": "Texto breve",
    "LEAD_AUFNR": "Orden superior",
    "GEWRK": "Puesto de trabajo",
    "INGPR": "Grupo planificador",
    "GSTRP": "Fecha inicio",
    "ADDAT": "Fecha inicio(care)",
    "GLTRP": "Fecha fin",
    "TPLNR": "Ubicación técnica",
    "PLTXT": "Descripción ubicación técnica",
    "STREET": "Calle",
    "BEBER": "Área de empresa",
    "USTXT": "Status usuario",
    "STTXT": "Status sistema",
    "ILART": "Clase de actividad",
    "AEDAT": "Fecha modificación",
    "AENAM": "Modificado por",
    "ERNAM": "Creado por",
    "QMNUM": "Aviso asociado",
}

campos_aviso = {
    "QMNAM": "Autor del aviso",
    "QMNUM": "Número de aviso",
    "ZZCANAL": "Canal",
    "QMART": "Clase de aviso",
    "ARTPR": "Clase Prioridad",
    "QMCOD": "Código",
    "QMTXT": "Descripción",
    "QMDAT": "Fecha de aviso",
    "LTRMN": "Fin deseado",
    "QMGRP": "Grupo códigos",
    "INGRP": "Grupo planificación",
    "AUSVN": "Inicio avería",
    "MSGRP": "Local",
    "ADRNR": "Dirección",
    "OBJNR": "Objeto",
    "PRIOK": "Prioridad",
    "ARBPL": "Puesto de trabajo responsable",
    "KTXTCD": "Tipo",
    "PRIOKX": "Texto para prioridad",
    "BTPLN": "Ubicación técnica afectada",
}