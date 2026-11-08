# Fichas técnicas — Módulos 1 y 2

Cada ficha tiene los ocho campos exigidos por la guía. Las expresiones de la fila 4 son las que ejecuta el código
(`app/modulo1.py`, `app/modulo2.py`, `app/utils/metricas.py`); las del pronóstico las calcula P1 en `etl/pronostico.py` y
el tablero solo las muestra. Reglas comunes a todas las fichas:

- Todo se calcula por **un subdestino y un tipo** (`extranjero` o `nacional`) a la vez. No existe total del destino y no se suman subdestinos ni tipos.
- Solo se usan filas con `destino_clave == "alta_verapaz"`, subdestino `Coban`, `Lanquin` o `Cuevas De Candelaria` y `tipo` en `extranjero`/`nacional` (`modulo1.solo_alta_verapaz`). `sin_dato` se excluye.
- Una fila o un mes ausente es **«Sin dato»**, nunca cero. Una suma con algún nulo se considera desconocida (`metricas._suma_estricta`).
- Cada gráfico declara su período (`theme.subtitulo_periodo`). Lo estimado se rotula «Estimación» y usa el color exclusivo de `theme.py`.

**Orígenes de datos** (nombres reales según `etl/movilidad.py` y `docs/data_contract.md`):

- **MENSUAL** — `BD_moviidad_mensual.xlsx`, hoja «Alta Verapaz». Columnas de origen: `destino`, `anio`, `mes`, `pais`, `es_consecutivo`, `visitantes`, `dias_persona`, `permanencia_prom`. Tablas procesadas: `movilidad_subdestino_mes.parquet` (`destino_clave`, `subdestino`, `anio_mes`, `tipo`, `segmento`, `visitantes`, `dias_persona`, `estadia_ponderada`) y `movilidad_mensual.parquet` (además `pais`). Cobertura: sep–dic 2025 y mar–ago 2026 (10 meses).
- **DIARIA** — `BD_moviidad_diario.xlsx`, hoja «Alta Verapaz». Columnas de origen: `destino`, `idfecha`, `dia_semana`, `pais`, `evento`, `cantidad_visitantes`. Tabla procesada: `movilidad_diaria.parquet` (`destino_clave`, `subdestino`, `fecha`, `anio_mes`, `pais`, `tipo`, `evento`, `es_regular`, `presencia`).
- **PRONÓSTICO** — `pronostico_ene_feb_2026.parquet` (generado por `etl/pronostico.py` a partir de la movilidad mensual y de `Base_Migracion_2009-2026jun.xlsx`) y `pronostico_resumen_modelo.parquet`.

Índice: 1 Visitantes promedio mensual · 2 Días-persona promedio mensual · 3 Estadía media ponderada · 4 Turista frente a excursionista · 5 Mercados emisores extranjeros · 6 Visitantes nacionales por mes · 7 Estadía media ponderada por mes · 8 Presencia diaria · 9 Lift por evento · 10 Patrón semanal · 11 Mapa de calor día × mes · 12 Visitantes mensuales observados (panel de pronóstico) · 13 Estimación mensual ene–feb 2026 · 14 Intervalo de la estimación · 15 MAPE · 16 RMSE · 17 MAE.

---

## Ficha 1 — Visitantes promedio mensual (Módulo 1, tarjeta KPI)

