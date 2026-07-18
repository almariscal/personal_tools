FROM python:3.12-slim

# Instala las dependencias primero (mejor cacheo de capas)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dni_watermark.py .

# /data es la carpeta que montarás con tus ficheros (-v "$PWD:/data").
# Las rutas relativas que pases se resuelven aquí dentro.
WORKDIR /data
ENTRYPOINT ["python", "/app/dni_watermark.py"]
