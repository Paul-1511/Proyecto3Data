# HANDOFF P3 → P4

**Estado:** P3 completo. Incluye el Módulo 3 (oferta hotelera y desagregación territorial), el indicador de cobertura del
encabezado, su aplicación a los módulos 1 y 2, y la documentación (fichas, supuestos y limitaciones, hallazgos). Tag
`handoff-p3`.

## Ramas y PR

| Rama | Contenido | Base |
|---|---|---|
| `p3/modulo3-cobertura` | Utilidad e indicador de cobertura, Módulo 3, pruebas, documentación y este archivo | `main` |
| `p3/cobertura-modulos-1-2` | **PR separado**: los módulos 1 y 2 respetan la tabla de cobertura (cambio mínimo en sus cargadores) | `p3/modulo3-cobertura` |

Fusionar primero `p3/modulo3-cobertura` y después `p3/cobertura-modulos-1-2`. El segundo usa
`cobertura.solo_con_cobertura`, que se agrega en esa misma rama.

**Cambio en los módulos de P2 (aviso):** en `app/modulo1.py` y `app/modulo2.py` solo cambian `_leer_sub`, `_leer_pais` y
`_leer_diaria`. Ahora pasan por `cobertura.solo_con_cobertura(df, fuente)`, que descarta los meses que `cobertura.parquet`
marca sin dato (y así esos meses se rotulan «Sin dato»). Con los datos actuales no cambia ninguna cifra, porque filas y
cobertura coinciden. La regla queda garantizada aunque cambie el ETL. Las pruebas de P2 pasan sin modificación.

## Cómo ejecutar y probar
```bash
uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -r requirements.txt   # o pip con Python 3.11
.venv/bin/python -m etl.run_all            # 17 tablas en data/processed/
.venv/bin/python -m app.main               # http://localhost:8050 → pestaña «3 Oferta y territorio»
.venv/bin/python -m pytest -q              # 252 aprobadas, 8 omitidas (con las dos ramas)
docker compose up --build                  # http://localhost:8050 ; detener: docker compose down
```
Pruebas nuevas: `tests/test_cobertura.py`, `tests/test_indicador_cobertura.py`, `tests/test_oferta_ocupacion.py` y
`tests/test_modulo3.py`. Docker se comprobó con los módulos 1–3 juntos: pestañas 1, 2 y 3, chips de cobertura, «Sin dato» en
mar–ago 2026 y los clics entre gráficos.

## Qué implementó P3

### Módulo 3 (`app/modulo3.py`, cálculos en `app/utils/oferta_ocupacion.py`)
- **A. Capacidad instalada 2022–2025** (departamento): barras agrupadas por corte anual, con selector de establecimientos,
  habitaciones o plazas cama. 2026 está apagado por defecto; si se activa, va rayado y rotulado «corte parcial (T1)». Nota
  visible: «No incluye plataformas digitales (Airbnb)».
- **B. Ocupación mensual 2023–2025**: serie continua con el promedio simple de los 22 departamentos (opcional y rotulado «no es
  el índice nacional oficial») y los picos y valles de cada año. Sin proyecciones. Tiene dos vistas: serie completa o solo
  los meses del filtro (sin cruce con el filtro → «Sin dato»).
- **C. Ventana sep–dic 2025**: dos paneles alineados (visitantes del subdestino y tipo / índice de ocupación). La lectura se
  hace por dirección de los cambios mensuales, sin correlación, con el aviso de n = 4 en pantalla. `datos_cruce` lanza
  `ValueError` con cualquier mes fuera de la ventana.
- **D. Subdestinos**: afluencia de Cobán, Lanquín y Cuevas de Candelaria (promedio de los meses observados o un mes), con
  la etiqueta «% del mayor». Nunca hay barra «Total»: `fig_subdestinos` lanza `ValueError` si la recibe.
- **E. Estacionalidad**: índice estacional de la ocupación por año frente al perfil compuesto de visitantes (media = 100).
- **Interacción**: clic en un año de A → B sombrea ese año y E lo resalta. Clic en un mes de C (o de B dentro de sep–dic
  2025) → D muestra ese mes. Clic en un subdestino de D → C y E usan ese subdestino. El botón «Quitar selección» limpia
  todo. Al cambiar el filtro global se borra la selección de subdestino.

### Indicador de cobertura
- `app/utils/cobertura.py` (lógica, sin Dash) y `app/indicador_cobertura.py` (chips). Hay un chip por fuente (Movilidad,
  Movilidad diaria, Ocupación, Oferta, Migración, más las extra si la tabla las trae): ✓ verde = completa, ◐ verde claro =
  parcial, — gris = sin dato. El tooltip muestra el período cubierto y los meses sin dato.
- `main.py` solo cambió dos cosas: importa `indicador_cobertura` y llama a `indicador_cobertura.registrar_callbacks(app)`; el
  texto «pendiente (P3)» pasó a «Cargando…». En `theme.py` se agregaron 4 colores de chips (con pares AA en
  `PARES_TEXTO_AA`).

