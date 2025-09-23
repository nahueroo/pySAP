"""
DEBUG TOOLS - Herramientas para debuggear el código paso a paso
==============================================================

Este archivo contiene funciones utilitarias para debuggear y probar
el código instrucción por instrucción de manera controlada.
"""

import time
import traceback
from typing import Any, Callable, Optional
import msvcrt

# Importar módulos del proyecto
try:
    from sap_connection import conectar_sap
    from getters import *
    from utils import *
    from scripts import *
    from globales import datos
    from pausa import pausaPorConsola, traer_consola_al_frente
except ImportError as e:
    print(f"Error al importar módulos: {e}")
    print("Asegúrate de que todos los archivos del proyecto estén en el mismo directorio")

class DebugSession:
    """Clase para manejar sesiones de debugging"""
    
    def __init__(self):
        self.session = None
        self.step_by_step = False
        self.verbose = True
        
    def log(self, message: str, level: str = "INFO"):
        """Imprime mensajes de log con formato"""
        if self.verbose:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")
    
    def wait_for_user(self, message: str = "Presiona ENTER para continuar, ESC para salir..."):
        """Pausa la ejecución esperando input del usuario"""
        if self.step_by_step:
            self.log(message, "DEBUG")
            traer_consola_al_frente()
            result = pausaPorConsola()
            if result == 1:  # ESC pressed
                self.log("Ejecución cancelada por el usuario", "WARNING")
                return False
        return True
    
    def execute_with_debug(self, func: Callable, *args, **kwargs) -> Any:
        """Ejecuta una función con debugging habilitado"""
        func_name = func.__name__
        self.log(f"Ejecutando función: {func_name}", "DEBUG")
        
        if not self.wait_for_user(f"A punto de ejecutar {func_name}. Continuar?"):
            return None
            
        try:
            result = func(*args, **kwargs)
            self.log(f"Función {func_name} completada exitosamente", "SUCCESS")
            return result
        except Exception as e:
            self.log(f"Error en función {func_name}: {str(e)}", "ERROR")
            if self.verbose:
                traceback.print_exc()
            return None

# Instancia global del debugger
debug = DebugSession()

def debug_connection():
    """Debuggea la conexión a SAP paso a paso"""
    print("\n" + "="*60)
    print("DEBUG: CONEXIÓN A SAP")
    print("="*60)
    
    debug.log("Iniciando debug de conexión a SAP")
    
    if not debug.wait_for_user("¿Conectar a SAP?"):
        return None
        
    session = debug.execute_with_debug(conectar_sap)
    
    if session:
        debug.session = session
        debug.log("Conexión establecida exitosamente")
        debug.log(f"Número de ventanas abiertas: {session.Children.Count}")
        
        if debug.wait_for_user("¿Mostrar información de la sesión?"):
            try:
                debug.log(f"ID de sesión: {session.id}")
                debug.log(f"Información de la aplicación: {session.info.ApplicationServer}")
            except Exception as e:
                debug.log(f"No se pudo obtener información adicional: {e}")
    
    return session

def debug_datos_actuales():
    """Debuggea la obtención de datos actuales"""
    print("\n" + "="*60)
    print("DEBUG: OBTENCIÓN DE DATOS")
    print("="*60)
    
    if not debug.session:
        debug.log("No hay sesión activa. Conectando primero...", "WARNING")
        if not debug_connection():
            return
    
    debug.log("Iniciando debug de obtención de datos")
    
    # Limpiar datos globales
    datos.clear()
    debug.log("Datos globales limpiados")
    
    if debug.wait_for_user("¿Obtener datos básicos?"):
        debug.execute_with_debug(obtener_datos_basicos, debug.session)
        debug.log(f"Datos básicos obtenidos: {len(datos)} campos")
        if debug.verbose:
            for key, value in datos.items():
                debug.log(f"  {key}: {value}")
    
    if debug.wait_for_user("¿Obtener datos CARE?"):
        care_data = debug.execute_with_debug(getter_care, debug.session)
        if care_data:
            datos["Datos CARE"] = care_data
            debug.log("Datos CARE obtenidos exitosamente")
    
    if debug.wait_for_user("¿Obtener datos CAME?"):
        came_data = debug.execute_with_debug(getter_came, debug.session)
        if came_data:
            datos["Datos CAME"] = came_data
            debug.log("Datos CAME obtenidos exitosamente")
    
    if debug.wait_for_user("¿Entrar a aviso?"):
        debug.execute_with_debug(entrar_a_aviso, debug.session)
        debug.log("Proceso de aviso completado")

