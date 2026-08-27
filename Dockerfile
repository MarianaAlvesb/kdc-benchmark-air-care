# Usar la imagen oficial de Python de Apify
FROM apify/actor-python:3.11

# Copiar el archivo de dependencias
COPY requirements.txt ./

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código fuente del proyecto al contenedor
COPY . ./

# Comando para ejecutar tu script principal
CMD ["python", "-m", "src.main"]
