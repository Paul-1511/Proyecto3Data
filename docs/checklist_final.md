# Checklist final de reglas metodológicas

| # | Regla | Estado | Evidencia |
|---:|---|:---:|---|
| 1 | Ausencia de dato no equivale a cero | [x] | `app/theme.py:figura_sin_dato`, `app/utils/datos.py:reindexar_meses`, módulos 1–4. |
| 2 | Estadía ponderada solo para más de un día | [x] | `app/utils/metricas.py:estadia_ponderada`; pruebas `tests/test_metricas.py`. |
| 3 | No sumar diaria a mes, meses ni subdestinos | [x] | `app/utils/metricas.py`, `app/utils/oferta_ocupacion.py`, `app/modulo4.py:presencia_fin_semana`. |
| 4 | Nacionales y extranjeros por separado | [x] | Filtro global `app/main.py`; colores y doble eje `app/modulo1.py`. |
| 5 | Estimaciones diferenciadas y rotuladas | [x] | `app/theme.py:COLOR_ESTIMACION`; `app/modulo2.py`. |
| 6 | Afluencia–ocupación solo sep–dic 2025 | [x] | `app/utils/oferta_ocupacion.py:VENTANA_CRUCE`; `tests/test_modulo3.py`. |
| 7 | Oferta como cortes anuales, sin Airbnb | [x] | `app/modulo3.py:fig_capacidad`; ficha 1 en `docs/fichas_modulo3.md`. |
| 8 | Encuestas solo dentro de segmento | [x] | `etl/encuestas.py`; las fuentes no fueron entregadas a Grupo 4, por lo que no se exponen. |
| 9 | Sin comparación interanual de movilidad | [x] | `app/utils/oferta_ocupacion.py:indice_estacional_visitantes`; ficha 11 de M3. |
| 10 | Aeronaves y pasajeros separados | [x] | Grupo 4 no recibió AIMM; `etl/tikal_aimm.py` conserva métricas separadas. |
| 11 | Período y cobertura visibles | [x] | `app/theme.py:subtitulo_periodo`, `app/indicador_cobertura.py`. |
| 12 | Gasto solo declarado por encuesta | [x] | No hay encuesta ni gasto expuesto para Grupo 4. |
| 13 | Sin microdatos en Git ni descargas | [x] | `.gitignore`, `.dockerignore`, `_CONFIG_GRAFICO` sin barra de exportación. |

## Verificación de instalación limpia

El 12-nov-2026 se clonó el repositorio en una carpeta temporal, se copiaron los cinco archivos fuente de Grupo 4 a `data/raw/` y `python3 -m etl.run_all` terminó correctamente. La imagen se construyó desde cero con `docker compose up --build -d`; el tablero respondió HTTP 200 en `http://127.0.0.1:8050/` y el healthcheck alcanzó estado `healthy`. Se ajustó `HOME=/tmp` en la imagen para conservar el sistema de archivos de solo lectura sin errores de Gunicorn.
