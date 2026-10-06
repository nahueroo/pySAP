```bash

set -e

echo "1. Creando entorno virtual..."
python -m venv venv

echo "2. Activando entorno virtual..."
source venv/scripts/activate

echo "3. Instalando dependencias..."
pip install -r requirements.txt

echo "Entorno configurado correctamente."
```
