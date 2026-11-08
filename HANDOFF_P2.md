# HANDOFF P2 → P3

**Estado:** P2 completo para su alcance (infraestructura Dash, tema, Docker, métricas y módulos 1 y 2). Las pestañas 3 y 4 muestran «En construcción» hasta que P3 y P4 agreguen sus módulos.

## Qué implementó P2
- **Capa de datos y filtros** (`app/utils/datos.py`): carga cacheada de Parquet, `Filtros` y filtros mensual/diario.
- **Tema** (`app/theme.py`, `docs/paleta.md`): paleta, plantilla Plotly, subtítulos de período, figura «Sin dato», rótulo de estimación, contraste AA.
- **Aplicación** (`app/main.py`): encabezado, filtros globales, `dcc.Store`, cuatro pestañas y descubrimiento automático de módulos.
- **Métricas** (`app/utils/metricas.py`): estadía ponderada, proporción turista/excursionista, promedio mensual, lift por evento y patrón semanal.
- **Módulo 1** (`app/modulo1.py`) y **Módulo 2** (`app/modulo2.py`).
- **Docker** (`Dockerfile`, `docker-compose.yml`, `.dockerignore`).
- **Documentación**: `docs/fichas_modulo1_2.md` (17 fichas), `docs/seccion_modulos_1_2.md`, `docs/paleta.md` y la sección de la app en el `README.md`.

## Archivos creados
```
app/main.py  app/theme.py  app/modulo1.py  app/modulo2.py  app/utils/datos.py  app/utils/metricas.py
tests/test_datos.py  tests/test_app_base.py  tests/test_metricas.py  tests/test_modulo1.py  tests/test_modulo2.py
Dockerfile  docker-compose.yml  .dockerignore
docs/paleta.md  docs/fichas_modulo1_2.md  docs/seccion_modulos_1_2.md  HANDOFF_P2.md
```

## Cómo ejecutar y probar
```bash
pip install -r requirements.txt
python -m etl.run_all                                   # genera data/processed/ (ver README)
python -m app.main                                      # http://localhost:8050
docker compose up --build                               # http://localhost:8050 (solo 127.0.0.1)
docker compose down
python -m pytest tests/test_datos.py tests/test_app_base.py tests/test_metricas.py tests/test_modulo1.py tests/test_modulo2.py -v
```
Resultados confirmados por el equipo: datos 32 pruebas aprobadas, infraestructura Dash 35, métricas 30, Módulo 1 21, Módulo 2 32. Docker: aplicación comprobada visualmente con datos reales. No se hicieron otras pruebas de integración.

## Cómo agregar `app/modulo3.py` o `app/modulo4.py`
`main.py` importa `app.modulo1`…`app.modulo4` por nombre. Basta crear el archivo con `layout()` y, opcionalmente, `registrar_callbacks(app)`; no hay que editar `main.py`. Mientras el archivo no exista, la pestaña muestra «En construcción».

Plantilla mínima (prefijo de IDs `m3-`; `m4-` para P4):

```python
from dash import Input, Output, dcc, html
from app.theme import ID_STORE_FILTROS, figura_sin_dato, subtitulo_periodo
from app.utils import datos
from app.utils.datos import Filtros

def layout():                                     # sin argumentos; devuelve un componente
    return html.Div([dcc.Graph(id="m3-ocupacion", config={"displayModeBar": False})])

def registrar_callbacks(app):                     # opcional; recibe la instancia Dash
    @app.callback(Output("m3-ocupacion", "figure"), Input(ID_STORE_FILTROS, "data"))
    def _ocupacion(estado):
        f = Filtros.desde_dict(estado)            # mes_ini, mes_fin, tipo, subdestino
        df = datos.filtrar_mensual(datos.cargar("ocupacion"), f)
        titulo, sub = "Ocupación", subtitulo_periodo(f.mes_ini, f.mes_fin, "ocupacion")
        if df.empty:                              # sin cobertura: «Sin dato», nunca 0
            return figura_sin_dato(titulo, sub)
        ...                                       # construir la figura con theme.PLANTILLA
```

## Cómo consumir `store-filtros`
- Es un `dcc.Store` con `{mes_ini, mes_fin, tipo, subdestino}` (meses como `"YYYY-MM"`). **Solo `main.py` lo escribe**; los módulos lo leen con `Input("store-filtros", "data")`.
- Conviértalo con `Filtros.desde_dict(estado)`. `tipo` y `subdestino` siempre traen un valor; no existe «Todos», así que nunca se suman nacionales y extranjeros ni subdestinos.
- `datos.filtrar_mensual(df, f)` (columna `anio_mes`) y `datos.filtrar_diaria(df, f)` (columna `fecha`, incluye todo el mes final). **Ojo:** si la tabla no tiene `tipo` o `subdestino` (p. ej. `ocupacion`, `oferta`) esos filtros se omiten; la ocupación y la oferta son del departamento de Alta Verapaz y hay que filtrarlas por `departamento` en el módulo.
- Para la movilidad, reutilice `modulo1.solo_alta_verapaz(df)` y `modulo1.preparar(df, f)` (Alta Verapaz + filtros). `modulo1.serie_completa(f)` indica si hay un subdestino y un tipo.

