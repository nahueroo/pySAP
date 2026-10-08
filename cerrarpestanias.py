import time
import pyautogui
import pygetwindow as gw
from constantes import PESTANAS

def cerrar_pestanas():
    
    count = 0
    # Limite para no entrar en loop
    max_tabs = 4

    while count < max_tabs:
        # Obtener todas las ventanas activas de Firefox
        windows = [
            w for w in gw.getWindowsWithTitle("") 
            if w.title and any(
                navegador in w.title.lower()
                for navegador in ("google chrome", "mozilla firefox", "microsoft edge")
            )
        ]

        if not windows:
            print("No se encontró ventana")
            break

        # Usar la primera ventana válida
        ventana = windows[0]
        
        # Activar la ventana
        try:
            ventana.activate()
            time.sleep(0.3)
        except Exception as e:
            print("No se pudo activar la ventana")
            break

        title = ventana.title.lower()
        
        if title == "mozilla firefox" or title == "microsoft edge" or title == "google chrome" or any(x in title for x in PESTANAS):
            pyautogui.hotkey("ctrl","w")
            time.sleep(0.6)
            count += 1
        else:
            pyautogui.hotkey("ctrl","tab")
            time.sleep(0.3)
            count += 1

if __name__ == "__main__":
    cerrar_pestanas()

