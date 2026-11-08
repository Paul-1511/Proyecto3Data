# Observatorio de Inteligencia Turística — Cobán y Alta Verapaz
# Imagen de producción: solo el código de la app. Los datos (data/processed) se montan en
# tiempo de ejecución en modo solo lectura; NO se copian a la imagen ni se ejecuta el ETL aquí.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Usuario sin privilegios (uid/gid fijos), sin shell de inicio de sesión ni directorio home.
RUN groupadd --system --gid 10001 observatorio \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin observatorio

# Dependencias de ejecución. requirements.txt también lista herramientas que la app no usa en
# producción (pytest) o que solo usa el ETL (openpyxl); se omiten para mantener la imagen mínima.
COPY requirements.txt .
RUN grep -Eiv '^[[:space:]]*(pytest|openpyxl)([[:space:]]|[<>=!~;]|$)' requirements.txt > requirements.runtime.txt \
    && pip install -r requirements.runtime.txt \
    && rm requirements.txt requirements.runtime.txt

# Solo el paquete de la aplicación (sin etl/, tests/, docs/ ni datos).
COPY app/ ./app/

# Punto de montaje de los Parquet (solo lectura desde docker-compose).
RUN mkdir -p /app/data/processed

USER observatorio

EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8050/', timeout=4)"]

# app.main:server es el servidor Flask de la app Dash. Las cachés de lectura son por proceso,
# por lo que pocos workers con varios hilos mantienen bajo el uso de memoria.
CMD ["gunicorn", \
     "--chdir", "/app", \
     "--bind", "0.0.0.0:8050", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "120", \
     "--worker-tmp-dir", "/dev/shm", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app.main:server"]
