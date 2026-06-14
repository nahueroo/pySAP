# ScriptPython - Automatización SAP

Script de automatización para interactuar con SAP GUI y gestionar documentos.

## 📋 Requisitos Previos

- **Python 3.8+** instalado en el sistema ([descargar aquí](https://www.python.org/downloads/))
- **SAP GUI** con sesión activa (el script se conecta automáticamente)
- **Firefox** (opcional, para cerrar pestañas)
- **Windows** (el script utiliza APIs específicas de Windows)

## 🚀 Instalación Rápida

### Opción 1: Automática (PowerShell - Recomendado)

```powershell
# Abre PowerShell en la carpeta del proyecto
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\setup.ps1
```

### Opción 2: Manual

```bash
# 1. Crear entorno virtual
python -m venv venv

# 2. Activar entorno virtual (Windows)
venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

## 📦 Dependencias

| Paquete | Versión | Descripción |
|---------|---------|------------|
| pywin32 | 306 | Interfaz COM con aplicaciones Windows (SAP GUI) |
| pyautogui | 0.9.53 | Automatización de mouse y teclado |
| pygetwindow | 0.0.9 | Control de ventanas |

## ▶️ Ejecución

```bash
# Asegúrate que el entorno virtual esté activado
python main.py
```

### Menú de Opciones

```
---MENU ---
1. Fotos/PDF    - Procesar archivos de fotos o PDF
2. Directo PDF  - Procesamiento directo de PDF
3. Mostrar último guardado
4. Salir
```

## 📂 Estructura del Proyecto

```
scriptPython/
├── main.py                  # Punto de entrada principal
├── scripts.py               # Lógica principal de automatización
├── sap_connection.py        # Conexión con SAP GUI
├── getters.py              # Obtención de datos de SAP
├── utils.py                # Funciones utilitarias
├── pausa.py                # Control de pausa/entrada
├── cerrarpestanias.py      # Gestión de ventanas Firefox
├── constantes.py           # Constantes y configuración
├── globales.py             # Variables globales
├── requirements.txt        # Dependencias Python
├── setup.ps1              # Script de setup (Windows)
├── ultimo_guardado.json   # Archivo de datos guardados
├── actas/                 # Carpeta de salida (creada automáticamente)
└── README.md              # Este archivo
```

## 🔧 Configuración

Edita [constantes.py](constantes.py) para personalizar:
- `RUTA_SAP_DESCARGAS` - Ruta de descargas de SAP
- `PESTANASFIREFOX` - Pestañas de Firefox a cerrar
- Timeouts y delays de ejecución

## ⚠️ Notas Importantes

- **SAP GUI debe estar abierto** con una sesión activa antes de ejecutar el script
- El script crea automáticamente la carpeta `actas/` en el directorio actual
- Los archivos se guardan con estructura jerárquica basada en datos de SAP
- Se requieren permisos de administrador en Windows para algunas operaciones

## 🐛 Solución de Problemas

### Error: "No se pudo obtener sesión SAP válida"
- Verifica que SAP GUI está abierto
- Confirma que hay una sesión activa

### Error: "ModuleNotFoundError: No module named 'win32com'"
- Ejecuta: `pip install -r requirements.txt`
- Luego ejecuta: `python -m pip install --upgrade pywin32`

### El script se detiene abruptamente
- Revisa la consola para mensajes de error
- Verifica que Firefox está disponible (si usas esa funcionalidad)

## 📝 Licencia

Uso interno. Todos los derechos reservados.

---

**Última actualización:** Junio 2026
**Versión:** 1.0
