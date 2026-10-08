import time

datos = {
    "Texto Breve" : None,
    "Clase de actividad" : None,
    "Ubicacion Tecnica" : None,
    "Ubicacion Aviso" : None,
    "Clase de actividad aviso" : None,
    "Tipo Aviso" : None,
    "Autor Aviso" : None,
    "Fecha Aviso" : None,
    "Servicio" : None,
    "Aviso" : None,
    "Datos CARE" : None,
    "Datos CAME" : None,
}

def esperar_elemento(session, elemento_id, timeout=5):
    """Espera hasta que el elemento esté disponible"""
    tiempo_inicial = time.time()

    while time.time() - tiempo_inicial < timeout:
        try:
            elemento = session.findById(elemento_id)
            if elemento:
                return True
        except:
            time.sleep(0.3)
    
    return False