| Campo | Contenido |
|---|---|
| 1. Nombre | Visitantes promedio por mes |
| 2. Definición de negocio | Tamaño típico de la demanda mensual de un subdestino y tipo de visitante, para dimensionar servicios y comparar subdestinos sin construir un total del destino que la fuente no trae. |
| 3. Fórmula | V̄(s,t) = (1/\|M\|) · Σ<sub>m∈M</sub> [ V(s,t,m,"mas_de_1_dia") + V(s,t,m,"menos_de_1_dia") ], donde M es el conjunto de meses con los dos segmentos presentes y sin nulos. |
| 4. Implementación | `metricas.promedio_mensual_visitantes(df)`: `validos = _visitantes_por_mes_y_segmento(df).dropna()`; `por_mes = validos.sum(axis=1)`; `PromedioMensual(float(por_mes.mean()), int(len(por_mes)))`. Con `_visitantes_por_mes_y_segmento` = `df.groupby(["anio_mes","segmento"])["visitantes"].agg(_suma_estricta).unstack("segmento").reindex(columns=["mas_de_1_dia","menos_de_1_dia"])`. En el módulo: `tarjetas_kpi(preparar(_leer_sub(), f), f)` → `_kpi(vis.promedio, vis.n_meses, periodo, ",.0f")`. |
| 5. Agregación y granularidad | Origen: subdestino × mes × tipo × segmento. Cálculo: promedio de meses para un subdestino y un tipo dentro del rango de meses del filtro global. |
| 6. Unidad | Visitantes únicos por mes (personas). Se acompaña de «n meses observados». |
| 7. Fuente | MENSUAL → `movilidad_subdestino_mes.parquet`: `destino_clave`, `subdestino`, `anio_mes`, `tipo`, `segmento`, `visitantes`. |
| 8. Reglas y exclusiones | No suma visitantes entre meses ni entre subdestinos. Los dos segmentos se suman solo dentro del mismo mes (categorías excluyentes según P1). Un mes sin uno de los segmentos, o con nulos, queda fuera y no cuenta como cero. Sin meses válidos: «Sin dato». Nacionales y extranjeros no se mezclan; los nacionales llevan factor de expansión. |

## Ficha 2 — Días-persona promedio mensual (Módulo 1, tarjeta KPI)

| Campo | Contenido |
|---|---|
| 1. Nombre | Días-persona promedio por mes |
| 2. Definición de negocio | Presión total de permanencia sobre el territorio: personas × días que pasan en el subdestino. Complementa a los visitantes, porque dos subdestinos con igual número de visitantes pueden ocupar el territorio de forma muy distinta. |
| 3. Fórmula | DP̄(s,t) = (1/\|M\|) · Σ<sub>m∈M</sub> [ DP(s,t,m,"mas_de_1_dia") + DP(s,t,m,"menos_de_1_dia") ], M = meses con los dos segmentos sin nulos en `dias_persona`. |
| 4. Implementación | Reutiliza la misma función con la columna de valor cambiada: `dias = metricas.promedio_mensual_visitantes(df.assign(visitantes=df["dias_persona"]))`; `_kpi(dias.promedio, dias.n_meses, periodo, ",.0f")`. No hay una métrica nueva. |
| 5. Agregación y granularidad | Igual que la ficha 1 (subdestino × mes × tipo × segmento → promedio de meses de un subdestino y un tipo). |
| 6. Unidad | Días-persona por mes. |
| 7. Fuente | MENSUAL → `movilidad_subdestino_mes.parquet`: `subdestino`, `anio_mes`, `tipo`, `segmento`, `dias_persona`. |
| 8. Reglas y exclusiones | Las mismas de la ficha 1. El número de meses puede ser menor que el de la ficha 1 si `dias_persona` tiene nulos. No se suman meses ni subdestinos; una persona puede estar contada en varios subdestinos. |

## Ficha 3 — Estadía media ponderada (Módulo 1, tarjeta KPI)

| Campo | Contenido |
|---|---|
| 1. Nombre | Estadía media ponderada (más de 1 día) |
| 2. Definición de negocio | Cuántos días permanece en promedio quien pernocta o se queda más de un día; base para estimar gasto, demanda de alojamiento y duración de la oferta de actividades. |
| 3. Fórmula | E(s,t) = Σ<sub>m</sub> DP(s,t,m,"mas_de_1_dia") / Σ<sub>m</sub> V(s,t,m,"mas_de_1_dia") |
| 4. Implementación | `metricas.estadia_ponderada(df)`: `seg = df.loc[df["segmento"] == "mas_de_1_dia", ["dias_persona","visitantes"]].dropna()`; `denominador = seg["visitantes"].sum()`; `float(seg["dias_persona"].sum() / denominador)` (NaN si no hay filas o `denominador <= 0`). KPI: `_kpi(estadia, n_meses, periodo, ".2f", " días")`, con `n_meses` = meses distintos de `solo_mas`. |
| 5. Agregación y granularidad | Origen: subdestino × mes × tipo × segmento. Cálculo: razón de sumas sobre los meses del rango, para un subdestino y un tipo. |
| 6. Unidad | Días. |
| 7. Fuente | MENSUAL → `movilidad_subdestino_mes.parquet`: `segmento`, `dias_persona`, `visitantes`. No usa `permanencia_prom` ni `estadia_ponderada` ya calculada. |
| 8. Reglas y exclusiones | Prohibido promediar `permanencia_prom` o promedios previos. Solo segmento `mas_de_1_dia`. Las filas con nulos en cualquiera de las dos columnas se excluyen de ambas sumas. Valores negativos son un error. Tooltip con la fórmula en la tarjeta. No se mezclan tipos ni subdestinos. |

