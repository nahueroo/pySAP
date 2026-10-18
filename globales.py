
datos = {
    "came": {},
    "care": {},
    "aviso": {}
}

came = {
    "Orden": None,
    "Texto Breve" : None,
    "Fecha creacion": None,
    "Puesto de trabajo": None,
    "Clase de actividad" : None,
    "Area de empresa": None,
    "Tiene foto": None,
    "Fecha inicio": None,
    "Fecha fin": None,
    "Ubicacion Tecnica" : None,
    "Descripcion Ubicacion Tecnica": None,
    "Status sistema": None,
    "Calle": None,
    "Fecha modificacion": None,
    "Modificado por": None,
    "Creado por": None,
    "operaciones": {
    },
    "CARE Asociada": None,
    "Aviso asociado": None,
}

care = {
    "Orden": None,
    "Clase de orden": None,
    "Fecha creacion": None,
    "Puesto de trabajo": None,
    "Grupo planificador": None,
    "Fecha inicio(care)": None,
    "Fecha fin": None,
    "Tiene foto": None,
    "Fin programado": None,
    "Area de empresa": None,
    "Ubicacion Tecnica": None,
    "Clase de actividad" : None,
    "Texto Breve": None,
    "Descripcion Ubicacion Tecnica": None,
    "Calle": None,
    "Fecha modificacion": None,
    "Modificado por": None,
    "Creado por": None,
    "Materialidad": None,
    "operaciones": {
    },
    "CAME asociada": None,
    "Aviso asociado": None,
}

aviso = {
    "Numero de aviso": None,
    "Area de empresa": None,
    "Autor del aviso": None,
    "Calle": None,
    "Canal": None,
    "Clase de aviso": None,
    "Clase Prioridad": None,
    "Codigo": None,
    "Fecha creacion": None,
    "Creado por": None,
    "Descripcion Ubicacion Tecnica": None,
    "Descripcion": None,
    "Fecha de aviso": None,
    "Fin deseado": None,
    "Grupo codigos": None,
    "Grupo planificacion": None,
    "Inicio averia": None,
    "Local": None,
    "Fecha modificacion": None,
    "Modificado por": None,
    "Cod.1": None,
    "Cod.2": None,
    "Direccion": None,
    "Prioridad": None,
    "Puesto de trabajo responsable": None,
    "Status usuario": None,
    "Status sistema": None,
    "Tipo": None,
    "Texto para prioridad": None,
    "Ubicacion Tecnica Afectada": None,
    "Servicio asociado": None,
    "CARE asociada": None,
    "CAME asociada": None,
    "Texto": [],
}

operaciones = {
    "KTSCH": "Clave de control",
    "STEUS": "Clave de control operacion",
    "VORNR": "Operacion",
    "LTXA1": "Texto breve operacion",
    "DAUNO": "Duracion normal",
    "ARBEI": "Trabajo",
    "USR00": "Largo", 
    "USR01": "Ancho",
    "USR02": "Profundidad",
    "UNIDAD_MEDIDA": "Unidad de Medida",
    "SLWID": "Forma",
}


# EQUIVALENCIAS
campos_ordenes = {
    "PM_SELECTED": "Seleccionado",
    "AUFNR": "Orden",
    "AUART": "Clase de orden",
    "ERDAT": "Fecha creacion",
    "KTEXT": "Texto Breve",
    "ADJUNTO": "Tiene foto",
    "GEWRK": "Puesto de trabajo",
    "INGPR": "Grupo planificador",
    "GSTRP": "Fecha inicio",
    "GLTRP": "Fecha fin",
    "TPLNR": "Ubicacion Tecnica",
    "PLTXT": "Descripcion Ubicacion Tecnica",
    "STREET": "Calle",
    "BEBER": "Area de empresa",
    "USTXT": "Status usuario",
    "STTXT": "Status sistema",
    "ILART": "Clase de actividad",
    "AEDAT": "Fecha modificacion",
    "AENAM": "Modificado por",
    "ERNAM": "Creado por",
}

campos_came = {
    **campos_ordenes,
    **operaciones,
    "LEAD_AUFNR": "CARE Asociada",
}

campos_care = {
    **campos_ordenes,
    **operaciones,
    "ADDAT": "Fecha inicio(care)",
    "GLTRS": "Fin programado",
    "QMNUM": "Aviso asociado",
    "ZZMATERIALIDAD": "Materialidad",
}

campos_aviso = {
    **campos_ordenes,
    "QMNAM": "Autor del aviso",
    "QMNUM": "Numero de aviso",
    "ZZCANAL": "Canal",
    "QMART": "Clase de aviso",
    "ARTPR": "Clase Prioridad",
    "QMCOD": "Codigo",
    "QMTXT": "Descripcion",
    "QMDAT": "Fecha de aviso",
    "LTRMN": "Fin deseado",
    "QMGRP": "Grupo codigos",
    "INGRP": "Grupo planificacion",
    "AUSVN": "Inicio averia",
    "MSGRP": "Local",
    "ADRNR": "Direccion",
    "PRIOK": "Prioridad",
    "ARBPL": "Puesto de trabajo responsable",
    "KTXTCD": "Cod.1",
    "KTXTGR": "Cod.2",
    "PRIOKX": "Texto para prioridad",
    "BTPLN": "Ubicacion Tecnica Afectada",
    "FETXT": "Servicio asociado",
}

equivalencias = {
    "aviso": campos_aviso,
    "care": campos_care,
    "came": campos_came,
}