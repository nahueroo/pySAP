import json


ARCHIVOS = {
    "came": "cames.json",
    "care": "cares.json",
    "aviso": "avisos.json",
}


def normalizar(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def cargar_datos():
    datos = {}

    for tipo, archivo in ARCHIVOS.items():
        with open(archivo, "r", encoding="utf-8") as f:
            datos[tipo] = json.load(f)

    return datos


def guardar_datos(datos):
    for tipo, archivo in ARCHIVOS.items():
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(datos[tipo], f, ensure_ascii=False, indent=4)


def vincular():
    datos = cargar_datos()

    cames = datos["came"]
    cares = datos["care"]
    avisos = datos["aviso"]

    # Índices para buscar rápidamente
    cares_por_orden = {
        normalizar(numero): care
        for numero, care in cares.items()
    }

    avisos_por_numero = {
        normalizar(numero): aviso
        for numero, aviso in avisos.items()
    }

    # CAME -> CARE
    for numero_came, came in cames.items():
        numero_care = normalizar(came.get("CARE Asociada"))

        if not numero_care:
            continue

        care = cares_por_orden.get(numero_care)

        if care is not None:
            care["CAME asociada"] = numero_came

    # CARE -> Aviso
    for numero_care, care in cares.items():
        numero_aviso = normalizar(care.get("Aviso asociado"))

        if not numero_aviso:
            continue

        aviso = avisos_por_numero.get(numero_aviso)

        if aviso is not None:
            aviso["CARE asociada"] = numero_care

            numero_came = normalizar(care.get("CAME asociada"))

            if numero_came:
                came = cames.get(numero_came)

                if came is not None:
                    came["Aviso asociado"] = numero_aviso
                    aviso["CAME asociada"] = numero_came

    guardar_datos(datos)

    print("Vinculación completada.")