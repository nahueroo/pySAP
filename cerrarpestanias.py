import time
import pyautogui
import pygetwindow as gw

def cerrar_pestanas_firefox(max_tabs=4):
    count = 0

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
            time.sleep(0.3)
        except:
            print("No se pudo activar la ventana")
            break

        title = ventana.title.lower()

        if title == "mozilla firefox" or any(x in title for x in["image.html","data.pdf", "Microsoft Word"]):
            pyautogui.hotkey("ctrl","w")
            time.sleep(0.5)
            count += 1
        else:
            pyautogui.hotkey("ctrl","tab")
            time.sleep(0.3)
            count += 1

if __name__ == "__main__":
    cerrar_pestanas_firefox()

