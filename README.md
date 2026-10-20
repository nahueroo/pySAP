### Instalacion

```bash
# 1. Crear entorno virtual
python -m venv venv

# 2. Activar entorno virtual (Windows)
venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

## ▶️ Ejecución

```bash
# Asegúrate que el entorno virtual esté activado
python main.py
```

## Visor local de actas

Para regenerar el visor desde la interfaz y elegir carpetas ubicadas en
cualquier ruta del equipo, ejecutá:

```bash
python visor_actas/app.py
```

La aplicación abre el visor en `http://127.0.0.1:8765/`. En el menú
**Cargar datos** están disponibles estas acciones:

- **Archivos**: selecciona hasta tres JSON desde cualquier ruta. Se identifican
  por el nombre (`cames`, `cares` o `avisos`) y se incorporan al visor.
- **Fotos**: selecciona una carpeta completa desde cualquier ruta. Se conserva
  la estructura de carpetas para asociar las actas a cada CAME.

Después de cada carga se regenera automáticamente el visor. Los archivos
seleccionados se copian a `visor_actas/importados/`, que es un área temporal
ignorada por Git.

El modo anterior de abrir `visor_actas/salida/index.html` directamente sigue
disponible. Para detener la aplicación local, cerrá la ventana de la consola.

## Importante!

- **SAP debe estar abierto** con una sesión activa antes de ejecutar el script, en iw38/39 y con el cursor en la came correspondiente en la celda del "Texto Breve" de la misma.
- El script crea automáticamente la carpeta `actas/` en el directorio actual
- Navegadores soportados: firefox,chrome,edge.