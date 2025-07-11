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
}

def esperar_elemento(session, elemento_id, timeout=5):
    # Espera hasta que el elemento esté disponible

    import time
    tiempo_inicial = time.time()

    while time.time() - tiempo_inicial < timeout:
        try:
            # Intenta encontrar el elemento
            elemento = session.findById(elemento_id)
            if elemento:
                # Si lo encuentra
                return True
        except:
            time.sleep(0.1)  # Espera un porquito antes de volver a intentar
    
    # Si llego aqui, se agota el timeout
    return False  # No se encontró el elemento en el tiempo dado



def esperar_popup(session, timeout=5):
    # Espera hasta que aparezca un popup

    import time
    tiempo_inicial = time.time()

    while time.time() - tiempo_inicial < timeout:
        if session.Children.Count > 1: # Hay popup
            return True
        time.sleep(0.1)

    return False