def debug_individual_getters():
    """Debuggea getters individuales"""
    print("\n" + "="*60)
    print("DEBUG: GETTERS INDIVIDUALES")
    print("="*60)
    
    if not debug.session:
        debug.log("No hay sesión activa", "ERROR")
        return
    
    getters_menu = {
        "1": ("Texto Breve", lambda: get_texto_breve(debug.session)),
        "2": ("Ubicación Técnica", lambda: get_ubicacion_tecnica(debug.session)),
        "3": ("Ubicación Aviso", lambda: get_ubicacion_aviso(debug.session)),
        "4": ("Clase de Actividad", lambda: get_clase_actividad(debug.session)),
        "5": ("Clase de Actividad Aviso", lambda: get_clase_actividad_aviso(debug.session)),
        "6": ("Aviso Tipo", lambda: get_aviso_tipo(debug.session)),
        "7": ("Aviso Autor", lambda: get_aviso_autor(debug.session)),
        "8": ("Aviso Fecha", lambda: get_aviso_fecha(debug.session)),
        "9": ("Aviso Servicio", lambda: get_aviso_servicio(debug.session)),
        "10": ("Texto Largo Aviso", lambda: get_texto_largo_aviso(debug.session))
    }
    
    while True:
        print("\n--- GETTERS DISPONIBLES ---")
        for key, (name, _) in getters_menu.items():
            print(f"{key}. {name}")
        print("0. Volver al menú principal")
        
        choice = input("\nSelecciona un getter (0-10): ").strip()
        
        if choice == "0":
            break
        elif choice in getters_menu:
            name, getter_func = getters_menu[choice]
            debug.log(f"Probando getter: {name}")
            result = debug.execute_with_debug(getter_func)
            debug.log(f"Resultado de {name}: {result}")
        else:
            print("Opción inválida")

def debug_custom_function():
    """Permite ejecutar funciones personalizadas paso a paso"""
    print("\n" + "="*60)
    print("DEBUG: FUNCIÓN PERSONALIZADA")
    print("="*60)
    
    if not debug.session:
        debug.log("No hay sesión activa", "ERROR")
        return
    
    print("Escribe el nombre de la función que quieres debuggear:")
    print("Funciones disponibles:")
    print("- ver_fotos_en_care")
    print("- ver_fotos_en_came") 
    print("- aceptar_g02")
    print("- obtener_datos_basicos")
    print("- mostrar_datos_formateados")
    
    func_name = input("\nNombre de la función: ").strip()
    
    try:
        # Obtener la función del namespace global
        func = globals().get(func_name)
        if func and callable(func):
            debug.log(f"Ejecutando función personalizada: {func_name}")
            result = debug.execute_with_debug(func, debug.session)
            debug.log(f"Resultado: {result}")
        else:
            debug.log(f"Función '{func_name}' no encontrada", "ERROR")
    except Exception as e:
        debug.log(f"Error al ejecutar función personalizada: {e}", "ERROR")

def show_current_state():
    """Muestra el estado actual de la sesión y datos"""
    print("\n" + "="*60)
    print("ESTADO ACTUAL")
    print("="*60)
    
    # Estado de la sesión
    if debug.session:
        try:
            debug.log(f"Sesión SAP: ACTIVA")
            debug.log(f"Ventanas abiertas: {debug.session.Children.Count}")
        except:
            debug.log("Sesión SAP: INACTIVA o ERROR")
    else:
        debug.log("Sesión SAP: NO CONECTADA")
    
    # Estado de los datos
    debug.log(f"Datos globales: {len(datos)} campos")
    if datos:
        for key, value in datos.items():
            # Truncar valores largos
            str_value = str(value)
            if len(str_value) > 50:
                str_value = str_value[:47] + "..."
            debug.log(f"  {key}: {str_value}")

def main_debug_menu():
    """Menú principal de debugging"""
    print("\n" + "="*70)
    print("🔧 HERRAMIENTAS DE DEBUG - SCRIPT PYTHON SAP")
    print("="*70)
    
    # Configuración inicial
    debug.verbose = True
    debug.step_by_step = True
    
    while True:
        print(f"\n--- MENÚ DE DEBUG ---")
        print("1. Debug Conexión SAP")
        print("2. Debug Obtención de Datos Completa")
        print("3. Debug Getters Individuales")
        print("4. Debug Función Personalizada")
        print("5. Mostrar Estado Actual")
        print("6. Configuración Debug")
        print("0. Salir")
        
        choice = input("\nSelecciona una opción (0-6): ").strip()
        
        if choice == "0":
            debug.log("Cerrando herramientas de debug...")
            break
        elif choice == "1":
            debug_connection()
        elif choice == "2":
            debug_datos_actuales()
        elif choice == "3":
            debug_individual_getters()
        elif choice == "4":
            debug_custom_function()
        elif choice == "5":
            show_current_state()
        elif choice == "6":
            configure_debug()
        else:
            print("Opción inválida")

def configure_debug():
    """Configuración de las opciones de debug"""
    print("\n--- CONFIGURACIÓN DEBUG ---")
    print(f"1. Modo paso a paso: {'ACTIVADO' if debug.step_by_step else 'DESACTIVADO'}")
    print(f"2. Modo verbose: {'ACTIVADO' if debug.verbose else 'DESACTIVADO'}")
    print("3. Volver")
    
    choice = input("\nSelecciona una opción (1-3): ").strip()
    
    if choice == "1":
        debug.step_by_step = not debug.step_by_step
        print(f"Modo paso a paso: {'ACTIVADO' if debug.step_by_step else 'DESACTIVADO'}")
    elif choice == "2":
        debug.verbose = not debug.verbose
        print(f"Modo verbose: {'ACTIVADO' if debug.verbose else 'DESACTIVADO'}")

if __name__ == "__main__":
    main_debug_menu()