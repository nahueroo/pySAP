If Not IsObject(application) Then
   Set SapGuiAuto  = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If
If Not IsObject(connection) Then
   Set connection = application.Children(0)
End If
If Not IsObject(session) Then
   Set session    = connection.Children(0)
End If
If IsObject(WScript) Then
   WScript.ConnectObject session,     "on"
   WScript.ConnectObject application, "on"
End If

On Error Resume Next

Sub LogError(mensaje)
   If Err.Number <> 0 Then
      WScript.StdOut.WriteLine Now & " - ERROR: " & "No hay foto" & " - " & Err.Description
      Err.Clear
   End If
End Sub

Sub PauseWithEnter()
   Set shell = CreateObject("WScript.Shell")
   shell.Run "cmd /c pause", 2, True
End Sub

' === Pausa personalizada usando PowerShell ===
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
psFile = folder & "\esperar.ps1"

session.findById("wnd[0]").maximize
LogError "Maximizar Ventana"

session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").doubleClickCurrentCell
LogError "Doble click en celda actual"

session.findById("wnd[0]/titl/shellcont/shell").pressButton "%GOS_TOOLBOX"
LogError "Reabrir menú GOS"

'Abre Visualizar imagenes
session.findById("wnd[0]/shellcont/shell").pressButton "VIEW_IMAG"
WScript.Sleep 500  ' Pausa breve para que cargue el popup

If session.Children.Count > 1 Then
   ' Presiona el botón Aceptar en el popup
   session.findById("wnd[1]/tbar[0]/btn[0]").press
   LogError "Presionar botón VIEW_IMAG"
   

   'Abre Lista de documentos
   session.findById("wnd[0]/shellcont/shell").pressButton "DOC_LIST"
   LogError "Presionar botón DOC_LIST"

   WScript.Sleep 300
   
   If session.Children.Count > 1 Then
      ' Presiona el botón Aceptar en el popup
      session.findById("wnd[1]/tbar[0]/btn[0]").press

      session.findById("wnd[0]/shellcont/shell").pressButton "VIEW_DOC"
      LogError "Presionar botón VIEW_DOC"

      WScript.Sleep 300

      session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell").currentCellColumn = "NOMBRE"
      LogError "Seleccionar columna NOMBRE"

      session.findById("wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell").doubleClickCurrentCell
      LogError "Doble click en documento"

      session.findById("wnd[1]").close
      LogError "Cerrar ventana 1"

      session.findById("wnd[0]/shellcont").close
      LogError "Cerrar contenedor shell"
   End If
End If

session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/subMAINORDER:SAPLCOIH:0152/ctxtCAUFVD-MAUFNR").setFocus
LogError "SetFocus en campo MAUFNR"

session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/subMAINORDER:SAPLCOIH:0152/ctxtCAUFVD-MAUFNR").caretPosition = 7
LogError "Set caretPosition"

session.findById("wnd[0]").sendVKey 2
LogError "sendVKey 2"

session.findById("wnd[0]/titl/shellcont[1]/shell").pressButton "%GOS_TOOLBOX"

session.findById("wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL").getAbsoluteRow(0).selected = true
session.findById("wnd[1]").sendVKey 0

WScript.Sleep 300

session.findById("wnd[0]/shellcont/shell").pressButton "VIEW_IMAG"
LogError "Presionar botón VIEW_IMAG"

If session.Children.Count > 1 Then
   ' Presiona el botón Aceptar en el popup
   session.findById("wnd[1]/tbar[0]/btn[0]").press
   LogError "Presionar botón VIEW_IMAG"

   'Abre Lista de documentos
   session.findById("wnd[0]/shellcont/shell").pressButton "DOC_LIST"
   LogError "Presionar botón DOC_LIST"
   
   If session.Children.Count > 1 Then
      ' Presiona el botón Aceptar en el popup
      session.findById("wnd[1]/tbar[0]/btn[0]").press
      
   End If

End If

