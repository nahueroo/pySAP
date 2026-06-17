import msvcrt
import ctypes
import time
from constantes import CONTINUE, CANCEL, ENTER, ESCAPE

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

def pausa_por_consola():
    traer_consola_al_frente()
    time.sleep(0.2)
    print("Presiona [ENTER] si la CAME esta correcta o [ESC] si tiene errores")

    while True:
        key = msvcrt.getch()
        if key == ENTER:
            print("CAME OK")
            return CONTINUE
        elif key == ESCAPE:
            print("CAME con errores")
            return CANCEL
        else:
            print("")

def pausa():
    teclaPresionada = pausa_por_consola()
    if teclaPresionada == CONTINUE:
        return ENTER
    elif teclaPresionada == CANCEL:
        return CANCEL
    else:
        print(f"Codigo de salida inesperado: {teclaPresionada}")
        exit(teclaPresionada)