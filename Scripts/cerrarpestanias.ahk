#Requires AutoHotkey v2.0
maxTabs := 8
count := 0

Loop {
    ; Obtener ID de la ventana de Chrome
    chrome := WinExist("ahk_class Chrome_WidgetWin_1 ahk_exe chrome.exe")
    if !chrome {
        MsgBox("No se encontró ventana de Chrome.")
        break
    }

    ; Activar ventana y esperar que esté activa
    WinActivate(chrome)
    WinWaitActive(chrome)
    Sleep(100)

    ; Obtener título de la ventana activa
    title := WinGetTitle(chrome)

    if InStr(title, "image.html") || InStr(title, "data.pdf") || InStr(title, "Microsoft Word") {
        ;MsgBox("Título actual: " . title)
        Send("{Ctrl down}w{Ctrl up}") ; Cerrar pestaña
        Sleep(500)
        count++
    } else {
        Send("{Ctrl down}{Tab}{Ctrl up}") ; Cambiar a siguiente pestaña
        Sleep(300)
        count++
    }

    if (count >= maxTabs) {
        break
    }
}
ExitApp