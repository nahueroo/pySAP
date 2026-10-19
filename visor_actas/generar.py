from __future__ import annotations

import html
import io
import json
import calendar
import math
import os
import re
import struct
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote


# ------------------------------------------------------------
# Rutas
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

AVISOS_FILE = BASE_DIR / "avisos.json"
CAMES_FILE = BASE_DIR / "cames.json"
CARES_FILE = BASE_DIR / "cares.json"
ACTA_DIR = BASE_DIR / "actas"
PRECIARIO_FILE = Path(__file__).resolve().parent / "Estimados.xlsx"
PRECIARIO_ITEMS: dict[str, str] = {}
ITEM_UNIDADES: dict[str, str] = {}

OUTPUT_DIR = Path(__file__).resolve().parent / "salida"
OUTPUT_FILE = OUTPUT_DIR / "index.html"
GEODATA_DIR = Path(__file__).resolve().parent / "datos_geograficos"
GEO_CACHE_FILE = GEODATA_DIR / "ubicaciones_enriquecidas.json"


# ------------------------------------------------------------
# Configuración
# ------------------------------------------------------------

EXTENSIONES_ACTA = {
    ".html",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
}


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------

def cargar_json(path: Path | None, nombre: str) -> dict:
    """Lee un archivo JSON UTF-8."""
    if path is None:
        print(f"Advertencia: {nombre} no cargado.")
        return {}
    if not path.exists():
        print(f"Advertencia: no existe {nombre}: {path}")
        return {}

    with path.open("r", encoding="utf-8") as archivo:
        contenido = json.load(archivo)

    if not isinstance(contenido, dict):
        print(f"Advertencia: {nombre} no contiene un objeto JSON.")
        return {}

    return contenido


def punto_en_poligono(x: float, y: float, puntos: list[tuple[float, float]]) -> bool:
    dentro = False
    for indice, (x1, y1) in enumerate(puntos):
        x2, y2 = puntos[indice - 1]
        cruza = (y1 > y) != (y2 > y)
        if cruza and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dentro = not dentro
    return dentro


def leer_poligonos_shp(path: Path) -> list[list[list[tuple[float, float]]]]:
    """Lee polígonos SHP sin agregar una dependencia geoespacial al visor."""
    poligonos = []
    with path.open("rb") as archivo:
        archivo.seek(100)
        while True:
            encabezado = archivo.read(8)
            if len(encabezado) < 8:
                break
            _, longitud = struct.unpack(">2i", encabezado)
            contenido = archivo.read(longitud * 2)
            if len(contenido) < 44:
                continue
            tipo = struct.unpack("<i", contenido[:4])[0]
            if tipo not in {5, 15, 25}:
                continue
            cantidad_partes, cantidad_puntos = struct.unpack(
                "<2i", contenido[36:44]
            )
            partes = list(struct.unpack(
                f"<{cantidad_partes}i",
                contenido[44:44 + cantidad_partes * 4],
            ))
            inicio_puntos = 44 + cantidad_partes * 4
            puntos = [
                struct.unpack("<2d", contenido[inicio_puntos + indice * 16:
                                                inicio_puntos + (indice + 1) * 16])
                for indice in range(cantidad_puntos)
            ]
            poligonos.append([
                puntos[inicio:fin]
                for inicio, fin in zip(
                    partes,
                    partes[1:] + [cantidad_puntos],
                )
            ])
    return poligonos


def leer_atributos_dbf(path: Path) -> list[dict[str, str]]:
    with path.open("rb") as archivo:
        encabezado = archivo.read(32)
        cantidad = struct.unpack("<I", encabezado[4:8])[0]
        largo_encabezado = struct.unpack("<H", encabezado[8:10])[0]
        largo_registro = struct.unpack("<H", encabezado[10:12])[0]
        campos = []
        for _ in range((largo_encabezado - 33) // 32):
            definicion = archivo.read(32)
            if definicion[0] == 0x0D:
                break
            campos.append((
                definicion[:11].split(b"\0", 1)[0].decode("latin-1"),
                definicion[16],
            ))
        archivo.seek(largo_encabezado)
        resultados = []
        for _ in range(cantidad):
            registro = archivo.read(largo_registro)
            if len(registro) < largo_registro or registro[0:1] == b"*":
                continue
            posicion = 1
            valores = {}
            for nombre, ancho in campos:
                valores[nombre] = registro[posicion:posicion + ancho].decode(
                    "latin-1"
                ).strip()
                posicion += ancho
            resultados.append(valores)
    return resultados


def cargar_barrios() -> list[tuple[str, list[list[tuple[float, float]]]]]:
    path = GEODATA_DIR / "barrios.geojson"
    if not path.exists():
        return []
    contenido = json.loads(path.read_text(encoding="utf-8"))
    barrios = []
    for feature in contenido.get("features", []):
        geometria = feature.get("geometry") or {}
        propiedades = feature.get("properties") or {}
        nombre = (
            propiedades.get("nombre")
            or propiedades.get("NOMBRE")
            or propiedades.get("barrio")
            or propiedades.get("BARRIO")
            or ""
        )
        coordenadas = geometria.get("coordinates", [])
        if geometria.get("type") == "Polygon":
            coordenadas = [coordenadas]
        for multipoligono in coordenadas:
            for poligono in multipoligono:
                if poligono:
                    barrios.append((str(nombre), [
                        (float(punto[0]), float(punto[1]))
                        for punto in poligono
                    ]))
    return barrios


def ubicar_en_barrio(
    longitud: float,
    latitud: float,
    barrios: list[tuple[str, list[list[tuple[float, float]]]]],
) -> str:
    for nombre, poligono in barrios:
        if punto_en_poligono(longitud, latitud, poligono):
            return nombre
    return ""


def medidas_poligono(
    poligonos: list[list[tuple[float, float]]],
    longitud: float,
    latitud: float,
) -> dict[str, float]:
    puntos = [punto for poligono in poligonos for punto in poligono]
    if not puntos:
        return {}
    escala_x = 111320 * max(0.1, abs(math.cos(math.radians(latitud))))
    escala_y = 110540
    puntos_metros = [
        ((x - longitud) * escala_x, (y - latitud) * escala_y)
        for x, y in puntos
    ]
    mejor_area = math.inf
    mejor_largo = 0.0
    mejor_ancho = 0.0
    aristas = []
    for poligono in poligonos:
        puntos_poligono = [
            ((x - longitud) * escala_x, (y - latitud) * escala_y)
            for x, y in poligono
        ]
        aristas.extend(zip(
            puntos_poligono,
            puntos_poligono[1:] + puntos_poligono[:1],
        ))
    for (x1, y1), (x2, y2) in aristas:
        vector_x = x2 - x1
        vector_y = y2 - y1
        norma = math.hypot(vector_x, vector_y)
        if norma == 0:
            continue
        unitario_x = vector_x / norma
        unitario_y = vector_y / norma
        perpendicular_x = -unitario_y
        perpendicular_y = unitario_x
        proyecciones_largo = [
            x * unitario_x + y * unitario_y
            for x, y in puntos_metros
        ]
        proyecciones_ancho = [
            x * perpendicular_x + y * perpendicular_y
            for x, y in puntos_metros
        ]
        largo = max(proyecciones_largo) - min(proyecciones_largo)
        ancho = max(proyecciones_ancho) - min(proyecciones_ancho)
        area = largo * ancho
        if area < mejor_area:
            mejor_area = area
            mejor_largo = largo
            mejor_ancho = ancho
    return {
        "largo_m": round(max(mejor_largo, mejor_ancho), 1),
        "ancho_m": round(min(mejor_largo, mejor_ancho), 1),
    }


def punto_medio_linea(coordenadas: list[list[float]]) -> tuple[float, float]:
    if not coordenadas:
        return 0.0, 0.0
    longitudes = []
    total = 0.0
    for primero, segundo in zip(coordenadas, coordenadas[1:]):
        distancia = (
            (segundo[0] - primero[0]) ** 2
            + (segundo[1] - primero[1]) ** 2
        ) ** 0.5
        longitudes.append(distancia)
        total += distancia
    objetivo = total / 2
    acumulado = 0.0
    for indice, distancia in enumerate(longitudes):
        if acumulado + distancia >= objetivo:
            proporcion = (
                (objetivo - acumulado) / distancia if distancia else 0
            )
            primero = coordenadas[indice]
            segundo = coordenadas[indice + 1]
            return (
                primero[0] + (segundo[0] - primero[0]) * proporcion,
                primero[1] + (segundo[1] - primero[1]) * proporcion,
            )
        acumulado += distancia
    return tuple(coordenadas[-1])


def punto_mas_cercano_linea(
    coordenadas: list[list[float]],
    longitud: float,
    latitud: float,
) -> tuple[float, float, float]:
    escala_x = 111320 * max(0.1, abs(math.cos(math.radians(latitud))))
    escala_y = 110540
    mejor = (0.0, 0.0, math.inf)
    for primero, segundo in zip(coordenadas, coordenadas[1:]):
        x1 = (primero[0] - longitud) * escala_x
        y1 = (primero[1] - latitud) * escala_y
        x2 = (segundo[0] - longitud) * escala_x
        y2 = (segundo[1] - latitud) * escala_y
        vector_x = x2 - x1
        vector_y = y2 - y1
        norma_cuadrada = vector_x * vector_x + vector_y * vector_y
        if norma_cuadrada == 0:
            continue
        proporcion = max(
            0.0,
            min(
                1.0,
                -(x1 * vector_x + y1 * vector_y) / norma_cuadrada,
            ),
        )
        punto_x = x1 + vector_x * proporcion
        punto_y = y1 + vector_y * proporcion
        distancia = math.hypot(punto_x, punto_y)
        if distancia < mejor[2]:
            mejor = (
                punto_x,
                punto_y,
                distancia,
            )
    return mejor


def ancho_de_cuadra(
    calle_objetivo: dict,
    calles: list[dict],
    longitud: float,
    latitud: float,
) -> float | None:
    geometria = calle_objetivo.get("geometry") or {}
    coordenadas = geometria.get("coordinates", [])
    if len(coordenadas) < 2:
        return None
    objetivo_x, objetivo_y, _ = punto_mas_cercano_linea(
        coordenadas,
        longitud,
        latitud,
    )
    candidatos = []
    propiedades_objetivo = calle_objetivo.get("properties") or {}
    codigo_objetivo = str(propiedades_objetivo.get("codigo", ""))
    for calle in calles:
        propiedades = calle.get("properties") or {}
        if str(propiedades.get("codigo", "")) == codigo_objetivo:
            continue
        linea = (calle.get("geometry") or {}).get("coordinates", [])
        if len(linea) < 2:
            continue
        punto_x, punto_y, distancia = punto_mas_cercano_linea(
            linea,
            longitud,
            latitud,
        )
        if distancia > 250:
            continue
        for primero, segundo in zip(coordenadas, coordenadas[1:]):
            x1 = (primero[0] - longitud) * 111320 * max(
                0.1, abs(math.cos(math.radians(latitud)))
            )
            y1 = (primero[1] - latitud) * 110540
            x2 = (segundo[0] - longitud) * 111320 * max(
                0.1, abs(math.cos(math.radians(latitud)))
            )
            y2 = (segundo[1] - latitud) * 110540
            if math.hypot(x2 - x1, y2 - y1) > 0:
                tangente = math.atan2(y2 - y1, x2 - x1)
                break
        else:
            continue
        for primero, segundo in zip(linea, linea[1:]):
            dx = (segundo[0] - primero[0]) * 111320 * max(
                0.1, abs(math.cos(math.radians(latitud)))
            )
            dy = (segundo[1] - primero[1]) * 110540
            if math.hypot(dx, dy) > 0:
                angulo = math.atan2(dy, dx)
                diferencia = abs(math.atan2(
                    math.sin(angulo - tangente),
                    math.cos(angulo - tangente),
                ))
                if diferencia > math.pi / 2:
                    diferencia = math.pi - diferencia
                if diferencia <= math.radians(20):
                    break
        else:
            continue
        desplazamiento_x = punto_x - objetivo_x
        desplazamiento_y = punto_y - objetivo_y
        normal = -math.sin(tangente) * desplazamiento_x + math.cos(
            tangente
        ) * desplazamiento_y
        candidatos.append((normal, distancia))
    positivos = min(
        (valor for valor in candidatos if valor[0] > 0),
        key=lambda valor: valor[0],
        default=None,
    )
    negativos = max(
        (valor for valor in candidatos if valor[0] < 0),
        key=lambda valor: valor[0],
        default=None,
    )
    if positivos is None or negativos is None:
        return None
    return round(positivos[0] - negativos[0], 1)


def calles_entre(
    calle_objetivo: dict,
    calles: list[dict],
    longitud: float,
    latitud: float,
) -> list[str]:
    coordenadas = (calle_objetivo.get("geometry") or {}).get(
        "coordinates",
        [],
    )
    if len(coordenadas) < 2:
        return []
    objetivo_x, objetivo_y, _ = punto_mas_cercano_linea(
        coordenadas, longitud, latitud
    )
    tangente = None
    escala_x = 111320 * max(0.1, abs(math.cos(math.radians(latitud))))
    for primero, segundo in zip(coordenadas, coordenadas[1:]):
        dx = (segundo[0] - primero[0]) * escala_x
        dy = (segundo[1] - primero[1]) * 110540
        if math.hypot(dx, dy) > 0:
            tangente = math.atan2(dy, dx)
            break
    if tangente is None:
        return []
    codigo_objetivo = str(
        (calle_objetivo.get("properties") or {}).get("codigo", "")
    )
    candidatos = []
    for calle in calles:
        propiedades = calle.get("properties") or {}
        if str(propiedades.get("codigo", "")) == codigo_objetivo:
            continue
        linea = (calle.get("geometry") or {}).get("coordinates", [])
        if len(linea) < 2:
            continue
        punto_x, punto_y, distancia = punto_mas_cercano_linea(
            linea, longitud, latitud
        )
        if distancia > 250:
            continue
        perpendicular = False
        for primero, segundo in zip(linea, linea[1:]):
            dx = (segundo[0] - primero[0]) * escala_x
            dy = (segundo[1] - primero[1]) * 110540
            if math.hypot(dx, dy) > 0:
                angulo = math.atan2(dy, dx)
                diferencia = abs(math.atan2(
                    math.sin(angulo - tangente),
                    math.cos(angulo - tangente),
                ))
                diferencia = min(diferencia, math.pi - diferencia)
                perpendicular = abs(
                    diferencia - math.pi / 2
                ) <= math.radians(25)
                break
        if not perpendicular:
            continue
        posicion = (
            (punto_x - objetivo_x) * math.cos(tangente)
            + (punto_y - objetivo_y) * math.sin(tangente)
        )
        nombre = str(
            propiedades.get("nomoficial")
            or propiedades.get("nom_mapa")
            or ""
        ).strip()
        if nombre:
            candidatos.append((posicion, nombre))
    por_nombre = {}
    for posicion, nombre in candidatos:
        anterior = por_nombre.get(nombre)
        if anterior is None or abs(posicion) < abs(anterior):
            por_nombre[nombre] = posicion
    positivos = min(
        (
            (posicion, nombre)
            for nombre, posicion in por_nombre.items()
            if posicion > 0
        ),
        key=lambda candidato: candidato[0],
        default=None,
    )
    negativos = max(
        (
            (posicion, nombre)
            for nombre, posicion in por_nombre.items()
            if posicion < 0
        ),
        key=lambda candidato: candidato[0],
        default=None,
    )
    return [
        candidato[1]
        for candidato in (negativos, positivos)
        if candidato is not None
    ]


def ancho_entre_bordes_manzana(
    calle_objetivo: dict,
    poligonos: list[list[list[tuple[float, float]]]],
    longitud: float,
    latitud: float,
) -> float | None:
    coordenadas = (calle_objetivo.get("geometry") or {}).get(
        "coordinates",
        [],
    )
    if len(coordenadas) < 2:
        return None
    escala_x = 111320 * max(0.1, abs(math.cos(math.radians(latitud))))
    escala_y = 110540
    referencia = punto_mas_cercano_linea(
        coordenadas,
        longitud,
        latitud,
    )
    objetivo_x, objetivo_y = referencia[:2]
    tangente = None
    for primero, segundo in zip(coordenadas, coordenadas[1:]):
        vector_x = (segundo[0] - primero[0]) * escala_x
        vector_y = (segundo[1] - primero[1]) * escala_y
        if math.hypot(vector_x, vector_y) > 0:
            tangente = math.atan2(vector_y, vector_x)
            break
    if tangente is None:
        return None
    normal_x = -math.sin(tangente)
    normal_y = math.cos(tangente)
    candidatos: list[tuple[float, float]] = []
    for poligono in poligonos:
        puntos = [
            ((x - longitud) * escala_x, (y - latitud) * escala_y)
            for parte in poligono
            for x, y in parte
        ]
        if not puntos:
            continue
        proyecciones_normales = [
            (x - objetivo_x) * normal_x + (y - objetivo_y) * normal_y
            for x, y in puntos
        ]
        proyecciones_tangentes = [
            (x - objetivo_x) * math.cos(tangente)
            + (y - objetivo_y) * math.sin(tangente)
            for x, y in puntos
        ]
        if (
            max(proyecciones_tangentes) < -180
            or min(proyecciones_tangentes) > 180
        ):
            continue
        minimo = min(proyecciones_normales)
        maximo = max(proyecciones_normales)
        if minimo > 0:
            candidatos.append((minimo, 1))
        elif maximo < 0:
            candidatos.append((maximo, -1))
    positivos = [
        distancia for distancia, lado in candidatos if lado == 1
    ]
    negativos = [
        distancia for distancia, lado in candidatos if lado == -1
    ]
    if not positivos or not negativos:
        return None
    return round(min(positivos) - max(negativos), 1)


def cargar_datos_geograficos(
    descripciones: dict[str, str],
    direcciones_exactas: set[str] | None = None,
) -> dict[str, dict]:
    if not GEODATA_DIR.exists():
        return {}
    cache = {}
    if GEO_CACHE_FILE.exists():
        try:
            cache = json.loads(GEO_CACHE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache = {}
    direcciones_exactas = direcciones_exactas or set()
    claves_direcciones = {
        f"direccion:{direccion}": direccion
        for direccion in direcciones_exactas
        if direccion
    }
    claves_requeridas = set(descripciones) | set(claves_direcciones)
    faltantes = [
        clave for clave in claves_requeridas
        if not cache.get(clave)
    ]
    if faltantes:
        print(
            f"Advertencia: {len(faltantes)} ubicación(es) no están en la "
            "caché local; se omite el cálculo geográfico para acelerar la "
            "generación."
        )
    return {
        clave: cache[clave]
        for clave in claves_requeridas
        if clave in cache
    }

    # El procesamiento de GeoJSON/SHP queda reservado para una actualización
    # manual de la caché y no debe ejecutarse durante la generación normal.
    calles_path = GEODATA_DIR / "calles.geojson"
    if calles_path.exists():
        calles = json.loads(calles_path.read_text(encoding="utf-8"))
        por_codigo = {}
        for feature in calles.get("features", []):
            propiedades = feature.get("properties") or {}
            codigo = str(propiedades.get("codigo", ""))
            if codigo:
                por_codigo.setdefault(codigo, []).append(feature)
        calles_objetivo = {}
        shp = GEODATA_DIR / "manzanas" / "manzanas_catastrales.shp"
        poligonos = leer_poligonos_shp(shp) if shp.exists() else []
        for descripcion in descripciones:
            dato = cache.get(descripcion)
            if not dato:
                continue
            if descripcion.startswith("direccion:"):
                continue
            codigo_match = re.search(
                r"-([A-Z]+)-(\d+)-(\d+)-",
                descripciones.get(descripcion, ""),
                flags=re.IGNORECASE,
            )
            if not codigo_match:
                continue
            opciones = por_codigo.get(codigo_match.group(2), [])
            if not opciones:
                continue
            rango = re.search(r"\s(\d+)-(\d+)", descripcion)
            altura = (
                (int(rango.group(1)) + int(rango.group(2))) / 2
                if rango else None
            )
            if altura is not None:
                ajustadas = [
                    opcion for opcion in opciones
                    if any(
                        minimo <= altura <= maximo
                        for minimo, maximo in (
                            (
                                min(
                                    float(opcion.get("properties", {}).get(
                                        "alt_izqini", 0
                                    ) or 0
                                ), float(opcion.get("properties", {}).get(
                                        "alt_izqfin", 0
                                    ) or 0
                                )),
                                max(
                                    float(opcion.get("properties", {}).get(
                                        "alt_izqini", 0
                                    ) or 0
                                ), float(opcion.get("properties", {}).get(
                                        "alt_izqfin", 0
                                    ) or 0
                                )),
                            ),
                            (
                                min(
                                    float(opcion.get("properties", {}).get(
                                        "alt_derini", 0
                                    ) or 0
                                ), float(opcion.get("properties", {}).get(
                                        "alt_derfin", 0
                                    ) or 0
                                )),
                                max(
                                    float(opcion.get("properties", {}).get(
                                        "alt_derini", 0
                                    ) or 0
                                ), float(opcion.get("properties", {}).get(
                                        "alt_derfin", 0
                                    ) or 0
                                )),
                            ),
                        )
                    )
                ]
                if ajustadas:
                    opciones = ajustadas
            coordenadas = (
                opciones[0].get("geometry", {}).get("coordinates", [])
            )
            longitud, latitud = punto_medio_linea(coordenadas)
            propiedades = opciones[0].get("properties") or {}
            rango = re.search(r"\s(\d+)-(\d+)", descripcion)
            dato.update({
                "direccion_normalizada": descripcion,
                "calle": propiedades.get("nomoficial", ""),
                "altura": round((
                    int(rango.group(1)) + int(rango.group(2))
                ) / 2) if rango else "",
                "longitud": longitud,
                "latitud": latitud,
                "barrio": propiedades.get("barrio", ""),
            })
            calles_objetivo[descripcion] = opciones[0]
        for descripcion, calle_objetivo in calles_objetivo.items():
            dato = cache[descripcion]
            dato["ancho_cuadra_m"] = ancho_de_cuadra(
                calle_objetivo,
                calles.get("features", []),
                dato["longitud"],
                dato["latitud"],
            )
            dato["ancho_bordes_manzana_m"] = ancho_entre_bordes_manzana(
                calle_objetivo,
                poligonos,
                dato["longitud"],
                dato["latitud"],
            )
            dato["entre_calles"] = calles_entre(
                calle_objetivo,
                calles.get("features", []),
                dato["longitud"],
                dato["latitud"],
            )
    barrios = cargar_barrios()
    for clave in claves_requeridas:
        dato = cache.get(clave)
        if not dato:
            continue
        if not dato or "longitud" not in dato:
            continue
        longitud = dato["longitud"]
        latitud = dato["latitud"]
        puntos_prueba = [
            (longitud + delta_x, latitud + delta_y)
            for delta_x, delta_y in (
                (0, 0), (0.00015, 0), (-0.00015, 0),
                (0, 0.00015), (0, -0.00015),
            )
        ]
        for poligono in poligonos:
            if any(
                punto_en_poligono(punto_x, punto_y, parte)
                for punto_x, punto_y in puntos_prueba
                for parte in poligono
            ):
                dato.update(medidas_poligono(poligono, longitud, latitud))
                break
        dato["barrio"] = dato.get("barrio") or ubicar_en_barrio(
            longitud,
            latitud,
            barrios,
        )
        dato["mapa_url"] = (
            "https://mapa.buenosaires.gob.ar/comollego/?"
            f"lat={latitud}&lng={longitud}&zl=17&modo=transporte"
        )
        dato["streetview_url"] = (
            "https://www.google.com/maps/@?api=1&map_action=pano&"
            f"viewpoint={latitud},{longitud}"
        )
        dato["google_maps_url"] = (
            "https://www.google.com/maps/search/?api=1&query="
            f"{latitud},{longitud}"
        )
    GEO_CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return cache


def cargar_preciario(path: Path) -> dict[tuple[str, str], float]:
    """Lee precios de Preciario indexados por clave y puesto de trabajo."""
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de precios: {path}")

    namespace = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    }
    relaciones_namespace = (
        "http://schemas.openxmlformats.org/officeDocument/2006/"
        "relationships"
    )

    with zipfile.ZipFile(path) as archivo:
        shared_root = ET.fromstring(archivo.read("xl/sharedStrings.xml"))
        shared_strings = [
            "".join(element.text or "" for element in item.iter(
                f"{{{namespace['m']}}}t"
            ))
            for item in shared_root.findall("m:si", namespace)
        ]
        workbook = ET.fromstring(archivo.read("xl/workbook.xml"))
        relaciones = ET.fromstring(
            archivo.read("xl/_rels/workbook.xml.rels")
        )
        destinos = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relaciones
        }
        hoja = next(
            item for item in workbook.find("m:sheets", namespace)
            if item.attrib["name"].lower() == "preciario"
        )
        relacion_id = hoja.attrib[f"{{{relaciones_namespace}}}id"]
        ruta_hoja = "xl/" + destinos[relacion_id].lstrip("/")
        sheet = ET.fromstring(archivo.read(ruta_hoja))

    filas = sheet.findall(".//m:sheetData/m:row", namespace)
    if not filas:
        return {}

    def valor_celda(celda: ET.Element) -> str:
        valor = celda.find("m:v", namespace)
        if valor is None or valor.text is None:
            return ""
        contenido = valor.text
        if celda.attrib.get("t") == "s":
            return shared_strings[int(contenido)]
        return contenido

    encabezados: dict[int, str] = {}
    precios: dict[tuple[str, str], float] = {}
    for celda in filas[0].findall("m:c", namespace):
        referencia = celda.attrib.get("r", "")
        columna = re.match(r"([A-Z]+)", referencia)
        if columna:
            numero_columna = 0
            for letra in columna.group(1):
                numero_columna = numero_columna * 26 + ord(letra) - 64
            encabezados[numero_columna] = valor_celda(celda).strip()

    puestos = {
        numero: encabezado
        for numero, encabezado in encabezados.items()
        if numero >= 5 and encabezado
    }
    for fila in filas[1:]:
        valores = {}
        for celda in fila.findall("m:c", namespace):
            referencia = celda.attrib.get("r", "")
            columna = re.match(r"([A-Z]+)", referencia)
            if columna:
                numero_columna = 0
                for letra in columna.group(1):
                    numero_columna = numero_columna * 26 + ord(letra) - 64
                valores[numero_columna] = valor_celda(celda).strip()
        clave = normalizar(valores.get(4, ""))
        if not clave:
            continue
        PRECIARIO_ITEMS[clave] = valores.get(1, "")
        for numero, puesto in puestos.items():
            precio = numero_decimal(valores.get(numero, ""))
            if precio is not None:
                precios[(clave, normalizar(puesto))] = precio
    return precios


def item_preciario(clave: object) -> str:
    return PRECIARIO_ITEMS.get(normalizar(clave), "")


def codigo_item(item: object) -> str:
    coincidencia = re.match(r"\s*(\d+(?:\.\d+)+)", str(item))
    return coincidencia.group(1) if coincidencia else ""


def resumen_comparacion_fotos(came: dict) -> str:
    resumen: dict[tuple[str, str], dict[str, float]] = {}
    operaciones = came.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return ""

    for operacion in operaciones.values():
        if not isinstance(operacion, dict):
            continue
        clave = operacion.get("Clave de control", "")
        item = item_preciario(clave) or texto_breve_operacion(
            operacion.get("Texto breve operacion", "")
        )
        if not item:
            continue
        unidad = texto(
            operacion.get("Unidad de Medida") or campo_operacion(
                operacion,
                "Unidad de medida",
                "Unidad medida",
                "Unidad",
            ),
            "",
        )
        clave = (item, unidad)
        valores = resumen.setdefault(clave, {"cantidad": 0, "duracion": 0})
        valores["cantidad"] += 1
        duracion = numero_decimal(operacion.get("Duracion normal"))
        if duracion is not None:
            valores["duracion"] += duracion

    formato = " | ".join(
        f"{mostrar_numero(valores['cantidad'])} - "
        f"{mostrar_numero(valores['duracion'])} - "
        f"{unidad or '-'} - {item}"
        for (item, unidad), valores in resumen.items()
    )
    return formato