## Ficha 4 — Turista frente a excursionista (Módulo 1, barras apiladas 100 %)

| Campo | Contenido |
|---|---|
| 1. Nombre | Turista vs. excursionista por mes (más / menos de 1 día) |
| 2. Definición de negocio | Peso relativo de quien se queda más de un día frente a quien visita en el día, mes a mes, para orientar la oferta de pernocta frente a la de visita corta. |
| 3. Fórmula | p<sub>mas</sub>(m) = V<sub>mas</sub>(m) / (V<sub>mas</sub>(m) + V<sub>menos</sub>(m)); p<sub>menos</sub>(m) = 1 − p<sub>mas</sub>(m) |
| 4. Implementación | `metricas.proporcion_turista_excursionista(df)`: `total = base["mas_de_1_dia"] + base["menos_de_1_dia"]`; `(base["mas_de_1_dia"] / total).where(total > 0)` y análogo para `menos_de_1_dia`. El gráfico usa `props[col] * 100` tras `datos.reindexar_meses(...)` (`modulo1.fig_segmentos`). |
| 5. Agregación y granularidad | Origen: subdestino × mes × tipo × segmento (o, con mercado seleccionado, subdestino × mes × país × segmento). Cálculo: una proporción por mes; no hay total del período. |
| 6. Unidad | Porcentaje de los visitantes del mes (0–100 %). |
| 7. Fuente | MENSUAL → `movilidad_subdestino_mes.parquet` (`segmento`, `visitantes`, `anio_mes`) o `movilidad_mensual.parquet` filtrada por `pais` si hay mercado seleccionado. |
| 8. Reglas y exclusiones | Los segmentos de la fuente se llaman «más de 1 día» y «menos de 1 día»; llamarlos turista y excursionista es una convención de P1 (categorías excluyentes). Si falta un segmento en un mes, hay nulos o el total es 0, ambas proporciones son NaN y el mes se rotula «Sin dato». No se construye ningún total de visitantes únicos entre meses. Con tipo global nacional la selección de mercado no se aplica. |

## Ficha 5 — Mercados emisores extranjeros (Módulo 1, top 10)

| Campo | Contenido |
|---|---|
| 1. Nombre | Top 10 mercados emisores extranjeros (promedio mensual) |
| 2. Definición de negocio | Identificar los países que más visitantes aportan a un subdestino para priorizar promoción y adaptar la oferta (idioma, producto, canales). |
| 3. Fórmula | Para el mercado g: X̄(g) = (1/\|M<sub>g</sub>\|) · Σ<sub>m∈M<sub>g</sub></sub> [ Σ<sub>seg</sub> V(g,m,seg) ], M<sub>g</sub> = meses en que g tiene dato sin nulos. Se ordena por X̄(g) descendente y se toman los 10 primeros. |
| 4. Implementación | `modulo1.ranking_mercados(df, n=10)`: `por_mes = base.groupby(["pais","anio_mes"])["visitantes"].agg(_suma_estricta).dropna()`; `r = por_mes.groupby(level="pais").agg(["mean","count"]).reset_index()`; `r.sort_values(["promedio_mensual","pais"], ascending=[False, True]).head(n)`. `ranking_extranjeros` fuerza `preparar(df_pais, f, tipo="extranjero")`. |
| 5. Agregación y granularidad | Origen: subdestino × mes × país × segmento. Cálculo: promedio por país de sus meses con dato, dentro de un subdestino y del rango del filtro. |
| 6. Unidad | Visitantes únicos por mes (promedio); `n_meses` visible al pasar el cursor. |
| 7. Fuente | MENSUAL → `movilidad_mensual.parquet`: `destino_clave`, `subdestino`, `anio_mes`, `pais`, `tipo`, `segmento`, `visitantes`. |
| 8. Reglas y exclusiones | Solo `tipo == "extranjero"`, sin importar el tipo global. Excluye `sin_dato` y países nulos. No suma meses. Una fila ausente de un país no se interpreta como cero: el promedio usa solo los meses en que el mercado aparece (se informa `n_meses`). No hay desagregación por origen para nacionales. Clic en una barra selecciona el mercado para las fichas 4 y 7. |

