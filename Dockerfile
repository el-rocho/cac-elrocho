FROM python:3.12-slim

# Evitar generación de .pyc y activar salida sin buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Instalar dependencias mínimas de sistema (curl para diagnósticos de red)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY app/ /app/app/
# Los recursos de marca se sirven desde /branding y no forman parte del paquete
# Python; deben estar presentes también en la imagen Docker.
COPY assets/ /app/assets/

# Crear directorios persistentes de una instalación nueva
RUN mkdir -p /app/data /app/inbox /app/backups /app/config /app/logs

EXPOSE 8000

# Punto de entrada
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
