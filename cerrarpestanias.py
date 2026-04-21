import time
import pyautogui
import pygetwindow as gw
from constantes import PESTANASFIREFOX, FIREFOX_ACTIVATE_DELAY, FIREFOX_CLOSE_DELAY, FIREFOX_TAB_SWITCH_DELAY

def cerrar_pestanas_firefox():
    
    count = 0
    # Limite para no entrar en loop
    max_tabs = 4

    while count < max_tabs:
        # Obtener todas las ventanas activas de Firefox
        firefox_windows = [w for w in gw.getWindowsWithTitle("") if w.title and "firefox" in w.title.lower()]
        if not firefox_windows:
            print("No se encontró ventana de Firefox")
            break
        # Usar la primera ventana válida
        ventana = firefox_windows[0]
        # Activar la ventana
        try:
            ventana.activate()
            time.sleep(FIREFOX_ACTIVATE_DELAY)
        except Exception as e:
            print("No se pudo activar la ventana")
            break
        title = ventana.title.lower()
        if title == "mozilla firefox" or any(x in title for x in PESTANASFIREFOX):
            pyautogui.hotkey("ctrl","w")
            time.sleep(FIREFOX_CLOSE_DELAY)
            count += 1
        else:
            pyautogui.hotkey("ctrl","tab")
            time.sleep(FIREFOX_TAB_SWITCH_DELAY)
            count += 1

if __name__ == "__main__":
    cerrar_pestanas_firefox()

