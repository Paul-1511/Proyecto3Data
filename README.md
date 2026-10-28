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
4. Pruebas: `pytest`

_(Instrucciones de Docker y del tablero: las completa P2/P4.)_

## Equipo y responsabilidades
Ver `docs/` y los archivos `HANDOFF_P*.md`.
