# Imagen base oficial de Apify con Python 3.11/3.14
FROM apify/actor-python:3.14

USER myuser

# Copiar requirements.txt e instalar dependencias
COPY --chown=myuser:myuser requirements.txt ./

RUN echo "Python version:" \
 && python --version \
 && echo "Pip version:" \
 && pip --version \
 && echo "Installing dependencies:" \
 && pip install --no-cache-dir -r requirements.txt \
 && echo "All installed Python packages:" \
 && pip freeze

# Copiar el resto del código del repositorio
COPY --chown=myuser:myuser . ./

# Verificar la sintaxis de la carpeta src/
RUN python -m compileall -q src/

# Ejecutar el módulo principal (src/__main__.py)
CMD ["python", "-m", "src"]