GRUPOS_ITEMS_COMPARABLES = (
    {
        "10.2",
        "6.2",
        "6.3",
        "4.2.2",
        "4.2.1",
        "4.21",
        "4.1.2",
        "4.1.1",
        "4.3.2",
        "4.3.1",
    },
    {"7.1", "7.2"},
)


def grupo_item_comparable(item: object) -> set[str] | None:
    codigo = codigo_item(item)
    for grupo in GRUPOS_ITEMS_COMPARABLES:
        if codigo in grupo:
            return grupo
    if codigo == "4.21":
        return next(
            grupo
            for grupo in GRUPOS_ITEMS_COMPARABLES
            if "4.2.1" in grupo
        )
    return None


def opciones_comparacion(
    clave_actual: object,
    puesto_came: str,
    precios: dict[tuple[str, str], float] | None,
) -> str:
    grupo = grupo_item_comparable(item_preciario(clave_actual))
    if grupo is None:
        return ""
    claves = sorted(
        (
            clave
            for clave, puesto in (precios or {})
            if puesto == normalizar(puesto_came)
            and clave != normalizar(clave_actual)
            and codigo_item(item_preciario(clave)) in grupo
        ),
        key=str.lower,
    )
    return "".join(
        f'<option value="{esc(mostrar_numero(precios[(clave, normalizar(puesto_came))]), "")}" '
        f'data-unidad="{esc(ITEM_UNIDADES.get(codigo_item(item_preciario(clave)), ""), "")}">'
        f'{esc(item_preciario(clave) or clave)}</option>'
        for clave in claves
    )


def texto(valor: object, valor_default: str = "-") -> str:
    """Convierte un valor a texto visible."""
    if valor is None:
        return valor_default

    if isinstance(valor, list):
        return ", ".join(str(item) for item in valor)

    if isinstance(valor, dict):
        return ", ".join(
            f"{clave}: {valor_item}"
            for clave, valor_item in valor.items()
        )

    resultado = str(valor).strip()
    return resultado or valor_default


def sufijo_puesto(valor: object) -> str:
    """Extrae el tramo de zona comparable, por ejemplo 2_Z12."""
    puesto = valor_real(valor).upper()
    coincidencia = re.search(r"(\d+)[_-](Z\d+)\s*$", puesto)
    if coincidencia is None:
        return puesto
    return f"{coincidencia.group(1)}_{coincidencia.group(2)}"


def es_cero_numerico(valor: object) -> bool:
    """Indica si un valor numérico representa exactamente cero."""
    contenido = valor_real(valor).replace(" ", "").replace(",", ".")
    if not contenido:
        return False
    try:
        return float(contenido) == 0
    except ValueError:
        return False


def numero_decimal(valor: object) -> float | None:
    contenido = valor_real(valor).replace(" ", "").replace(",", ".")
    if not contenido:
        return None
    try:
        return float(contenido)
    except ValueError:
        return None


def normalizar_numero_texto(valor: object) -> str:
    """Normaliza decimales visibles sin alterar textos no numéricos."""
    contenido = texto(valor, "")
    if not contenido:
        return ""
    candidato = contenido.strip().replace(",", ".")
    if re.fullmatch(r"-?(?:\d+|\d*\.\d+)", candidato):
        if candidato.startswith("-."):
            return "-0" + candidato[1:]
        if candidato.startswith("."):
            return "0" + candidato
        return candidato
    return contenido


def separador_decimal_valido(valor: object, requiere_coma: bool = False) -> bool:
    """Valida el separador decimal original de un valor numérico."""
    contenido = valor_real(valor).strip()
    if not contenido or not re.search(r"[.,]", contenido):
        return True
    tiene_coma = "," in contenido
    tiene_punto = "." in contenido
    if tiene_coma and tiene_punto:
        return False
    return tiene_coma == requiere_coma


def separadores_decimales_operacion_validos(operacion: dict) -> bool:
    """Valida coma en duración y, para M2, también en profundidad."""
    unidad = campo_operacion(
        operacion,
        "Unidad de Medida",
        "Unidad de medida",
        "Unidad medida",
        "Unidad",
    )
    es_m2 = normalizar(unidad) == "m2"
    campos_generales = (
        ("Duracion normal", True),
        ("Trabajo", False),
        ("Largo", False),
        ("Longitud", False),
        ("Ancho", False),
    )
    for campo, requiere_coma in campos_generales:
        if not separador_decimal_valido(
            campo_operacion(operacion, campo),
            requiere_coma,
        ):
            return False
    profundidad = campo_operacion(operacion, "Profundidad")
    return separador_decimal_valido(profundidad, es_m2)


def cantidad_operacion(
    largo: object,
    ancho: object,
    profundidad: object,
    unidad: object,
) -> float | None:
    unidad_normalizada = normalizar(unidad)
    largo_numero = numero_decimal(largo)
    ancho_numero = numero_decimal(ancho)
    profundidad_numero = numero_decimal(profundidad)
    if largo_numero is None or ancho_numero is None:
        return None
    if unidad_normalizada == "m2":
        return largo_numero * ancho_numero
    if unidad_normalizada == "m3":
        if profundidad_numero is None:
            return None
        return largo_numero * ancho_numero * profundidad_numero
    if unidad_normalizada in {"toneladas", "ton", "tn"}:
        if profundidad_numero is None:
            return None
        return largo_numero * ancho_numero * profundidad_numero * 0.24
    return None


def mostrar_numero(valor: float | None) -> str:
    if valor is None:
        return "-"
    return f"{valor:.2f}".rstrip("0").rstrip(".")


def mostrar_moneda(valor: float | None) -> str:
    """Formatea importes con separadores argentinos."""
    if valor is None:
        return "-"
    contenido = f"{valor:,.2f}"
    return "$ " + contenido.replace(",", "X").replace(".", ",").replace("X", ".")


def coincide_duracion_normal(
    cantidad: float | None,
    duracion: object,
    precio_unitario: float | None,
) -> str:
    duracion_numero = numero_decimal(duracion)
    if (
        cantidad is None
        or duracion_numero is None
        or precio_unitario is None
    ):
        return "-"
    monto_calculo = cantidad * precio_unitario
    monto_duracion = duracion_numero * precio_unitario
    tolerancia = abs(precio_unitario) * 0.5
    return (
        "Sí"
        if abs(monto_calculo - monto_duracion) <= tolerancia
        else "No"
    )


def tiene_duracion_normal_cero(orden: dict) -> bool:
    """Detecta operaciones con duración normal igual a cero."""
    operaciones = orden.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return False
    return any(
        isinstance(operacion, dict)
        and es_cero_numerico(operacion.get("Duracion normal"))
        for operacion in operaciones.values()
    )


def totales_montos_came(
    orden: dict,
    puesto_came: str,
    precios: dict[tuple[str, str], float] | None,
) -> tuple[float | None, float | None]:
    operaciones = orden.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return None, None

    total_sap = 0.0
    total_estimado = 0.0
    tiene_sap = False
    tiene_estimado = False
    for operacion in operaciones.values():
        if not isinstance(operacion, dict):
            continue
        clave = operacion.get("Clave de control", "")
        precio = (precios or {}).get(
            (normalizar(clave), normalizar(puesto_came))
        )
        duracion = numero_decimal(
            operacion.get("Duracion normal") or ""
        )
        cantidad = cantidad_operacion(
            operacion.get("Largo") or campo_operacion(
                operacion, "Largo", "Longitud"
            ),
            operacion.get("Ancho") or campo_operacion(operacion, "Ancho"),
            operacion.get("Profundidad") or campo_operacion(
                operacion, "Profundidad"
            ),
            operacion.get("Unidad de Medida") or campo_operacion(
                operacion,
                "Unidad de medida",
                "Unidad medida",
                "Unidad",
            ),
        )
        if precio is None:
            continue
        if duracion is not None:
            total_sap += duracion * precio
            tiene_sap = True
        if cantidad is not None:
            total_estimado += cantidad * precio
            tiene_estimado = True
    return (
        total_sap if tiene_sap else None,
        total_estimado if tiene_estimado else None,
    )


def montos_came_coinciden(
    orden: dict,
    puesto_came: str,
    precios: dict[tuple[str, str], float] | None,
) -> bool:
    operaciones = orden.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return True

    for operacion in operaciones.values():
        if not isinstance(operacion, dict):
            continue
        clave = operacion.get("Clave de control", "")
        precio = (precios or {}).get(
            (normalizar(clave), normalizar(puesto_came))
        )
        cantidad = cantidad_operacion(
            operacion.get("Largo") or campo_operacion(
                operacion, "Largo", "Longitud"
            ),
            operacion.get("Ancho") or campo_operacion(operacion, "Ancho"),
            operacion.get("Profundidad") or campo_operacion(
                operacion, "Profundidad"
            ),
            operacion.get("Unidad de Medida") or campo_operacion(
                operacion,
                "Unidad de medida",
                "Unidad medida",
                "Unidad",
            ),
        )
        if (
            coincide_duracion_normal(
                cantidad,
                operacion.get("Duracion normal") or "",
                precio,
            )
            == "No"
        ):
            return False
    return True


def tiene_duracion_por_debajo_del_umbral(
    orden: dict,
    umbral: float,
) -> bool:
    operaciones = orden.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return False
    duraciones = [
        numero_decimal(operacion.get("Duracion normal"))
        for operacion in operaciones.values()
        if isinstance(operacion, dict)
    ]
    duraciones_validas = [
        duracion for duracion in duraciones if duracion is not None
    ]
    return not any(duracion > umbral for duracion in duraciones_validas)


def tiene_ancho_por_encima_del_umbral(
    orden: dict,
    umbral: float,
) -> bool:
    operaciones = orden.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return False
    return any(
        isinstance(operacion, dict)
        and (
            (ancho := numero_decimal(campo_operacion(operacion, "Ancho")))
            is not None
            and ancho > umbral
        )
        for operacion in operaciones.values()
    )


def faltan_items_g11(orden: dict) -> bool:
    operaciones = orden.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return True
    items = {
        normalizar(item_preciario(operacion.get("Clave de control", "")))
        for operacion in operaciones.values()
        if isinstance(operacion, dict)
    }
    return not bool({codigo_item(item) for item in items} & {"7.1", "7.2"})


def tiene_items_problematicos(orden: dict) -> bool:
    operaciones = orden.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return False

    items_presentes: set[str] = set()
    operaciones_por_item: dict[str, list[dict]] = {}
    for operacion in operaciones.values():
        if not isinstance(operacion, dict):
            continue
        item = codigo_item(item_preciario(operacion.get("Clave de control", "")))
        if not item:
            continue
        items_presentes.add(item)
        operaciones_por_item.setdefault(item, []).append(operacion)

    if "10.2" in items_presentes and items_presentes & {
        "6.2", "6.3", "3.3.2", "11.5"
    }:
        return True

    for operacion in operaciones_por_item.get("10.2", []):
        profundidad = numero_decimal(
            campo_operacion(operacion, "Profundidad")
        )
        if (profundidad or 0) > 0.15:
            return True

    for item in {"6.1.1", "6.1.2", "6.2", "6.3"}:
        for operacion in operaciones_por_item.get(item, []):
            largo = numero_decimal(campo_operacion(operacion, "Largo", "Longitud"))
            ancho = numero_decimal(campo_operacion(operacion, "Ancho"))
            if largo is not None and ancho is not None and largo * ancho > 20:
                return True
    if tiene_ancho_por_encima_del_umbral(orden, 7.5):
        return True
    return False


def detalles_items_problematicos(orden: dict) -> list[str]:
    operaciones = orden.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return []
    detalles = []
    for operacion in operaciones.values():
        if not isinstance(operacion, dict):
            continue
        item = codigo_item(item_preciario(operacion.get("Clave de control", "")))
        profundidad = numero_decimal(
            campo_operacion(operacion, "Profundidad")
        )
        if item == "10.2" and profundidad is not None and profundidad > 0.15:
            detalles.append(
                f"El ítem 10.2 tiene profundidad {mostrar_numero(profundidad)}, "
                "mayor al máximo permitido de 0.15."
            )
        ancho = numero_decimal(campo_operacion(operacion, "Ancho"))
        if ancho is not None and ancho > 7.5:
            detalles.append(
                f"El ítem {item or 'sin código'} tiene ancho "
                f"{mostrar_numero(ancho)}, mayor al máximo permitido de 7.5."
            )
    return detalles


def tiene_items_7_fuera_de_g11(orden: dict, clase: str) -> bool:
    if normalizar(clase) == "g11":
        return False
    operaciones = orden.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return False
    return any(
        codigo_item(item_preciario(operacion.get("Clave de control", "")))
        in {"7.1", "7.2"}
        for operacion in operaciones.values()
        if isinstance(operacion, dict)
    )


def items_materialidad_validos(orden: dict, materialidad: str) -> bool:
    permitidos = {
        "adoquin": {"4.1.1", "4.1.2", "6.1.1", "6.1.2"},
        "hormigon": {"4.2.1", "4.2.2", "6.3"},
        "asfalto": {"6.2", "10.2"},
        "intertrabado": {"11.5"},
    }
    materialidad_normalizada = normalizar(materialidad)
    if materialidad_normalizada in {"adoquin", "adoquines"}:
        materialidad_normalizada = "adoquin"
    items = {
        codigo_item(item_preciario(operacion.get("Clave de control", "")))
        for operacion in (orden.get("operaciones", {}) or {}).values()
        if isinstance(operacion, dict)
    }
    for materialidad_item, items_permitidos in permitidos.items():
        if (
            items & items_permitidos
            and materialidad_normalizada != materialidad_item
        ):
            return False
    return True


def correspondencia_items_valida(orden: dict, clase: str) -> bool:
    correspondencias = {
        "g02": {"6.1.1", "6.1.2", "6.2", "6.3"},
        "g01": {"10.2"},
        "g11": {"7.1", "7.2"},
    }
    clase_normalizada = normalizar(clase)
    items = {
        codigo_item(item_preciario(operacion.get("Clave de control", "")))
        for operacion in (orden.get("operaciones", {}) or {}).values()
        if isinstance(operacion, dict)
    }
    for clase_item, items_permitidos in correspondencias.items():
        if clase_normalizada != clase_item and items & items_permitidos:
            return False
    return True


def total_superficie_m2(orden: dict) -> float:
    operaciones = orden.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return 0.0
    return sum(
        cantidad_operacion(
            operacion.get("Largo") or campo_operacion(
                operacion, "Largo", "Longitud"
            ),
            operacion.get("Ancho") or campo_operacion(operacion, "Ancho"),
            operacion.get("Profundidad") or campo_operacion(
                operacion, "Profundidad"
            ),
            operacion.get("Unidad de Medida") or campo_operacion(
                operacion,
                "Unidad de medida",
                "Unidad medida",
                "Unidad",
            ),
        ) or 0.0
        for operacion in operaciones.values()
        if isinstance(operacion, dict)
        and normalizar(
            operacion.get("Unidad de Medida") or campo_operacion(
                operacion, "Unidad de medida", "Unidad medida", "Unidad"
            )
        ) == "m2"
    )


ERROR_TIPOS = (
    ("acta", "Número de acta faltante"),
    ("clase", "Clase de Actividad"),
    ("servicio", "Servicio G02"),
    ("fecha", "Fecha creación invalida"),
    ("fecha_formato", "Fecha inicio/fin fuera de período"),
    ("fechas_iguales", "Fechas inicio/fin no uniformes"),
    ("texto_correlativo", "Textos breves no correlativos"),
    ("separadores_decimales", "Separadores decimales incorrectos"),
    ("foto", "Fotos existentes"),
    ("duracion", "Valores en 0"),
    ("montos", "Monto estimado no coincidente"),
    ("duracion_g13", "Duración G13 no supera 12"),
    ("duracion_g05", "Duración G05 no supera 100"),
    ("items_g11", "G11 sin ítems 7.1 o 7.2"),
    ("items_7_fuera_g11", "Ítems 7.1/7.2 fuera de G11"),
    ("check", "Check"),
    ("ut", "UT Invalida"),
    ("items_problematicos", "Items incompatibles"),
    ("materialidad", "Materialidad"),
    ("correspondencia", "Correspondencia de ítems"),
    ("itemizado_care", "Itemizado Care"),
)


def esc(valor: object, valor_default: str = "-") -> str:
    """Escapa texto para insertarlo en HTML."""
    return html.escape(texto(valor, valor_default))


def valor_real(valor: object) -> str:
    """Devuelve un valor comparable vacío cuando no hay dato."""
    resultado = texto(valor, "")
    return "" if resultado == "-" else resultado


def campo_operacion(operacion: dict, *nombres: str) -> object:
    """Obtiene un campo de operación tolerando variantes de escritura."""
    claves = {
        normalizar(clave): valor
        for clave, valor in operacion.items()
    }
    for nombre in nombres:
        nombre_normalizado = normalizar(nombre)
        valor = claves.get(nombre_normalizado)
        if valor not in (None, ""):
            return valor
        for clave, valor in claves.items():
            if nombre_normalizado in clave and valor not in (None, ""):
                return valor
    return ""


def tiene_foto(orden: dict) -> bool:
    """Reconoce las marcas SAP que indican que la orden tiene foto."""
    marca = valor_real(orden.get("Tiene foto")).lower()
    return "anexo" in marca and "sap" in marca


def normalizar(valor: object) -> str:
    """
    Normaliza un texto para comparar IDs y nombres de archivos.

    Por ejemplo:
    S00213689/26 -> s0021368926
    """
    return re.sub(r"[^a-z0-9]", "", texto(valor, "").lower())


def numero_acta(texto_breve: object) -> tuple[float, str]:
    """Extrae el número final del Texto Breve para ordenar las actas."""
    valor = texto(texto_breve, "")
    coincidencia = re.search(r"(\d+)\s*$", valor)

    if coincidencia is None:
        return (float("inf"), valor.lower())

    return (int(coincidencia.group(1)), valor.lower())


def identificador_acta(texto_breve: object) -> str:
    coincidencia = re.search(
        r"acta[_\s-]*(\d+)",
        texto(texto_breve, ""),
        re.IGNORECASE,
    )
    return coincidencia.group(1) if coincidencia else ""


def fecha_orden(valor: object) -> tuple[int, int, int] | None:
    coincidencia = re.fullmatch(
        r"\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*",
        texto(valor, ""),
    )
    if coincidencia is None:
        return None
    dia, mes, anio = (int(parte) for parte in coincidencia.groups())
    return (anio, mes, dia)


def fecha_inicio_valida(valor: object) -> bool:
    fecha = fecha_orden(valor)
    return bool(fecha and fecha[2] == 1 and 1 <= fecha[1] <= 12)


def fecha_fin_valida(valor: object) -> bool:
    fecha = fecha_orden(valor)
    return bool(
        fecha
        and 1 <= fecha[1] <= 12
        and fecha[2] == calendar.monthrange(fecha[0], fecha[1])[1]
    )


def ruta_archivo_relativa(archivo: Path) -> str:
    """Genera una ruta válida desde salida/index.html hacia actas."""
    relativa = os.path.relpath(archivo, OUTPUT_DIR)
    return quote(Path(relativa).as_posix())


def listar_archivos_acta() -> list[Path]:
    """Busca archivos de CAME, CARE o AVISO dentro de las carpetas de actas."""
    if not ACTA_DIR.exists():
        print(f"Advertencia: no existe la carpeta de actas: {ACTA_DIR}")
        return []

    return sorted(
        (
            archivo
            for archivo in ACTA_DIR.rglob("*")
            if archivo.is_file()
            and archivo.suffix.lower() in EXTENSIONES_ACTA
            and any(
                palabra in archivo.name.lower()
                for palabra in ("came", "care", "aviso")
            )
        ),
        key=lambda archivo: (
            archivo.parent.name.lower(),
            archivo.name.lower(),
        ),
    )


def buscar_archivos_acta(
    archivos: list[Path],
    texto_breve: str,
) -> list[Path]:
    """Busca archivos en la carpeta cuyo nombre coincide con el Texto Breve."""
    texto_breve_normalizado = normalizar(texto_breve)

    if not texto_breve_normalizado:
        return []

    carpetas = {
        archivo.parent
        for archivo in archivos
        if (
            texto_breve_normalizado in normalizar(archivo.parent.name)
            or normalizar(archivo.parent.name) in texto_breve_normalizado
        )
    }

    return [
        archivo
        for archivo in archivos
        if archivo.parent in carpetas
    ]


def mostrar_campo(label: str, valor: object) -> str:
    return f"""
        <div class="campo">
            <span class="campo-label">{html.escape(label)}</span>
            <span class="campo-valor">{esc(valor)}</span>
        </div>
    """


def mostrar_texto_aviso(aviso: dict) -> str:
    textos = aviso.get("Texto", [])

    if not isinstance(textos, list):
        textos = [textos]

    elementos = []

    for item in textos:
        elementos.append(f"<li>{esc(item)}</li>")

    if not elementos:
        return "<p class=\"sin-datos\">Sin texto registrado</p>"

    return f"""
        <ul class="texto-aviso">
            {"".join(elementos)}
        </ul>
    """


def resumen_operaciones_care(care: dict) -> tuple[str, str]:
    operaciones = care.get("operaciones", {})
    if not isinstance(operaciones, dict):
        return "-", "0"

    items = []
    total_trabajo = 0.0
    for operacion in operaciones.values():
        if not isinstance(operacion, dict):
            continue
        item = item_preciario(operacion.get("Clave de control", ""))
        if item and item not in items:
            items.append(item)
        trabajo = numero_decimal(operacion.get("Trabajo"))
        if trabajo is not None:
            total_trabajo += trabajo

    return ", ".join(items) or "-", mostrar_numero(total_trabajo)


def texto_breve_operacion(valor: object) -> str:
    coincidencia = re.match(
        r"^\s*(\d+(?:\.\d+)+|\d+)(?=\s|[_-–—:]|$)",
        str(valor or ""),
    )
    return coincidencia.group(1) if coincidencia else str(valor or "").strip()


def ubicacion_tecnica_corta(valor: object) -> str:
    resultado = texto(valor, "").strip()
    return re.sub(
        r"\s+(?:ACERA|VEREDA|CALZADA)?\s*(?:PAR|IMPAR|IMP)?\s*$",
        "",
        resultado,
        flags=re.IGNORECASE,
    )


def mostrar_operaciones(
    orden: dict,
    tipo: str,
    puesto_came: str = "",
    precios: dict[tuple[str, str], float] | None = None,
) -> str:
    operaciones = orden.get("operaciones", {})

    if not isinstance(operaciones, dict) or not operaciones:
        return f"""
            <div class="sin-datos">
                No hay operaciones registradas para {html.escape(tipo)}.
            </div>
        """

    filas = []
    filtros = {
        "clave": set(),
        "control": set(),
        "duracion": set(),
        "unidad": set(),
    }
    es_came = tipo.upper() == "CAME"
    total_monto_sap, total_monto_estimado = (
        totales_montos_came(orden, puesto_came, precios)
        if es_came
        else (None, None)
    )
    mostrar_monto_estimado = (
        not es_came
        or (
            total_monto_sap is not None
            and total_monto_estimado is not None
            and not montos_came_coinciden(orden, puesto_came, precios)
        )
    )
    for numero, operacion in operaciones.items():
        if not isinstance(operacion, dict):
            continue

        clave = operacion.get("Clave de control", "")
        texto_breve = texto_breve_operacion(
            operacion.get("Texto breve operacion", "")
        )
        duracion = normalizar_numero_texto(
            operacion.get("Duracion normal") or ""
        )
        trabajo = normalizar_numero_texto(operacion.get("Trabajo") or "")
        largo = normalizar_numero_texto(
            operacion.get("Largo") or campo_operacion(
            operacion, "Largo", "Longitud"
            )
        )
        ancho = normalizar_numero_texto(
            operacion.get("Ancho") or campo_operacion(
            operacion, "Ancho"
            )
        )
        profundidad = normalizar_numero_texto(
            operacion.get("Profundidad") or campo_operacion(
            operacion, "Profundidad"
            )
        )
        unidad = operacion.get("Unidad de Medida") or campo_operacion(
            operacion,
            "Unidad de medida",
            "Unidad medida",
            "Unidad",
        )
        cantidad = cantidad_operacion(largo, ancho, profundidad, unidad)
        control = operacion.get("Clave de control operacion", "")
        trabajo_numero = numero_decimal(trabajo)
        superficie = (
            numero_decimal(largo) * numero_decimal(ancho)
            if numero_decimal(largo) is not None
            and numero_decimal(ancho) is not None
            else None
        )
        precio_unitario = (
            (precios or {}).get(
                (normalizar(clave), normalizar(puesto_came))
            )
        )
        coincide = coincide_duracion_normal(
            cantidad,
            duracion,
            precio_unitario,
        )
        monto_duracion = (
            numero_decimal(duracion) * precio_unitario
            if precio_unitario is not None and numero_decimal(duracion) is not None
            else None
        )
        monto_calculo = (
            cantidad * precio_unitario
            if precio_unitario is not None and cantidad is not None
            else None
        )
        monto_estimado = (
            trabajo_numero * precio_unitario
            if not es_came
            and trabajo_numero is not None
            and precio_unitario is not None
            else monto_calculo
        )
        monto_estimado_visible = monto_estimado
        item = item_preciario(clave)
        comparacion_habilitada = (
            es_came and grupo_item_comparable(item) is not None
        )
        opciones_profundidad = "".join(
            f'<option value="{valor}">{valor}</option>'
            for valor in ("0.08", "0.1", "0.15", "0.2")
        )
        comparador = (
            f'<select class="comparador-clave">'
            f'<option value="">Comparar con ítem</option>'
            f'{opciones_comparacion(clave, puesto_came, precios)}'
            f'</select>'
            f'<select class="profundidad-comparacion" '
            f'title="Profundidad para el cálculo en toneladas" '
            f'style="display: none;">'
            f'<option value="0.1" selected>0.10</option>'
            f'{opciones_profundidad}'
            f'</select>'
            if comparacion_habilitada else ""
        )
        for nombre, valor in (
            ("clave", clave),
            ("control", control),
            ("duracion", duracion if es_came else trabajo),
            ("unidad", unidad),
        ):
            if str(valor).strip():
                filtros[nombre].add(str(valor).strip())
        filas.append(f"""
            <tr
                data-operacion="{esc(numero, '')}"
                data-clave="{esc(clave, '')}"
                data-control="{esc(control, '')}"
                data-texto="{esc(texto_breve, '')}"
                data-duracion="{esc(duracion, '')}"
                data-trabajo="{esc(trabajo, '')}"
                data-superficie="{esc(mostrar_numero(superficie), '')}"
                data-largo="{esc(largo, '')}"
                data-ancho="{esc(ancho, '')}"
                data-profundidad="{esc(profundidad, '')}"
                data-unidad="{esc(unidad, '')}"
                data-cantidad="{esc(mostrar_numero(cantidad), '')}"
                data-precio="{esc(mostrar_numero(precio_unitario), '')}"
                data-monto-sap="{esc(mostrar_numero(monto_duracion), '')}"
                data-monto-estimado="{esc(mostrar_numero(monto_estimado_visible), '')}"
                data-duracion-numero="{esc(mostrar_numero(numero_decimal(duracion)), '')}"
                data-precio-actual="{esc(mostrar_numero(precio_unitario), '')}"
                data-largo-numero="{esc(mostrar_numero(numero_decimal(largo)), '')}"
                data-ancho-numero="{esc(mostrar_numero(numero_decimal(ancho)), '')}"
                data-unidad-normalizada="{esc(normalizar(unidad), '')}"
            >
                <td class="{"columna-importante" if es_came else ""}">{esc(numero)}</td>
                {f'<td>{esc(clave)}</td>' if not es_came else ""}
                <td class="{"columna-importante" if es_came else ""}">{esc(texto_breve)}</td>
                {f'<td class="columna-importante">{esc(duracion)}</td><td>{esc(mostrar_numero(superficie))}</td><td>{esc(largo)}</td><td>{esc(ancho)}</td><td>{esc(profundidad)}</td><td>{esc(unidad)}</td><td>{esc(mostrar_numero(cantidad))}</td><td>{esc(coincide)}</td><td>{esc(mostrar_moneda(precio_unitario))}</td><td>{esc(mostrar_moneda(monto_duracion))}</td>{f"<td>{esc(mostrar_moneda(monto_estimado_visible))}</td>" if mostrar_monto_estimado else ""}<td>{comparador}</td><td class="total-comparado">{"-" if comparacion_habilitada else ""}</td><td class="diferencia-clave">{"-" if comparacion_habilitada else ""}</td>' if es_came else f'<td>{esc(item)}</td><td>{esc(trabajo)}</td><td>{esc(mostrar_moneda(precio_unitario))}</td><td>{esc(mostrar_moneda(monto_estimado))}</td>'}
            </tr>
        """)

    return f"""
        <div class="operaciones-controles">
            {"".join(
                f'<select class="filtro-operaciones" data-filtro="{nombre}"><option value="">{etiqueta}</option>'
                + "".join(
                    f'<option value="{esc(valor, "")}">{esc(valor)}</option>'
                    for valor in sorted(valores, key=str.lower)
                )
                + '</select>'
                for nombre, etiqueta, valores in (
                    ("clave", "Clave de control", filtros["clave"]),
                    *(
                        [
                        ]
                        if not es_came
                        else []
                    ),
                    ("duracion" if es_came else "trabajo", "Duración normal" if es_came else "Trabajo", filtros["duracion"]),
                    ("unidad", "Unidad", filtros["unidad"]),
                )
            )}
            <span>Ordená haciendo clic en los encabezados.</span>
        </div>
        <div class="tabla-scroll">
            <table class="operaciones-tabla">
                <thead>
                    <tr>
                        <th class="{"columna-importante" if es_came else ""}"><button class="orden-columna" data-columna="operacion">
                            Operación
                        </button></th>
                        {(
                            '<th><button class="orden-columna" data-columna="clave">Clave de control</button></th>'
                            if not es_came
                            else ""
                        )}
                        <th class="{"columna-importante" if es_came else ""}"><button class="orden-columna" data-columna="texto">
                            Texto breve
                        </button></th>
                        {(
                            '<th class="columna-importante">Duración normal</th><th>Superficie</th><th>Largo</th><th>Ancho</th><th>Profundidad</th><th>Unidad</th><th>Cálculo</th><th>Coincide duración</th><th>Precio unitario</th><th>Monto SAP</th>'
                            + ('<th>Monto estimado</th>' if mostrar_monto_estimado else '')
                            + '<th>Comparar ítem</th><th>Total comparado</th><th>Diferencia</th>'
                            if es_came
                            else '<th>Ítem</th><th>Trabajo</th><th>Precio unitario</th><th>Monto estimado</th>'
                        )}
                    </tr>
                </thead>
                <tbody>
                    {"".join(filas)}
                </tbody>
                <tfoot>
                    <tr>
                        <th colspan="{2 if es_came else 3}">Totales visibles</th>
                        {(
                            '<th class="total-duracion">0</th><th colspan="8"></th><th class="total-monto-sap">-</th>'
                            + ('<th class="total-monto-estimado">-</th>' if mostrar_monto_estimado else '')
                            + '<th colspan="3"></th>'
                            if es_came
                            else '<th></th><th class="total-trabajo">0</th><th></th><th class="total-monto-estimado">-</th>'
                        )}
                    </tr>
                </tfoot>
            </table>
        </div>
    """