session.findById("wnd[0]/titl/shellcont[1]/shell").pressButton "%GOS_TOOLBOX"

session.findById("wnd[1]/usr/tblSAPLSWUGOBJECT_CONTROL").getAbsoluteRow(1).selected = true
session.findById("wnd[1]").sendVKey 0

session.findById("wnd[0]/shellcont[1]/shell").pressButton "VIEW_IMAG"
LogError "Presionar botón VIEW_IMAG"

WScript.Sleep 300

If session.Children.Count > 1 Then
   ' Presiona el botón Aceptar en el popup
   session.findById("wnd[1]/tbar[0]/btn[0]").press
   LogError "Presionar botón VIEW_IMAG"

   'Abre Lista de documentos
   session.findById("wnd[0]/shellcont[1]/shell").pressButton "DOC_LIST"
   LogError "Presionar botón DOC_LIST"

   WScript.Sleep 300
   
   If session.Children.Count > 1 Then
      ' Presiona el botón Aceptar en el popup
      session.findById("wnd[1]/tbar[0]/btn[0]").press
      
   End If

End If

session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/btnICON_NTF").press

   WScript.Sleep 500
' PauseWithEnter
Set objShell = CreateObject("WScript.Shell")

' Ejecutar el script PowerShell y esperar a que termine
' Usamos 1 para que se vea la ventana y el usuario pueda presionar teclas
exitCode = objShell.Run("powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & psFile & """", 1, True)

If exitCode = 0 Then
   WScript.Echo "PowerShell terminó con exit 0, continúo con el script..."
   ' Aquí sigue el resto de tu código si quieres
ElseIf exitCode = 1 Then
   WScript.Echo "PowerShell terminó con exit 1, deteniendo ejecución."
   WScript.Quit 1
Else
   WScript.Echo "Código de salida inesperado: " & exitCode
   WScript.Quit exitCode
End If

session.findById("wnd[0]/tbar[0]/btn[3]").press
WScript.Sleep 500

session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE").select

' PauseWithEnter
Set objShell = CreateObject("WScript.Shell")

' Ejecutar el script PowerShell y esperar a que termine
' Usamos 1 para que se vea la ventana y el usuario pueda presionar teclas
exitCode = objShell.Run("powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & psFile & """", 1, True)

If exitCode = 0 Then
   WScript.Echo "PowerShell terminó con exit 0, continúo con el script..."
   ' Aquí sigue el resto de tu código si quieres
ElseIf exitCode = 1 Then
   WScript.Echo "PowerShell terminó con exit 1, deteniendo ejecución."
   WScript.Quit 1
Else
   WScript.Echo "Código de salida inesperado: " & exitCode
   WScript.Quit exitCode
End If

session.findById("wnd[0]/tbar[0]/btn[3]").press
WScript.Sleep 500

session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpVGUE").select

   WScript.Sleep 2000
' PauseWithEnter
Set objShell = CreateObject("WScript.Shell")

' Ejecutar el script PowerShell y esperar a que termine
' Usamos 1 para que se vea la ventana y el usuario pueda presionar teclas
exitCode = objShell.Run("powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & psFile & """", 1, True)

If exitCode = 0 Then
   WScript.Echo "PowerShell terminó con exit 0, continúo con el script..."
   ' Aquí sigue el resto de tu código si quieres
ElseIf exitCode = 1 Then
   WScript.Echo "PowerShell terminó con exit 1, deteniendo ejecución."
   WScript.Quit 1
Else
   WScript.Echo "Código de salida inesperado: " & exitCode
   WScript.Quit exitCode
End If

session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1107/tabsTS_1100/tabpIHKZ").select
WScript.Sleep 250
session.findById("wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/ctxtCAUFVD-INGPR").text = "Cgi"
session.findById("wnd[0]/tbar[0]/btn[11]").press

WScript.Sleep 500

Set WshShell = WScript.CreateObject("WScript.Shell")
WshShell.SendKeys "{DOWN}"