### Documentación
- `docs/fichas_modulo3.md`: 12 fichas de 8 campos (Módulo 3 + indicador de cobertura).
- `docs/seccion_supuestos_y_limitaciones.md`: puntos a) a h) y la tabla de calidad de las fuentes.
- `docs/hallazgos_modulo3.md`: 3 hallazgos cuantitativos (y uno complementario) para el resumen ejecutivo.

## Qué debe reutilizar P4

**Cobertura** (`from app.utils import cobertura as cb`):
- `cb.cargar()`: la tabla validada (vacía si falta el parquet).
- `cb.tiene_dato(cob, fuente, ini, fin)`, `cb.meses_con_dato(...)`, `cb.meses_sin_dato(...)`: decidir «Sin dato» según la
  cobertura y no según la presencia de filas.
- `cb.solo_con_cobertura(df, fuente)`: el mismo filtro que usan los módulos 1 y 2.
- `cb.estado_fuentes(cob, ini, fin)` y `cb.texto_tramos(meses)`: texto de período del tipo «sep 2025 – dic 2025, mar 2026 –
  ago 2026».
- **No escriba en `slot-cobertura`**: el indicador ya está en el encabezado de todas las pestañas y `indicador_cobertura` es
  su único escritor. Si P4 suma una fuente extra, basta con que el ETL la agregue a `cobertura.parquet`; el chip aparece solo
  (para darle nombre propio, agréguela a `cobertura.FUENTES`).

**Filtros y datos** (patrón de P2, sin cambios):
- Lea `store-filtros` con `Filtros.desde_dict(estado)`. `tipo` y `subdestino` siempre traen un valor.
- `oo.visitantes_mes(mov, subdestino, tipo, meses)`: visitantes únicos del mes de una serie (suma de segmentos dentro del
  mes, NaN si falta uno).
- `oo.afluencia_subdestinos(mov, tipo, meses, mes)`: comparación de subdestinos sin total.
- `oo.SUBDESTINOS`, `oo.nombre_subdestino()` (rótulos con tilde), `oo.VENTANA_CRUCE`, `oo.meses_cruce(ini, fin)`.
- Patrón de clic: `m3.valor_desde_click`, `m3.mes_desde_click` y `m3.alternar`, más un `dcc.Store` propio con prefijo
  (`m4-…`) por cada selección. Ejemplo completo en `registrar_callbacks` de `app/modulo3.py`.

## Pendientes
1. **Tags `handoff-p1` y `handoff-p2` no existen en el remoto** (P3 empezó desde `main` con el PR #4 fusionado). Que P1 y P2 los
   creen y suban.
2. **Total del destino**: la consigna del bloque C pedía «movilidad mensual, total destino», pero la fuente no trae esa fila y
   la guía prohíbe sumar subdestinos. El cruce se hace por subdestino y tipo. Sigue abierta la pregunta a la coordinación
   (también figura en HANDOFF_P1).
3. **Bloque E**: no existe ocupación de residentes y no residentes en los datos del grupo. Por eso se hizo la estacionalidad
   de ocupación frente a la de visitantes (la otra opción que daba la consigna).
4. P4 debe llevar los hallazgos de `docs/hallazgos_modulo3.md` al resumen ejecutivo de la memoria.

## Bugs y limitaciones conocidos
1. **Calendario del filtro global**: el rango de meses solo va de sep 2025 a ago 2026, porque P2 lo toma de la movilidad. Desde
   el filtro no se puede elegir 2023–2024. Por eso B muestra la serie completa por defecto y A no depende del rango (es
   anual).
2. **La cobertura es por fuente, no por destino** (así la construye `etl/cobertura.py`). Ejemplo: la movilidad diaria de Alta
   Verapaz no tiene jul-2025, pero otro destino sí (2 días). No afecta al tablero, porque jul-2025 está fuera del calendario
   del filtro.
3. La tabla de cobertura empieza en 2017: el tooltip de Migración dice «ene 2017 – jun 2026», aunque la base empieza en 2009.
4. **Docker**: gunicorn registra `Control server error: [Errno 30] Read-only file system: '/home/observatorio'` por el
   `read_only: true` de `docker-compose.yml` (configuración de P2). La app sirve normal; para silenciarlo, montar un `tmpfs`
   en `/home/observatorio` o desactivar el control server de gunicorn.
5. El tooltip de los chips se vuelve a crear con cada cambio de filtro (lo hace `dbc.Tooltip`); con muchos cambios rápidos puede
   parpadear.
6. Entorno local: la Mac del equipo trae Python 3.14 y el stack fija 3.11. Use `uv venv --python 3.11` (o pyenv). En Docker ya
   es 3.11.
7. Los archivos de datos llegaron en una carpeta `OneDrive_…` en la raíz del repo y se movieron a `data/raw/`. `*.xlsx` y
   `*.csv` están en `.gitignore`, pero conviene descargarlos directo a `data/raw/`.