def mostrar_archivos_acta(archivos: list[Path], titulo: str) -> str:
    if not archivos:
        return f"""
            <div class="sin-fotos">
                No se encontraron archivos de {html.escape(titulo)} asociados.
            </div>
        """

    elementos = []

    for archivo in archivos:
        ruta = ruta_archivo_relativa(archivo)
        nombre = esc(archivo.name)
        extension = archivo.suffix.lower()

        if extension == ".html":
            elementos.append(f"""
                <div class="documento-acta">
                    <div class="documento-titulo">{nombre}</div>
                    <iframe src="{ruta}" title="{nombre}" loading="eager"></iframe>
                    <a href="{ruta}" target="_blank">Abrir archivo completo</a>
                </div>
            """)
        elif extension in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            elementos.append(f"""
                <a class="foto" href="{ruta}" target="_blank">
                    <img src="{ruta}" alt="{nombre}" loading="lazy">
                    <span>{nombre}</span>
                </a>
            """)
        elif extension == ".pdf":
            elementos.append(f"""
                <div class="documento-acta documento-pdf">
                    <div class="documento-titulo">{nombre}</div>
                    <iframe src="{ruta}" title="{nombre}" loading="eager"></iframe>
                    <a href="{ruta}" target="_blank">Abrir PDF completo</a>
                </div>
            """)

    return f"""
        <h4>{html.escape(titulo)}</h4>
        <div class="archivos-acta">
            {"".join(elementos)}
        </div>
    """


def mostrar_todas_operaciones_came(
    cames: dict,
    cares: dict,
    avisos: dict,
    precios: dict[tuple[str, str], float] | None = None,
) -> str:
    filas = []
    campos_filtro = {
        "acta": set(),
        "texto-breve": set(),
        "item": set(),
        "clave-control": set(),
        "duracion": set(),
        "largo": set(),
        "ancho": set(),
        "profundidad": set(),
        "unidad": set(),
        "coincide": set(),
        "monto-sap": set(),
        "materialidad": set(),
        "clase-actividad": set(),
        "servicio": set(),
    }

    for came_id, came in cames.items():
        operaciones = came.get("operaciones", {})
        if not isinstance(operaciones, dict):
            continue

        for numero, operacion in operaciones.items():
            if not isinstance(operacion, dict):
                continue

            largo = normalizar_numero_texto(operacion.get("Largo", ""))
            ancho = normalizar_numero_texto(operacion.get("Ancho", ""))
            profundidad = normalizar_numero_texto(
                operacion.get("Profundidad", "")
            )
            unidad = operacion.get("Unidad de Medida", "")
            duracion = normalizar_numero_texto(
                operacion.get("Duracion normal", "")
            )
            cantidad = cantidad_operacion(
                largo,
                ancho,
                profundidad,
                unidad,
            )
            puesto_came = valor_real(came.get("Puesto de trabajo"))
            precio_unitario = (precios or {}).get(
                (
                    normalizar(operacion.get("Clave de control", "")),
                    normalizar(puesto_came),
                )
            )
            coincide = coincide_duracion_normal(
                cantidad,
                duracion,
                precio_unitario,
            )
            monto_duracion = (
                numero_decimal(duracion) * precio_unitario
                if precio_unitario is not None
                and numero_decimal(duracion) is not None
                else None
            )
            monto_calculo = (
                cantidad * precio_unitario
                if precio_unitario is not None and cantidad is not None
                else None
            )
            area = came.get("Area de empresa", "")
            clase = came.get("Clase de actividad", "")
            acta = identificador_acta(came.get("Texto Breve", ""))
            care_id = str(
                came.get("CARE Asociada")
                or came.get("CARE asociada")
                or ""
            )
            aviso_id = str(
                came.get("Aviso asociado")
                or came.get("Aviso Asociado")
                or ""
            )
            care = cares.get(care_id, {})
            aviso = avisos.get(aviso_id, {})
            materialidad = (
                texto(care.get("Materialidad"), "")
                if isinstance(care, dict) else ""
            )
            servicio = (
                texto(aviso.get("Servicio asociado"), "")
                if isinstance(aviso, dict) else ""
            )
            servicio = re.sub(r"\s*:\s*\d+\s*$", "", servicio).strip()
            clave_control = operacion.get("Clave de control", "")
            item = item_preciario(clave_control)
            control = operacion.get("Clave de control operacion", "")
            valores_filtro = {
                "acta": acta,
                "texto-breve": came.get("Texto Breve", ""),
                "item": item,
                "clave-control": clave_control,
                "duracion": duracion,
                "largo": largo,
                "ancho": ancho,
                "profundidad": profundidad,
                "unidad": unidad,
                "coincide": coincide,
                "monto-sap": mostrar_moneda(monto_duracion),
                "materialidad": materialidad,
                "clase-actividad": clase,
                "servicio": servicio,
            }
            for campo, valor in valores_filtro.items():
                if str(valor).strip():
                    campos_filtro[campo].add(str(valor).strip())
            filas.append(f"""
                <tr data-acta="{esc(acta, '')}"
                    data-texto-breve="{esc(came.get("Texto Breve"), '')}"
                    data-item="{esc(item, '')}"
                    data-area="{esc(area, '')}"
                    data-clase="{esc(clase, '')}"
                    data-unidad="{esc(unidad, '')}"
                    data-largo="{esc(largo, '')}"
                    data-ancho="{esc(ancho, '')}"
                    data-profundidad="{esc(profundidad, '')}"
                    data-clave-control="{esc(clave_control, '')}"
                    data-duracion="{esc(duracion, '')}"
                    data-coincide="{esc(coincide, '')}"
                    data-precio-unitario="{esc(mostrar_moneda(precio_unitario), '')}"
                    data-monto-sap="{esc(mostrar_moneda(monto_duracion), '')}"
                    data-materialidad="{esc(materialidad, '')}"
                    data-clase-actividad="{esc(clase, '')}"
                    data-servicio="{esc(servicio, '')}">
                    <td>{esc(acta)}</td>
                    <td>{esc(came.get("Texto Breve"))}</td>
                    <td>{esc(item)}</td>
                    <td>{esc(duracion)}</td>
                    <td>{esc(largo)}</td>
                    <td>{esc(ancho)}</td>
                    <td>{esc(profundidad)}</td>
                    <td>{esc(unidad)}</td>
                    <td>{esc(coincide)}</td>
                    <td>{esc(mostrar_moneda(monto_duracion))}</td>
                </tr>
            """)

    columnas_globales = (
        ("acta", "Acta", True),
        ("texto-breve", "Texto breve", False),
        ("item", "Item", True),
        ("duracion", "Duración normal", False),
        ("largo", "Largo", False),
        ("ancho", "Ancho", False),
        ("profundidad", "Profundidad", True),
        ("unidad", "Unidad", True),
        ("coincide", "Coincide duración", True),
        ("monto-sap", "Monto SAP", False),
    )
    encabezados_globales = []
    for campo, etiqueta, filtrable in columnas_globales:
        campo_filtro = campo
        contenido_filtro = ""
        if filtrable:
            opciones = "".join(
                f'<option value="{esc(valor, "")}">{esc(valor)}</option>'
                for valor in sorted(
                    campos_filtro[campo],
                    key=str.lower,
                )
            )
            contenido_filtro = (
                f'<select class="filtro-columna" data-campo="{campo}">'
                f'<option value="">Todos</option>{opciones}</select>'
            )
        encabezados_globales.append(
            f'<th><button class="orden-global" data-campo="{campo_filtro}">'
            f'{etiqueta}</button>{contenido_filtro}</th>'
        )

    return f"""
        <section class="seccion operaciones-globales">
            <h2>Operaciones de todas las cames</h2>
            <div class="operaciones-controles">
                {"".join(
                    f'<select class="filtro-extra" data-campo="{campo}">'
                    f'<option value="">{etiqueta}</option>'
                    + "".join(
                        f'<option value="{esc(valor, "")}">{esc(valor)}</option>'
                        for valor in sorted(campos_filtro[campo], key=str.lower)
                    )
                    + "</select>"
                    for campo, etiqueta in (
                        ("clave-control", "Clave de control"),
                        ("materialidad", "Materialidad CARE"),
                        ("clase-actividad", "Clase de actividad"),
                        ("servicio", "Servicio asociado"),
                    )
                )}
            </div>
            <div class="tabla-scroll">
                <table id="tabla-operaciones-global" class="operaciones-tabla">
                    <thead>
                        <tr>
                            {"".join(encabezados_globales)}
                        </tr>
                    </thead>
                    <tbody>{"".join(filas)}</tbody>
                    <tfoot>
                        <tr>
                            <th colspan="3">Subtotales visibles</th>
                            <th data-subtotal="duracion">-</th>
                            <th data-subtotal="largo">-</th>
                            <th data-subtotal="ancho">-</th>
                            <th data-subtotal="profundidad">-</th>
                            <th></th>
                            <th></th>
                            <th data-subtotal="monto-sap">-</th>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </section>
    """


def generar_archivo_operaciones(
    cames: dict,
    cares: dict,
    avisos: dict,
    precios: dict[tuple[str, str], float],
) -> str:
    contenido = mostrar_todas_operaciones_came(cames, cares, avisos, precios)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Operaciones de todas las CAME</title>
    <style>
        body {{
            margin: 0;
            padding: 24px;
            color: #172033;
            background: #eef2f7;
            font-family: Arial, Helvetica, sans-serif;
        }}
        .contenedor {{
            width: min(1800px, 100%);
            margin: 0 auto;
        }}
        .operaciones-globales {{
            padding: 24px;
            background: white;
            border: 1px solid #dbe3ef;
            border-radius: 18px;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.09);
        }}
        .operaciones-globales h2 {{
            margin-top: 0;
            color: #1e3a8a;
        }}
        .operaciones-controles {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 16px;
        }}
        select {{
            min-height: 40px;
            padding: 0 12px;
            border: 1px solid #dbe3ef;
            border-radius: 8px;
            font: inherit;
        }}
        .tabla-scroll {{
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th, td {{
            padding: 10px;
            border-bottom: 1px solid #dbe3ef;
            text-align: left;
            vertical-align: top;
            white-space: nowrap;
        }}
        th {{
            color: #1e3a8a;
            background: #eef4ff;
        }}
        .operaciones-globales th {{
            min-width: 120px;
        }}
        .orden-global {{
            display: inline;
            min-height: 0;
            padding: 0;
            color: inherit;
            border: 0;
            background: transparent;
            font: inherit;
            font-weight: 700;
            cursor: pointer;
        }}
        .orden-global::after {{
            content: " \\2195";
            color: #607089;
            font-size: 12px;
        }}
        .filtro-columna {{
            display: block;
            width: 100%;
            min-height: 28px;
            margin-top: 6px;
            padding: 2px 6px;
            font-size: 11px;
        }}
    </style>
</head>
<body>
    <main class="contenedor">
        {contenido}
    </main>
    <script>
        const tabla = document.getElementById("tabla-operaciones-global");
        const filtros = Array.from(
            tabla.closest("section").querySelectorAll(".filtro-columna")
        );
        const filtrosExtra = Array.from(
            tabla.closest("section").querySelectorAll(".filtro-extra")
        );
        const numero = (valor) => {{
            const original = String(valor || "").trim();
            const texto = original.includes("$")
                ? original.replace("$", "").replace(/[.]/g, "").replace(",", ".")
                : original.replace(",", ".");
            const resultado = parseFloat(texto.replace(/[^0-9.-]/g, ""));
            return Number.isNaN(resultado) ? 0 : resultado;
        }};
        const formatoNumero = (valor) =>
            valor.toLocaleString("es-AR", {{ maximumFractionDigits: 2 }});
        const formatoMoneda = (valor) =>
            valor.toLocaleString("es-AR", {{
                style: "currency",
                currency: "ARS",
            }});

        function aplicarFiltros() {{
            tabla.querySelectorAll("tbody tr").forEach((fila) => {{
                fila.hidden = filtros.concat(filtrosExtra).some((filtro) => {{
                    const valor = filtro.value.toLowerCase();
                    const campo = filtro.dataset.campo.replace(
                        /-([a-z])/g,
                        (_, letra) => letra.toUpperCase(),
                    );
                    const contenido = (
                        fila.dataset[campo]
                        || fila.getAttribute(`data-${{filtro.dataset.campo}}`)
                        || ""
                    )
                        .trim().toLowerCase();
                    return valor && contenido !== valor;
                }});
            }});
            actualizarSubtotales();
        }}

        filtros.forEach((filtro) => {{
            filtro.addEventListener("change", aplicarFiltros);
        }});
        filtrosExtra.forEach((filtro) => {{
            filtro.addEventListener("change", aplicarFiltros);
        }});

        tabla.querySelectorAll(".orden-global").forEach((boton) => {{
            boton.addEventListener("click", () => {{
                const filas = Array.from(tabla.querySelectorAll("tbody tr"));
                const campo = boton.dataset.campo.replace(
                    /-([a-z])/g,
                    (_, letra) => letra.toUpperCase(),
                );
                const valorFila = (fila) => (
                    fila.getAttribute(`data-${{boton.dataset.campo}}`)
                    || fila.dataset[campo]
                    || ""
                ).trim().toLowerCase();
                const ascendente = boton.dataset.orden !== "asc";
                boton.dataset.orden = ascendente ? "asc" : "desc";
                filas.sort((a, b) => {{
                    const valorA = valorFila(a);
                    const valorB = valorFila(b);
                    const numeroA = numero(valorA);
                    const numeroB = numero(valorB);
                    const esNumero = (valor) =>
                        /^-?[0-9]+([.,][0-9]+)?$/.test(valor);
                    const ambosNumericos = esNumero(valorA)
                        && esNumero(valorB);
                    const comparacion = ambosNumericos
                        ? numeroA - numeroB
                        : valorA.localeCompare(valorB, "es");
                    return ascendente ? comparacion : -comparacion;
                }});
                filas.forEach((fila) => tabla.querySelector("tbody").appendChild(fila));
            }});
        }});

        function actualizarSubtotales() {{
            const filas = Array.from(tabla.querySelectorAll("tbody tr"))
                .filter((fila) => !fila.hidden);
            const sumas = {{
                duracion: 0, largo: 0, ancho: 0,
                profundidad: 0, montoSap: 0,
            }};
            filas.forEach((fila) => {{
                Object.keys(sumas).forEach((campo) => {{
                    sumas[campo] += numero(fila.dataset[campo]);
                }});
            }});
            ["duracion", "largo", "ancho", "profundidad"]
                .forEach((campo) => {{
                    tabla.querySelector(
                        `[data-subtotal="${{campo}}"]`
                    ).textContent = formatoNumero(sumas[campo]);
                }});
            [["montoSap", "monto-sap"]].forEach(([campo, campoSubtotal]) => {{
                tabla.querySelector(
                    `[data-subtotal="${{campoSubtotal}}"]`
                ).textContent = formatoMoneda(sumas[campo]);
            }});
        }}

        actualizarSubtotales();
    </script>
</body>
</html>
"""


def generar_reporte_errores(filas: list[dict[str, str]]) -> str:
    """Genera el reporte tabular de errores sincronizado con los estados."""
    filas_con_error = [
        fila for fila in filas if fila["tiene_error"] == "si"
    ]
    opciones_error = sorted(
        {
            tipo.strip()
            for fila in filas_con_error
            for tipo in fila["tipos"].split(",")
            if tipo.strip()
        },
        key=str.lower,
    )
    opciones_error = sorted(
        set(opciones_error) - {"Check"},
        key=str.lower,
    )
    opciones_came = sorted(
        {fila["came"] for fila in filas_con_error},
        key=str.lower,
    )
    opciones_acta = sorted(
        {fila["acta"] for fila in filas_con_error if fila["acta"]},
        key=str.lower,
    )
    opciones_observaciones = sorted(
        {
            fila["observaciones"]
            for fila in filas_con_error
            if fila["observaciones"]
        },
        key=str.lower,
    )

    def selector_filtro(campo: str, opciones: list[str]) -> str:
        valores = "".join(
            f'<option value="{esc(opcion, "")}">{esc(opcion)}</option>'
            for opcion in opciones
        )
        return (
            f'<select data-filtro="{campo}">'
            f'<option value="">Todas</option>{valores}</select>'
        )

    filas_html = "".join(
        f"""
            <tr data-came="{esc(fila['came'], '')}"
                data-tiene-error="{'si' if fila['tiene_error'] == 'si' else 'no'}"
                data-claves-error="{esc(fila.get('claves', ''), '')}"
                data-detalles-checks="{esc(
                    fila.get('detalles_checks', '{}'), ''
                )}"
                data-observaciones-base="{esc(
                    fila.get('observaciones_base', fila['observaciones']), ''
                )}">
                <td>{esc(fila['came'])}</td>
                <td>{esc(fila['acta'])}</td>
                <td class="celda-tipo-error">{esc(fila['tipos'], '')}</td>
                <td class="celda-observaciones" contenteditable="true"
                    data-observaciones="{esc(fila['observaciones'], '')}">{esc(fila['observaciones'])}</td>
            </tr>
        """
        for fila in filas
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte de errores</title>
    <style>
        body {{ margin: 0; padding: 24px; color: #172033; background: #eef2f7;
            font-family: Arial, Helvetica, sans-serif; }}
        .contenedor {{ width: min(1800px, 100%); margin: 0 auto; }}
        .reporte {{ padding: 24px; background: white; border: 1px solid #dbe3ef;
            border-radius: 18px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.09); }}
        h1 {{ margin-top: 0; color: #1e3a8a; }}
        .controles {{ display: flex; flex-wrap: wrap; gap: 12px;
            align-items: center; margin-bottom: 16px; }}
        .controles a, .controles button {{ padding: 9px 12px; color: white;
            border: 0; border-radius: 8px; background: #2563eb; font: inherit;
            text-decoration: none; cursor: pointer; }}
        .estado {{ color: #607089; font-size: 13px; }}
        .tabla-scroll {{ overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th, td {{ padding: 10px; border-bottom: 1px solid #dbe3ef;
            text-align: left; vertical-align: top; }}
        th {{ color: #1e3a8a; background: #eef4ff; }}
        th button {{
            display: block;
            padding: 0;
            color: inherit;
            border: 0;
            background: transparent;
            font: inherit;
            font-weight: 700;
            cursor: pointer;
        }}
        th select {{
            width: 100%;
            min-width: 110px;
            margin-top: 7px;
            padding: 5px 6px;
            border: 1px solid #dbe3ef;
            border-radius: 5px;
            font: inherit;
            font-size: 11px;
        }}
        td:nth-child(1), td:nth-child(2) {{ white-space: nowrap; }}
        tr.oculta {{ display: none; }}
    </style>
</head>
<body>
    <main class="contenedor">
        <section class="reporte">
            <h1>Reporte de errores</h1>
            <div class="controles">
                <a href="index.html">Volver al visor</a>
                <button id="actualizar" type="button">Actualizar</button>
                <button id="descargar-excel" type="button">
                    Descargar Excel
                </button>
                <span id="estado" class="estado"></span>
                <span id="ultima-actualizacion" class="estado"></span>
            </div>
            <div class="tabla-scroll">
                <table id="tabla-errores">
                    <thead><tr>
                        <th><button data-columna="came" type="button">CAME ↕</button>
                            {selector_filtro("came", opciones_came)}</th>
                        <th><button data-columna="acta" type="button">Número de acta ↕</button>
                            {selector_filtro("acta", opciones_acta)}</th>
                        <th><button data-columna="tipos" type="button">Tipo de error ↕</button>
                            {selector_filtro("tipos", opciones_error)}</th>
                        <th><button data-columna="observaciones" type="button">Observaciones ↕</button>
                            {selector_filtro("observaciones", opciones_observaciones)}</th>
                    </tr></thead>
                    <tbody>{filas_html}</tbody>
                </table>
            </div>
        </section>
    </main>
    <script>
        const claveEstados = "visor-actas-estados-correccion";
        const claveChecksOrden = "visor-actas-checks-orden";
        const claveObservaciones = "visor-actas-observaciones-errores";
        const filas = Array.from(document.querySelectorAll("#tabla-errores tbody tr"));
        const estado = document.getElementById("estado");
        const ultimaActualizacion = document.getElementById(
            "ultima-actualizacion",
        );
        const filtros = Array.from(document.querySelectorAll("[data-filtro]"));
        const encabezados = Array.from(document.querySelectorAll("[data-columna]"));
        let firmaEstadoAnterior = "";

        function obtenerFirmaEstado() {{
            return [
                localStorage.getItem(claveEstados) || "",
                localStorage.getItem(claveChecksOrden) || "",
                localStorage.getItem(claveObservaciones) || "",
            ].join("\\u0000");
        }}

        function cargarObservaciones() {{
            try {{
                const valor = JSON.parse(
                    localStorage.getItem(claveObservaciones) || "{{}}",
                );
                return valor && typeof valor === "object" ? valor : {{}};
            }} catch (error) {{
                console.warn("No se pudieron cargar las observaciones.", error);
                return {{}};
            }}
        }}

        const observacionesGuardadas = cargarObservaciones();
        filas.forEach((fila) => {{
            const observacion = fila.querySelector(".celda-observaciones");
            const came = fila.dataset.came;
            if (Object.prototype.hasOwnProperty.call(observacionesGuardadas, came)) {{
                observacion.textContent = observacionesGuardadas[came];
            }}
            observacion.addEventListener("input", () => {{
                observacionesGuardadas[came] = observacion.textContent.trim();
                try {{
                    localStorage.setItem(
                        claveObservaciones,
                        JSON.stringify(observacionesGuardadas),
                    );
                }} catch (error) {{
                    console.warn("No se pudo guardar la observación.", error);
                }}
            }});
        }});

        function valorColumna(fila, columna) {{
            const indice = {{
                came: 0,
                acta: 1,
                tipos: 2,
                observaciones: 3,
            }}[columna];
            return fila.cells[indice]?.textContent.trim() || "";
        }}

        function actualizarOpcionesFiltros(estados, checks) {{
            const manualPendiente = (valores) =>
                valores?.errores_carga === "pendiente"
                || valores?.fotos_correctas === "pendiente";
            const filasConError = filas.filter((fila) =>
                fila.dataset.tieneError === "si"
                || estados[fila.dataset.came] === "con-errores"
                || manualPendiente(checks[fila.dataset.came])
            );
            filtros.forEach((filtro) => {{
                const columna = filtro.dataset.filtro;
                const valores = new Set(
                    filasConError
                            .map((fila) => {{
                                return valorColumna(fila, columna);
                            }})
                            .filter(Boolean),
                    );
                const valorActual = filtro.value;
                Array.from(filtro.options).forEach((opcion, indice) => {{
                    if (indice > 0) {{
                        opcion.remove();
                    }}
                }});
                Array.from(valores)
                    .sort((a, b) => a.localeCompare(b, "es"))
                    .forEach((valor) => {{
                        const opcion = document.createElement("option");
                        opcion.value = valor;
                        opcion.textContent = valor;
                        filtro.appendChild(opcion);
                    }});
                filtro.value = valores.has(valorActual) ? valorActual : "";
            }});
        }}

        function actualizarObservacionDesdeChecks(fila, checks) {{
            const came = fila.dataset.came;
            if (observacionesGuardadas[came]?.trim()) {{
                return;
            }}
            const valores = [];
            const base = fila.dataset.observacionesBase || "";
            if (base) {{
                valores.push(base);
            }}
            const controlesManuales = [
                ["errores_carga", "errores_carga_motivo", "Carga"],
                ["fotos_correctas", "fotos_correctas_motivo", "Fotos"],
            ];
            controlesManuales.forEach(([clave, claveMotivo, etiqueta]) => {{
                const estado = checks[came]?.[clave] || "pendiente";
                if (estado !== "correcto") {{
                    const motivo = checks[came]?.[claveMotivo];
                    valores.push(
                        `${{etiqueta}} ${{estado}}`
                        + (motivo ? `: ${{motivo}}.` : "."),
                    );
                }}
            }});
            fila.querySelector(".celda-observaciones").textContent =
                valores.join(" ") || "-";
        }}

        function actualizarDetalleChecks(fila, checks) {{
            const came = fila.dataset.came;
            let detalles = {{}};
            try {{
                detalles = JSON.parse(fila.dataset.detallesChecks || "{{}}");
            }} catch (error) {{
                console.warn("No se pudieron leer los detalles del check.", error);
            }}
            const valores = [];
            const tipos = [];
            const automaticos = {{
                clase: "Clase de Actividad",
                fecha: "Fecha creación valida",
                foto: "Fotos existentes",
                items_problematicos: "Sin items incompatibles",
                ut: "UT valida",
                montos: "Monto estimado coincidente",
                separadores_decimales: "Separadores decimales correctos",
                duracion: "Sin valores en 0",
                materialidad: "Materialidad",
                correspondencia: "Correspondencia de ítems",
            }};
            Object.entries(automaticos).forEach(([clave, etiqueta]) => {{
                const clavesError = (fila.dataset.clavesError || "")
                    .split(",")
                    .filter(Boolean);
                if (
                    clavesError.includes(clave)
                    && checks[came]?.[clave] !== true
                ) {{
                    tipos.push(etiqueta);
                    valores.push(detalles[clave] || `${{etiqueta}} incorrecto.`);
                }}
            }});
            [
                ["errores_carga", "errores_carga_motivo", "Carga"],
                ["fotos_correctas", "fotos_correctas_motivo", "Fotos"],
            ].forEach(([clave, claveMotivo, etiqueta]) => {{
                const estado = checks[came]?.[clave];
                if (
                    estado === "incorrecto"
                    || estado === "pendiente"
                ) {{
                    tipos.push(etiqueta);
                    const motivo = checks[came]?.[claveMotivo];
                    valores.push(
                        `${{etiqueta}} ${{estado || "pendiente"}}`
                        + (motivo ? `: ${{motivo}}.` : "."),
                    );
                }}
            }});
            const tipo = fila.querySelector(".celda-tipo-error");
            tipo.textContent = tipos.join(", ");
            const observacion = fila.querySelector(".celda-observaciones");
            if (!observacionesGuardadas[came]?.trim()) {{
                observacion.textContent = valores.join(" ") || "-";
            }}
        }}

        function actualizar() {{
            let estados = {{}};
            let checks = {{}};
            try {{
                estados = JSON.parse(localStorage.getItem(claveEstados) || "{{}}");
            }} catch (error) {{
                console.warn("No se pudieron leer los estados de corrección.", error);
            }}
            try {{
                checks = JSON.parse(
                    localStorage.getItem(claveChecksOrden) || "{{}}",
                );
            }} catch (error) {{
                console.warn("No se pudieron leer los checks.", error);
            }}
            let visibles = 0;
            filas.forEach((fila) => {{
                const checksCame = checks[fila.dataset.came] || {{}};
                actualizarObservacionDesdeChecks(fila, checks);
                actualizarDetalleChecks(fila, checks);
                const checksPendientes =
                    checksCame.errores_carga === "pendiente"
                    || checksCame.fotos_correctas === "pendiente";
                const checksManualesIncorrectos =
                    checksCame.errores_carga === "incorrecto"
                    || checksCame.fotos_correctas === "incorrecto";
                const clavesError = (fila.dataset.clavesError || "")
                    .split(",")
                    .filter(Boolean);
                const checksSuperados = [];
                if (checksCame.clase === true) {{
                    checksSuperados.push(
                        "clase", "servicio", "duracion_g13",
                        "duracion_g05", "items_g11", "items_7_fuera_g11",
                    );
                }}
                [
                    "fecha", "foto", "items_problematicos", "ut", "montos",
                    "separadores_decimales", "duracion", "materialidad",
                    "correspondencia",
                ].forEach((clave) => {{
                    if (checksCame[clave] === true) checksSuperados.push(clave);
                }});
                const tieneErrorAutomatico = clavesError.some(
                    (clave) => !checksSuperados.includes(clave),
                );
                const tieneError = tieneErrorAutomatico
                    || checksPendientes
                    || checksManualesIncorrectos;
                const coincideFiltros = filtros.every((filtro) =>
                    !filtro.value
                    || valorColumna(fila, filtro.dataset.filtro)
                        .toLowerCase()
                        .includes(filtro.value.trim().toLowerCase())
                );
                const visible = coincideFiltros
                    && tieneError;
                fila.classList.toggle("oculta", !visible);
                if (visible) visibles += 1;
            }});
            actualizarOpcionesFiltros(estados, checks);
            estado.textContent = `${{visibles}} CAME(s) con errores`;
            firmaEstadoAnterior = obtenerFirmaEstado();
            if (ultimaActualizacion) {{
                ultimaActualizacion.textContent =
                    `Actualizado ${{new Date().toLocaleTimeString("es-AR")}}`;
            }}
        }}

        function descargarExcel() {{
            const encabezadosExcel = [
                "CAME",
                "Número de acta",
                "Tipo de error",
                "Observaciones",
            ];
            const escaparExcel = (valor) => String(valor)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;");
            const filasVisibles = filas.filter(
                (fila) => !fila.classList.contains("oculta"),
            );
            const contenido = filasVisibles.map((fila) => [
                fila.cells[0]?.textContent.trim() || "",
                fila.cells[1]?.textContent.trim() || "",
                fila.querySelector(".celda-tipo-error")?.textContent.trim() || "",
                fila.querySelector(".celda-observaciones")?.textContent.trim() || "",
            ]);
            const tablaExcel = [
                encabezadosExcel,
                ...contenido,
            ].map((fila) =>
                `<tr>${{fila.map((valor) =>
                    `<td>${{escaparExcel(valor)}}</td>`
                ).join("")}}</tr>`
            ).join("");
            const archivo = [
                '<html xmlns:o="urn:schemas-microsoft-com:office:office"',
                ' xmlns:x="urn:schemas-microsoft-com:office:excel"',
                ' xmlns="http://www.w3.org/TR/REC-html40">',
                '<head><meta charset="UTF-8"></head>',
                `<body><table border="1">${{tablaExcel}}</table></body></html>`,
            ].join("");
            const blob = new Blob(["\uFEFF", archivo], {{
                type: "application/vnd.ms-excel;charset=utf-8",
            }});
            const enlace = document.createElement("a");
            enlace.href = URL.createObjectURL(blob);
            enlace.download =
                `reporte_de_errores_${{new Date().toISOString().slice(0, 10)}}.xls`;
            document.body.appendChild(enlace);
            enlace.click();
            enlace.remove();
            URL.revokeObjectURL(enlace.href);
        }}

        window.addEventListener("message", (evento) => {{
            if (evento.data === "actualizar-reporte-errores") {{
                actualizar();
            }}
        }});
        window.addEventListener(
            "visor-actas-reporte-actualizar",
            actualizar,
        );

        filtros.forEach((filtro) => {{
            filtro.addEventListener("change", actualizar);
        }});
        encabezados.forEach((encabezado) => {{
            encabezado.addEventListener("click", () => {{
                const columna = encabezado.dataset.columna;
                const ascendente = encabezado.dataset.orden !== "asc";
                encabezado.dataset.orden = ascendente ? "asc" : "desc";
                filas.sort((a, b) => {{
                    const valorA = valorColumna(a, columna).toLowerCase();
                    const valorB = valorColumna(b, columna).toLowerCase();
                    const numeroA = Number(valorA);
                    const numeroB = Number(valorB);
                    const comparacion = Number.isNaN(numeroA) || Number.isNaN(numeroB)
                        ? valorA.localeCompare(valorB, "es")
                        : numeroA - numeroB;
                    return ascendente ? comparacion : -comparacion;
                }});
                const cuerpo = document.querySelector("#tabla-errores tbody");
                filas.forEach((fila) => cuerpo.appendChild(fila));
                actualizar();
            }});
        }});
        document.getElementById("actualizar").addEventListener("click", actualizar);
        document.getElementById("descargar-excel").addEventListener(
            "click",
            descargarExcel,
        );
        window.addEventListener("storage", (evento) => {{
            if (
                evento.key === claveEstados
                || evento.key === claveChecksOrden
                || evento.key === claveObservaciones
            ) actualizar();
        }});
        window.addEventListener("focus", actualizar);
        window.setInterval(() => {{
            if (obtenerFirmaEstado() !== firmaEstadoAnterior) {{
                actualizar();
            }}
        }}, 500);
        actualizar();
    </script>
</body>
</html>"""


