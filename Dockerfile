# 1. Usa la imagen oficial de Apify para Python
FROM apify/actor-python:3.11

# 2. Copia los archivos de requerimientos e instálalos
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copia todo el código fuente del proyecto al contenedor
COPY . ./

# 4. Define el comando de inicio para ejecutar tu script
# (Ajusta 'src/main.py' por la ruta exacta a tu archivo principal)
CMD ["python", "my_actor/main.py"]
