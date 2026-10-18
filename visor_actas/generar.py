from __future__ import annotations

import html
import io
import json
import math
import os
import re
import struct
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
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

def cargar_json(path: Path) -> dict:
    """Lee un archivo JSON UTF-8."""
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    with path.open("r", encoding="utf-8") as archivo:
        contenido = json.load(archivo)

    if not isinstance(contenido, dict):
        raise ValueError(f"El archivo no contiene un objeto JSON: {path}")

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


def consultar_ubicacion_oficial(descripcion: str) -> dict[str, object]:
    coincidencia = re.search(
        r"^(.+?)\s+(\d+)\s*-\s*(\d+)",
        descripcion.strip(),
        flags=re.IGNORECASE,
    )
    if not coincidencia:
        return {}
    calle = coincidencia.group(1).strip()
    altura = round(
        (int(coincidencia.group(2)) + int(coincidencia.group(3))) / 2
    )
    return consultar_direccion_oficial(f"{calle} {altura}")


def consultar_direccion_oficial(direccion: str) -> dict[str, object]:
    consulta = urllib.parse.urlencode({
        "direccion": direccion,
        "geocodificar": "True",
        "maxOptions": "10",
    })
    url = f"https://servicios.usig.buenosaires.gob.ar/normalizar/?{consulta}"
    try:
        with urllib.request.urlopen(url, timeout=4) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except (OSError, ValueError) as error:
        print(f"No se pudo geocodificar {direccion}: {error}")
        return {}
    opciones = [
        opcion for opcion in datos.get("direccionesNormalizadas", [])
        if opcion.get("cod_partido") == "caba"
        and opcion.get("coordenadas")
    ]
    if not opciones:
        return {}
    opcion = opciones[0]
    coordenadas = opcion["coordenadas"]
    return {
        "direccion_normalizada": opcion.get("direccion", direccion),
        "calle": opcion.get("nombre_calle", ""),
        "longitud": float(coordenadas["x"]),
        "latitud": float(coordenadas["y"]),
    }


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
    pendientes = [
        descripcion for descripcion in sorted(descripciones)
        if descripcion not in cache or not cache[descripcion]
    ]
    with ThreadPoolExecutor(max_workers=8) as ejecutor:
        resultados = ejecutor.map(
            consultar_ubicacion_oficial,
            pendientes,
        )
        cache.update(zip(pendientes, resultados))
    direcciones_exactas = direcciones_exactas or set()
    claves_direcciones = {
        f"direccion:{direccion}": direccion
        for direccion in direcciones_exactas
        if direccion
    }
    pendientes_direcciones = [
        clave for clave, direccion in claves_direcciones.items()
        if clave not in cache or not cache[clave]
    ]
    with ThreadPoolExecutor(max_workers=8) as ejecutor:
        resultados = ejecutor.map(
            consultar_direccion_oficial,
            (claves_direcciones[clave] for clave in pendientes_direcciones),
        )
        cache.update(zip(pendientes_direcciones, resultados))
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
        for descripcion, dato in cache.items():
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
    for dato in cache.values():
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
    return False


