from __future__ import annotations

import json
import mimetypes
import shutil
import subprocess
import sys
import threading
import webbrowser
from email import policy
from email.parser import BytesParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


VISOR_DIR = Path(__file__).resolve().parent
BASE_DIR = VISOR_DIR.parent
SALIDA_DIR = VISOR_DIR / "salida"
GENERADOR = VISOR_DIR / "generar.py"
IMPORTADOS_DIR = VISOR_DIR / "importados"
DATOS_IMPORTADOS_DIR = IMPORTADOS_DIR / "datos"
ACTAS_IMPORTADAS_DIR = IMPORTADOS_DIR / "actas"
PUERTO = 8765


class EstadoAplicacion:
    def __init__(self) -> None:
        self.data_dir = BASE_DIR
        self.actas_dir = BASE_DIR / "actas"
        self.lock = threading.Lock()

    def preparar_importados(self) -> None:
        DATOS_IMPORTADOS_DIR.mkdir(parents=True, exist_ok=True)
        ACTAS_IMPORTADAS_DIR.mkdir(parents=True, exist_ok=True)

    def cargar_archivos(self, partes: list[tuple[str, bytes]]) -> None:
        self.preparar_importados()
        nombres = {
            "avisos": "avisos.json",
            "aviso": "avisos.json",
            "cames": "cames.json",
            "came": "cames.json",
            "cares": "cares.json",
            "care": "cares.json",
        }
        for nombre, contenido in partes:
            try:
                datos = json.loads(contenido.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError(f"El archivo {nombre} no es JSON válido.") from error
            if not isinstance(datos, dict):
                raise ValueError(f"El archivo {nombre} debe contener un objeto JSON.")
            base = Path(nombre).stem.lower()
            destino = next(
                (nombres[clave] for clave in nombres if clave in base),
                None,
            )
            if destino is None:
                registros = [
                    valor for valor in datos.values() if isinstance(valor, dict)
                ]
                if any("Clase de aviso" in valor for valor in registros):
                    destino = "avisos.json"
                elif any("Materialidad" in valor for valor in registros):
                    destino = "cares.json"
                elif any(
                    "CARE Asociada" in valor or "CARE asociada" in valor
                    for valor in registros
                ):
                    destino = "cames.json"
            if destino is None:
                raise ValueError(
                    f"No se pudo identificar el tipo de datos de {nombre}. "
                    "Usá nombres que contengan came, care o aviso."
                )
            (DATOS_IMPORTADOS_DIR / destino).write_bytes(contenido)
        self.data_dir = DATOS_IMPORTADOS_DIR

    def cargar_fotos(self, partes: list[tuple[str, bytes]]) -> None:
        if not partes:
            raise ValueError("No se recibieron fotos o archivos de acta.")
        if ACTAS_IMPORTADAS_DIR.exists():
            shutil.rmtree(ACTAS_IMPORTADAS_DIR)
        ACTAS_IMPORTADAS_DIR.mkdir(parents=True, exist_ok=True)
        for nombre, contenido in partes:
            relativo = Path(nombre)
            if relativo.is_absolute() or ".." in relativo.parts:
                raise ValueError("La ruta relativa de un archivo no es válida.")
            destino = (ACTAS_IMPORTADAS_DIR / relativo).resolve()
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(contenido)
        self.actas_dir = ACTAS_IMPORTADAS_DIR

    def regenerar(self) -> tuple[bool, str]:
        with self.lock:
            comando = [
                sys.executable,
                str(GENERADOR),
                "--data-dir",
                str(self.data_dir),
                "--actas-dir",
                str(self.actas_dir),
                "--media-url-prefix",
                "/media",
            ]
            resultado = subprocess.run(
                comando,
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        salida = (
            (resultado.stdout or "")
            + "\n"
            + (resultado.stderr or "")
        ).strip()
        return resultado.returncode == 0, salida


estado = EstadoAplicacion()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SALIDA_DIR), **kwargs)

    def enviar_json(self, status: int, payload: dict[str, object]) -> None:
        contenido = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(contenido)))
        self.end_headers()
        self.wfile.write(contenido)

    def do_GET(self) -> None:
        ruta = urlparse(self.path).path
        if ruta == "/":
            self.path = "/index.html"
            return super().do_GET()
        if ruta.startswith("/media/"):
            self.enviar_archivo_acta(unquote(ruta.removeprefix("/media/")))
            return
        super().do_GET()

    def enviar_archivo_acta(self, relativa: str) -> None:
        raiz = estado.actas_dir.resolve()
        archivo = (raiz / relativa).resolve()
        try:
            archivo.relative_to(raiz)
        except ValueError:
            self.send_error(403, "Ruta de acta no permitida")
            return
        if not archivo.is_file():
            self.send_error(404, "Archivo de acta no encontrado")
            return
        contenido = archivo.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(archivo.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(contenido)))
        self.end_headers()
        self.wfile.write(contenido)

    def recibir_multipart(self) -> list[tuple[str, bytes]]:
        longitud = int(self.headers.get("Content-Length", "0"))
        if longitud <= 0:
            raise ValueError("La carga no contiene archivos.")
        cuerpo = self.rfile.read(longitud)
        mensaje = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: " + self.headers["Content-Type"].encode()
            + b"\r\n\r\n" + cuerpo
        )
        archivos = []
        for parte in mensaje.iter_attachments():
            contenido = parte.get_payload(decode=True)
            nombre = parte.get_filename()
            if contenido is not None and nombre:
                archivos.append((unquote(nombre).replace("\\", "/"), contenido))
        return archivos

    def do_POST(self) -> None:
        ruta = urlparse(self.path).path
        if ruta in {"/api/cargar-archivos", "/api/cargar-fotos"}:
            try:
                archivos = self.recibir_multipart()
                if ruta.endswith("archivos"):
                    estado.cargar_archivos(archivos)
                else:
                    estado.cargar_fotos(archivos)
                correcto, salida = estado.regenerar()
                self.enviar_json(
                    200 if correcto else 500,
                    {"ok": correcto, "salida": salida},
                )
            except (ValueError, OSError) as error:
                self.enviar_json(400, {"ok": False, "error": str(error)})
            return
        if ruta == "/api/regenerar":
            correcto, salida = estado.regenerar()
            self.enviar_json(
                200 if correcto else 500,
                {"ok": correcto, "salida": salida},
            )
            return
        self.send_error(404, "Endpoint no encontrado")


def main() -> None:
    correcto, salida = estado.regenerar()
    if not correcto:
        raise RuntimeError(f"No se pudo generar el visor:\n{salida}")
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Handler)
    url = f"http://127.0.0.1:{PUERTO}/"
    print(f"Visor local: {url}")
    print("Cerrá esta ventana para detener el visor.")
    webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