## Ficha 6 — Visitantes nacionales por mes (Módulo 1, panel de nacionales)

| Campo | Contenido |
|---|---|
| 1. Nombre | Visitantes nacionales por mes |
| 2. Definición de negocio | Mostrar el universo nacional por separado del extranjero, porque su escala y su método de estimación son distintos. |
| 3. Fórmula | V<sub>nac</sub>(s,m) = V(s,"nacional",m,"mas_de_1_dia") + V(s,"nacional",m,"menos_de_1_dia"), solo en meses con los dos segmentos sin nulos. El subtítulo informa el promedio mensual de la ficha 1. |
| 4. Implementación | `modulo1.visitantes_mensuales(df)`: `tabla = df.groupby(["anio_mes","segmento"])["visitantes"].agg(_suma_estricta).unstack("segmento")`; `tabla.reindex(columns=list(metricas.SEGMENTOS)).dropna().sum(axis=1)`; luego `mensual.reindex(meses)` para dejar huecos. |
| 5. Agregación y granularidad | Origen: subdestino × mes × tipo × segmento. Cálculo: un valor por mes para un subdestino y `tipo == "nacional"`. |
| 6. Unidad | Visitantes únicos del mes. |
| 7. Fuente | MENSUAL → `movilidad_subdestino_mes.parquet`: `subdestino`, `anio_mes`, `tipo`, `segmento`, `visitantes`. |
| 8. Reglas y exclusiones | Cifras con factor de expansión (advertencia visible). No se desagregan por origen. Meses sin cobertura: hueco y «Sin dato». No se suman meses ni subdestinos. Se muestra siempre el universo nacional, aunque el filtro global sea extranjero. |

## Ficha 7 — Estadía media ponderada por mes (Módulo 1, visualización adicional)

| Campo | Contenido |
|---|---|
| 1. Nombre | Estadía media ponderada por mes (más de 1 día) |
| 2. Definición de negocio | Detectar si la permanencia cambia por temporada o por mercado, lo que la tarjeta de promedio no muestra. |
| 3. Fórmula | E(s,t,m) = DP(s,t,m,"mas_de_1_dia") / V(s,t,m,"mas_de_1_dia"), una por mes. |
| 4. Implementación | `modulo1.fig_estadia`: `valores = [metricas.estadia_ponderada(df[df["anio_mes"] == m]) for m in meses]`; los meses sin filas dan NaN y se anotan «Sin dato» (`connectgaps=False`). Con mercado seleccionado, `df` viene de `movilidad_mensual` filtrada por `pais`. |
| 5. Agregación y granularidad | Origen: subdestino × mes × tipo × segmento (o × país). Cálculo: un valor por mes. |
| 6. Unidad | Días. |
| 7. Fuente | MENSUAL → `movilidad_subdestino_mes.parquet` o `movilidad_mensual.parquet`: `anio_mes`, `segmento`, `dias_persona`, `visitantes`. |
| 8. Reglas y exclusiones | Mismas reglas que la ficha 3. El eje parte de cero solo como escala visual; los meses ausentes no se dibujan como cero. Con tipo global nacional la selección de mercado se ignora. |