ERROR_TIPOS = (
    ("clase", "Clase de actividad CAME/CARE"),
    ("servicio", "Servicio G02"),
    ("fecha", "Fecha creación/inicio"),
    ("foto", "Foto CAME"),
    ("duracion", "Duración normal 0"),
    ("montos", "Monto estimado/SAP"),
    ("duracion_g13", "Duración G13 no supera 12"),
    ("duracion_g05", "Duración G05 no supera 100"),
    ("items_g11", "G11 sin ítems 7.1 o 7.2"),
    ("via_publica", "Vía pública"),
    ("items_problematicos", "Ítems problemáticos"),
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
        duracion = operacion.get("Duracion normal") or ""
        trabajo = operacion.get("Trabajo") or ""
        largo = operacion.get("Largo") or campo_operacion(
            operacion, "Largo", "Longitud"
        )
        ancho = operacion.get("Ancho") or campo_operacion(
            operacion, "Ancho"
        )
        profundidad = operacion.get("Profundidad") or campo_operacion(
            operacion, "Profundidad"
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
            contenido = archivo.read_text(encoding="utf-8", errors="replace")
            imagenes = re.findall(
                r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']",
                contenido,
                flags=re.IGNORECASE | re.DOTALL,
            )
            imagenes_embebidas = [
                imagen for imagen in imagenes
                if imagen.startswith("data:image/")
            ]
            if imagenes_embebidas:
                for indice, imagen in enumerate(imagenes_embebidas, start=1):
                    etiqueta = nombre if len(imagenes_embebidas) == 1 else (
                        f"{nombre} ({indice}/{len(imagenes_embebidas)})"
                    )
                    elementos.append(f"""
                        <a class="foto" href="{ruta}" target="_blank">
                            <img src="{html.escape(imagen)}"
                                alt="{html.escape(etiqueta)}" loading="lazy">
                            <span>{html.escape(etiqueta)}</span>
                        </a>
                    """)
            else:
                elementos.append(f"""
                    <div class="documento-acta">
                        <div class="documento-titulo">{nombre}</div>
                        <iframe src="{ruta}" title="{nombre}" loading="lazy"></iframe>
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
                    <iframe src="{ruta}" title="{nombre}" loading="lazy"></iframe>
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

            largo = operacion.get("Largo", "")
            ancho = operacion.get("Ancho", "")
            profundidad = operacion.get("Profundidad", "")
            unidad = operacion.get("Unidad de Medida", "")
            duracion = operacion.get("Duracion normal", "")
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
            control = operacion.get("Clave de control operacion", "")
            valores_filtro = {
                "acta": acta,
                "texto-breve": came.get("Texto Breve", ""),
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
                    <td>{esc(operacion.get("Clave de control"))}</td>
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
        ("acta", "Acta", False),
        ("texto-breve", "Texto breve", True),
        ("clave-control", "Clave de control", True),
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
            ["montoSap"].forEach((campo) => {{
                tabla.querySelector(
                    `[data-subtotal="${{campo}}"]`
                ).textContent = formatoMoneda(sumas[campo]);
            }});
        }}

        actualizarSubtotales();
    </script>
</body>
</html>
"""


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
            duracion = operacion.get("Duracion normal") or ""
            largo = operacion.get("Largo") or campo_operacion(
                operacion, "Largo", "Longitud"
            )
            ancho = operacion.get("Ancho") or campo_operacion(
                operacion, "Ancho"
            )
            profundidad = operacion.get("Profundidad") or campo_operacion(
                operacion, "Profundidad"
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
) -> str:
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
        duracion_g05 = (
            clase_came_normalizada == "g05"
            and tiene_duracion_por_debajo_del_umbral(came, 100)
        )
        items_g11 = (
            clase_came_normalizada == "g11"
            and faltan_items_g11(came)
        )
        items_problematicos = tiene_items_problematicos(came)
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
        modificacion_care = texto(care.get("Fecha modificacion"), "")
        modificado_por_care = texto(care.get("Modificado por"), "")
        estado_usuario_aviso = texto(aviso.get("Status usuario"), "")
        clase_aviso = valor_real(aviso.get("Clase de aviso"))
        errores = {
            "clase": not clases_iguales,
            "servicio": not servicio_g02_ok,
            "fecha": not fechas_came_ok,
            "foto": not came_tiene_foto,
            "duracion": tiene_duracion_cero,
            "montos": montos_no_coinciden,
            "duracion_g13": duracion_g13,
            "duracion_g05": duracion_g05,
            "items_g11": items_g11,
            "via_publica": "viapublica" in normalizar(descripcion_ubicacion),
            "items_problematicos": items_problematicos,
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
            data-clase-aviso="{esc(clase_aviso)}"
            data-tiene-servicio="{"si" if servicio_valido else "no"}"
            data-tiene-errores="{"si" if tiene_errores else "no"}"
            data-tipos-error="{esc(tipos_error, '')}"
            data-fecha-modificacion="{esc(fecha_modificacion, '')}"
            data-texto-breve="{esc(texto_breve, '')}"
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

                <span class="estado">
                    {len(archivos_acta_asociados)} archivo(s)
                </span>
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
                    <span class="relacion-tipo">Aviso relacionado</span>
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
                    <label class="{"check-ok" if clases_iguales else "check-no"}">
                        <input type="checkbox" disabled
                            {"checked" if clases_iguales else ""}>
                        Clase de actividad CAME/CARE igual
                    </label>
                    <label class="{"check-ok" if servicio_g02_ok else "check-no"}">
                        <input type="checkbox" disabled
                            {"checked" if servicio_g02_ok else ""}>
                        G02 con servicio asociado
                    </label>
                    <label class="{"check-ok" if fechas_came_ok else "check-no"}">
                        <input type="checkbox" disabled
                            {"checked" if fechas_came_ok else ""}>
                        Creación CAME anterior o igual al inicio
                    </label>
                    <label class="{"check-no" if errores["via_publica"] else "check-ok"}">
                        <input type="checkbox" disabled
                            {"checked" if not errores["via_publica"] else ""}>
                        Vía pública
                    </label>
                    <label class="{"check-ok" if not duracion_g13 else "check-no"}">
                        <input type="checkbox" disabled
                            {"checked" if not duracion_g13 else ""}>
                        G13 supera 12
                    </label>
                    <label class="{"check-ok" if not duracion_g05 else "check-no"}">
                        <input type="checkbox" disabled
                            {"checked" if not duracion_g05 else ""}>
                        G05 supera 100
                    </label>
                    <label class="{"check-ok" if not items_g11 else "check-no"}">
                        <input type="checkbox" disabled
                            {"checked" if not items_g11 else ""}>
                        G11 con ítems 7.1 o 7.2
                    </label>
                    <label class="{"check-warning" if items_problematicos else "check-ok"}">
                        <input type="checkbox" disabled
                            {"checked" if not items_problematicos else ""}>
                        Ítems problemáticos
                    </label>
                    <label class="{"check-ok" if came_tiene_foto else "check-no"}">
                        <input type="checkbox" disabled
                            {"checked" if came_tiene_foto else ""}>
                        CAME con foto
                    </label>
                    <label class="{"check-ok" if not tiene_duracion_cero else "check-no"}">
                        <input type="checkbox" disabled
                            {"checked" if not tiene_duracion_cero else ""}>
                        Operaciones con duración normal 0
                    </label>
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

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Previsualización de actas</title>

    <style>
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

        .contenedor {{
            width: min(1400px, 94%);
            margin: 0 auto;
        }}

        .cabecera {{
            padding: 42px 0 28px;
        }}

        .cabecera h1 {{
            margin: 0 0 8px;
            font-size: clamp(28px, 4vw, 48px);
            color: var(--azul-oscuro);
        }}

        .cabecera p {{
            margin: 0;
            color: var(--secundario);
            font-size: 17px;
        }}

        .filtros {{
            position: sticky;
            top: 20px;
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
            padding: 24px 24px 58px;
            color: white;
            background: linear-gradient(135deg, #1e3a8a, #2563eb);
        }}

        .tarjeta-header h2 {{
            margin: 5px 0 0;
            font-size: 22px;
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

        .relaciones {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            padding: 16px 24px;
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
            padding: 20px 24px;
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
            height: 420px;
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
                height: 320px;
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
    <main class="contenedor">
        <header class="cabecera">
            <h1>Previsualización de actas</h1>
            <p>Relación entre CAME, CARE, avisos y fotografías.</p>
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

            <select id="filtro-errores">
                <option value="">Todas las cames</option>
                <option value="si">CAME con errores</option>
                <option value="no">CAME sin errores</option>
            </select>

            <select id="filtro-tipo-error">
                <option value="">Tipo de error</option>
                {opciones_error}
            </select>

            <select id="filtro-fecha-modificacion">
                <option value="">Fecha modificación</option>
                {opciones_fecha_modificacion}
            </select>

            <button id="limpiar" type="button">
                Limpiar filtros
            </button>
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
    </main>

    <script>
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
        const filtroErrores = document.getElementById("filtro-errores");
        const filtroTipoError = document.getElementById("filtro-tipo-error");
        const filtroFechaModificacion = document.getElementById(
            "filtro-fecha-modificacion",
        );
        const botonLimpiar = document.getElementById("limpiar");
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
        const cerrarModal = document.getElementById("cerrar-modal");
        let tarjetasFiltradas = tarjetas;
        let indiceActual = 0;

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
            [filtroErrores, "tieneErrores"],
            [filtroTipoError, "tiposError"],
            [filtroFechaModificacion, "fechaModificacion"],
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

        function aplicarFiltros() {{
            if (!buscador || filtrosOrden.some(([filtro]) => !filtro)) {{
                return;
            }}
            actualizarOpcionesDependientes();
            tarjetasFiltradas = tarjetas.filter((tarjeta) =>
                coincideConFiltros(tarjeta, null)
            );
            indiceActual = 0;
            mostrarOrdenActual();
            mostrarResultadosBusqueda();
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
            const filtros = Array.from(
                tabla.closest(".seccion")
                    .querySelectorAll(".filtro-operaciones")
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
                    profundidadSelector.style.display = requiereProfundidad
                        ? ""
                        : "none";
                    const largo = numero(fila.dataset.largoNumero);
                    const ancho = numero(fila.dataset.anchoNumero);
                    const profundidad = numero(
                        profundidadSelector.value
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
                    diferenciaElemento.textContent = diferencia === null
                        ? "-"
                        : (diferencia > 0 ? "+" : diferencia < 0 ? "-" : "")
                            + formatoMoneda(Math.abs(diferencia));
                }};
                selector.addEventListener("change", actualizarComparacion);
                selector.closest("tr")
                    .querySelector(".profundidad-comparacion")
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

        document.querySelectorAll(".comparacion-fotos iframe").forEach((iframe) => {{
            iframe.addEventListener("load", () => {{
                try {{
                    const estilo = iframe.contentDocument.createElement("style");
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
            }});
        }});

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
        filtroArea.addEventListener("change", aplicarFiltros);
        filtroClaseActividad.addEventListener("change", aplicarFiltros);
        filtroMaterialidad.addEventListener("change", aplicarFiltros);
        filtroClaseAviso.addEventListener("change", aplicarFiltros);
        filtroServicio.addEventListener("change", aplicarFiltros);
        filtroErrores.addEventListener("change", aplicarFiltros);
        filtroTipoError.addEventListener("change", aplicarFiltros);
        filtroFechaModificacion.addEventListener("change", aplicarFiltros);
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

            if (apartadoOperacionesGlobales &&
                apartadoOperacionesGlobales.classList.contains("abierto")) {{
                if (evento.key === "Escape") {{
                    cerrarApartadoOperaciones();
                }}
                return;
            }}

            const elemento = document.activeElement;
            const escribiendo = elemento &&
                ["INPUT", "SELECT", "TEXTAREA"].includes(elemento.tagName);
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

        botonLimpiar.addEventListener("click", () => {{
            buscador.value = "";
            filtroArea.value = "";
            filtroClaseActividad.value = "";
            filtroMaterialidad.value = "";
            filtroClaseAviso.value = "";
            filtroServicio.value = "";
            filtroErrores.value = "";
            filtroTipoError.value = "";
            filtroFechaModificacion.value = "";
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

def main() -> None:
    print("Leyendo archivos JSON...")

    avisos = cargar_json(AVISOS_FILE)
    cames = cargar_json(CAMES_FILE)
    cares = cargar_json(CARES_FILE)
    precios = cargar_preciario(PRECIARIO_FILE)

    print(f"Avisos encontrados: {len(avisos)}")
    print(f"CAMEs encontradas: {len(cames)}")
    print(f"CAREs encontradas: {len(cares)}")
    print(f"Precios encontrados: {len(precios)}")

    archivos_acta = listar_archivos_acta()
    print(f"Archivos de acta encontrados: {len(archivos_acta)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    contenido_html = generar_html(
        avisos=avisos,
        cames=cames,
        cares=cares,
        archivos_acta=archivos_acta,
        precios=precios,
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

    print()
    print("Previsualización generada correctamente.")
    print(f"Archivo: {OUTPUT_FILE}")
    print(f"Operaciones: {operaciones_file}")
    print(f"Excel: {operaciones_xlsx_file}")


if __name__ == "__main__":
    main()