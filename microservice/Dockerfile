FROM python:3.10-slim

# Instalar dependencias del sistema para audio
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Puerto
EXPOSE 8000

# Variables de entorno por defecto
ENV PYTHONPATH="/app"
ENV LOG_LEVEL=INFO

# Comando de inicio
CMD ["python", "main.py"]