## Ficha 8 — Presencia diaria (Módulo 2, serie diaria)

| Campo | Contenido |
|---|---|
| 1. Nombre | Presencia diaria |
| 2. Definición de negocio | Ver el pulso diario de afluencia a un subdestino y reconocer el efecto de feriados y festividades sobre la presencia. |
| 3. Fórmula | P(s,t,d) = Σ<sub>p</sub> presencia(s,t,d,p), suma sobre los países de la misma serie en la fecha d. |
| 4. Implementación | `modulo2.serie_diaria(df)` → `metricas._presencia_por_fecha(df, con_evento=True)`: `d["fecha"] = pd.to_datetime(d["fecha"]).dt.normalize()`; `g["presencia"].agg(_suma_estricta)`; luego `dias["presencia"].reindex(rango)` con `rango = pd.date_range(ini, fin_mes + pd.DateOffset(months=1) - pd.Timedelta(days=1), freq="D")`. Eventos seleccionados: rectángulos por tramo consecutivo (`_tramos`); marcas para días no regulares. |
| 5. Agregación y granularidad | Origen: subdestino × fecha × país. Cálculo: un valor por fecha para un subdestino y un tipo. |
| 6. Unidad | Personas presentes por día. |
| 7. Fuente | DIARIA → `movilidad_diaria.parquet`: `destino_clave`, `subdestino`, `fecha`, `tipo`, `pais`, `evento`, `es_regular`, `presencia` (origen `cantidad_visitantes`). |
| 8. Reglas y exclusiones | La presencia diaria no es visitantes únicos mensuales: no se suma para reconstruir el mes ni se grafica junto a la serie mensual. Los días sin fila son huecos (tramos grises, «Sin dato» en los de 7 días o más), nunca ceros. Una fecha con dos eventos distintos es un error. No se suman subdestinos ni tipos. |

## Ficha 9 — Lift por evento (Módulo 2, tabla)

| Campo | Contenido |
|---|---|
| 1. Nombre | Lift de presencia por evento |
| 2. Definición de negocio | Cuantificar cuánto más (o menos) visitado está un subdestino en un feriado o festividad que en un día regular equivalente, para planificar capacidad, seguridad y promoción. |
| 3. Fórmula | Lift(e) = ( x̄<sub>e</sub> / x̄<sub>reg</sub> − 1 ) · 100, con x̄<sub>e</sub> = media de P en los días del evento comparables y x̄<sub>reg</sub> = media de las medias de P de los días regulares del mismo día de la semana, una por cada día del evento. |
| 4. Implementación | `metricas.lift_evento(diaria, evento)`: `media_por_dow = regulares.groupby("dow")["presencia"].mean()`; `comparables = del_evento[del_evento["dow"].isin(media_por_dow.index)]`; `media_evento = comparables["presencia"].mean()`; `media_regular = comparables["dow"].map(media_por_dow).mean()`; `(media_evento / media_regular - 1) * 100`. `modulo2.tabla_lift` aplica la función a cada evento y ordena por lift descendente con NaN al final. |
| 5. Agregación y granularidad | Origen: subdestino × fecha × país → presencia por fecha. Cálculo: una cifra por evento, para un subdestino y un tipo, dentro del rango de meses del filtro. |
| 6. Unidad | Porcentaje sobre la presencia regular. La tabla muestra además presencia media del evento, media regular comparable y días usados (evento / regulares). |
| 7. Fuente | DIARIA → `movilidad_diaria.parquet`: `fecha`, `evento`, `es_regular`, `presencia`, `subdestino`, `tipo`. |
| 8. Reglas y exclusiones | Día regular = `es_regular == True` (`evento == "Regular"`). Los días del evento sin día regular del mismo día de la semana se excluyen. Sin días comparables o media regular ≤ 0: lift NaN, mostrado como «Sin dato», nunca 0 %. Con pocos días el valor es muy variable (se muestran los días usados). «Regular» no es un evento. Sin eventos seleccionados se listan todos los disponibles. |

## Ficha 10 — Patrón semanal (Módulo 2, barras)