def generar_reporte_operaciones_xlsx(
    cames: dict,
    precios: dict[tuple[str, str], float],
    ) -> bytes:
    encabezados = (
        "Acta", "Texto breve", "Clave de control", "Duración normal",
        "Largo", "Ancho", "Profundidad", "Unidad",
        "Coincide duración", "Monto SAP",
    )
    filas = [encabezados]
    for came in cames.values():
        if not isinstance(came, dict):
            continue
        acta = identificador_acta(came.get("Texto Breve", ""))
        texto_breve = came.get("Texto Breve", "")
        puesto = valor_real(came.get("Puesto de trabajo"))
        operaciones = came.get("operaciones", {})
        if not isinstance(operaciones, dict):
            continue
        for operacion in operaciones.values():
            if not isinstance(operacion, dict):
                continue
            clave = operacion.get("Clave de control", "")
            duracion = normalizar_numero_texto(
                operacion.get("Duracion normal") or ""
            )
            largo = normalizar_numero_texto(
                operacion.get("Largo") or campo_operacion(
                operacion, "Largo", "Longitud"
                )
            )
            ancho = normalizar_numero_texto(
                operacion.get("Ancho") or campo_operacion(
                operacion, "Ancho"
                )
            )
            profundidad = normalizar_numero_texto(
                operacion.get("Profundidad") or campo_operacion(
                operacion, "Profundidad"
                )
            )
            unidad = operacion.get("Unidad de Medida") or campo_operacion(
                operacion,
                "Unidad de medida",
                "Unidad medida",
                "Unidad",
            )
            cantidad = cantidad_operacion(largo, ancho, profundidad, unidad)
            precio = precios.get((normalizar(clave), normalizar(puesto)))
            monto_sap = (
                numero_decimal(duracion) * precio
                if precio is not None and numero_decimal(duracion) is not None
                else None
            )
            filas.append((
                acta,
                texto_breve,
                clave,
                duracion,
                largo,
                ancho,
                profundidad,
                unidad,
                coincide_duracion_normal(cantidad, duracion, precio),
                mostrar_moneda(monto_sap),
            ))
    
    def xml_texto(valor: object) -> str:
        return html.escape(str(valor if valor is not None else ""))
    
    filas_xml = []
    for fila in filas:
        celdas = "".join(
            f'<c t="inlineStr"><is><t>{xml_texto(valor)}</t></is></c>'
            for valor in fila
        )
        filas_xml.append(f"<row>{celdas}</row>")
    hoja = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(filas_xml) + "</sheetData></worksheet>"
    )
    contenido_tipos = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    relaciones = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    relaciones_libro = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    libro = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Operaciones" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    archivo = io.BytesIO()
    with zipfile.ZipFile(archivo, "w", zipfile.ZIP_DEFLATED) as paquete:
        paquete.writestr("[Content_Types].xml", contenido_tipos)
        paquete.writestr("_rels/.rels", relaciones)
        paquete.writestr("xl/_rels/workbook.xml.rels", relaciones_libro)
        paquete.writestr("xl/workbook.xml", libro)
        paquete.writestr("xl/worksheets/sheet1.xml", hoja)
    return archivo.getvalue()
    
    
# ------------------------------------------------------------
# HTML
# ------------------------------------------------------------

