# esperar.ps1
Write-Host "Presiona ENTER para continuar, 'n' para detener, o ESC para salir..."

do {
    $key = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown").VirtualKeyCode

    switch ($key) {
        13 { Write-Host "Continuando..."; exit 0 }       # ENTER
        27 { Write-Host "Detenido por ESC."; exit 1 }     # ESC
        default { Write-Host "Tecla no válida. Usa ENTER, o ESC." }
    }
} while ($true)