| Campo | Contenido |
|---|---|
| 1. Nombre | Patrón semanal de presencia |
| 2. Definición de negocio | Saber qué días de la semana concentran la presencia, para programar servicios, personal y promociones de fin de semana. |
| 3. Fórmula | P̄(w) = (1/\|D<sub>w</sub>\|) · Σ<sub>d∈D<sub>w</sub></sub> P(d), D<sub>w</sub> = fechas distintas con día de la semana w y presencia disponible. |
| 4. Implementación | `metricas.patron_semanal(diaria, solo_regulares=False)`: `dias = _presencia_por_fecha(base, con_evento=False)`; `dias.groupby("dow")["presencia"].agg(["mean","count"]).reindex(range(7))`. `modulo2.patron_modo` selecciona los días: todos, `solo_regulares=True`, o `diaria[diaria["evento"].isin(eventos)]`. |
| 5. Agregación y granularidad | Origen: subdestino × fecha × país. Cálculo: media por día de la semana (lunes a domingo, siempre 7 filas) para un subdestino y un tipo. |
| 6. Unidad | Personas presentes por día (media); `n_dias` indica las fechas promediadas. |
| 7. Fuente | DIARIA → `movilidad_diaria.parquet`: `fecha`, `presencia`, `es_regular`, `evento`, `subdestino`, `tipo`. |
| 8. Reglas y exclusiones | Se agrega por fecha antes de promediar (no se promedian filas por país). Un día de la semana sin datos queda NaN con `n_dias = 0` («Sin dato»). El modo «eventos» exige eventos seleccionados. Sábado y domingo se resaltan con otro color. Es presencia diaria, no visitantes mensuales. |

## Ficha 11 — Mapa de calor día de la semana × mes (Módulo 2, visualización adicional)

| Campo | Contenido |
|---|---|
| 1. Nombre | Presencia media por día de la semana y mes |
| 2. Definición de negocio | Ver si el patrón semanal cambia de un mes a otro (temporada, festividades) en una sola vista. |
| 3. Fórmula | H(w,m) = P̄(w) calculada solo con las fechas del mes m (ficha 10). |
| 4. Implementación | `modulo2.matriz_dia_mes`: para cada mes `patron = patron_modo(df[df["anio_mes"] == mes], modo, eventos)`; `z[:, j] = patron["presencia_media"].to_numpy()`; `n[:, j] = patron["n_dias"].to_numpy()`. Escala `theme.ESCALA_VOLUMEN`. |
| 5. Agregación y granularidad | Origen: subdestino × fecha × país. Cálculo: media por (día de la semana, mes) para un subdestino y un tipo. |
| 6. Unidad | Personas presentes por día (media); el hover muestra los días observados. |
| 7. Fuente | DIARIA → `movilidad_diaria.parquet`: `anio_mes`, `fecha`, `presencia`, `es_regular`, `evento`. |
| 8. Reglas y exclusiones | Solo movilidad diaria. Celdas y meses sin dato: NaN, fondo gris y «Sin dato» (nunca 0). Orden fijo lunes a domingo. Respeta los modos de la ficha 10. |

## Ficha 12 — Visitantes mensuales observados (Módulo 2, panel de pronóstico)

| Campo | Contenido |
|---|---|
| 1. Nombre | Visitantes mensuales observados |
| 2. Definición de negocio | Dar el contexto observado contra el cual se lee la estimación de enero y febrero de 2026. |
| 3. Fórmula | V(s,t,m) = V(s,t,m,"mas_de_1_dia") + V(s,t,m,"menos_de_1_dia"), meses con los dos segmentos sin nulos. Misma definición que la serie que modela P1. |
| 4. Implementación | `modulo1.visitantes_mensuales(modulo1.preparar(_leer_sub(), replace(f, mes_ini=None, mes_fin=None)))`; `obs.reindex(meses)` para dejar huecos. |
| 5. Agregación y granularidad | Origen: subdestino × mes × tipo × segmento. Cálculo: un valor por mes para un subdestino y un tipo; el panel ignora el rango de meses global para mostrar toda la serie. |
| 6. Unidad | Visitantes únicos del mes. |
| 7. Fuente | MENSUAL → `movilidad_subdestino_mes.parquet`: `subdestino`, `anio_mes`, `tipo`, `segmento`, `visitantes`. |
| 8. Reglas y exclusiones | Serie observada con el color de dato observado; nunca incluye estimaciones. Meses ni observados ni estimados: hueco y «Sin dato». No se suman subdestinos ni tipos. |

