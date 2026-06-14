# Script de setup para crear entorno virtual e instalar dependencias
# Ejecutar: PowerShell -ExecutionPolicy Bypass -File setup.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup del Entorno Virtual - ScriptPython" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que Python está instalado
$pythonCheck = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Python no esta instalado o no esta en el PATH" -ForegroundColor Red
    exit 1
}
Write-Host "Python encontrado: $pythonCheck" -ForegroundColor Green

# Crear entorno virtual
Write-Host ""
Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
python -m venv venv

if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "Error al crear el entorno virtual" -ForegroundColor Red
    exit 1
}
Write-Host "Entorno virtual creado" -ForegroundColor Green

# Activar entorno virtual
Write-Host ""
Write-Host "Activando entorno virtual..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
Write-Host "Entorno virtual activado" -ForegroundColor Green

# Actualizar pip
Write-Host ""
Write-Host "Actualizando pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Instalar dependencias
Write-Host ""
Write-Host "Instalando dependencias desde requirements.txt..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup completado exitosamente" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para activar el entorno virtual en futuras sesiones:" -ForegroundColor Yellow
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Para ejecutar el script:" -ForegroundColor Yellow
Write-Host "  python main.py" -ForegroundColor White
Write-Host ""
