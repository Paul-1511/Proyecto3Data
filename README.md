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

**Fuentes opcionales.** Los archivos de Tikal/AIMM y de las encuestas solo los reciben algunos grupos. Si faltan en
`data/raw/`, el ETL omite esos bloques con un aviso y produce las 17 tablas restantes (es el caso del Grupo 4: Cobán y
Alta Verapaz). Las pruebas y el checklist se ajustan solos a los archivos presentes.

## Tablero (aplicación Dash)

**Requisitos.** Python 3.11 con `pip install -r requirements.txt`, y Docker Desktop (con Docker Compose v2) para la ejecución
en contenedor. El tablero solo lee los Parquet de `data/processed/`; los datos originales van en `data/raw/` y el ETL se
ejecuta como se describe en «Cómo correr el ETL».

**Ejecución local.**

```bash
python -m app.main        # http://localhost:8050
```

`python -m app.main` escucha en todas las interfaces de la máquina; para uso local es preferible Docker Compose, que publica
el puerto solo en `127.0.0.1`.

**Ejecución con Docker Compose** (requiere `data/processed/` ya generado):

```powershell
docker compose up --build        # construye la imagen y levanta el tablero
docker compose up --build -d     # igual, en segundo plano
docker compose down              # detiene y elimina el contenedor
```

Abrir `http://localhost:8050`. El contenedor monta `./data/processed` en solo lectura y no recibe `data/raw/`; la imagen no
contiene datos (`.dockerignore`) ni ejecuta el ETL.

**Estructura de los módulos.** `app/main.py` crea la aplicación, los filtros globales (`store-filtros`: rango de meses, tipo y
subdestino) y las cuatro pestañas. Cada pestaña se implementa en `app/modulo1.py` … `app/modulo4.py` con `layout()` y
`registrar_callbacks(app)`; si el archivo no existe, la pestaña muestra «En construcción».

| Pestaña | Archivo | Estado |
|---|---|---|
| 1 Demanda y mercados | `app/modulo1.py` | Implementado (P2) |
| 2 Dinámica y pronóstico | `app/modulo2.py` | Implementado (P2) |
| 3 Oferta y territorio | `app/modulo3.py` | En construcción (P3) |
| 4 Reto de Cobán y Alta Verapaz | `app/modulo4.py` | En construcción (P4) |

Apoyos: `app/theme.py` (paleta y plantilla Plotly), `app/utils/datos.py` (carga y filtros) y `app/utils/metricas.py`
(indicadores). Cómo agregar un módulo: `HANDOFF_P2.md`; paleta: `docs/paleta.md`; indicadores: `docs/fichas_modulo1_2.md`.

**Pruebas de la aplicación.**

```bash
python -m pytest tests/test_datos.py tests/test_app_base.py tests/test_metricas.py tests/test_modulo1.py tests/test_modulo2.py -v
```

**Confidencialidad.** Los datos son institucionales y de uso académico: no se suben a git ni a la imagen Docker, el tablero no
ofrece descargas ni tablas de microdatos, y los gráficos no incluyen barra de exportación.

## Equipo y responsabilidades
Ver `docs/` y los archivos `HANDOFF_P*.md`.