## Ficha 13 — Estimación mensual ene–feb 2026 (Módulo 2, línea punteada)

| Campo | Contenido |
|---|---|
| 1. Nombre | Estimación de visitantes de enero y febrero de 2026 |
| 2. Definición de negocio | Cubrir los dos meses sin cobertura de telefonía con un valor de referencia para que la serie no tenga un vacío en la planificación. |
| 3. Fórmula | V̂(s,t,m) = f(s,t) · M(m), con M(m) = entradas migratorias de visitantes del mes. Razón agregada: f = Σ V / Σ M sobre los 8 meses con ambas fuentes. Variante por mercado (extranjeros): V̂ = Σ<sub>g</sub> f<sub>g</sub> · M<sub>g</sub>(m), f<sub>g</sub> = media de V<sub>g</sub>/M<sub>g</sub>. |
| 4. Implementación | Cálculo de P1 (`etl/pronostico.py`): `_pred`: `float(tr_v.sum() / tr_m.sum()) * m_t` (razón agregada) y `float((f * mk["Mt"]).sum())` con `f = (mk["V"] / mk["M"]).mean(axis=0)` (por mercado). El tablero **no calcula ni entrena**: `modulo2.datos_pronostico` filtra `est = datos.filtrar_mensual(base, replace(f, mes_ini=None, mes_fin=None))` y `est[est["es_estimacion"].fillna(False).astype(bool) & est["anio_mes"].isin(MESES_PRONOSTICO)]`, y dibuja `estimacion`. |
| 5. Agregación y granularidad | Origen: subdestino × tipo × mes. Una estimación por subdestino, tipo y mes (ene-2026, feb-2026). |
| 6. Unidad | Visitantes únicos del mes, rotulados «Estimación». |
| 7. Fuente | PRONÓSTICO → `pronostico_ene_feb_2026.parquet`: `destino_clave`, `subdestino`, `tipo`, `anio_mes`, `estimacion`, `metodo`, `es_estimacion`, `nota`. |
| 8. Reglas y exclusiones | Solo enero y febrero de 2026. Color exclusivo de estimación, línea punteada y rótulo «Estimación». No se suman estimaciones de subdestinos ni se mezclan tipos. Para nacionales la migración no mejora a la línea base sin migración (aviso en pantalla con las medianas de `pronostico_resumen_modelo`). Aviso adicional si el MAPE de la serie supera 40 %. |

## Ficha 14 — Intervalo de la estimación (Módulo 2, banda de error)

| Campo | Contenido |
|---|---|
| 1. Nombre | Intervalo orientativo de la estimación (≈ ±1.96 × RMSE) |
| 2. Definición de negocio | Comunicar la incertidumbre de la estimación para no leerla como un dato exacto. |
| 3. Fórmula | [ max(V̂ − 1.96·RMSE, 0) ; V̂ + 1.96·RMSE ], con RMSE leave-one-out de la serie. |
| 4. Implementación | Cálculo de P1: `lim_inf=max(est - Z * met.rmse, 0.0), lim_sup=est + Z * met.rmse` con `Z = 1.96`. El tablero dibuja dos trazos: `lim_sup` sin línea y `lim_inf` con `fill="tonexty"` y `fillcolor=theme.COLOR_ESTIMACION_BANDA`. |
| 5. Agregación y granularidad | Subdestino × tipo × mes (ene y feb 2026). |
| 6. Unidad | Visitantes únicos del mes. |
| 7. Fuente | PRONÓSTICO → `pronostico_ene_feb_2026.parquet`: `lim_inf`, `lim_sup`. |
| 8. Reglas y exclusiones | Con n = 8 meses de validación el intervalo es solo orientativo (no es un intervalo de confianza estadístico). Se dibuja con el color de estimación y rótulo en la leyenda. |

