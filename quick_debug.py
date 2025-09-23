"""
QUICK DEBUG - Debug rápido para desarrollo
==========================================

Script simple para probar funciones específicas rápidamente
sin tener que pasar por todo el flujo principal.
"""

# Importar todo lo necesario
from sap_connection import conectar_sap
from getters import *
from utils import *
from scripts import *
from globales import datos
import time

def quick_test():
    """Función para pruebas rápidas - modifica según necesites"""
    
    print("🔧 QUICK DEBUG - Conectando a SAP...")
    
    # Conectar a SAP
    session = conectar_sap()
    if not session:
        print("❌ Error: No se pudo conectar a SAP")
        return
    
    print("✅ Conectado a SAP")
    print(f"Ventanas abiertas: {session.Children.Count}")
    
    # Aquí puedes modificar para probar lo que necesites
    # Ejemplo 1: Probar un getter específico
    print("\n--- Probando getter específico ---")
    resultado = get_texto_breve(session)
    print(f"Texto breve: {resultado}")
    
    # Ejemplo 2: Probar múltiples getters
    print("\n--- Probando múltiples getters ---")
    datos.clear()
    
    # Puedes comentar/descomentar las líneas que quieras probar:
    # datos["Texto Breve"] = get_texto_breve(session)
    # datos["Ubicacion Tecnica"] = get_ubicacion_tecnica(session) 
    # datos["Ubicacion Aviso"] = get_ubicacion_aviso(session)
    # datos["Clase de actividad"] = get_clase_actividad(session)
    # datos["Clase de actividad aviso"] = get_clase_actividad_aviso(session)
    
    print("Datos obtenidos:")
    for key, value in datos.items():
        print(f"  {key}: {value}")
    
    # Ejemplo 3: Probar función específica
    print("\n--- Probando función específica ---")
    # Descomenta la que quieras probar:
    # ver_fotos_en_care(session)
    # ver_fotos_en_came(session)
    # entrar_a_aviso(session)
    
    print("\n✅ Quick test completado")

def test_specific_getter(getter_name):
    """Prueba un getter específico"""
    
    session = conectar_sap()
    if not session:
        print("❌ Error: No se pudo conectar a SAP")
        return
    
    getters = {
        'texto_breve': get_texto_breve,
        'ubicacion_tecnica': get_ubicacion_tecnica,
        'ubicacion_aviso': get_ubicacion_aviso,
        'clase_actividad': get_clase_actividad,
        'clase_actividad_aviso': get_clase_actividad_aviso,
        'aviso_tipo': get_aviso_tipo,
        'aviso_autor': get_aviso_autor,
        'aviso_fecha': get_aviso_fecha,
        'aviso_servicio': get_aviso_servicio,
        'texto_largo_aviso': get_texto_largo_aviso
    }
    
    if getter_name in getters:
        print(f"🔧 Probando getter: {getter_name}")
        try:
            resultado = getters[getter_name](session)
            print(f"✅ Resultado: {resultado}")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"❌ Getter '{getter_name}' no encontrado")
        print("Getters disponibles:", list(getters.keys()))

def test_with_breakpoints():
    """Ejemplo de cómo usar breakpoints en el código"""
    
    session = conectar_sap()
    if not session:
        return
    
    print("🔧 Iniciando test con breakpoints...")
    
    # Breakpoint 1: Antes de obtener datos
    input("🛑 BREAKPOINT 1: Presiona ENTER para obtener texto breve...")
    texto_breve = get_texto_breve(session)
    print(f"Texto breve obtenido: {texto_breve}")
    
    # Breakpoint 2: Antes de siguiente operación
    input("🛑 BREAKPOINT 2: Presiona ENTER para obtener ubicación técnica...")
    ubicacion = get_ubicacion_tecnica(session)
    print(f"Ubicación técnica: {ubicacion}")
    
    # Breakpoint 3: Antes de operación compleja
    input("🛑 BREAKPOINT 3: Presiona ENTER para ver fotos en CARE...")
    try:
        ver_fotos_en_care(session)
        print("✅ Fotos en CARE completado")
    except Exception as e:
        print(f"❌ Error en fotos CARE: {e}")
    
    print("✅ Test con breakpoints completado")

def inspect_sap_elements():
    """Función para inspeccionar elementos de SAP"""
    
    session = conectar_sap()
    if not session:
        return
    
    print("🔍 INSPECTOR DE ELEMENTOS SAP")
    print("="*40)
    
    # Inspeccionar ventanas
    print(f"Número total de ventanas: {session.Children.Count}")
    for i in range(session.Children.Count):
        try:
            ventana = session.Children(i)
            print(f"Ventana {i}: {getattr(ventana, 'text', 'Sin texto')}")
        except Exception as e:
            print(f"Error al inspeccionar ventana {i}: {e}")
    
    # Aquí puedes agregar más inspecciones según necesites
    # Por ejemplo, inspeccionar elementos específicos:
    
    elementos_a_inspeccionar = [
        "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/txtCOIH-KTEXT",
        "wnd[0]/usr/subSUB_ALL:SAPLCOIH:3001/ssubSUB_LEVEL:SAPLCOIH:1100/tabsTS_1100/tabpIHKZ/ssubSUB_AUFTRAG:SAPLCOIH:1120/subHEADER:SAPLCOIH:0154/txtCOIH-TPLNR",
    ]
    
    for ruta in elementos_a_inspeccionar:
        try:
            elemento = session.findById(ruta)
            print(f"✅ Elemento encontrado: {ruta}")
            print(f"   Texto: {getattr(elemento, 'text', 'N/A')}")
            print(f"   Tipo: {type(elemento).__name__}")
        except Exception as e:
            print(f"❌ Elemento no encontrado: {ruta}")
            print(f"   Error: {e}")

if __name__ == "__main__":
    print("QUICK DEBUG - Selecciona una opción:")
    print("1. Quick test general")
    print("2. Test getter específico")
    print("3. Test con breakpoints")
    print("4. Inspector de elementos SAP")
    
    opcion = input("Opción (1-4): ").strip()
    
    if opcion == "1":
        quick_test()
    elif opcion == "2":
        getter = input("Nombre del getter: ").strip()
        test_specific_getter(getter)
    elif opcion == "3":
        test_with_breakpoints()
    elif opcion == "4":
        inspect_sap_elements()
    else:
        print("Opción inválida")