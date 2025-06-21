@echo off

REM Cerrar instancias anteriores del script AHK
taskkill /im AutoHotkey64.exe /f >nul 2>&1

REM REM Ejecutar el VBS
cscript //nologo "%~dp0Script2.vbs"

REM Ejecutar el script AHK nuevo
start "" "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe" "%~dp0cerrarpestanias.ahk"