## Ficha 15 — MAPE (Módulo 2, tarjeta)

| Campo | Contenido |
|---|---|
| 1. Nombre | MAPE leave-one-out |
| 2. Definición de negocio | Error porcentual típico con el que el método habría acertado los meses ya observados; indica cuánta confianza dar a la estimación. |
| 3. Fórmula | MAPE = (100/n) · Σ<sub>h</sub> \|V̂<sub>h</sub> − V<sub>h</sub>\| / V<sub>h</sub>, sobre los meses observados h con V<sub>h</sub> ≠ 0; V̂<sub>h</sub> se predice sin el mes h. |
| 4. Implementación | Cálculo de P1 (`etl/pronostico.py`, `_metricas`): `e = est - obs`; `ok = obs != 0`; `mape = float(np.mean(np.abs(e[ok] / obs[ok])) * 100)`. El tablero muestra `r['mape_loo']` con `f"{r['mape_loo']:.1f} %"` (`modulo2.tarjetas_error`). |
| 5. Agregación y granularidad | Origen: observado vs. predicho por mes ocultado. Cálculo: una cifra por subdestino × tipo y variante elegida (se repite en las dos filas de la serie). |
| 6. Unidad | Porcentaje. |
| 7. Fuente | PRONÓSTICO → `pronostico_ene_feb_2026.parquet`: `mape_loo`, `n_loo`, `metodo`; comparación nacional en `pronostico_resumen_modelo.parquet`: `mape_mediano`, `mape_mediano_base_sin_migracion`. |
| 8. Reglas y exclusiones | Corresponde a la serie y variante mostradas (la tarjeta indica `n_loo` meses y la variante). Se excluyen observados iguales a cero. Con MAPE > 40 % se muestra una advertencia. En nacionales se compara con la mediana de la línea base sin migración. |

## Ficha 16 — RMSE (Módulo 2, tarjeta)

| Campo | Contenido |
|---|---|
| 1. Nombre | RMSE leave-one-out |
| 2. Definición de negocio | Magnitud del error en visitantes (penaliza más los errores grandes); sirve para dimensionar el margen de planificación. |
| 3. Fórmula | RMSE = √( (1/n) · Σ<sub>h</sub> (V̂<sub>h</sub> − V<sub>h</sub>)² ) |
| 4. Implementación | Cálculo de P1: `float(np.sqrt(np.mean(e ** 2)))` con `e = est - obs`. El tablero muestra `f"{r['rmse_loo']:,.0f} visitantes"`. |
| 5. Agregación y granularidad | Una cifra por subdestino × tipo y variante elegida. |
| 6. Unidad | Visitantes únicos del mes. |
| 7. Fuente | PRONÓSTICO → `pronostico_ene_feb_2026.parquet`: `rmse_loo`. |
| 8. Reglas y exclusiones | Misma serie y variante que el MAPE. Con n = 8 es orientativo. Define el ancho del intervalo de la ficha 14. |

## Ficha 17 — MAE (Módulo 2, tarjeta)

| Campo | Contenido |
|---|---|
| 1. Nombre | MAE leave-one-out |
| 2. Definición de negocio | Error absoluto medio en visitantes, de lectura directa para quien planifica. |
| 3. Fórmula | MAE = (1/n) · Σ<sub>h</sub> \|V̂<sub>h</sub> − V<sub>h</sub>\| |
| 4. Implementación | Cálculo de P1: `float(np.mean(np.abs(e)))`. El tablero muestra `f"{r['mae_loo']:,.0f} visitantes"`. |
| 5. Agregación y granularidad | Una cifra por subdestino × tipo y variante elegida. |
| 6. Unidad | Visitantes únicos del mes. |
| 7. Fuente | PRONÓSTICO → `pronostico_ene_feb_2026.parquet`: `mae_loo`. |
| 8. Reglas y exclusiones | Misma serie y variante que el MAPE y el RMSE. Se muestra siempre junto a ellos. |
