import msvcrt
import ctypes
import time
import subprocess,os

def limpiar_consola():
    subprocess.run("cls" if os.name == "nt" else "clear", shell=True)

def traer_consola_al_frente():

    try:
        # Obtener el handle de la ventana de la consola
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        
        # Obtener el handle de la ventana de la consola actual
        console_window = kernel32.GetConsoleWindow()
        
        if console_window:
            # Traer la ventana al frente
            user32.SetForegroundWindow(console_window)
            # Asegurar que la ventana esté visible y no minimizada
            user32.ShowWindow(console_window, 9)  # SW_RESTORE
        else:
            print("No se pudo obtener el handle de la consola")
    except Exception as e:
        print(f"Error al traer la consola al frente: {e}")