def generar_html(
    avisos: dict,
    cames: dict,
    cares: dict,
    archivos_acta: list[Path],
    precios: dict[tuple[str, str], float],
    fuentes: dict[str, bool] | None = None,
    errores_reporte: list[dict[str, str]] | None = None,
) -> str:
    fuentes = fuentes or {}
    errores_reporte = errores_reporte if errores_reporte is not None else []
    puestos_renglones_cargados = sorted(
        {
            (
                coincidencia.group(1).upper(),
                coincidencia.group(2)[1:].upper(),
            )
            for came in cames.values()
            if isinstance(came, dict)
            for coincidencia in [
                re.search(
                    r"^(.+?)_(R\d+)(?:_|$)",
                    texto(came.get("Texto Breve"), ""),
                    re.IGNORECASE,
                )
            ]
            if coincidencia
        }
    )
    resumen_puestos_renglones = ", ".join(
        f"{puesto} · Renglón {renglon}"
        for puesto, renglon in puestos_renglones_cargados
    ) or "ninguno"
    descripciones_ubicacion = {
        texto(
            came.get("Descripcion Ubicacion Tecnica")
            or cares.get(
                str(came.get("CARE Asociada") or came.get("CARE asociada") or ""),
                {},
            ).get("Descripcion Ubicacion Tecnica")
            or avisos.get(
                str(came.get("Aviso asociado") or came.get("Aviso Asociado") or ""),
                {},
            ).get("Descripcion Ubicacion Tecnica"),
            "",
        ): texto(came.get("Ubicacion Tecnica"), "")
        for came in cames.values()
    }
    descripciones_ubicacion.pop("", None)
    direcciones_exactas = set()
    for came in cames.values():
        care_id = str(
            came.get("CARE Asociada")
            or came.get("CARE asociada")
            or ""
        )
        care = cares.get(care_id, {})
        if isinstance(care, dict):
            direccion_care = texto(care.get("Calle"), "").strip()
            if direccion_care:
                direcciones_exactas.add(direccion_care)
    datos_geograficos = cargar_datos_geograficos(
        descripciones_ubicacion,
        direcciones_exactas,
    )
    ITEM_UNIDADES.clear()
    for came in cames.values():
        for operacion in (
            came.get("operaciones", {})
            if isinstance(came, dict)
            else {}
        ).values():
            if not isinstance(operacion, dict):
                continue
            item = codigo_item(
                operacion.get("Texto breve operacion", "")
            )
            unidad = operacion.get("Unidad de Medida", "")
            if item and unidad:
                ITEM_UNIDADES.setdefault(item, normalizar(unidad))

    tarjetas = []

    cames_ordenadas = sorted(
        cames.items(),
        key=lambda elemento: numero_acta(
            elemento[1].get("Texto Breve", "")
        ),
    )
    numeros_acta_validos = {
        int(numero_acta(came.get("Texto Breve", ""))[0])
        for came in cames.values()
        if numero_acta(came.get("Texto Breve", ""))[0] != float("inf")
    }
    numeros_acta_faltantes = set()
    if len(numeros_acta_validos) >= 2:
        numeros_acta_faltantes = set(
            range(min(numeros_acta_validos), max(numeros_acta_validos) + 1)
        ) - numeros_acta_validos
    fechas_inicio = {
        fecha_orden(came.get("Fecha inicio"))
        for came in cames.values()
        if fecha_orden(came.get("Fecha inicio")) is not None
    }
    fechas_fin = {
        fecha_orden(came.get("Fecha fin"))
        for came in cames.values()
        if fecha_orden(came.get("Fecha fin")) is not None
    }
    fechas_inicio_no_uniformes = len(fechas_inicio) > 1
    fechas_fin_no_uniformes = len(fechas_fin) > 1

    for indice_came, (came_id, came) in enumerate(cames_ordenadas):
        came_id = str(came_id)

        care_id = str(
            came.get("CARE Asociada")
            or came.get("CARE asociada")
            or ""
        )

        aviso_id = str(
            came.get("Aviso asociado")
            or came.get("Aviso Asociado")
            or ""
        )

        care = cares.get(care_id, {})
        aviso = avisos.get(aviso_id, {})

        if not isinstance(care, dict):
            care = {}

        if not isinstance(aviso, dict):
            aviso = {}

        care_items, care_total_trabajo = resumen_operaciones_care(care)

        texto_breve = texto(
            came.get("Texto Breve"),
            f"CAME {came_id}",
        )

        archivos_acta_asociados = buscar_archivos_acta(
            archivos=archivos_acta,
            texto_breve=texto_breve,
        )
        archivos_came = [
            archivo
            for archivo in archivos_acta_asociados
            if "came" in archivo.name.lower()
            and "care" not in archivo.name.lower()
        ]
        archivos_care = [
            archivo
            for archivo in archivos_acta_asociados
            if "care" in archivo.name.lower()
            or "aviso" in archivo.name.lower()
        ]
        descripcion_ubicacion = texto(
            came.get("Descripcion Ubicacion Tecnica")
            or care.get("Descripcion Ubicacion Tecnica")
            or aviso.get("Descripcion Ubicacion Tecnica"),
            "",
        )
        direccion = (
            texto(care.get("Calle"), "")
            or texto(aviso.get("Calle"), "")
            or texto(aviso.get("Direccion"), "")
        )
        mapa_url = (
            "https://www.google.com/maps/search/?api=1&query="
            + quote(direccion)
            if direccion
            else ""
        )
        direccion_care = texto(care.get("Calle"), "").strip()
        datos_direccion = datos_geograficos.get(
            f"direccion:{direccion_care}",
            {},
        )
        datos_ubicacion = datos_direccion or datos_geograficos.get(
            descripcion_ubicacion,
            {},
        )
        datos_tecnica = datos_geograficos.get(descripcion_ubicacion, {})
        entre_calles = (
            datos_ubicacion.get("entre_calles")
            or datos_tecnica.get("entre_calles")
            or []
        )
        streetview_url = (
            datos_ubicacion.get("streetview_url")
            or mapa_url
        )
        entre_calles_texto = (
            " y ".join(entre_calles)
            if entre_calles
            else "No identificadas"
        )
        largo_m = datos_ubicacion.get("largo_m")
        clase_came = valor_real(came.get("Clase de actividad"))
        clase_care = valor_real(care.get("Clase de actividad"))
        clases_iguales = bool(
            clase_came and clase_care and clase_came == clase_care
        )
        servicio = texto(aviso.get("Servicio asociado"), "")
        servicio_normalizado = servicio.strip().lower()
        servicio_valido = (
            aviso.get("Servicio asociado") is not None
            and servicio_normalizado not in {"", "none", "-"}
            and not servicio_normalizado.startswith("número de documento")
        )
        servicio_g02_ok = (
            clase_came.lower() != "g02"
            or bool(servicio_valido)
        )
        servicio_visible = re.sub(
            r"\s*:\s*\d+\s*$",
            "",
            servicio,
        ).strip()
        fecha_creacion_came = fecha_orden(came.get("Fecha creacion"))
        fecha_inicio_came = fecha_orden(came.get("Fecha inicio"))
        fechas_came_ok = bool(
            fecha_creacion_came
            and fecha_inicio_came
            and fecha_creacion_came <= fecha_inicio_came
        )
        area_came = valor_real(came.get("Area de empresa"))
        area_care = valor_real(care.get("Area de empresa"))
        areas_iguales = bool(area_came and area_care and area_came == area_care)
        puesto_came = valor_real(came.get("Puesto de trabajo"))
        puesto_care = valor_real(care.get("Puesto de trabajo"))
        puesto_responsable = valor_real(
            aviso.get("Puesto de trabajo responsable")
        )
        puesto_came_sufijo = sufijo_puesto(puesto_came)
        puesto_care_sufijo = sufijo_puesto(puesto_care)
        puesto_responsable_sufijo = sufijo_puesto(puesto_responsable)
        puestos_iguales = bool(
            puesto_came_sufijo
            and puesto_care_sufijo
            and puesto_came_sufijo == puesto_care_sufijo
        )
        came_tiene_foto = tiene_foto(came)
        tiene_duracion_cero = tiene_duracion_normal_cero(came)
        clase_came_normalizada = normalizar(clase_came)
        duracion_g13 = (
            clase_came_normalizada == "g13"
            and tiene_duracion_por_debajo_del_umbral(came, 12)
        )
        ancho_g13 = (
            clase_came_normalizada == "g13"
            and tiene_ancho_por_encima_del_umbral(came, 1.75)
        )
        duracion_g05 = (
            clase_came_normalizada == "g05"
            and tiene_duracion_por_debajo_del_umbral(came, 100)
        )
        items_g11 = (
            clase_came_normalizada == "g11"
            and faltan_items_g11(came)
        )
        items_7_fuera_g11 = tiene_items_7_fuera_de_g11(came, clase_came)
        items_problematicos = tiene_items_problematicos(came)
        operaciones = came.get("operaciones", {})
        separadores_decimales_ok = all(
            separadores_decimales_operacion_validos(operacion)
            for operacion in operaciones.values()
            if isinstance(operacion, dict)
        ) if isinstance(operaciones, dict) else True
        total_monto_sap, total_monto_estimado = totales_montos_came(
            came,
            puesto_came,
            precios,
        )
        montos_no_coinciden = not montos_came_coinciden(
            came,
            puesto_came,
            precios,
        )
        materialidad_care = texto(care.get("Materialidad"), "")
        materialidad_items_ok = items_materialidad_validos(
            came,
            materialidad_care,
        )
        correspondencia_items_ok = correspondencia_items_valida(
            came,
            clase_came,
        )
        servicio_sin_g02 = bool(servicio_valido) and clase_came_normalizada != "g02"
        materialidad_normalizada = normalizar(materialidad_care)
        if materialidad_normalizada in {"adoquin", "adoquines"}:
            materialidad_normalizada = "adoquin"
        superficie_m2 = total_superficie_m2(came)
        reglas_clase_ok = (
            not (
                clase_came_normalizada == "g13"
                and materialidad_normalizada != "hormigon"
            )
            and not (
                clase_came_normalizada == "g05"
                and materialidad_normalizada not in {"asfalto", "hormigon"}
            )
            and not (
                clase_came_normalizada in {"g09", "g10"}
                and materialidad_normalizada != "adoquin"
            )
            and not (
                clase_came_normalizada in {"g05", "g10"}
                and superficie_m2 <= 100
            )
            and not (
                clase_came_normalizada in {"g04", "g09"}
                and superficie_m2 <= 400
            )
        )
        clase_actividad_ok = (
            clases_iguales
            and servicio_g02_ok
            and not servicio_sin_g02
            and not duracion_g13
            and not ancho_g13
            and not duracion_g05
            and not items_g11
            and not items_7_fuera_g11
            and reglas_clase_ok
        )
        max_duracion_came = max(
            (
                numero_decimal(operacion.get("Duracion normal"))
                for operacion in operaciones.values()
                if isinstance(operacion, dict)
            ),
            default=None,
        ) if isinstance(operaciones, dict) else None
        _, care_total_trabajo = resumen_operaciones_care(care)
        itemizado_care_ok = (
            max_duracion_came is None
            or numero_decimal(care_total_trabajo) is None
            or abs(
                max_duracion_came - numero_decimal(care_total_trabajo)
            ) <= 0.01
        )
        resumen_fotos = resumen_comparacion_fotos(came)
        modificacion_care = texto(care.get("Fecha modificacion"), "")
        modificado_por_care = texto(care.get("Modificado por"), "")
        estado_usuario_aviso = texto(aviso.get("Status usuario"), "")
        clase_aviso = valor_real(aviso.get("Clase de aviso"))
        numero_acta_came = identificador_acta(came.get("Texto Breve", ""))
        fecha_periodo_valida = (
            fecha_inicio_valida(came.get("Fecha inicio"))
            and fecha_fin_valida(came.get("Fecha fin"))
        )
        texto_breve_correlativo = (
            not numeros_acta_faltantes
            and numero_acta(came.get("Texto Breve", ""))[0] != float("inf")
        )
        errores = {
            "acta": not numero_acta_came,
            "clase": not clase_actividad_ok,
            "servicio": not servicio_g02_ok,
            "fecha": not fechas_came_ok,
            "fecha_formato": not fecha_periodo_valida,
            "fechas_iguales": (
                fechas_inicio_no_uniformes or fechas_fin_no_uniformes
            ),
            "texto_correlativo": not texto_breve_correlativo,
            "separadores_decimales": not separadores_decimales_ok,
            "foto": not came_tiene_foto,
            "duracion": tiene_duracion_cero,
            "montos": montos_no_coinciden,
            "duracion_g13": duracion_g13,
            "duracion_g05": duracion_g05,
            "items_g11": items_g11,
            "items_7_fuera_g11": items_7_fuera_g11,
            "check": False,
            "via_publica": "viapublica" in normalizar(descripcion_ubicacion),
            "items_problematicos": items_problematicos,
            "ut": "viapublica" in normalizar(descripcion_ubicacion),
            "materialidad": not materialidad_items_ok,
            "correspondencia": not correspondencia_items_ok,
            "itemizado_care": False,
        }
        tiene_errores = any(errores.values())
        tipos_error = ",".join(
            tipo for tipo, tiene_error in errores.items() if tiene_error
        )
        errores_titulo = ", ".join(
            etiqueta
            for tipo, etiqueta in ERROR_TIPOS
            if errores[tipo]
        )
        checks_orden = (
            ("clase", "Clase de Actividad", not errores["clase"]),
            ("fecha", "Fecha creación valida", not errores["fecha"]),
            ("foto", "Fotos existentes", not errores["foto"]),
            ("items_problematicos", "Sin items incompatibles",
             not errores["items_problematicos"]),
            ("ut", "UT valida", not errores["ut"]),
            ("montos", "Monto estimado coincidente",
             not errores["montos"]),
            ("separadores_decimales", "Separadores decimales correctos",
             not errores["separadores_decimales"]),
            ("duracion", "Sin valores en 0", not errores["duracion"]),
            ("materialidad", "Materialidad", not errores["materialidad"]),
            ("correspondencia", "Correspondencia de ítems",
             not errores["correspondencia"]),
        )
        items_came = {
            codigo_item(item_preciario(operacion.get("Clave de control", "")))
            for operacion in (came.get("operaciones", {}) or {}).values()
            if isinstance(operacion, dict)
        }
        reglas_materialidad = (
            ("adoquín", {"4.1.1", "4.1.2", "6.1.1", "6.1.2"}),
            ("hormigón", {"4.2.1", "4.2.2", "6.3"}),
            ("asfalto", {"6.2", "10.2"}),
            ("intertrabado", {"11.5"}),
        )
        materialidad_detalles = [
            f"Ítems {', '.join(sorted(items_came & items_permitidos))} "
            f"requieren materialidad {materialidad_requerida}."
            for materialidad_requerida, items_permitidos in reglas_materialidad
            if items_came & items_permitidos
            and materialidad_normalizada != (
                "adoquin"
                if materialidad_requerida == "adoquín"
                else materialidad_requerida
            )
        ]
        detalles_items = detalles_items_problematicos(came)
        detalles_checks = {
            "clase": " · ".join(
                detalle for detalle, aplica in (
                    (
                        f"CAME ({clase_came}) y CARE ({clase_care}) "
                        "tienen distinta clase de actividad.",
                        not clases_iguales,
                    ),
                    (
                        "G02 no tiene servicio asociado.",
                        not servicio_g02_ok,
                    ),
                    (
                        "Hay servicio asociado sin clase G02.",
                        servicio_sin_g02,
                    ),
                    (
                        "G13 tiene una duración normal que no supera 12.",
                        duracion_g13,
                    ),
                    (
                        "G13 tiene ítems con ancho mayor a 1.75.",
                        ancho_g13,
                    ),
                    (
                        "G05 tiene una duración normal que no supera 100.",
                        duracion_g05,
                    ),
                    (
                        "G11 no contiene ítems 7.1 o 7.2.",
                        items_g11,
                    ),
                    (
                        "Hay ítems 7.1 o 7.2 fuera de G11.",
                        items_7_fuera_g11,
                    ),
                    (
                        f"{clase_came} requiere materialidad hormigón.",
                        clase_came_normalizada == "g13"
                        and materialidad_normalizada != "hormigon",
                    ),
                    (
                        f"{clase_came} requiere materialidad asfalto u hormigón.",
                        clase_came_normalizada == "g05"
                        and materialidad_normalizada not in {"asfalto", "hormigon"},
                    ),
                    (
                        f"{clase_came} requiere materialidad adoquín.",
                        clase_came_normalizada in {"g09", "g10"}
                        and materialidad_normalizada != "adoquin",
                    ),
                    (
                        f"{clase_came} requiere una superficie mayor a 100 m2.",
                        clase_came_normalizada in {"g05", "g10"}
                        and superficie_m2 <= 100,
                    ),
                    (
                        f"{clase_came} requiere una superficie mayor a 400 m2.",
                        clase_came_normalizada in {"g04", "g09"}
                        and superficie_m2 <= 400,
                    ),
                )
                if aplica
            ) or "La clase de actividad cumple todas las reglas.",
            "fecha": " · ".join(
                detalle for detalle, aplica in (
                    (
                        "La fecha de creación no es válida.",
                        not fechas_came_ok,
                    ),
                    (
                        "El período de la CAME no es válido: inicio o fin "
                        "no corresponde al período requerido.",
                        not fecha_periodo_valida,
                    ),
                )
                if aplica
            ) or "La fecha de creación y el período son válidos.",
            "foto": (
                "No se encontraron fotos asociadas a la CAME."
                if errores["foto"] else "Las fotos asociadas existen."
            ),
            "items_problematicos": (
                " · ".join(
                    detalle for detalle in [
                        "Hay ítems incompatibles entre sí."
                        if tiene_items_problematicos(came)
                        else "",
                        *detalles_items,
                    ] if detalle
                )
                if errores["items_problematicos"]
                else "No hay ítems incompatibles."
            ),
            "ut": (
                "La UT corresponde a Vía Pública."
                if errores["ut"] else "La UT es válida."
            ),
            "montos": (
                "El monto estimado no coincide con el monto calculado."
                if errores["montos"] else "El monto estimado coincide."
            ),
            "separadores_decimales": (
                "Los separadores decimales no respetan el formato requerido."
                if errores["separadores_decimales"]
                else "Los separadores decimales son correctos."
            ),
            "duracion": (
                "Hay operaciones con duración normal igual a cero."
                if errores["duracion"] else "No hay valores en cero."
            ),
            "materialidad": (
                " · ".join(materialidad_detalles)
                if materialidad_detalles
                else "La materialidad corresponde a los ítems."
            ),
            "correspondencia": (
                f"Los ítems no corresponden a la clase {clase_came} "
                "según las reglas de correspondencia."
                if errores["correspondencia"]
                else "La correspondencia de ítems es correcta."
            ),
        }
        checks_orden_html = "".join(
            f"""
                    <label class="check-automatico {
                        "check-automatico-error" if not correcto
                        else "check-automatico-ok"
                    }" title="{esc(detalles_checks[clave])}">
                        <input type="checkbox" class="check-automatico-input"
                            data-check="{clave}"
                            {"checked" if correcto else ""}>
                        {etiqueta}
                    </label>
            """
            for clave, etiqueta, correcto in checks_orden
        ) + """
                    <label class="check-manual">
                        <span>Carga</span>
                        <button type="button" class="check-manual-input"
                            data-check="errores_carga"
                            data-estado="pendiente"
                            aria-label="Estado de Carga">
                            Pendiente
                        </button>
                        <select class="motivo-check-manual"
                            data-motivo="errores_carga_motivo"
                            aria-label="Motivo de Carga incorrecta" hidden>
                            <option value="">Motivo</option>
                            <option>Trabajos en cero</option>
                            <option>Error en profundidad de ítems m3</option>
                            <option>Error de carga</option>
                        </select>
                    </label>
                    <label class="check-manual">
                        <span>Fotos</span>
                        <button type="button" class="check-manual-input"
                            data-check="fotos_correctas"
                            data-estado="pendiente"
                            aria-label="Estado de Fotos">
                            Pendiente
                        </button>
                        <select class="motivo-check-manual"
                            data-motivo="fotos_correctas_motivo"
                            aria-label="Motivo de Fotos incorrectas" hidden>
                            <option value="">Motivo</option>
                            <option>Falta foto terminado</option>
                            <option>Falta foto durante</option>
                            <option>El trabajo no es lo solicitado</option>
                        </select>
                    </label>
        """
        observaciones = []
        if not numero_acta_came:
            observaciones.append("El Texto Breve no contiene número de acta.")
        if not fecha_periodo_valida:
            observaciones.append(
                "Inicio debe ser día 01 y fin último día del mes."
            )
        if fechas_inicio_no_uniformes:
            observaciones.append("Las fechas de inicio no son iguales.")
        if fechas_fin_no_uniformes:
            observaciones.append("Las fechas de fin no son iguales.")
        if numeros_acta_faltantes:
            observaciones.append(
                "Faltan números de acta en la secuencia: "
                + ", ".join(str(numero) for numero in sorted(numeros_acta_faltantes))
            )
        if items_7_fuera_g11:
            observaciones.append(
                "La CAME contiene ítems 7.1 o 7.2 y no pertenece a G11."
            )
        if not separadores_decimales_ok:
            observaciones.append(
                "Duración normal debe usar coma; los demás decimales deben usar "
                "punto, salvo Profundidad de ítems M2, que también debe usar coma."
            )
        detalles_error = [
            detalles_checks[clave]
            for clave, _, correcto in checks_orden
            if not correcto
        ]
        observaciones.extend(detalles_error)
        errores_reporte.append(
            {
                "came": came_id,
                "acta": numero_acta_came,
                "tipos": errores_titulo,
                "observaciones": " ".join(observaciones),
                "tiene_error": "si" if tiene_errores else "no",
                "claves": ",".join(
                    tipo for tipo, tiene_error in errores.items()
                    if tiene_error
                ),
                "observaciones_base": " ".join(observaciones),
                "detalles_checks": json.dumps(
                    detalles_checks,
                    ensure_ascii=False,
                ),
            }
        )
        fecha_inicio = texto(came.get("Fecha inicio"), "")
        fecha_fin = texto(came.get("Fecha fin"), "")
        fecha_creacion = texto(came.get("Fecha creacion"), "")
        fecha_modificacion = texto(came.get("Fecha modificacion"), "")
        modificado_por = texto(came.get("Modificado por"), "")

        campos_busqueda = [
            came_id,
            care_id,
            aviso_id,
            texto_breve,
            texto(came.get("Descripcion Ubicacion Tecnica"), ""),
            texto(care.get("Texto Breve"), ""),
            texto(aviso.get("Descripcion"), ""),
            texto(aviso.get("Calle"), ""),
        ]
        texto_busqueda = " ".join(campos_busqueda)
        detalles_busqueda = json.dumps(
            [campo for campo in campos_busqueda if campo],
            ensure_ascii=False,
        )

        estado_fotos = (
            "con-fotos"
            if archivos_acta_asociados
            else "sin-fotos"
        )

        tarjetas.append(f"""
        <article
            class="tarjeta {estado_fotos}{" actual" if indice_came == 0 else ""}"
            data-busqueda="{esc(texto_busqueda)}"
            data-busqueda-detalle="{esc(detalles_busqueda)}"
            data-area="{esc(came.get("Area de empresa"), "")}"
            data-clase-actividad="{esc(came.get("Clase de actividad"), "")}"
            data-materialidad="{esc(materialidad_care)}"
            data-resumen-fotos="{esc(resumen_fotos, '')}"
            data-clase-aviso="{esc(clase_aviso)}"
            data-tiene-servicio="{"si" if servicio_valido else "no"}"
            data-tiene-errores="{"si" if tiene_errores else "no"}"
            data-tiene-errores-base="{"si" if tiene_errores else "no"}"
            data-tipos-error="{esc(tipos_error, '')}"
            data-tipos-error-base="{esc(tipos_error, '')}"
            data-check-pendiente="si"
            data-fecha-modificacion="{esc(fecha_modificacion, '')}"
            data-texto-breve="{esc(texto_breve, '')}"
            data-came-id="{esc(came_id, '')}"
            data-acta="{esc(numero_acta_came, '')}"
            data-estado-correccion="no-corregida"
        >
            <header class="tarjeta-header">
                <div>
                    <div class="etiqueta came-id">CAME {esc(came_id)}</div>
                    <div class="titulo-came">
                        <h2>{esc(ubicacion_tecnica_corta(descripcion_ubicacion))}</h2>
                    </div>
                    {
                        f'<div class="errores-titulo">'
                        f'Errores: {esc(errores_titulo)}</div>'
                        if tiene_errores else ""
                    }
                    <p class="materialidad-titulo">
                        Materialidad: {esc(materialidad_care)}
                    </p>
                    <div class="fechas-titulo">
                        Inicio: {esc(fecha_inicio)} ·
                        Fin: {esc(fecha_fin)} ·
                        Creación: {esc(fecha_creacion)} ·
                        Modificación: {esc(fecha_modificacion)} ·
                        Por: {esc(modificado_por)}
                    </div>
                </div>

                <div class="estado-tarjeta">
                    <span class="estado cantidad-archivos">
                        {len(archivos_acta_asociados)} archivo(s)
                    </span>
                    <span class="estado-correccion-resumen estado-pendiente"
                        data-estado-indicador>
                        Pendiente de revisión
                    </span>
                    <fieldset class="estado-correccion">
                        <legend>Estado</legend>
                        <label>
                            <input type="radio" name="estado-{esc(came_id)}"
                                value="no-corregida">
                            No corregida
                        </label>
                        <label>
                            <input type="radio" name="estado-{esc(came_id)}"
                                value="corregida">
                            Correcta
                        </label>
                        <label>
                            <input type="radio" name="estado-{esc(came_id)}"
                                value="con-errores">
                            Con errores
                        </label>
                    </fieldset>
                </div>
            </header>

            <div class="relaciones">
                <div class="relacion">
                    <span class="relacion-tipo">CARE relacionada</span>
                    <strong>{esc(care_id)}</strong>
                    <span>{esc(care.get("Texto Breve"))}</span>
                    <span class="resumen-care">
                        <strong>Ítem: {esc(care_items)}</strong>
                        <strong>Trabajo total: {esc(care_total_trabajo)}</strong>
                    </span>
                    <small>
                        Modificación: {esc(modificacion_care)} ·
                        Por: {esc(modificado_por_care)}
                    </small>
                </div>

                <div class="relacion">
                    <span class="relacion-tipo">
                        Aviso relacionado
                    </span>
                    <strong>{esc(aviso_id)}</strong>
                    <span>{esc(aviso.get("Descripcion"))}</span>
                    <button class="boton-texto-aviso" type="button">
                        Ver texto del aviso
                    </button>
                    <small>Estado usuario: {esc(estado_usuario_aviso)}</small>
                </div>
            </div>

            <div class="modal-texto-aviso" aria-hidden="true">
                <div class="modal-texto-aviso-contenido" role="dialog"
                    aria-modal="true">
                    <button class="cerrar-texto-aviso" type="button">
                        Cerrar
                    </button>
                    <h3>Texto del aviso</h3>
                    {mostrar_texto_aviso(aviso)}
                </div>
            </div>

            <section class="seccion">
                <div class="titulo-seccion-con-accion">
                    <h3>Información de la CAME</h3>
                    <button class="boton-comparar-fotos" type="button">
                        Ver fotos en pantalla completa
                    </button>
                </div>
                {
                    f"""
                    <div class="detalle-ubicacion">
                        <span>Barrio: {esc(datos_ubicacion.get("barrio", ""))}</span>
                        <span>Entre calles: {esc(entre_calles_texto)}</span>
                        {
                            f'<span>Largo: {mostrar_numero(largo_m)} m</span>'
                            if largo_m is not None else ""
                        }
                        <div class="enlaces-geograficos">
                        {
                            f'<a class="mapa-link" href="{esc(streetview_url)}" '
                            f'target="_blank">Abrir Street View</a>'
                            if streetview_url else ""
                        }
                        {
                            f'<a class="mapa-link" href="{esc(datos_ubicacion.get("google_maps_url", ""))}" '
                            f'target="_blank">Abrir punto en Google Maps</a>'
                            if datos_ubicacion.get("google_maps_url") else ""
                        }
                        </div>
                    </div>
                    """
                }
            </section>

            <section class="seccion">
                <h3>Controles de la ORDEN</h3>
                <div class="checks-clase">
                    {checks_orden_html}
                    <div class="detalle-controles">
                        Clases: {esc(clase_came)} / {esc(clase_care)}
                    </div>
                    <div class="detalle-servicio">
                        Servicio asociado:
                        {esc(servicio_visible if servicio_valido else "No tiene")}
                    </div>
                </div>
            </section>

            <section class="seccion">
                <h3>Operaciones CAME</h3>
                {mostrar_operaciones(
                    came,
                    "CAME",
                    puesto_came,
                    precios,
                )}
            </section>

            <section class="seccion">
                <h3>Operaciones CARE</h3>
                <details class="operaciones-care-desplegable">
                    <summary>Mostrar operaciones CARE</summary>
                    {mostrar_operaciones(
                        care,
                        "CARE",
                        puesto_came,
                        precios,
                    )}
                </details>
            </section>

            <section class="seccion">
                <h3>Comparación de fotos de la ORDEN</h3>
                <div class="comparacion-fotos">
                    <div class="panel-fotos came-panel">
                        {mostrar_archivos_acta(archivos_came, "CAME")}
                    </div>
                    <div class="panel-fotos care-panel">
                        {mostrar_archivos_acta(archivos_care, "CARE / AVISO")}
                    </div>
                </div>
            </section>
        </article>
        """)

    if not tarjetas:
        tarjetas_html = """
            <div class="sin-resultados">
                No se encontraron CAMEs para mostrar.
            </div>
        """
    else:
        tarjetas_html = "".join(tarjetas)

    modal_html = """
        <div id="modal-fotos" class="modal-fotos" aria-hidden="true">
            <div class="modal-contenido" role="dialog"
                aria-modal="true" aria-labelledby="modal-titulo">
                <button id="cerrar-modal" class="cerrar-modal" type="button">
                    Cerrar
                </button>
                <h2 id="modal-titulo">Comparación de fotos</h2>
                <div id="modal-resumen-fotos" class="modal-resumen-fotos"></div>
                <div id="galeria-modal" class="galeria-modal"></div>
            </div>
        </div>
    """

    areas = sorted(
        {
            texto(came.get("Area de empresa"), "")
            for came in cames.values()
            if isinstance(came, dict)
            and texto(came.get("Area de empresa"), "")
        }
    )

    opciones_area = "\n".join(
        f'<option value="{html.escape(area)}">{html.escape(area)}</option>'
        for area in areas
    )
    clases_actividad = sorted(
        {
            texto(came.get("Clase de actividad"), "")
            for came in cames.values()
            if isinstance(came, dict)
            and texto(came.get("Clase de actividad"), "")
        }
    )
    opciones_clase_actividad = "\n".join(
        f'<option value="{html.escape(clase)}">{html.escape(clase)}</option>'
        for clase in clases_actividad
    )
    materialidades = sorted(
        {
            texto(
                cares.get(
                    came.get("CARE Asociada")
                    or came.get("CARE asociada")
                    or "",
                    {},
                ).get("Materialidad"),
                "",
            )
            for came in cames.values()
            if isinstance(came, dict)
            and isinstance(
                cares.get(
                    came.get("CARE Asociada")
                    or came.get("CARE asociada")
                    or "",
                    {},
                ),
                dict,
            )
            and texto(
                cares.get(
                    came.get("CARE Asociada")
                    or came.get("CARE asociada")
                    or "",
                    {},
                ).get("Materialidad"),
                "",
            )
        }
    )
    clases_aviso = sorted(
        {
            valor_real(
                avisos.get(
                    came.get("Aviso asociado")
                    or came.get("Aviso Asociado")
                    or "",
                    {},
                ).get("Clase de aviso")
            )
            for came in cames.values()
            if isinstance(came, dict)
            and valor_real(
                avisos.get(
                    came.get("Aviso asociado")
                    or came.get("Aviso Asociado")
                    or "",
                    {},
                ).get("Clase de aviso")
            )
        }
    )
    opciones_materialidad = "\n".join(
        f'<option value="{html.escape(valor)}">{html.escape(valor)}</option>'
        for valor in materialidades
    )
    opciones_clase_aviso = "\n".join(
        f'<option value="{html.escape(valor)}">{html.escape(valor)}</option>'
        for valor in clases_aviso
    )
    fechas_modificacion = sorted(
        {
            valor_real(came.get("Fecha modificacion"))
            for came in cames.values()
            if isinstance(came, dict)
            and valor_real(came.get("Fecha modificacion"))
        }
    )
    opciones_fecha_modificacion = "\n".join(
        f'<option value="{html.escape(valor)}">{html.escape(valor)}</option>'
        for valor in fechas_modificacion
    )
    opciones_error = "\n".join(
        f'<option value="{tipo}">{html.escape(etiqueta)}</option>'
        for tipo, etiqueta in ERROR_TIPOS
    )
    reporte_completo = generar_reporte_errores(errores_reporte)
    reporte_estilos = re.search(
        r"<style>(.*?)</style>", reporte_completo, re.DOTALL
    )
    reporte_cuerpo = re.search(
        r"<body>(.*?)</body>", reporte_completo, re.DOTALL
    )
    reporte_javascript = re.search(
        r"<script>(.*?)</script>", reporte_completo, re.DOTALL
    )
    reporte_estilos_html = reporte_estilos.group(1) if reporte_estilos else ""
    reporte_cuerpo_html = reporte_cuerpo.group(1) if reporte_cuerpo else ""
    reporte_javascript_html = (
        reporte_javascript.group(1) if reporte_javascript else ""
    )
    reporte_cuerpo_html = reporte_cuerpo_html.replace(
        'href="index.html"', 'href="#" id="volver-del-reporte"'
    )
    reporte_cuerpo_html = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        reporte_cuerpo_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    reporte_cuerpo_html = reporte_cuerpo_html.split("<script", 1)[0]

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Previsualización de actas</title>

    <style>
        {reporte_estilos_html}
        :root {{
            --fondo: #eef2f7;
            --blanco: #ffffff;
            --texto: #172033;
            --secundario: #607089;
            --azul: #2563eb;
            --azul-oscuro: #1e3a8a;
            --verde: #15803d;
            --borde: #dbe3ef;
            --sombra: 0 10px 30px rgba(15, 23, 42, 0.09);
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: var(--fondo);
            color: var(--texto);
            font-family: Arial, Helvetica, sans-serif;
        }}

        body.cargando {{
            overflow: hidden;
        }}

        .pantalla-carga {{
            position: fixed;
            inset: 0;
            z-index: 10000;
            display: grid;
            place-items: center;
            background: rgba(248, 250, 252, 0.98);
            color: var(--azul-oscuro);
            transition: opacity 180ms ease, visibility 180ms ease;
        }}

        .pantalla-carga.oculta {{
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
        }}

        .pantalla-carga-contenido {{
            width: min(420px, 84vw);
            text-align: center;
        }}

        .pantalla-carga-titulo {{
            margin: 0 0 8px;
            font-size: 22px;
            font-weight: bold;
        }}

        .estado-correccion-resumen {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 154px;
            padding: 9px 13px;
            border-radius: 999px;
            color: #172554;
            background: #fef3c7;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.18);
            font-size: 13px;
            font-weight: 800;
            text-align: center;
        }}

        .estado-correccion-resumen.estado-corregida {{
            color: #eff6ff;
            background: #2563eb;
        }}

        .estado-correccion-resumen.estado-pendiente {{
            color: #7c2d12;
            background: #fb923c;
        }}

        .estado-correccion-resumen.estado-con-errores {{
            color: #fff1f2;
            background: #dc2626;
        }}

        .estado-relacion {{
            display: inline-flex;
            align-items: center;
            margin-left: 6px;
            padding: 4px 9px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 800;
            vertical-align: middle;
        }}

        .estado-relacion.estado-corregida {{
            color: #eff6ff;
            background: #2563eb;
        }}

        .estado-relacion.estado-pendiente {{
            color: #78350f;
            background: #facc15;
        }}

        .estado-relacion.estado-con-errores {{
            color: #fff1f2;
            background: #dc2626;
        }}

        .pantalla-carga-mensaje {{
            margin: 0 0 16px;
            color: var(--secundario);
            font-size: 14px;
        }}

        .pantalla-carga-barra {{
            height: 12px;
            overflow: hidden;
            border-radius: 999px;
            background: #dbeafe;
        }}

        .pantalla-carga-progreso {{
            width: 0%;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, #2563eb, #14b8a6);
            transition: width 180ms ease;
        }}

        .pantalla-carga-porcentaje {{
            display: block;
            margin-top: 9px;
            color: var(--secundario);
            font-size: 12px;
            font-variant-numeric: tabular-nums;
        }}

        .contenedor {{
            width: min(1400px, 94%);
            margin: 0 auto;
        }}

        .cabecera {{
            padding: 34px 0 22px;
        }}

        .cabecera h1 {{
            margin: 0 0 8px;
            font-size: clamp(28px, 4vw, 48px);
            color: var(--azul-oscuro);
        }}

        .cabecera p {{
            margin: 0;
            color: var(--secundario);
            font-size: 16px;
        }}

        .fuentes-cargadas {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
            color: var(--secundario);
            font-size: 12px;
        }}

        .fuentes-cargadas span {{
            padding: 5px 9px;
            border-radius: 999px;
            font-weight: bold;
        }}

        .fuente-ok {{
            color: #166534;
            background: #dcfce7;
        }}

        .fuente-no {{
            color: #991b1b;
            background: #fee2e2;
        }}

        .cargar-datos {{
            position: relative;
            display: block;
            margin-top: 16px;
        }}

        .cargar-datos > button {{
            padding: 7px 12px;
            border-radius: 8px;
            font-size: 12px;
        }}

        .menu-cargar-datos {{
            position: absolute;
            z-index: 30;
            top: calc(100% + 6px);
            left: 0;
            display: none;
            width: 100%;
            min-width: 0;
            max-width: 100%;
            padding: 12px;
            border: 1px solid var(--borde);
            border-radius: 10px;
            background: var(--blanco);
            box-shadow: var(--sombra);
        }}

        .menu-cargar-datos.abierto {{
            display: grid;
            gap: 8px;
        }}

        .menu-cargar-datos button {{
            width: 100%;
            text-align: left;
        }}

        .menu-cargar-datos input[type="file"] {{
            display: none;
        }}

        .estado-carga-fuentes {{
            display: grid;
            gap: 3px;
            color: var(--secundario);
            font-size: 11px;
        }}

        .estado-carga-fuentes strong {{
            color: var(--texto);
        }}

        .filtros {{
            position: sticky;
            top: 12px;
            z-index: 10;
            display: grid;
            grid-template-columns: 1fr;
            gap: 12px;
            padding: 16px;
            margin: 0;
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid var(--borde);
            border-radius: 16px;
            box-shadow: var(--sombra);
            backdrop-filter: blur(10px);
            align-self: start;
            min-width: 0;
            overflow: hidden;
        }}

        .filtros input,
        .filtros select,
        .filtros button,
        .filtros a,
        .filtros .acciones-reporte,
        .filtros .cargar-datos {{
            width: 100%;
            min-width: 0;
            max-width: 100%;
        }}

        .filtros .boton-apartado {{
            grid-column: 1 / -1;
            margin: 0;
            justify-self: start;
        }}

        .visor-layout {{
            display: grid;
            grid-template-columns: 300px minmax(0, 1fr);
            gap: 24px;
            align-items: start;
        }}

        .previsualizacion {{
            min-width: 0;
        }}

        .resultados-busqueda {{
            position: absolute;
            top: calc(100% - 8px);
            left: 16px;
            right: 16px;
            z-index: 20;
            display: none;
            max-height: 300px;
            overflow-y: auto;
            border: 1px solid var(--borde);
            border-radius: 10px;
            background: white;
            box-shadow: var(--sombra);
        }}

        .resultado-busqueda {{
            display: block;
            width: 100%;
            padding: 12px 14px;
            color: var(--texto);
            border: 0;
            border-bottom: 1px solid var(--borde);
            border-radius: 0;
            background: white;
            text-align: left;
        }}

        .resultado-busqueda:hover {{
            color: white;
            background: var(--azul);
        }}

        .resultado-busqueda strong,
        .resultado-busqueda small {{
            display: block;
        }}

        .resultado-busqueda small {{
            margin-top: 4px;
            opacity: 0.75;
        }}

        .resultado-coincidencia {{
            color: var(--azul);
            font-weight: 600;
        }}

        .resultado-busqueda:hover .resultado-coincidencia {{
            color: white;
        }}

        .total-comparado-menor {{
            color: #15803d;
            font-weight: 700;
        }}

        .total-comparado-mayor {{
            color: #dc2626;
            font-weight: 700;
        }}

        input,
        select,
        button {{
            min-height: 44px;
            border: 1px solid var(--borde);
            border-radius: 10px;
            padding: 0 14px;
            font: inherit;
        }}

        input:focus,
        select:focus {{
            outline: 3px solid rgba(37, 99, 235, 0.18);
            border-color: var(--azul);
        }}

        button {{
            cursor: pointer;
            color: white;
            background: var(--azul);
            border-color: var(--azul);
            font-weight: bold;
        }}

        button:hover {{
            background: var(--azul-oscuro);
        }}

        .resumen {{
            margin-bottom: 20px;
            color: var(--secundario);
        }}

        .listado {{
            display: block;
            padding-bottom: 50px;
        }}

        .tarjeta {{
            overflow: hidden;
            background: var(--blanco);
            border: 1px solid var(--borde);
            border-radius: 18px;
            box-shadow: var(--sombra);
        }}

        .tarjeta:not(.actual) {{
            display: none;
        }}

        .navegacion-orden {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 18px;
        }}

        .navegacion-orden button {{
            min-width: 130px;
        }}

        .indicador-orden {{
            color: var(--secundario);
            font-weight: bold;
            text-align: center;
        }}

        .tarjeta-header {{
            position: relative;
            display: flex;
            justify-content: space-between;
            gap: 15px;
            padding: 20px 22px 50px;
            color: white;
            background: linear-gradient(135deg, #1e3a8a, #2563eb);
        }}

        .tarjeta-header h2 {{
            margin: 5px 0 0;
            font-size: 21px;
            line-height: 1.25;
        }}

        .titulo-came {{
            display: flex;
            flex-wrap: wrap;
            align-items: baseline;
            gap: 10px;
        }}

        .came-id {{
            font-size: 16px;
        }}

        .tarjeta-header > div:first-child {{
            flex: 1;
        }}

        .ubicacion-titulo {{
            font-size: 15px;
            opacity: 0.9;
        }}

        .materialidad-titulo {{
            margin: 12px 0 0;
            color: #dbeafe;
            font-size: 14px;
            text-align: right;
        }}

        .fechas-titulo {{
            margin-top: 8px;
            color: #dbeafe;
            font-size: 11px;
            line-height: 1.5;
            text-align: right;
            opacity: 0.85;
        }}

        .errores-titulo {{
            margin-top: 6px;
            color: #fecaca;
            font-size: 12px;
            font-weight: bold;
        }}

        .etiqueta {{
            font-size: 12px;
            font-weight: bold;
            letter-spacing: 0.08em;
            opacity: 0.8;
        }}

        .estado {{
            align-self: flex-start;
            white-space: nowrap;
            padding: 7px 10px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.18);
            font-size: 12px;
        }}

        .estado-tarjeta {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 10px;
        }}

        .estado-correccion {{
            display: grid;
            gap: 3px;
            margin: 0;
            padding: 6px 8px;
            border: 1px solid rgba(255, 255, 255, 0.35);
            border-radius: 8px;
            color: white;
            font-size: 12px;
            font-weight: bold;
        }}

        .estado-correccion legend {{
            padding: 0 3px;
            font-size: 11px;
        }}

        .estado-correccion label {{
            display: flex;
            align-items: center;
            gap: 4px;
            white-space: nowrap;
        }}

        .estado-correccion input {{
            min-height: auto;
            width: 14px;
            height: 14px;
        }}

        .check-automatico {{
            position: relative;
            border-radius: 6px;
            font-weight: bold;
            cursor: help;
        }}

        .check-automatico::after {{
            position: absolute;
            left: 0;
            bottom: calc(100% + 8px);
            z-index: 40;
            display: none;
            width: min(360px, 70vw);
            padding: 8px 10px;
            border: 1px solid #cbd5e1;
            border-radius: 7px;
            color: #1e293b;
            background: #ffffff;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.2);
            content: attr(title);
            font-size: 11px;
            font-weight: normal;
            line-height: 1.35;
            white-space: normal;
            pointer-events: none;
        }}

        .check-automatico:hover::after,
        .check-automatico:focus-within::after {{
            display: block;
        }}

        .check-automatico-ok {{
            color: #166534;
            background: #dcfce7;
        }}

        .check-automatico-error {{
            color: #991b1b;
            background: #fee2e2;
        }}

        .check-manual {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
        }}

        .check-manual-input {{
            min-width: 118px;
            padding: 4px 6px;
            border-radius: 6px;
            font-size: 11px;
        }}

        .check-manual-input {{
            border: 1px solid #94a3b8;
            color: #334155;
            background: #f1f5f9;
        }}

        .check-manual-input.estado-correcto {{
            border-color: #16a34a;
            color: #166534;
            background: #dcfce7;
        }}

        .check-manual-input.estado-incorrecto {{
            border-color: #dc2626;
            color: #991b1b;
            background: #fee2e2;
        }}

        .motivo-check-manual {{
            min-width: 0;
            max-width: 170px;
            min-height: 32px;
            padding: 0 6px;
            font-size: 11px;
        }}

        .motivo-check-manual[hidden] {{
            display: none;
        }}

        .acciones-reporte {{
            display: grid;
            gap: 8px;
            margin-top: 8px;
        }}

        .acciones-reporte button {{
            min-height: 38px;
            padding: 0 10px;
            font-size: 12px;
        }}

        .acciones-reporte a {{
            width: 100%;
            min-width: 0;
            box-sizing: border-box;
        }}

        .cantidad-archivos {{
            display: inline-block;
            padding: 5px 9px;
            color: var(--secundario);
            border: 1px solid var(--borde);
            border-radius: 6px;
            background: #f8fafc;
            font-size: 12px;
        }}

        .modal-seleccion-actas {{
            position: fixed;
            inset: 0;
            z-index: 110;
            display: none;
            overflow-y: auto;
            padding: 24px;
            background: rgba(15, 23, 42, 0.78);
        }}

        .modal-seleccion-actas.abierto {{
            display: block;
        }}

        .modal-seleccion-actas-contenido {{
            width: min(850px, 100%);
            margin: 0 auto;
            padding: 24px;
            border-radius: 16px;
            background: white;
            box-shadow: var(--sombra);
        }}

        .lista-seleccion-actas {{
            display: grid;
            max-height: 60vh;
            overflow-y: auto;
            gap: 6px;
            margin: 16px 0;
            padding: 10px;
            border: 1px solid var(--borde);
            border-radius: 10px;
            background: #f8fafc;
        }}

        .seleccion-acta {{
            display: flex;
            gap: 10px;
            align-items: center;
            padding: 8px;
            border-radius: 6px;
            background: white;
        }}

        .acciones-seleccion-actas {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .acciones-reporte a {{
            display: block;
            padding: 11px 10px;
            color: white;
            border-radius: 6px;
            background: var(--azul);
            font-size: 12px;
            text-align: center;
            text-decoration: none;
        }}

        .modal-reporte {{
            position: fixed;
            inset: 0;
            z-index: 100;
            display: none;
            align-items: center;
            justify-content: center;
            padding: 24px;
            background: rgba(15, 23, 42, 0.68);
        }}

        .modal-reporte.abierto {{
            display: flex;
        }}

        .modal-reporte-contenido {{
            position: relative;
            width: min(1600px, 96vw);
            height: min(900px, 92vh);
            overflow: hidden;
            border-radius: 16px;
            background: var(--blanco);
            box-shadow: var(--sombra);
        }}

        .modal-reporte iframe {{
            width: 100%;
            height: 100%;
            border: 0;
        }}

        .cerrar-reporte {{
            position: absolute;
            top: 10px;
            right: 12px;
            z-index: 2;
            min-height: 32px;
            padding: 0 12px;
            border-radius: 7px;
            background: #b91c1c;
            font-size: 12px;
        }}

        .acciones-reporte small {{
            min-height: 16px;
            color: var(--secundario);
            font-size: 11px;
        }}

        .relaciones {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            padding: 14px 22px;
            background: #f8fafc;
            border-bottom: 1px solid var(--borde);
        }}

        .relacion {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            min-width: 0;
        }}

        .relacion-tipo {{
            color: var(--secundario);
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }}

        .relacion strong {{
            color: var(--azul-oscuro);
        }}

        .resumen-care {{
            display: inline-flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
            padding: 9px 10px;
            color: var(--azul-oscuro);
            border: 1px solid #93c5fd;
            border-radius: 8px;
            background: #eff6ff;
            font-size: 13px;
        }}

        .relacion .boton-texto-aviso {{
            align-self: flex-start;
            width: fit-content;
            padding: 7px 10px;
            font-size: 12px;
        }}

        .relacion span:last-child {{
            overflow: hidden;
            color: var(--secundario);
            font-size: 13px;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .relacion small {{
            color: var(--secundario);
            font-size: 12px;
        }}

        .seccion {{
            padding: 18px 22px;
            border-bottom: 1px solid var(--borde);
        }}

        .seccion:last-child {{
            border-bottom: 0;
        }}

        .seccion h3 {{
            margin: 0 0 14px;
            color: var(--azul-oscuro);
            font-size: 16px;
        }}

        .titulo-seccion-con-accion {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }}

        .titulo-seccion-con-accion h3 {{
            margin-bottom: 14px;
        }}

        .checks-clase {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 18px;
        }}

        .checks-clase label {{
            display: flex;
            align-items: center;
            gap: 7px;
        }}

        .checks-clase label.check-ok {{
            color: #15803d;
            font-weight: bold;
        }}

        .checks-clase label.check-no {{
            color: #b91c1c;
            font-weight: bold;
        }}

        .checks-clase label.check-warning {{
            color: #c2410c;
            font-weight: bold;
        }}

        .checks-clase label.check-ok input {{
            accent-color: #16a34a;
        }}

        .checks-clase label.check-no input {{
            accent-color: #dc2626;
        }}

        .checks-clase label.check-warning input {{
            accent-color: #f97316;
        }}

        .checks-clase input {{
            min-height: auto;
            width: 18px;
            height: 18px;
        }}

        .checks-clase label {{
            font-size: 12px;
        }}

        .resultado-clase {{
            color: var(--verde);
        }}

        .detalle-controles {{
            flex-basis: 100%;
            color: var(--secundario);
            font-size: 13px;
        }}

        .detalle-servicio {{
            flex-basis: 100%;
            color: #8a94a6;
            font-size: 13px;
        }}

        .operaciones-controles {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
            color: var(--secundario);
            font-size: 13px;
        }}

        .filtro-operaciones {{
            min-height: 36px;
            max-width: 280px;
        }}

        .tabla-scroll {{
            overflow-x: auto;
        }}

        .operaciones-tabla {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}

        .operaciones-tabla th,
        .operaciones-tabla td {{
            padding: 10px;
            border-bottom: 1px solid var(--borde);
            text-align: left;
            vertical-align: top;
        }}

        .operaciones-tabla th {{
            color: var(--azul-oscuro);
            background: #eef4ff;
            white-space: nowrap;
        }}

        .operaciones-tabla .columna-importante {{
            background: #dbeafe;
        }}

        .orden-columna {{
            min-height: 30px;
            padding: 4px 8px;
            color: var(--azul-oscuro);
            background: transparent;
            border: 0;
            font-size: inherit;
        }}

        .operaciones-tabla tfoot th {{
            color: var(--azul-oscuro);
            background: #eef4ff;
        }}

        .servicio-link,
        .mapa-link {{
            display: inline-block;
            margin-top: 14px;
            margin-right: 12px;
            color: var(--azul);
            font-weight: bold;
            text-decoration: none;
        }}

        .campos {{
            display: grid;
            gap: 9px;
        }}

        .campo {{
            display: grid;
            grid-template-columns: 42% 58%;
            gap: 10px;
            font-size: 14px;
        }}

        .campo-label {{
            color: var(--secundario);
        }}

        .campo-valor {{
            overflow-wrap: anywhere;
            font-weight: bold;
            text-align: right;
        }}

        details {{
            margin-top: 16px;
        }}

        summary {{
            cursor: pointer;
            color: var(--azul);
            font-weight: bold;
        }}

        .texto-aviso {{
            padding-left: 20px;
            color: var(--secundario);
            font-size: 13px;
            line-height: 1.5;
        }}

        .modal-texto-aviso {{
            position: fixed;
            inset: 0;
            z-index: 110;
            display: none;
            place-items: center;
            padding: 24px;
            background: rgba(15, 23, 42, 0.7);
        }}

        .modal-texto-aviso.abierto {{
            display: grid;
        }}

        .modal-texto-aviso-contenido {{
            width: min(700px, 100%);
            max-height: 80vh;
            overflow-y: auto;
            padding: 24px;
            border-radius: 14px;
            background: white;
            box-shadow: var(--sombra);
        }}

        .cerrar-texto-aviso {{
            float: right;
        }}

        .galeria {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
            gap: 10px;
        }}

        .archivos-acta {{
            display: grid;
            gap: 16px;
        }}

        .comparacion-fotos {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
        }}

        .panel-fotos {{
            min-width: 0;
            max-height: 760px;
            overflow-y: auto;
            padding: 16px;
            border: 1px solid var(--borde);
            border-radius: 14px;
            background: #f8fafc;
        }}

        .panel-fotos h4 {{
            margin: 0 0 14px;
            color: var(--azul-oscuro);
            font-size: 18px;
        }}

        .documento-acta {{
            overflow: hidden;
            border: 1px solid var(--borde);
            border-radius: 10px;
            background: #f8fafc;
        }}

        .documento-titulo {{
            padding: 10px;
            color: var(--azul-oscuro);
            font-size: 13px;
            font-weight: bold;
        }}

        .documento-acta iframe {{
            display: block;
            width: 100%;
            height: 620px;
            border: 0;
            background: white;
        }}

        .documento-acta a,
        .archivo-pdf {{
            display: block;
            padding: 10px;
            color: var(--azul);
            font-size: 13px;
            font-weight: bold;
            text-decoration: none;
        }}

        .archivo-pdf {{
            border: 1px solid var(--borde);
            border-radius: 10px;
            background: #f8fafc;
        }}

        .boton-comparar-fotos {{
            margin: 0 0 14px;
            padding: 8px 12px;
            font-size: 12px;
        }}

        .modal-fotos {{
            position: fixed;
            inset: 0;
            z-index: 100;
            display: none;
            overflow-y: auto;
            padding: 24px;
            background: rgba(15, 23, 42, 0.92);
        }}

        .modal-fotos.abierto {{
            display: block;
        }}

        .modal-contenido {{
            width: min(1800px, 100%);
            margin: 0 auto;
            padding: 24px;
            border-radius: 18px;
            background: white;
        }}

        .modal-contenido h2 {{
            margin-top: 0;
            color: var(--azul-oscuro);
        }}

        .modal-resumen-fotos {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px 18px;
            margin: -8px 0 18px;
            color: var(--secundario);
            font-size: 13px;
        }}

        .modal-resumen-fotos strong {{
            color: var(--azul-oscuro);
        }}

        .cerrar-modal {{
            float: right;
        }}

        .galeria-modal {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 24px;
        }}

        .galeria-modal .grupo-modal {{
            min-width: 0;
            padding: 16px;
            border: 1px solid var(--borde);
            border-radius: 14px;
        }}

        .galeria-modal img {{
            display: block;
            width: 100%;
            height: auto;
            max-height: 80vh;
            object-fit: contain;
            background: #0f172a;
            cursor: zoom-in;
        }}

        .galeria-modal iframe {{
            display: block;
            width: 100%;
            height: 760px;
            border: 0;
            background: white;
        }}

        .foto-modal {{
            display: block;
            margin-bottom: 18px;
            color: var(--texto);
            text-decoration: none;
        }}

        .documento-modal {{
            margin-bottom: 18px;
            overflow: hidden;
            border: 1px solid var(--borde);
            border-radius: 10px;
        }}

        .documento-modal .documento-titulo {{
            background: #f8fafc;
        }}

        .foto {{
            overflow: hidden;
            display: block;
            color: var(--texto);
            border: 1px solid var(--borde);
            border-radius: 10px;
            text-decoration: none;
            background: #f8fafc;
        }}

        .operaciones-globales {{
            margin: 0;
            background: white;
        }}

        .operaciones-globales h2 {{
            margin-top: 0;
            color: var(--azul-oscuro);
        }}

        .boton-apartado {{
            display: block;
            margin: 24px 0 50px;
            width: fit-content;
            padding: 12px 16px;
            color: white;
            border-radius: 10px;
            background: var(--azul);
            font-weight: bold;
            text-decoration: none;
        }}

        .apartado-modal {{
            position: fixed;
            inset: 0;
            z-index: 90;
            display: none;
            overflow-y: auto;
            padding: 24px;
            background: rgba(15, 23, 42, 0.92);
        }}

        .apartado-modal.abierto {{
            display: block;
        }}

        .apartado-modal-contenido {{
            width: min(1800px, 100%);
            margin: 0 auto;
            padding: 24px;
            border-radius: 18px;
            background: white;
        }}

        .foto img {{
            display: block;
            width: 100%;
            height: 390px;
            object-fit: cover;
        }}

        .comparacion-fotos .foto img {{
            width: auto !important;
            max-width: 100%;
            height: auto !important;
            max-height: none;
            object-fit: initial;
            aspect-ratio: auto;
            background: #e2e8f0;
        }}

        .comparacion-fotos .foto {{
            display: flex;
            flex-direction: column;
            align-items: flex-start;
        }}

        .foto span {{
            display: block;
            overflow: hidden;
            padding: 7px;
            font-size: 11px;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .sin-fotos,
        .sin-datos,
        .sin-resultados {{
            padding: 14px;
            color: var(--secundario);
            border: 1px dashed var(--borde);
            border-radius: 10px;
            background: #f8fafc;
            font-size: 14px;
        }}

        .oculto {{
            display: none;
        }}

        @media (max-width: 700px) {{
            .filtros {{
                position: static;
                grid-template-columns: 1fr;
            }}

            .visor-layout {{
                grid-template-columns: 1fr;
            }}

            .comparacion-fotos {{
                grid-template-columns: 1fr;
            }}

            .filtros {{
                position: static;
            }}

            .listado {{
                grid-template-columns: 1fr;
            }}

            .comparacion-fotos {{
                grid-template-columns: 1fr;
            }}

            .relaciones {{
                grid-template-columns: 1fr;
            }}

            .campo {{
                grid-template-columns: 1fr;
                gap: 2px;
            }}

            .campo-valor {{
                text-align: left;
            }}

            .foto img {{
                height: 300px;
            }}

            .documento-acta iframe {{
                height: 480px;
            }}

            .galeria-modal {{
                grid-template-columns: 1fr;
            }}

            .galeria-modal iframe {{
                height: 560px;
            }}
        }}
    </style>
</head>

<body>
    <div id="pantalla-carga" class="pantalla-carga" role="status"
        aria-live="polite" aria-label="Cargando visor">
        <div class="pantalla-carga-contenido">
            <p class="pantalla-carga-titulo">Cargando visor</p>
            <p id="pantalla-carga-mensaje" class="pantalla-carga-mensaje">
                Preparando datos, filtros y documentos...
            </p>
            <div class="pantalla-carga-barra" role="progressbar"
                aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
                <div id="pantalla-carga-progreso"
                    class="pantalla-carga-progreso"></div>
            </div>
            <span id="pantalla-carga-porcentaje"
                class="pantalla-carga-porcentaje">0%</span>
        </div>
    </div>
    <main class="contenedor" inert>
        <header class="cabecera">
            <h1>Previsualización de actas</h1>
            <p>Relación entre CAME, CARE, avisos y fotografías.</p>
            <div class="fuentes-cargadas" aria-live="polite">
                Puesto de trabajo y renglón: {esc(resumen_puestos_renglones)}
            </div>
        </header>

        <div class="visor-layout">
        <aside class="filtros">
            <input
                id="buscador"
                type="search"
                placeholder="Buscar CAME, CARE, aviso, dirección..."
            >
            <div id="resultados-busqueda" class="resultados-busqueda"></div>

            <select id="filtro-area">
                <option value="">Área</option>
                {opciones_area}
            </select>

            <select id="filtro-clase-actividad">
                <option value="">Clase actividad</option>
                {opciones_clase_actividad}
            </select>

            <select id="filtro-materialidad">
                <option value="">Materialidad</option>
                {opciones_materialidad}
            </select>

            <select id="filtro-clase-aviso">
                <option value="">Aviso</option>
                {opciones_clase_aviso}
            </select>

            <select id="filtro-servicio">
                <option value="">Servicio</option>
                <option value="si">Con servicio asociado</option>
                <option value="no">Sin servicio asociado</option>
            </select>

            <select id="filtro-tipo-error">
                <option value="">Tipo de error</option>
                <option value="manual">Error desconocido</option>
                {opciones_error}
            </select>

            <select id="filtro-fecha-modificacion">
                <option value="">Fecha modificación</option>
                {opciones_fecha_modificacion}
            </select>

            <select id="filtro-estado-correccion">
                <option value="">Estado de corrección</option>
                <option value="no-corregida">No corregidas</option>
                <option value="pendiente-revision">Pendientes de revisión</option>
                <option value="corregida">Correctas</option>
                <option value="con-errores">Con errores</option>
            </select>

            <div class="acciones-reporte">
                <button id="abrir-reporte-errores" type="button">
                    Reporte de errores
                </button>
                <button id="abrir-registro-operaciones" type="button">
                    Registro de operaciones
                </button>
                <button id="copiar-cames-filtradas" type="button">
                    Copiar CAME filtradas
                </button>
                <button id="descargar-cames-filtradas" type="button">
                    Descargar listado CAME
                </button>
                <button id="abrir-seleccion-actas" type="button">
                    Corregir actas seleccionadas
                </button>
                <small id="resultado-listado-cames" aria-live="polite"></small>
            </div>

            <button id="limpiar" type="button">
                Limpiar filtros
            </button>

            <div class="cargar-datos">
                <button id="boton-cargar-datos" type="button">Cargar datos</button>
                <div id="menu-cargar-datos" class="menu-cargar-datos">
                    <button id="boton-cargar-archivos" type="button">Archivos</button>
                    <button id="boton-cargar-fotos" type="button">Fotos</button>
                    <input id="selector-archivos" type="file" accept=".json,application/json" multiple>
                    <input id="selector-fotos" type="file" webkitdirectory directory multiple>
                    <div class="estado-carga-fuentes" aria-live="polite">
                        <strong>Última carga disponible</strong>
                        <span id="estado-carga-archivos">{"Datos cargados" if fuentes.get("cames") or fuentes.get("cares") or fuentes.get("avisos") else "Sin archivos"}</span>
                        <span id="estado-carga-fotos">{"Fotos cargadas" if fuentes.get("actas") else "Sin fotos"}</span>
                    </div>
                </div>
            </div>
        </aside>

        <section class="previsualizacion">
        <div class="resumen">
            ORDEN <strong id="cantidad-visible">1</strong>
            de <strong id="cantidad-total">{len(tarjetas)}</strong>
        </div>

        <div class="navegacion-orden">
            <button id="anterior" type="button">← Anterior</button>
            <span id="indicador-orden" class="indicador-orden"></span>
            <button id="siguiente" type="button">Siguiente →</button>
        </div>

        <section id="listado" class="listado">
            {tarjetas_html}
        </section>
        </section>
        </div>
            {modal_html}
            <div id="modal-seleccion-actas" class="modal-seleccion-actas"
                aria-hidden="true">
                <div class="modal-seleccion-actas-contenido" role="dialog"
                    aria-modal="true" aria-labelledby="titulo-seleccion-actas">
                    <button id="cerrar-seleccion-actas" class="cerrar-modal"
                        type="button">Cerrar</button>
                    <h2 id="titulo-seleccion-actas">Seleccionar actas</h2>
                    <p>
                        Seleccioná las actas que quieras marcar como corregidas.
                        Se establecerán todos sus checks como correctos.
                    </p>
                    <div class="acciones-seleccion-actas">
                        <button id="seleccionar-todas-actas" type="button">
                            Seleccionar todas
                        </button>
                        <button id="deseleccionar-todas-actas" type="button">
                            Deseleccionar todas
                        </button>
                    </div>
                    <div id="lista-seleccion-actas" class="lista-seleccion-actas"></div>
                    <button id="aplicar-seleccion-actas" type="button">
                        Marcar seleccionadas como corregidas
                    </button>
                    <small id="resultado-seleccion-actas" aria-live="polite"></small>
                </div>
            </div>
            <div id="modal-reporte" class="modal-reporte" aria-hidden="true">
                <div class="modal-reporte-contenido" role="dialog"
                    aria-modal="true" aria-label="Reporte">
                    <button id="cerrar-reporte" class="cerrar-reporte" type="button">
                        Cerrar
                    </button>
                    <div id="reporte-embebido">{reporte_cuerpo_html}</div>
                </div>
            </div>
    </main>

    <script>
        (() => {{
            {reporte_javascript_html}
        }})();
    </script>
    <script>
        document.body.classList.add("cargando");
        const pantallaCarga = document.getElementById("pantalla-carga");
        const progresoCarga = document.getElementById("pantalla-carga-progreso");
        const porcentajeCarga = document.getElementById(
            "pantalla-carga-porcentaje",
        );
        const mensajeCarga = document.getElementById("pantalla-carga-mensaje");
        const barraCarga = pantallaCarga?.querySelector('[role="progressbar"]');

        function actualizarCarga(porcentaje, mensaje) {{
            const valor = Math.max(0, Math.min(100, porcentaje));
            if (progresoCarga) {{
                progresoCarga.style.width = `${{valor}}%`;
            }}
            if (porcentajeCarga) {{
                porcentajeCarga.textContent = `${{valor}}%`;
            }}
            if (barraCarga) {{
                barraCarga.setAttribute("aria-valuenow", String(valor));
            }}
            if (mensajeCarga && mensaje) {{
                mensajeCarga.textContent = mensaje;
            }}
        }}

        function finalizarCarga() {{
            actualizarCarga(100, "Visor listo.");
            window.setTimeout(() => {{
                document.querySelector("main")?.removeAttribute("inert");
                document.body.classList.remove("cargando");
                pantallaCarga?.classList.add("oculta");
            }}, 50);
        }}

        actualizarCarga(15, "Preparando datos, filtros y documentos...");
        function completarCargaInicial() {{
            actualizarCarga(85, "Verificando que el archivo terminó de cargarse...");
            window.setTimeout(() => {{
                actualizarCarga(95, "Aplicando la configuración inicial...");
                window.setTimeout(finalizarCarga, 50);
            }}, 50);
        }}
        document.addEventListener("keydown", (evento) => {{
            if (document.body.classList.contains("cargando")) {{
                evento.preventDefault();
                evento.stopImmediatePropagation();
            }}
        }}, true);
        if (document.readyState === "loading") {{
            document.addEventListener(
                "DOMContentLoaded",
                completarCargaInicial,
                {{ once: true }},
            );
        }} else {{
            completarCargaInicial();
        }}

        const buscador = document.getElementById("buscador");
        const filtroArea = document.getElementById("filtro-area");
        const filtroClaseActividad = document.getElementById(
            "filtro-clase-actividad",
        );
        const filtroMaterialidad = document.getElementById(
            "filtro-materialidad",
        );
        const filtroClaseAviso = document.getElementById(
            "filtro-clase-aviso",
        );
        const filtroServicio = document.getElementById("filtro-servicio");
        const filtroTipoError = document.getElementById("filtro-tipo-error");
        const filtroFechaModificacion = document.getElementById(
            "filtro-fecha-modificacion",
        );
        const filtroEstadoCorreccion = document.getElementById(
            "filtro-estado-correccion",
        );
        const botonLimpiar = document.getElementById("limpiar");
        const copiarCamesFiltradas = document.getElementById(
            "copiar-cames-filtradas",
        );
        const descargarCamesFiltradas = document.getElementById(
            "descargar-cames-filtradas",
        );
        const resultadoListadoCames = document.getElementById(
            "resultado-listado-cames",
        );
        const resultadosBusqueda = document.getElementById("resultados-busqueda");
        const filtroOperacionesGlobal = document.getElementById(
            "filtro-operaciones-global",
        );
        const filtrosOperacionesGlobales = [
            filtroOperacionesGlobal,
            document.getElementById("filtro-area-operaciones"),
            document.getElementById("filtro-clase-operaciones"),
            document.getElementById("filtro-unidad-operaciones"),
        ].filter(Boolean);
        const tablaOperacionesGlobal = document.getElementById(
            "tabla-operaciones-global",
        );
        const abrirOperacionesGlobales = document.getElementById(
            "abrir-operaciones-globales",
        );
        const cerrarOperacionesGlobales = document.getElementById(
            "cerrar-operaciones-globales",
        );
        const apartadoOperacionesGlobales = document.getElementById(
            "apartado-operaciones-globales",
        );
        const tarjetas = Array.from(document.querySelectorAll(".tarjeta"));
        const cantidadVisible = document.getElementById("cantidad-visible");
        const indicadorOrden = document.getElementById("indicador-orden");
        const botonAnterior = document.getElementById("anterior");
        const botonSiguiente = document.getElementById("siguiente");
        const modalFotos = document.getElementById("modal-fotos");
        const galeriaModal = document.getElementById("galeria-modal");
        const modalResumenFotos = document.getElementById(
            "modal-resumen-fotos",
        );
        const cerrarModal = document.getElementById("cerrar-modal");
        const modalReporte = document.getElementById("modal-reporte");
        const cerrarReporte = document.getElementById("cerrar-reporte");
        const abrirReporteErrores = document.getElementById(
            "abrir-reporte-errores",
        );
        const abrirRegistroOperaciones = document.getElementById(
            "abrir-registro-operaciones",
        );
        const modalSeleccionActas = document.getElementById(
            "modal-seleccion-actas",
        );
        const listaSeleccionActas = document.getElementById(
            "lista-seleccion-actas",
        );
        const resultadoSeleccionActas = document.getElementById(
            "resultado-seleccion-actas",
        );
        let tarjetasFiltradas = tarjetas;
        let indiceActual = 0;
        const claveEstadosCorreccion = "visor-actas-estados-correccion";
        const claveChecksOrden = "visor-actas-checks-orden";

        function abrirReporte(titulo) {{
            if (!modalReporte) {{
                return;
            }}
            modalReporte.classList.add("abierto");
            modalReporte.setAttribute("aria-hidden", "false");
            cerrarReporte?.focus();
        }}

        function cerrarReporteModal() {{
            if (!modalReporte) {{
                return;
            }}
            modalReporte.classList.remove("abierto");
            modalReporte.setAttribute("aria-hidden", "true");
        }}

        abrirReporteErrores?.addEventListener("click", () => {{
            abrirReporte("Reporte de errores");
        }});
        abrirRegistroOperaciones?.addEventListener("click", () => {{
            window.open("operaciones.html", "_blank", "noopener");
        }});
        cerrarReporte?.addEventListener("click", cerrarReporteModal);
        modalReporte?.addEventListener("click", (evento) => {{
            if (evento.target === modalReporte) {{
                cerrarReporteModal();
            }}
        }});
        document.getElementById("volver-del-reporte")?.addEventListener(
            "click",
            (evento) => {{
                evento.preventDefault();
                cerrarReporteModal();
            }},
        );
        document.getElementById("abrir-seleccion-actas")?.addEventListener(
            "click",
            abrirSeleccionActas,
        );
        document.getElementById("cerrar-seleccion-actas")?.addEventListener(
            "click",
            cerrarSeleccionActas,
        );
        document.getElementById("seleccionar-todas-actas")?.addEventListener(
            "click",
            () => {{
                listaSeleccionActas?.querySelectorAll(
                    'input[type="checkbox"]',
                ).forEach((checkbox) => {{
                    checkbox.checked = true;
                }});
            }},
        );
        document.getElementById("deseleccionar-todas-actas")?.addEventListener(
            "click",
            () => {{
                listaSeleccionActas?.querySelectorAll(
                    'input[type="checkbox"]',
                ).forEach((checkbox) => {{
                    checkbox.checked = false;
                }});
            }},
        );
        document.getElementById("aplicar-seleccion-actas")?.addEventListener(
            "click",
            aplicarSeleccionActas,
        );
        modalSeleccionActas?.addEventListener("click", (evento) => {{
            if (evento.target === modalSeleccionActas) {{
                cerrarSeleccionActas();
            }}
        }});
        function actualizarReporteEmbebido() {{
            window.dispatchEvent(new Event("visor-actas-reporte-actualizar"));
        }}

        function cargarListaSeleccionActas() {{
            if (!listaSeleccionActas) {{
                return;
            }}
            listaSeleccionActas.innerHTML = "";
            tarjetas
                .slice()
                .sort((a, b) =>
                    (Number(a.dataset.acta) || 0) - (Number(b.dataset.acta) || 0)
                )
                .forEach((tarjeta) => {{
                    const etiqueta = document.createElement("label");
                    etiqueta.className = "seleccion-acta";
                    const checkbox = document.createElement("input");
                    checkbox.type = "checkbox";
                    checkbox.dataset.came = tarjeta.dataset.cameId || "";
                    const textoActa = tarjeta.dataset.acta
                        ? `Acta ${{tarjeta.dataset.acta}}`
                        : `Acta sin número · ${{tarjeta.dataset.textoBreve
                            || "sin Texto Breve"}}`;
                    const textoCame = tarjeta.dataset.cameId
                        ? ` · CAME ${{tarjeta.dataset.cameId}}`
                        : "";
                    etiqueta.append(
                        checkbox,
                        `${{textoActa}}${{textoCame}}`,
                    );
                    listaSeleccionActas.appendChild(etiqueta);
                }});
        }}

        function abrirSeleccionActas() {{
            cargarListaSeleccionActas();
            modalSeleccionActas?.classList.add("abierto");
            modalSeleccionActas?.setAttribute("aria-hidden", "false");
        }}

        function cerrarSeleccionActas() {{
            modalSeleccionActas?.classList.remove("abierto");
            modalSeleccionActas?.setAttribute("aria-hidden", "true");
        }}

        function establecerTodosLosChecksCorrectos(tarjeta) {{
            const cameId = tarjeta.dataset.cameId;
            const checks = {{}};
            tarjeta.querySelectorAll(".check-automatico-input").forEach(
                (check) => {{
                    check.checked = true;
                    checks[check.dataset.check] = true;
                }},
            );
            tarjeta.querySelectorAll(".check-manual-input").forEach(
                (check) => {{
                    check.dataset.estado = "correcto";
                    checks[check.dataset.check] = "correcto";
                }},
            );
            tarjeta.querySelectorAll(".motivo-check-manual").forEach(
                (motivo) => {{
                    motivo.value = "";
                    checks[motivo.dataset.motivo] = "";
                }},
            );
            checksOrden[cameId] = checks;
            guardarChecksOrden(checksOrden);
            actualizarVisualesChecks(tarjeta);
            actualizarEstadoPorChecks(tarjeta, cameId);
        }}

        function aplicarSeleccionActas() {{
            const seleccionadas = Array.from(
                listaSeleccionActas?.querySelectorAll(
                    'input[type="checkbox"]:checked',
                ) || [],
            );
            seleccionadas.forEach((checkbox) => {{
                const tarjeta = tarjetas.find(
                    (elemento) => elemento.dataset.cameId === checkbox.dataset.came,
                );
                if (tarjeta) {{
                    establecerTodosLosChecksCorrectos(tarjeta);
                }}
            }});
            if (seleccionadas.length) {{
                actualizarReporteEmbebido();
                aplicarFiltros();
            }}
            if (resultadoSeleccionActas) {{
                resultadoSeleccionActas.textContent =
                    `${{seleccionadas.length}} acta(s) marcada(s) como corregida(s).`;
            }}
            cargarListaSeleccionActas();
        }}
        const botonCargarDatos = document.getElementById("boton-cargar-datos");
        const menuCargarDatos = document.getElementById("menu-cargar-datos");
        const botonCargarArchivos = document.getElementById("boton-cargar-archivos");
        const botonCargarFotos = document.getElementById("boton-cargar-fotos");
        const selectorArchivos = document.getElementById("selector-archivos");
        const selectorFotos = document.getElementById("selector-fotos");
        const estadoCargaArchivos = document.getElementById("estado-carga-archivos");
        const estadoCargaFotos = document.getElementById("estado-carga-fotos");

        botonCargarDatos?.addEventListener("click", (evento) => {{
            evento.stopPropagation();
            menuCargarDatos?.classList.toggle("abierto");
        }});

        menuCargarDatos?.addEventListener("click", (evento) => {{
            evento.stopPropagation();
        }});

        document.addEventListener("click", () => {{
            menuCargarDatos?.classList.remove("abierto");
        }});

        botonCargarArchivos?.addEventListener("click", () => {{
            selectorArchivos?.click();
        }});

        botonCargarFotos?.addEventListener("click", () => {{
            selectorFotos?.click();
        }});

        selectorArchivos?.addEventListener("change", () => {{
            const archivos = Array.from(selectorArchivos.files || []);
            if (archivos.length > 3) {{
                alert("Podés seleccionar como máximo 3 archivos JSON.");
                selectorArchivos.value = "";
                return;
            }}
            if (!archivos.length) {{
                return;
            }}
            Promise.all(archivos.map((archivo) => archivo.text()))
                .then((contenidos) => {{
                    const puestosRenglones = new Set();
                    contenidos.forEach((contenido) => {{
                        const datos = JSON.parse(contenido);
                        Object.values(datos || {{}}).forEach((registro) => {{
                            if (!registro || typeof registro !== "object") {{
                                return;
                            }}
                            const textoBreve = String(registro["Texto Breve"] || "");
                            const coincidencia = textoBreve.match(
                                /^(.+?)_(R\d+)(?:_|$)/i,
                            );
                            if (coincidencia) {{
                                puestosRenglones.add(
                                    `${{coincidencia[1].toUpperCase()}} · `
                                    + `Renglón ${{coincidencia[2].slice(1).toUpperCase()}}`,
                                );
                            }}
                        }});
                    }});
                    const textoCarga =
                        `Puesto de trabajo y renglón: `
                        + `${{[...puestosRenglones].join(", ") || "ninguno"}}`;
                    if (estadoCargaArchivos) {{
                        estadoCargaArchivos.textContent = textoCarga;
                    }}
                    try {{
                        localStorage.setItem(
                            "visor-actas-ultima-carga-archivos",
                            textoCarga,
                        );
                    }} catch (error) {{
                        console.warn("No se pudo guardar la última selección.", error);
                    }}
                }})
                .catch((error) => {{
                    alert("No se pudieron leer los archivos seleccionados.");
                    console.warn("Error leyendo JSON seleccionado.", error);
                }});
        }});

        selectorFotos?.addEventListener("change", () => {{
            const archivos = Array.from(selectorFotos.files || []);
            if (!archivos.length) {{
                return;
            }}
            const texto = `${{archivos.length}} archivo(s) de la carpeta seleccionada`;
            if (estadoCargaFotos) {{
                estadoCargaFotos.textContent = texto;
            }}
            try {{
                localStorage.setItem("visor-actas-ultima-carga-fotos", texto);
            }} catch (error) {{
                console.warn("No se pudo guardar la última selección de fotos.", error);
            }}
        }});

        try {{
            const ultimaCargaArchivos = localStorage.getItem(
                "visor-actas-ultima-carga-archivos",
            );
            const ultimaCargaFotos = localStorage.getItem(
                "visor-actas-ultima-carga-fotos",
            );
            if (ultimaCargaArchivos && estadoCargaArchivos) {{
                estadoCargaArchivos.textContent = ultimaCargaArchivos;
            }}
            if (ultimaCargaFotos && estadoCargaFotos) {{
                estadoCargaFotos.textContent = ultimaCargaFotos;
            }}
        }} catch (error) {{
            console.warn("No se pudo recuperar la última carga.", error);
        }}

        function cargarEstadosCorreccion() {{
            try {{
                const estados = JSON.parse(
                    localStorage.getItem(claveEstadosCorreccion) || "{{}}",
                );
                return estados && typeof estados === "object" ? estados : {{}};
            }} catch (error) {{
                console.warn("No se pudieron cargar los estados de corrección.", error);
                return {{}};
            }}
        }}

        function guardarEstadosCorreccion(estados) {{
            try {{
                localStorage.setItem(
                    claveEstadosCorreccion,
                    JSON.stringify(estados),
                );
            }} catch (error) {{
                console.warn("No se pudo guardar el estado de corrección.", error);
            }}
        }}

        function cargarChecksOrden() {{
            try {{
                const checks = JSON.parse(
                    localStorage.getItem(claveChecksOrden) || "{{}}",
                );
                return checks && typeof checks === "object" ? checks : {{}};
            }} catch (error) {{
                console.warn("No se pudieron cargar los checks.", error);
                return {{}};
            }}
        }}

        function guardarChecksOrden(checks) {{
            try {{
                localStorage.setItem(claveChecksOrden, JSON.stringify(checks));
            }} catch (error) {{
                console.warn("No se pudieron guardar los checks.", error);
            }}
        }}

        const estadosCorreccion = cargarEstadosCorreccion();
        const checksOrden = cargarChecksOrden();
        const claveMigracionMaterialidad = (
            "visor-actas-materialidad-normalizada-v2"
        );
        try {{
            if (!localStorage.getItem(claveMigracionMaterialidad)) {{
                Object.values(checksOrden).forEach((checks) => {{
                    if (checks && typeof checks === "object") {{
                        delete checks.materialidad;
                    }}
                }});
                guardarChecksOrden(checksOrden);
                localStorage.setItem(claveMigracionMaterialidad, "1");
            }}
        }} catch (error) {{
            console.warn(
                "No se pudo actualizar la validación de materialidad.",
                error,
            );
        }}

        function actualizarIndicadoresEstado(tarjeta) {{
            const estado = tarjeta.dataset.estadoCorreccion
                || "pendiente-revision";
            const configuracion = {{
                "no-corregida": {{
                    clase: "estado-pendiente",
                    texto: "Pendiente de revisión",
                }},
                "pendiente-revision": {{
                    clase: "estado-pendiente",
                    texto: "Pendiente de revisión",
                }},
                corregida: {{
                    clase: "estado-corregida",
                    texto: "Corregida",
                }},
                "con-errores": {{
                    clase: "estado-con-errores",
                    texto: "Con errores",
                }},
            }}[estado] || {{
                clase: "estado-pendiente",
                texto: "Pendiente de revisión",
            }};
            tarjeta.querySelectorAll("[data-estado-indicador]").forEach(
                (indicador) => {{
                    indicador.classList.remove(
                        "estado-pendiente",
                        "estado-corregida",
                        "estado-con-errores",
                    );
                    indicador.classList.add(configuracion.clase);
                    indicador.textContent = configuracion.texto;
                }},
            );
        }}

        function actualizarVisualesChecks(tarjeta) {{
            tarjeta.querySelectorAll(".check-automatico").forEach((etiqueta) => {{
                const check = etiqueta.querySelector(".check-automatico-input");
                etiqueta.classList.toggle(
                    "check-automatico-ok",
                    Boolean(check?.checked),
                );
                etiqueta.classList.toggle(
                    "check-automatico-error",
                    Boolean(check && !check.checked),
                );
            }});
            tarjeta.querySelectorAll(".check-manual-input").forEach((boton) => {{
                const estado = boton.dataset.estado || "pendiente";
                boton.classList.remove(
                    "estado-pendiente",
                    "estado-correcto",
                    "estado-incorrecto",
                );
                boton.classList.add(`estado-${{estado}}`);
                boton.textContent = estado[0].toUpperCase() + estado.slice(1);
                const motivo = boton
                    .closest(".check-manual")
                    ?.querySelector(".motivo-check-manual");
                if (motivo) {{
                    motivo.hidden = estado !== "incorrecto";
                }}
            }});
        }}

        function actualizarEstadoPorChecks(tarjeta, cameId) {{
            const checks = checksOrden[cameId] || {{}};
            const automaticos = Array.from(
                tarjeta.querySelectorAll(".check-automatico-input"),
            );
            const manuales = Array.from(
                tarjeta.querySelectorAll(".check-manual-input"),
            );
            const automaticosConError = automaticos.filter(
                (check) => !check.checked,
            );
            const manualesIncorrectos = manuales.filter(
                (check) => check.dataset.estado === "incorrecto",
            );
            const manualesPendientes = manuales.filter(
                (check) => check.dataset.estado === "pendiente",
            );
            const clavesSuperadas = new Set(
                automaticos
                    .filter((check) => check.checked)
                    .map((check) => check.dataset.check),
            );
            if (clavesSuperadas.has("clase")) {{
                [
                    "clase",
                    "servicio",
                    "duracion_g13",
                    "duracion_g05",
                    "items_g11",
                    "items_7_fuera_g11",
                ].forEach((clave) => clavesSuperadas.add(clave));
            }}
            const tiposBase = (tarjeta.dataset.tiposErrorBase || "")
                .split(",")
                .filter((tipo) => tipo && !clavesSuperadas.has(tipo));
            const hayErrores = automaticosConError.length
                || manualesIncorrectos.length
                || tiposBase.length;
            tarjeta.dataset.checkPendiente = manualesPendientes.length
                ? "si"
                : "no";
            tarjeta.dataset.tieneErrores = (
                hayErrores
            ) ? "si" : "no";
            tarjeta.dataset.tiposError = [
                ...tiposBase,
                ...(automaticosConError.length ? ["check"] : []),
                ...(manualesIncorrectos.length ? ["manual"] : []),
            ].join(",");
            tarjeta.dataset.estadoCorreccion = hayErrores
                ? "con-errores"
                : manualesPendientes.length
                    ? "pendiente-revision"
                    : "corregida";
            actualizarIndicadoresEstado(tarjeta);
            estadosCorreccion[cameId] = tarjeta.dataset.estadoCorreccion;
            guardarEstadosCorreccion(estadosCorreccion);
            tarjeta.querySelectorAll('input[name^="estado-"]').forEach(
                (selector) => {{
                    selector.checked = selector.value
                        === tarjeta.dataset.estadoCorreccion;
                    selector.disabled = true;
                }},
            );
        }}

        function aplicarEstadoManual(tarjeta, estado) {{
            const tiposAutomaticos = tarjeta.dataset.tiposErrorBase || "";
            const marcadaComoError = estado === "con-errores";
            tarjeta.dataset.tieneErrores = (
                marcadaComoError || tiposAutomaticos
            ) ? "si" : "no";
            tarjeta.dataset.tiposError = tiposAutomaticos;
            if (marcadaComoError) {{
                tarjeta.dataset.tiposError = tiposAutomaticos
                    ? `${{tiposAutomaticos}},manual`
                    : "manual";
            }}
        }}

        tarjetas.forEach((tarjeta) => {{
            const cameId = tarjeta.dataset.cameId;
            const estado = [
                "no-corregida",
                "corregida",
                "con-errores",
            ].includes(estadosCorreccion[cameId])
                ? estadosCorreccion[cameId]
                : "no-corregida";
            tarjeta.dataset.estadoCorreccion = estado;
            aplicarEstadoManual(tarjeta, estado);
            const checkInputs = Array.from(tarjeta.querySelectorAll(
                ".check-automatico-input, .check-manual-input",
            ));
            const checksGuardados = checksOrden[cameId] || {{}};
            checkInputs.forEach((check) => {{
                if (Object.prototype.hasOwnProperty.call(
                    checksGuardados,
                    check.dataset.check,
                )) {{
                    const valorGuardado = checksGuardados[check.dataset.check];
                    if (check.classList.contains("check-manual-input")) {{
                        check.dataset.estado = valorGuardado === true
                            ? "correcto"
                            : valorGuardado === false
                                ? "pendiente"
                                : ["pendiente", "correcto", "incorrecto"].includes(
                                    valorGuardado,
                                )
                                    ? valorGuardado
                                    : "pendiente";
                    }} else {{
                        check.checked = valorGuardado === true;
                    }}
                }}
            }});
            const selectores = Array.from(tarjeta.querySelectorAll(
                'input[name^="estado-"]',
            ));
            actualizarEstadoPorChecks(tarjeta, cameId);
            actualizarVisualesChecks(tarjeta);
            selectores.forEach((selector) => {{
                selector.checked = selector.value
                    === tarjeta.dataset.estadoCorreccion;
                selector.disabled = true;
            }});
            checkInputs.forEach((check) => {{
                check.addEventListener("change", () => {{
                    if (
                        check.classList.contains("check-automatico-input")
                        && !window.confirm(
                            "¿Confirmás cambiar el resultado de este check automático?"
                        )
                    ) {{
                        check.checked = !check.checked;
                        actualizarVisualesChecks(tarjeta);
                        return;
                    }}
                    checksOrden[cameId] = {{
                        ...(checksOrden[cameId] || {{}}),
                        ...Object.fromEntries(
                            checkInputs.map((entrada) => [
                                entrada.dataset.check,
                                entrada.classList.contains("check-manual-input")
                                    ? entrada.dataset.estado
                                    : entrada.checked,
                            ]),
                        ),
                    }};
                    guardarChecksOrden(checksOrden);
                    actualizarEstadoPorChecks(tarjeta, cameId);
                    guardarEstadosCorreccion(estadosCorreccion);
                    actualizarReporteEmbebido();
                    aplicarFiltros(cameId);
                }});
            }});
            tarjeta.querySelectorAll(".check-manual-input").forEach((boton) => {{
                boton.addEventListener("click", () => {{
                    const estados = ["pendiente", "correcto", "incorrecto"];
                    const actual = boton.dataset.estado || "pendiente";
                    boton.dataset.estado = estados[
                        (estados.indexOf(actual) + 1) % estados.length
                    ];
                    actualizarVisualesChecks(tarjeta);
                    boton.dispatchEvent(new Event("change", {{ bubbles: true }}));
                }});
            }});
            tarjeta.querySelectorAll(".motivo-check-manual").forEach((motivo) => {{
                const valorGuardado = checksGuardados[motivo.dataset.motivo];
                if (typeof valorGuardado === "string") {{
                    motivo.value = valorGuardado;
                }}
                motivo.addEventListener("change", () => {{
                    checksOrden[cameId] = {{
                        ...(checksOrden[cameId] || {{}}),
                        [motivo.dataset.motivo]: motivo.value,
                    }};
                    guardarChecksOrden(checksOrden);
                    actualizarReporteEmbebido();
                }});
            }});
            selectores.forEach((selector) => {{
                selector.checked = selector.value
                    === tarjeta.dataset.estadoCorreccion;
            }});
        }});

        function mostrarResultadosBusqueda() {{
            if (!buscador || !resultadosBusqueda) {{
                return;
            }}
            const termino = buscador.value.trim().toLowerCase();
            resultadosBusqueda.innerHTML = "";

            if (!termino) {{
                resultadosBusqueda.style.display = "none";
                return;
            }}

            tarjetasFiltradas.forEach((tarjeta) => {{
                const contenidoOriginal = tarjeta.dataset.busqueda || "";
                const contenido = contenidoOriginal.toLowerCase();
                const posicionCoincidencia = contenido.indexOf(termino);
                if (posicionCoincidencia < 0) {{
                    return;
                }}

                const resultado = document.createElement("button");
                resultado.type = "button";
                resultado.className = "resultado-busqueda";
                const titulo = tarjeta.querySelector("h2");
                if (!titulo) {{
                    return;
                }}
                resultado.textContent = "";
                const tituloResultado = document.createElement("strong");
                tituloResultado.textContent = titulo.textContent;
                resultado.append(tituloResultado);
                const coincidencia = document.createElement("small");
                coincidencia.className = "resultado-coincidencia";
                let textoCoincidente = contenidoOriginal;
                try {{
                    const campos = JSON.parse(
                        tarjeta.dataset.busquedaDetalle || "[]"
                    );
                    const campoCoincidente = campos.find((campo) =>
                        campo.toLowerCase().includes(termino)
                    );
                    if (campoCoincidente) {{
                        textoCoincidente = campoCoincidente;
                    }}
                }} catch (error) {{
                    textoCoincidente = contenidoOriginal;
                }}
                coincidencia.textContent =
                    "Coincide: " +
                    textoCoincidente;
                resultado.append(coincidencia);
                resultado.addEventListener("click", () => {{
                    tarjetasFiltradas = tarjetas.filter((item) =>
                        item === tarjeta
                    );
                    indiceActual = 0;
                    mostrarOrdenActual();
                    resultadosBusqueda.style.display = "none";
                    buscador.value = termino;
                }});
                resultadosBusqueda.appendChild(resultado);
            }});

            resultadosBusqueda.style.display = resultadosBusqueda.children.length
                ? "block"
                : "none";
        }}

        const filtrosOrden = [
            [filtroArea, "area"],
            [filtroClaseActividad, "claseActividad"],
            [filtroMaterialidad, "materialidad"],
            [filtroClaseAviso, "claseAviso"],
            [filtroServicio, "tieneServicio"],
            [filtroTipoError, "tiposError"],
            [filtroFechaModificacion, "fechaModificacion"],
            [filtroEstadoCorreccion, "estadoCorreccion"],
        ];

        function coincideConFiltros(tarjeta, excluir) {{
            const termino = (buscador.value || "").trim().toLowerCase();
            if (
                termino &&
                !(tarjeta.dataset.busqueda || "").toLowerCase().includes(termino)
            ) {{
                return false;
            }}

            return filtrosOrden.every(([filtro, atributo]) => {{
                if (!filtro || filtro === excluir || !filtro.value) {{
                    return true;
                }}
                const valor = filtro.value.trim().toLowerCase();
                const dato = (tarjeta.dataset[atributo] || "").toLowerCase();
                return atributo === "tiposError"
                    ? dato.split(",").includes(valor)
                    : dato === valor;
            }});
        }}

        function actualizarOpcionesDependientes() {{
            filtrosOrden.forEach(([filtro, atributo]) => {{
                if (!filtro) {{
                    return;
                }}
                const valorActual = filtro.value;
                const valoresDisponibles = new Set(
                    tarjetas
                        .filter((tarjeta) => coincideConFiltros(tarjeta, filtro))
                        .flatMap((tarjeta) =>
                            atributo === "tiposError"
                                ? (tarjeta.dataset[atributo] || "").split(",")
                                : [tarjeta.dataset[atributo] || ""]
                        )
                        .filter(Boolean)
                        .map((valor) => valor.toLowerCase()),
                );
                Array.from(filtro.options).forEach((opcion) => {{
                    if (opcion.value) {{
                        opcion.hidden = !valoresDisponibles.has(
                            opcion.value.toLowerCase(),
                        );
                    }}
                }});
                if (
                    valorActual &&
                    !valoresDisponibles.has(valorActual.toLowerCase())
                ) {{
                    filtro.value = "";
                }}
            }});
        }}

        function aplicarFiltros(mantenerCameId = null) {{
            if (!buscador || filtrosOrden.some(([filtro]) => !filtro)) {{
                return;
            }}
            actualizarOpcionesDependientes();
            tarjetasFiltradas = tarjetas.filter((tarjeta) =>
                coincideConFiltros(tarjeta, null)
            );
            const indiceMantenido = mantenerCameId
                ? tarjetasFiltradas.findIndex(
                    (tarjeta) => tarjeta.dataset.cameId === mantenerCameId,
                )
                : -1;
            indiceActual = indiceMantenido >= 0 ? indiceMantenido : 0;
            mostrarOrdenActual();
            mostrarResultadosBusqueda();
            actualizarListadoCames();
        }}

        function obtenerListadoCames() {{
            return tarjetasFiltradas
                .map((tarjeta) => tarjeta.dataset.cameId)
                .filter(Boolean)
                .join("\\n");
        }}

        function informarResultadoListado(mensaje) {{
            if (!resultadoListadoCames) {{
                return;
            }}
            resultadoListadoCames.textContent = mensaje;
            window.setTimeout(() => {{
                resultadoListadoCames.textContent = "";
            }}, 3000);
        }}

        function actualizarListadoCames() {{
            if (!resultadoListadoCames) {{
                return;
            }}
            resultadoListadoCames.textContent =
                `${{tarjetasFiltradas.length}} CAME(s) en el filtro actual`;
        }}

        async function copiarListadoCames() {{
            const listado = obtenerListadoCames();
            if (!listado) {{
                informarResultadoListado("No hay CAMEs en el filtro actual.");
                return;
            }}
            try {{
                if (!navigator.clipboard) {{
                    throw new Error("Portapapeles no disponible en este archivo local.");
                }}
                await navigator.clipboard.writeText(listado);
                informarResultadoListado(
                    `${{tarjetasFiltradas.length}} CAME(s) copiadas.`,
                );
            }} catch (error) {{
                const auxiliar = document.createElement("textarea");
                auxiliar.value = listado;
                document.body.appendChild(auxiliar);
                auxiliar.select();
                const copiado = document.execCommand("copy");
                auxiliar.remove();
                informarResultadoListado(
                    copiado
                        ? `${{tarjetasFiltradas.length}} CAME(s) copiadas.`
                        : "No se pudo copiar el listado.",
                );
            }}
        }}

        function descargarListadoCames() {{
            const listado = obtenerListadoCames();
            if (!listado) {{
                informarResultadoListado("No hay CAMEs en el filtro actual.");
                return;
            }}
            const tarjetaBase = tarjetasFiltradas[0];
            const textoBreve = tarjetaBase?.dataset.textoBreve || "";
            const partesTextoBreve = textoBreve.match(
                /^(.+?)_(R\d+)(?:_.*)?_CERT[_-]?([^_ ]+)/i,
            );
            const limpiarNombre = (valor, reemplazo) =>
                String(valor || reemplazo)
                    .trim()
                    .replace(/[<>:"/\\|?*]+/g, "-")
                    .replace(/\s+/g, "-")
                    .replace(/-+/g, "-");
            const puesto = partesTextoBreve?.[1] || "puesto";
            const renglon = partesTextoBreve?.[2] || "renglon";
            const certificado = partesTextoBreve?.[3] || "certificado";
            const filtrosActivos = [
                buscador?.value,
                filtroArea?.value,
                filtroClaseActividad?.value,
                filtroMaterialidad?.value,
                filtroClaseAviso?.value,
                filtroServicio?.value,
                filtroTipoError?.value,
                filtroFechaModificacion?.value,
                filtroEstadoCorreccion?.value,
            ].filter(Boolean);
            const tipoFiltro = filtrosActivos.length
                ? filtrosActivos.join("-")
                : "todos";
            const sufijoListado = filtrosActivos.length
                ? limpiarNombre(tipoFiltro, "filtro")
                : "listadocompleto";
            const nombreArchivo = [
                limpiarNombre(puesto, "puesto"),
                limpiarNombre(renglon, "renglon"),
                limpiarNombre(certificado, "certificado"),
                sufijoListado,
            ].join("-") + ".txt";
            const archivo = new Blob([listado + "\\n"], {{
                type: "text/plain;charset=utf-8",
            }});
            const enlace = document.createElement("a");
            enlace.href = URL.createObjectURL(archivo);
            enlace.download = nombreArchivo;
            document.body.appendChild(enlace);
            enlace.click();
            enlace.remove();
            URL.revokeObjectURL(enlace.href);
            informarResultadoListado(
                `${{tarjetasFiltradas.length}} CAME(s) descargadas.`,
            );
        }}

        function mostrarOrdenActual() {{
            tarjetas.forEach((tarjeta) => {{
                tarjeta.classList.remove("actual");
            }});

            if (!tarjetasFiltradas.length) {{
                cantidadVisible.textContent = "0";
                document.getElementById("cantidad-total").textContent = "0";
                indicadorOrden.textContent = "Sin resultados";
                botonAnterior.disabled = true;
                botonSiguiente.disabled = true;
                return;
            }}

            const tarjetaActual = tarjetasFiltradas[indiceActual];
            tarjetaActual.classList.add("actual");
            cantidadVisible.textContent = String(indiceActual + 1);
            document.getElementById("cantidad-total").textContent =
                String(tarjetasFiltradas.length);
            indicadorOrden.textContent = tarjetaActual.dataset.textoBreve || "";
            botonAnterior.disabled = indiceActual === 0;
            botonSiguiente.disabled = indiceActual === tarjetasFiltradas.length - 1;
        }}

        document.querySelectorAll(
            ".operaciones-tabla:not(#tabla-operaciones-global)"
        ).forEach((tabla) => {{
            const cuerpo = tabla.querySelector("tbody");
            const seccion = tabla.closest(".seccion");
            if (!cuerpo || !seccion) {{
                return;
            }}
            const filtros = Array.from(
                seccion.querySelectorAll(".filtro-operaciones")
            );

            if (!filtros.length) {{
                return;
            }}

            function actualizarTotales() {{
                let totalDuracion = 0;
                let totalTrabajo = 0;
                let totalSuperficie = 0;
                let totalMontoSap = 0;
                let totalMontoEstimado = 0;

                cuerpo.querySelectorAll("tr").forEach((fila) => {{
                    if (fila.hidden) {{
                        return;
                    }}
                    totalDuracion += numero(fila.dataset.duracion);
                    totalTrabajo += numero(fila.dataset.trabajo);
                    totalSuperficie += numero(fila.dataset.superficie);
                    totalMontoSap += numero(fila.dataset.montoSap);
                    totalMontoEstimado += numero(fila.dataset.montoEstimado);
                }});

                const totalDuracionElemento = tabla.querySelector(
                    ".total-duracion"
                );
                if (totalDuracionElemento) {{
                    totalDuracionElemento.textContent =
                        formatoNumero(totalDuracion);
                }}
                const totalTrabajoElemento = tabla.querySelector(
                    ".total-trabajo"
                );
                if (totalTrabajoElemento) {{
                    totalTrabajoElemento.textContent =
                        formatoNumero(totalTrabajo);
                }}
                const totalSuperficieElemento = tabla.querySelector(
                    ".total-superficie"
                );
                if (totalSuperficieElemento) {{
                    totalSuperficieElemento.textContent =
                        formatoNumero(totalSuperficie);
                }}
                const totalMontoSapElemento = tabla.querySelector(
                    ".total-monto-sap"
                );
                if (totalMontoSapElemento) {{
                    totalMontoSapElemento.textContent =
                        formatoMoneda(totalMontoSap);
                }}
                const totalMontoEstimadoElemento = tabla.querySelector(
                    ".total-monto-estimado"
                );
                if (totalMontoEstimadoElemento) {{
                    totalMontoEstimadoElemento.textContent =
                        formatoMoneda(totalMontoEstimado);
                }}
            }}

            function ordenar(columna) {{
                const filas = Array.from(cuerpo.querySelectorAll("tr"));
                filas.sort((a, b) => comparar(
                    valorOrden(a, columna),
                    valorOrden(b, columna),
                ));
                filas.forEach((fila) => cuerpo.appendChild(fila));
            }}

            function aplicarFiltrosOperaciones() {{
                cuerpo.querySelectorAll("tr").forEach((fila) => {{
                    fila.hidden = filtros.some((filtro) => {{
                        const valor = filtro.value.trim().toLowerCase();
                        return valor &&
                            (fila.dataset[filtro.dataset.filtro] || "")
                                .toLowerCase() !== valor;
                    }});
                }});
                actualizarTotales();
            }}

            filtros.forEach((filtro) => {{
                filtro.addEventListener("change", aplicarFiltrosOperaciones);
            }});

            tabla.querySelectorAll(".comparador-clave").forEach((selector) => {{
                const actualizarComparacion = () => {{
                    const fila = selector.closest("tr");
                    if (!fila) {{
                        return;
                    }}
                    const precioComparado = numero(selector.value);
                    const unidadComparada = selector.selectedOptions[0]
                        ?.dataset.unidad || "";
                    const profundidadSelector = fila.querySelector(
                        ".profundidad-comparacion"
                    );
                    const requiereProfundidad = [
                        "m3",
                        "toneladas",
                        "ton",
                        "tn",
                        "t",
                    ].includes(unidadComparada);
                    if (profundidadSelector) {{
                        profundidadSelector.style.display = requiereProfundidad
                            ? ""
                            : "none";
                    }}
                    const largo = numero(fila.dataset.largoNumero);
                    const ancho = numero(fila.dataset.anchoNumero);
                    const profundidad = numero(
                        profundidadSelector?.value
                    );
                    const unidad = unidadComparada
                        || fila.dataset.unidadNormalizada;
                    let cantidadComparada = null;
                    if (unidad === "m2" && largo !== null && ancho !== null) {{
                        cantidadComparada = largo * ancho;
                    }} else if (
                        unidad === "m3"
                        && largo !== null
                        && ancho !== null
                        && profundidad !== null
                    ) {{
                        cantidadComparada = largo * ancho * profundidad;
                    }} else if (
                        ["toneladas", "ton", "tn", "t"].includes(unidad)
                        && largo !== null
                        && ancho !== null
                        && profundidad !== null
                    ) {{
                        cantidadComparada =
                            largo * ancho * 0.24 * profundidad;
                    }}
                    const diferencia =
                        selector.value && cantidadComparada !== null
                            ? cantidadComparada * precioComparado
                                - numero(fila.dataset.montoSap)
                            : null;
                    const totalComparado = cantidadComparada === null
                        || !selector.value
                        ? null
                        : cantidadComparada * precioComparado;
                    const totalElemento = fila.querySelector(
                        ".total-comparado"
                    );
                    const diferenciaElemento = fila.querySelector(
                        ".diferencia-clave"
                    );
                    if (totalElemento && diferenciaElemento) {{
                        totalElemento.textContent = totalComparado === null
                            ? "-"
                            : formatoMoneda(totalComparado);
                        totalElemento.className = "total-comparado";
                        if (totalComparado !== null) {{
                            totalElemento.classList.add(
                                totalComparado < numero(fila.dataset.montoSap)
                                    ? "total-comparado-menor"
                                    : "total-comparado-mayor"
                            );
                        }}
                        diferenciaElemento.textContent =
                            diferencia === null
                                ? "-"
                                : (diferencia > 0 ? "+" : diferencia < 0 ? "-" : "")
                                    + formatoMoneda(Math.abs(diferencia));
                    }}
                }};
                selector.addEventListener("change", actualizarComparacion);
                selector.closest("tr")
                    ?.querySelector(".profundidad-comparacion")
                    ?.addEventListener("change", actualizarComparacion);
            }});

            tabla.querySelectorAll(".orden-columna").forEach((boton) => {{
                boton.addEventListener("click", () => {{
                    ordenar(boton.dataset.columna);
                    actualizarTotales();
                }});
            }});

            actualizarTotales();
        }});

        let galeriaAbiertaConF = false;

        function abrirGaleriaFotos(tarjeta, desdeF = false) {{
            if (!tarjeta) {{
                return;
            }}
            galeriaAbiertaConF = desdeF;
            galeriaModal.innerHTML = "";
            if (modalResumenFotos) {{
                const materialidad = tarjeta.dataset.materialidad || "-";
                const resumen = tarjeta.dataset.resumenFotos || "-";
                modalResumenFotos.innerHTML = "";
                const materialidadElemento = document.createElement("span");
                materialidadElemento.innerHTML =
                    `<strong>Materialidad:</strong> ${{materialidad}}`;
                modalResumenFotos.appendChild(materialidadElemento);

                const resumenElemento = document.createElement("span");
                const tituloResumen = document.createElement("strong");
                tituloResumen.textContent = "Totales:";
                resumenElemento.appendChild(tituloResumen);
                resumen.split(" | ").forEach((parte, indice) => {{
                    if (indice) {{
                        resumenElemento.append(" | ");
                    }}
                    const datos = parte.split(" - ");
                    const cantidad = datos[0] || "";
                    const total = datos[1] || "";
                    const unidad = (datos[2] || "").toLowerCase();
                    const item = datos.slice(3).join(" - ");
                    resumenElemento.append(` ${{cantidad}} - `);
                    const totalNegrita = document.createElement("strong");
                    totalNegrita.textContent = total;
                    resumenElemento.appendChild(totalNegrita);
                    resumenElemento.append(` ${{unidad}} `);
                    const itemNegrita = document.createElement("strong");
                    itemNegrita.textContent = item;
                    resumenElemento.appendChild(itemNegrita);
                }});
                modalResumenFotos.appendChild(resumenElemento);
            }}

            tarjeta.querySelectorAll(".panel-fotos").forEach((panel) => {{
                const grupo = document.createElement("section");
                grupo.className = "grupo-modal";

                const titulo = document.createElement("h3");
                titulo.textContent = panel.querySelector("h4")?.textContent
                    || "Fotos";
                grupo.appendChild(titulo);

                const elementosVisuales = panel.querySelectorAll(
                    ".foto img, .documento-acta iframe",
                );
                if (!elementosVisuales.length) {{
                    const vacio = document.createElement("p");
                    vacio.textContent = "No hay archivos visuales.";
                    grupo.appendChild(vacio);
                }}

                elementosVisuales.forEach((elemento) => {{
                    if (elemento.tagName === "IMG") {{
                        const enlace = document.createElement("a");
                        enlace.className = "foto-modal";
                        enlace.href = elemento.closest("a").href;
                        enlace.target = "_blank";

                        const clon = document.createElement("img");
                        clon.src = elemento.src;
                        clon.alt = elemento.alt;
                        enlace.appendChild(clon);
                        grupo.appendChild(enlace);
                        configurarInteraccionFoto(enlace);
                        return;
                    }}

                    const documento = document.createElement("div");
                    documento.className = "documento-modal";
                    const tituloDocumento = elemento
                        .closest(".documento-acta")
                        .querySelector(".documento-titulo")
                        .cloneNode(true);
                    documento.appendChild(tituloDocumento);

                    const iframe = document.createElement("iframe");
                    iframe.src = elemento.src;
                    iframe.title = elemento.title;
                    documento.appendChild(iframe);
                    configurarIframeActa(iframe);

                    const enlace = document.createElement("a");
                    enlace.href = elemento.src;
                    enlace.target = "_blank";
                    enlace.textContent = "Abrir archivo completo";
                    documento.appendChild(enlace);
                    grupo.appendChild(documento);
                }});

                galeriaModal.appendChild(grupo);
            }});

            modalFotos.classList.add("abierto");
            modalFotos.setAttribute("aria-hidden", "false");
            if (!desdeF) {{
                cerrarModal.focus();
            }}
        }}

        document.querySelectorAll(".boton-comparar-fotos").forEach((boton) => {{
            boton.addEventListener("click", () => {{
                abrirGaleriaFotos(boton.closest(".tarjeta"));
            }});
        }});

        document.querySelectorAll(".boton-texto-aviso").forEach((boton) => {{
            const tarjeta = boton.closest(".tarjeta");
            const modal = tarjeta?.querySelector(".modal-texto-aviso");
            const cerrar = modal?.querySelector(".cerrar-texto-aviso");
            if (!modal || !cerrar) {{
                return;
            }}
            const cerrarModalAviso = () => {{
                modal.classList.remove("abierto");
                modal.setAttribute("aria-hidden", "true");
            }};
            boton.addEventListener("click", () => {{
                modal.classList.add("abierto");
                modal.setAttribute("aria-hidden", "false");
                cerrar.focus();
            }});
            cerrar.addEventListener("click", cerrarModalAviso);
            modal.addEventListener("click", (evento) => {{
                if (evento.target === modal) {{
                    cerrarModalAviso();
                }}
            }});
        }});

        function configurarInteraccionFoto(enlace) {{
            const imagen = enlace.querySelector("img");
            if (!imagen) {{
                return;
            }}
            let escala = 1;
            let desplazamientoX = 0;
            let desplazamientoY = 0;
            let arrastrando = false;
            let seMovio = false;
            let inicioX = 0;
            let inicioY = 0;

            const actualizarTransformacion = () => {{
                imagen.style.transform =
                    `translate(${{desplazamientoX}}px, ${{desplazamientoY}}px) scale(${{escala}})`;
            }};

            enlace.addEventListener("wheel", (evento) => {{
                evento.preventDefault();
                escala = Math.min(
                    5,
                    Math.max(1, escala * (evento.deltaY < 0 ? 1.15 : 0.87)),
                );
                if (escala === 1) {{
                    desplazamientoX = 0;
                    desplazamientoY = 0;
                }}
                actualizarTransformacion();
            }}, {{ passive: false }});

            enlace.addEventListener("mousedown", (evento) => {{
                if (evento.button !== 0 || escala === 1) {{
                    return;
                }}
                arrastrando = true;
                seMovio = false;
                inicioX = evento.clientX - desplazamientoX;
                inicioY = evento.clientY - desplazamientoY;
                enlace.classList.add("arrastrando");
                evento.preventDefault();
            }});

            window.addEventListener("mousemove", (evento) => {{
                if (!arrastrando) {{
                    return;
                }}
                desplazamientoX = evento.clientX - inicioX;
                desplazamientoY = evento.clientY - inicioY;
                seMovio = true;
                actualizarTransformacion();
            }});

            window.addEventListener("mouseup", () => {{
                arrastrando = false;
                enlace.classList.remove("arrastrando");
            }});

            enlace.addEventListener("click", (evento) => {{
                if (seMovio) {{
                    evento.preventDefault();
                    seMovio = false;
                }}
            }});
        }}

        document.querySelectorAll(".comparacion-fotos .foto").forEach(
            configurarInteraccionFoto,
        );

        function configurarIframeActa(iframe) {{
            const convertirImagenEmbebida = () => {{
                try {{
                    const imagenEmbebida = iframe.contentDocument?.querySelector(
                        'img[src^="data:image/"]',
                    );
                    if (imagenEmbebida) {{
                        const contenedor = iframe.closest(".documento-acta");
                        if (contenedor) {{
                            const enlace = document.createElement("a");
                            enlace.className = "foto";
                            enlace.href = iframe.src;
                            enlace.target = "_blank";

                            const imagen = document.createElement("img");
                            imagen.src = imagenEmbebida.src;
                            imagen.alt = iframe.title;
                            imagen.loading = "lazy";
                            enlace.appendChild(imagen);

                            const nombre = document.createElement("span");
                            nombre.textContent = iframe.title;
                            enlace.appendChild(nombre);
                            iframe.replaceWith(enlace);
                            configurarInteraccionFoto(enlace);
                        }}
                        return;
                    }}

                    const documento = iframe.contentDocument;
                    if (!documento?.head) {{
                        return;
                    }}
                    const estilo = documento.createElement("style");
                    estilo.textContent = `
                        html, body {{
                            margin: 0;
                            overflow: auto;
                        }}
                        img {{
                            display: block;
                            width: auto !important;
                            height: auto !important;
                            max-width: 100% !important;
                            object-fit: contain !important;
                        }}
                    `;
                    iframe.contentDocument.head.appendChild(estilo);
                }} catch (error) {{
                    console.warn("No se pudo ajustar la imagen embebida.", error);
                }}
            }};
            iframe.addEventListener("load", convertirImagenEmbebida);
            window.setTimeout(convertirImagenEmbebida, 0);
        }}

        document.querySelectorAll(".comparacion-fotos iframe").forEach(
            configurarIframeActa,
        );

        function cerrarGaleria() {{
            modalFotos.classList.remove("abierto");
            modalFotos.setAttribute("aria-hidden", "true");
            galeriaAbiertaConF = false;
        }}

        cerrarModal.addEventListener("click", cerrarGaleria);
        modalFotos.addEventListener("click", (evento) => {{
            if (evento.target === modalFotos) {{
                cerrarGaleria();
            }}
        }});

        function numero(valor) {{
            const resultado = parseFloat(
                String(valor || "").replace(",", "."),
            );
            return Number.isNaN(resultado) ? 0 : resultado;
        }}

        function formatoNumero(valor) {{
            return valor.toLocaleString("es-AR", {{
                maximumFractionDigits: 2,
            }});
        }}

        function formatoMoneda(valor) {{
            return valor.toLocaleString("es-AR", {{
                style: "currency",
                currency: "ARS",
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            }});
        }}

        function valorOrden(fila, columna) {{
            return String(fila.dataset[columna] || "").toLowerCase();
        }}

        function comparar(valorA, valorB) {{
            const numeroA = numero(valorA);
            const numeroB = numero(valorB);
            const ambosNumeros = valorA.trim() && valorB.trim()
                && !Number.isNaN(parseFloat(valorA.replace(",", ".")))
                && !Number.isNaN(parseFloat(valorB.replace(",", ".")));

            if (ambosNumeros) {{
                return numeroA - numeroB;
            }}

            return valorA.localeCompare(valorB, "es", {{ numeric: true }});
        }}

        buscador.addEventListener("input", () => {{
            actualizarCarga(70, "Construyendo la vista...");
            aplicarFiltros();
            mostrarResultadosBusqueda();
        }});
        buscador.addEventListener("focus", mostrarResultadosBusqueda);
        document.addEventListener("click", (evento) => {{
            if (!resultadosBusqueda.contains(evento.target) &&
                evento.target !== buscador) {{
                resultadosBusqueda.style.display = "none";
            }}
        }});
        [
            filtroArea,
            filtroClaseActividad,
            filtroMaterialidad,
            filtroClaseAviso,
            filtroServicio,
            filtroTipoError,
            filtroFechaModificacion,
            filtroEstadoCorreccion,
        ].forEach((filtro) => {{
            filtro?.addEventListener("change", aplicarFiltros);
        }});
        copiarCamesFiltradas?.addEventListener(
            "click",
            copiarListadoCames,
        );
        descargarCamesFiltradas?.addEventListener(
            "click",
            descargarListadoCames,
        );
        botonAnterior.addEventListener("click", () => {{
            if (indiceActual > 0) {{
                indiceActual -= 1;
                mostrarOrdenActual();
                window.scrollTo({{ top: 0, behavior: "smooth" }});
            }}
        }});
        botonSiguiente.addEventListener("click", () => {{
            if (indiceActual < tarjetasFiltradas.length - 1) {{
                indiceActual += 1;
                mostrarOrdenActual();
                window.scrollTo({{ top: 0, behavior: "smooth" }});
            }}
        }});

        function avanzarConBarra() {{
            const posicionScroll = window.scrollY;
            if (botonSiguiente.disabled) {{
                return;
            }}
            botonSiguiente.click();
            requestAnimationFrame(() => {{
                window.scrollTo({{ top: posicionScroll, behavior: "instant" }});
            }});
        }}

        function retrocederConShiftBarra() {{
            const posicionScroll = window.scrollY;
            if (botonAnterior.disabled) {{
                return;
            }}
            botonAnterior.click();
            requestAnimationFrame(() => {{
                window.scrollTo({{ top: posicionScroll, behavior: "instant" }});
            }});
        }}

        function aplicarFiltrosOperacionesGlobales() {{
            if (!tablaOperacionesGlobal) {{
                return;
            }}
            const termino = filtroOperacionesGlobal.value.toLowerCase();
            const area = document.getElementById(
                "filtro-area-operaciones",
            ).value.toLowerCase();
            const clase = document.getElementById(
                "filtro-clase-operaciones",
            ).value.toLowerCase();
            const unidad = document.getElementById(
                "filtro-unidad-operaciones",
            ).value.toLowerCase();
            tablaOperacionesGlobal.querySelectorAll("tbody tr").forEach((fila) => {{
                const coincideTexto = !termino ||
                    fila.textContent.toLowerCase().includes(termino);
                const coincideArea = !area ||
                    fila.dataset.area.toLowerCase() === area;
                const coincideClase = !clase ||
                    fila.dataset.clase.toLowerCase() === clase;
                const coincideUnidad = !unidad ||
                    fila.dataset.unidad.toLowerCase() === unidad;
                fila.hidden = !(
                    coincideTexto &&
                    coincideArea &&
                    coincideClase &&
                    coincideUnidad
                );
            }});
        }}

        filtrosOperacionesGlobales.forEach((filtro) => {{
            filtro.addEventListener("change", aplicarFiltrosOperacionesGlobales);
        }});

        if (abrirOperacionesGlobales && apartadoOperacionesGlobales) {{
            abrirOperacionesGlobales.addEventListener("click", () => {{
                apartadoOperacionesGlobales.classList.add("abierto");
                apartadoOperacionesGlobales.setAttribute("aria-hidden", "false");
                cerrarOperacionesGlobales.focus();
            }});
        }}

        function cerrarApartadoOperaciones() {{
            if (!apartadoOperacionesGlobales) {{
                return;
            }}
            apartadoOperacionesGlobales.classList.remove("abierto");
            apartadoOperacionesGlobales.setAttribute("aria-hidden", "true");
        }}

        if (cerrarOperacionesGlobales && apartadoOperacionesGlobales) {{
            cerrarOperacionesGlobales.addEventListener(
                "click",
                cerrarApartadoOperaciones,
            );
            apartadoOperacionesGlobales.addEventListener("click", (evento) => {{
                if (evento.target === apartadoOperacionesGlobales) {{
                    cerrarApartadoOperaciones();
                }}
            }});
        }}

        document.addEventListener("keydown", (evento) => {{
            if (
                evento.key.toLowerCase() === "f"
                && !evento.repeat
                && !modalFotos.classList.contains("abierto")
                && !modalReporte?.classList.contains("abierto")
            ) {{
                const elemento = document.activeElement;
                const escribiendo = elemento &&
                    ["INPUT", "SELECT", "TEXTAREA"].includes(elemento.tagName);
                if (!escribiendo) {{
                    abrirGaleriaFotos(
                        document.querySelector(".tarjeta.actual"),
                        true,
                    );
                }}
                return;
            }}

            if (modalFotos.classList.contains("abierto")) {{
                if (evento.key === "Escape") {{
                    cerrarGaleria();
                }}
                return;
            }}

            if (modalReporte?.classList.contains("abierto")) {{
                if (evento.key === "Escape") {{
                    cerrarReporteModal();
                }}
                return;
            }}

            if (apartadoOperacionesGlobales &&
                apartadoOperacionesGlobales.classList.contains("abierto")) {{
                if (evento.key === "Escape") {{
                    cerrarApartadoOperaciones();
                }}
                return;
            }}

            const elemento = document.activeElement;
            const escribiendo = elemento &&
                ["INPUT", "SELECT", "TEXTAREA"].includes(elemento.tagName)
                && elemento.type !== "radio";
            if (escribiendo) {{
                return;
            }}

            const avanzar = evento.key === "ArrowRight" ||
                (evento.key === " " && !evento.shiftKey);
            const retroceder = evento.key === "ArrowLeft" ||
                (evento.key === " " && evento.shiftKey);

            if (evento.key === " " && !evento.shiftKey && avanzar) {{
                evento.preventDefault();
                avanzarConBarra();
            }} else if (evento.key === " " && evento.shiftKey && retroceder) {{
                evento.preventDefault();
                retrocederConShiftBarra();
            }} else if (evento.key === "ArrowRight" && avanzar &&
                !botonSiguiente.disabled) {{
                evento.preventDefault();
                botonSiguiente.click();
            }} else if (evento.key === "ArrowLeft" && retroceder &&
                !botonAnterior.disabled) {{
                evento.preventDefault();
                botonAnterior.click();
            }}
        }});

        document.addEventListener("keyup", (evento) => {{
            if (
                evento.key.toLowerCase() === "f"
                && galeriaAbiertaConF
            ) {{
                cerrarGaleria();
            }}
        }});

        window.addEventListener("blur", () => {{
            if (galeriaAbiertaConF) {{
                cerrarGaleria();
            }}
        }});

        botonLimpiar?.addEventListener("click", () => {{
            buscador.value = "";
            filtroArea.value = "";
            filtroClaseActividad.value = "";
            filtroMaterialidad.value = "";
            filtroClaseAviso.value = "";
            filtroServicio.value = "";
            filtroTipoError.value = "";
            filtroFechaModificacion.value = "";
            filtroEstadoCorreccion.value = "";
            aplicarFiltros();
        }});

        aplicarFiltros();
    </script>
</body>
</html>
"""


# ------------------------------------------------------------
# Programa principal
# ------------------------------------------------------------

def seleccionar_fuentes() -> tuple[Path | None, Path | None, Path | None, Path | None]:
    """Usa las fuentes existentes; la selección visual vive en el reporte HTML."""
    return (
        AVISOS_FILE if AVISOS_FILE.exists() else None,
        CAMES_FILE if CAMES_FILE.exists() else None,
        CARES_FILE if CARES_FILE.exists() else None,
        ACTA_DIR if ACTA_DIR.exists() else None,
    )


def main() -> None:
    global ACTA_DIR

    print("Leyendo archivos JSON...")

    avisos_file, cames_file, cares_file, actas_dir = seleccionar_fuentes()
    ACTA_DIR = actas_dir or Path(
        "__carpeta_actas_no_seleccionada__"
    )

    avisos = cargar_json(avisos_file, "avisos.json")
    cames = cargar_json(cames_file, "cames.json")
    cares = cargar_json(cares_file, "cares.json")
    precios = cargar_preciario(PRECIARIO_FILE)

    print(f"Avisos encontrados: {len(avisos)}")
    print(f"CAMEs encontradas: {len(cames)}")
    print(f"CAREs encontradas: {len(cares)}")
    print(f"Precios encontrados: {len(precios)}")

    archivos_acta = listar_archivos_acta()
    print(f"Archivos de acta encontrados: {len(archivos_acta)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    errores_reporte: list[dict[str, str]] = []
    contenido_html = generar_html(
        avisos=avisos,
        cames=cames,
        cares=cares,
        archivos_acta=archivos_acta,
        precios=precios,
        fuentes={
            "avisos": avisos_file is not None,
            "cames": cames_file is not None,
            "cares": cares_file is not None,
            "actas": actas_dir is not None,
        },
        errores_reporte=errores_reporte,
    )

    OUTPUT_FILE.write_text(
        contenido_html,
        encoding="utf-8",
    )

    operaciones_file = OUTPUT_DIR / "operaciones.html"
    operaciones_file.write_text(
        generar_archivo_operaciones(cames, cares, avisos, precios),
        encoding="utf-8",
    )
    operaciones_xlsx_file = OUTPUT_DIR / "operaciones.xlsx"
    operaciones_xlsx_file.write_bytes(
        generar_reporte_operaciones_xlsx(cames, precios)
    )
    reporte_errores_file = OUTPUT_DIR / "reporte de errores.html"
    reporte_errores_file.write_text(
        generar_reporte_errores(errores_reporte),
        encoding="utf-8",
    )

    print()
    print("Previsualización generada correctamente.")
    print(f"Archivo: {OUTPUT_FILE}")
    print(f"Operaciones: {operaciones_file}")
    print(f"Excel: {operaciones_xlsx_file}")
    print(f"Reporte de errores: {reporte_errores_file}")


if __name__ == "__main__":
    main()