## Cómo reutilizar `app/theme.py`
- Colores: `COLOR_OBSERVADO`, `CATEGORICOS`, `SECUENCIAL`/`ESCALA_VOLUMEN`, `COLOR_SIN_DATO`; **`COLOR_ESTIMACION` es exclusivo de estimaciones** (nunca para dato observado).
- `PLANTILLA` (`template=theme.PLANTILLA`), `titulo_con_subtitulo(titulo, sub)`, `subtitulo_periodo(ini, fin, fuente)`, `etiqueta_mes(...)`.
- `figura_sin_dato(titulo, periodo)`, `rotulo_estimacion()`, `estilo_estimacion()`, `razon_contraste`/`cumple_aa`.
- Constantes de IDs compartidos: `ID_STORE_FILTROS`, `ID_SLOT_COBERTURA`.

## Cómo usar `app/utils/datos.py` y `app/utils/metricas.py`
- `datos.cargar(nombre)` solo acepta las 17 tablas del contrato y devuelve una copia (la caché no se altera). Si falta el archivo lanza `FileNotFoundError`.
- `datos.meses_observados`, `tipos_disponibles`, `subdestinos_disponibles`, `rango_meses`, `reindexar_meses` (los meses sin cobertura quedan `NaN`, no 0).
- `metricas.*` exige datos de **un** subdestino y **un** tipo (lanza `ValueError` si se mezclan) y rechaza estimaciones.

## IDs y convenciones de callbacks
- Todo ID lleva el prefijo del módulo (`m1-`, `m2-`, `m3-`, `m4-`). `crear_app` lanza `ValueError` si hay IDs repetidos; Dash también falla si dos callbacks escriben la misma salida.
- Cada gráfico declara período y fuente en el subtítulo; si no hay filas devuelve `figura_sin_dato`.
- Mantenga los cálculos como funciones puras fuera del callback para poder probarlas con datos sintéticos (ver `tests/test_modulo1.py`).
- Gráficos con `config={"displayModeBar": False}`; no hay descargas ni tablas de microdatos.
- Estado interno de un módulo: use un `dcc.Store` propio con prefijo (p. ej. `m1-seleccion`); el módulo que lo define es el único que lo escribe.

## Indicador de cobertura (pendiente de P3)
- `main.py` deja el espacio `id="slot-cobertura"` (constante `theme.ID_SLOT_COBERTURA`) en el encabezado con el texto «Indicador de cobertura: pendiente (P3)». P3 debe reemplazar su contenido con los chips por fuente, usando `cobertura.parquet` (`fuente`, `anio_mes`, `tiene_dato`, `dias_con_dato`, `dias_en_mes`, `granularidad`, `cobertura_completa`). Fuentes en la tabla: `movilidad_mensual`, `movilidad_diaria`, `migracion`, `ocupacion`, `tikal`, `aimm_pasajeros`, `aimm_operaciones` y `oferta_corte_anual`; el Grupo 4 solo tiene las que sus archivos aportan.
- Hoy los módulos 1 y 2 muestran «Sin dato» según la presencia de filas, no según la tabla `cobertura`. Aplicar el indicador a esos módulos es trabajo de P3 (PR separado).

## Problemas conocidos y limitaciones
1. El tema Bootstrap se carga desde un CDN en el navegador: sin internet la app se ve sin estilos.
2. `modulo2` usa `metricas._presencia_por_fecha`, una función no pública. Conviene hacerla pública si se modifica `metricas.py`.
3. El ranking de mercados promedia solo los meses en que cada país tiene dato (se muestra `n_meses`); una fila ausente no se interpreta como cero.
4. La selección de mercado requiere los dos segmentos en cada mes; si falta uno, ese mes sale como «Sin dato» en las proporciones.
5. El KPI de días-persona exige `dias_persona` sin nulos en los dos segmentos; si no, muestra «Sin dato».
6. El panel de pronóstico ignora el rango de meses global (muestra la serie completa y la estimación de ene–feb 2026).
7. El lift es muy variable con pocos días de evento; la tabla muestra los días usados.
8. Los nacionales llevan factor de expansión y no se desagregan por origen. No existe total del destino.
9. El contenedor corre con sistema de archivos de solo lectura; si surge un error al escribir, revisar `read_only` en `docker-compose.yml`.
10. `python -m app.main` escucha en todas las interfaces (`0.0.0.0`); para uso local es preferible Docker Compose, que publica solo en `127.0.0.1`.

## Qué debe verificar P3 antes de continuar
- Que `data/processed/` esté generado (`python -m etl.run_all`) y que las pruebas de P2 listadas arriba pasen en su máquina.
- Que `docker compose up --build` levante la app en `http://localhost:8050` con los módulos 1 y 2 funcionando.
- Que sus tablas (`ocupacion`, `oferta`, `cobertura`) existan en `data/processed/` y revisar sus columnas en `docs/data_contract.md`.
- Que la regla metodológica correspondiente se respete: el cruce afluencia–ocupación solo en sep–dic 2025, la oferta como corte anual (no tendencia) y los subdestinos nunca sumados.
- Que sus IDs usen el prefijo `m3-` y no choquen con los de los módulos 1 y 2.
