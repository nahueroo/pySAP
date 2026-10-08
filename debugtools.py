def debug_window(session, window="wnd[0]"):

    objetos = []

    def recorrer(obj, nivel=0):
        try:
            objetos.append((obj,nivel))
        except Exception:
            pass

        try:
            for i in range(obj.Children.Count):
                recorrer(obj.Children(i), nivel + 1)
        except Exception:
            pass

    recorrer(session.findById(window))

    for obj,nivel in objetos:
        try:
            print(
                f"{'    ' * nivel}"
                f"[{obj.Type}] "
                f"{obj.Id}"
            )
        except Exception:
            pass

    return objetos

def inspect_object(obj):

    print("=" * 80)
    print(f"TYPE: {getattr(obj, 'Type', '?')}")
    print(f"ID  : {getattr(obj, 'Id', '?')}")
    print("=" * 80)

    for name in dir(obj):

        try:
            value = getattr(obj, name)

            print("NOMBRE:", name)
            print("TIPO:  ", type(value).__name__)
            print("VALOR: ", repr(value))
            print()

        except Exception as e:
            print("NOMBRE:", name)
            print("ERROR: ", e)
            print()