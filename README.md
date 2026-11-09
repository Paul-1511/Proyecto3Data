# Observatorio de Inteligencia Turística · INGUAT

Proyecto del curso CC3084 Data Science (UVG, semestre II 2026).
Tablero web open source (Plotly Dash), contenerizado con Docker.

> **Datos institucionales.** Los datos son de uso exclusivamente académico. No se suben al repositorio
> (ver `.gitignore`), el repo es privado y el tablero no permite descargas masivas de microdatos.

## Estructura

```
data/raw/        datos originales (NO se suben)
data/processed/  parquet generados por el ETL (NO se suben)
etl/             pipeline de limpieza y cálculo
app/             tablero Dash (módulos 1-4)
docs/            memoria técnica, fichas, contrato de datos
tests/           pruebas
```

## Cómo correr el ETL

1. Colocar los archivos entregados por el curso en `data/raw/` (mismos nombres de archivo).
2. Instalar dependencias: `pip install -r requirements.txt`
3. Ejecutar: `python -m etl.run_all`
4. Contrato de datos: `python -m etl.generar_contrato` (genera `docs/data_contract.md`)
5. Pruebas: `pytest`
6. Verificación de P1: `python -m etl.checklist_p1`

Genera hasta 34 tablas Parquet en `data/processed/` (ver `docs/data_contract.md`).

## Cómo correr el tablero con Docker

Con Docker Desktop iniciado y los archivos del curso en `data/raw/`:

```bash
docker compose up --build
```

Compose ejecuta primero el ETL y luego inicia el tablero Dash en
<http://localhost:8050>. El tablero muestra datos de Alta Verapaz por subdestino.
Los archivos de `data/raw/` se montan como solo lectura y los datos institucionales
no se copian a la imagen. Para detenerlo, use `docker compose down`.

Para correr el tablero sin Docker, ejecute primero `python -m etl.run_all` y luego:

```bash
python -m app.main
```

**Fuentes opcionales.** Los archivos de Tikal/AIMM y de las encuestas solo los reciben algunos grupos. Si faltan en
`data/raw/`, el ETL omite esos bloques con un aviso y produce las 17 tablas restantes (es el caso del Grupo 4: Cobán y
Alta Verapaz). Las pruebas y el checklist se ajustan solos a los archivos presentes.

_(Instrucciones de Docker y del tablero: las completan P2 y P4.)_

## Equipo y responsabilidades
Ver `docs/` y los archivos `HANDOFF_P*.md`.
