# Fichas técnicas — Módulo 3 e indicador de cobertura

Cada ficha tiene los ocho campos de la guía. Las expresiones de la fila 4 son las que ejecuta el código:
`app/utils/oferta_ocupacion.py` (cálculos), `app/modulo3.py` (figuras y callbacks), `app/utils/cobertura.py` y
`app/indicador_cobertura.py` (cobertura). Reglas comunes:

- La **oferta** y la **ocupación** son del **departamento de Alta Verapaz**, no del destino Cobán (`oo.DEPARTAMENTO`).
  El Grupo 4 no requiere consolidar departamentos (eso solo aplica a la Costa del Pacífico).
- La **movilidad** se usa por **un subdestino y un tipo** a la vez (`Coban`, `Lanquin`, `Cuevas De Candelaria`;
  `extranjero` / `nacional`). No existe total del destino en la fuente y no se suman subdestinos ni tipos.
- Un mes o año sin fila es **«Sin dato»** (NaN), nunca cero. Cada gráfico declara período y fuente en su subtítulo.
- El Módulo 3 no muestra estimaciones: todo es dato observado (no usa el color de «Estimación»).

**Orígenes de datos** (nombres reales; ver `docs/data_contract.md`):

- **OFERTA** — `oferta_hotelera_2022_2026.csv`. Columnas de origen: `anio`, `trimestre`, `departamento`,
  `tipo_alojamiento`, `establecimientos`, `habitaciones`, `plazas_cama`. Tabla procesada `oferta.parquet`
  (`trimestre` → `corte_trimestre`; añade `es_corte_parcial` y `repite_valor_anio_previo`).
- **OCUPACIÓN** — `indice_ocupacion_mensual_2023_2025_1.csv`. Columnas: `anio`, `mes`, `departamento`,
  `indice_ocupacion` (fracción 0–1). Tabla `ocupacion.parquet` (añade `anio_mes` e `indice_pct = indice_ocupacion × 100`).
  22 departamentos × 36 meses; **no trae fila nacional**.
- **MOVILIDAD** — `BD_moviidad_mensual.xlsx`, hoja «Alta Verapaz». Columnas: `destino` (subdestino), `anio`, `mes`, `pais`,
  `es_consecutivo`, `visitantes`. Tabla `movilidad_subdestino_mes.parquet` (`destino_clave`, `subdestino`, `anio_mes`,
  `tipo`, `segmento`, `visitantes`).
- **COBERTURA** — `cobertura.parquet` (generada por `etl/cobertura.py`): `fuente`, `anio_mes`, `tiene_dato`,
  `cobertura_completa`.

Índice: 1 Capacidad instalada · 2 Índice de ocupación mensual · 3 Promedio simple departamental · 4 Mes pico y mes valle ·
5 Brecha de ocupación · 6 Visitantes del mes en la ventana coincidente · 7 Co-movimiento afluencia–ocupación ·
8 Afluencia por subdestino · 9 Afluencia relativa · 10 Índice estacional de ocupación · 11 Índice estacional compuesto
de visitantes · 12 Indicador de cobertura por fuente.

---

## Ficha 1 — Capacidad instalada por tipo de alojamiento (bloque A)

| Campo | Contenido |
|---|---|
| 1. Nombre | Capacidad instalada: establecimientos, habitaciones y plazas cama por corte anual |
| 2. Definición de negocio | Tamaño de la planta hotelera formal del departamento y su composición (hotel, hospedaje, pensión). Sirve a INGUAT para ver si la oferta acompaña a la demanda y qué tipo de alojamiento crece, comparando inventarios año contra año. |
| 3. Fórmula | C(a, k, x) = valor de la medida x ∈ {establecimientos, habitaciones, plazas_cama} en el corte del año a para el tipo k, en el departamento d = Alta Verapaz. Sin agregación temporal: un corte por año. |
| 4. Implementación | `oo.capacidad_por_anio(oferta, incluir_parcial)`: `df = oferta[oferta["departamento"] == "Alta Verapaz"]`; `df = df[df["anio"].isin([2022, 2023, 2024, 2025] + ([2026] if incluir_parcial else []))]`; verifica un único corte por `(anio, tipo_alojamiento)`. Figura: `m3.fig_capacidad(cap, metrica, anio_sel)` → `go.Bar(x=tipos, y=d[metrica])` por año, `barmode="group"`. |
| 5. Agregación y granularidad | Origen: departamento × tipo × año (corte anual). Cálculo: mismo grano, filtrado al departamento. El total del departamento de un año (`total_departamento_por_anio`) suma tipos del **mismo** corte; nunca se suman años. |
| 6. Unidad | Establecimientos, habitaciones o plazas cama (inventario al corte). |
| 7. Fuente | OFERTA → `oferta.parquet`: `anio`, `departamento`, `tipo_alojamiento`, `establecimientos`, `habitaciones`, `plazas_cama`, `es_corte_parcial`, `repite_valor_anio_previo`. |
| 8. Reglas y exclusiones | Es inventario (cortes anuales), no flujo ni serie mensual: barras agrupadas por año, **sin línea de tendencia**. 2026 se excluye por defecto: es el corte del primer trimestre y 31 de 66 combinaciones departamento × tipo repiten el valor de 2025; si se activa, se dibuja con trama rayada y el rótulo «corte parcial (T1)». El tooltip indica si un valor repite el del año previo. **No incluye plataformas digitales (Airbnb)**: nota visible bajo el gráfico. La oferta no es el denominador del índice de ocupación (no se calculan habitaciones ocupadas). |

## Ficha 2 — Índice de ocupación hotelera mensual (bloque B)

| Campo | Contenido |
|---|---|
| 1. Nombre | Índice de ocupación hotelera mensual de Alta Verapaz |
| 2. Definición de negocio | Proporción de la capacidad hotelera formal ocupada cada mes. Permite a INGUAT ubicar temporadas altas y bajas del departamento y su evolución 2023–2025. |
| 3. Fórmula | O(d, m) = `indice_ocupacion`(d, m) × 100, para d = Alta Verapaz y m ∈ [ene 2023, dic 2025]. |
| 4. Implementación | `oo.serie_ocupacion(ocup)`: `df = ocup.loc[ocup["departamento"] == "Alta Verapaz", ["anio_mes", "indice_pct"]]`; `datos.reindexar_meses(df, datos.rango_meses("2023-01", "2025-12"))`. Vista «solo meses del filtro»: `serie[serie["anio_mes"].isin(meses_filtro ∩ [2023-01, 2025-12])]` (`m3.construir_ocupacion`). |
| 5. Agregación y granularidad | Origen: departamento × mes. Cálculo: mismo grano (no se agrega). |
| 6. Unidad | Porcentaje (%). |
| 7. Fuente | OCUPACIÓN → `ocupacion.parquet`: `departamento`, `anio_mes`, `indice_pct` (de `indice_ocupacion`). |
| 8. Reglas y exclusiones | Serie continua 2023–2025; sin proyecciones ni interpolación (`connectgaps=False`). Si el rango del filtro no toca 2023–2025 (vista «solo meses del filtro»), el gráfico muestra «Sin dato», no una línea en cero. Es un índice del departamento, no del destino Cobán, y solo mide hotelería formal. |

## Ficha 3 — Promedio simple departamental de ocupación (bloque B, línea de comparación)

| Campo | Contenido |
|---|---|
| 1. Nombre | Promedio simple de los 22 departamentos |
| 2. Definición de negocio | Referencia para saber si Alta Verapaz está por encima o por debajo de un departamento típico del país en cada mes. |
| 3. Fórmula | P(m) = (1/22) · Σ<sub>d=1..22</sub> O(d, m); se informa solo si los 22 departamentos tienen dato en m. |
| 4. Implementación | `oo.promedio_departamental(ocup)`: `g = ocup.groupby("anio_mes").agg(indice_pct=("indice_pct", "mean"), n_departamentos=("indice_pct", "count"))`; `g.loc[g["n_departamentos"] < ocup["departamento"].nunique(), "indice_pct"] = NaN`; reindexado a 2023–2025. |
| 5. Agregación y granularidad | Origen: departamento × mes. Cálculo: país (media simple) × mes. |
| 6. Unidad | Porcentaje (%). |
| 7. Fuente | OCUPACIÓN → `ocupacion.parquet`: `departamento`, `anio_mes`, `indice_pct`. |
| 8. Reglas y exclusiones | **No es el índice nacional oficial**: el archivo no trae fila nacional y ponderar por la oferta no reproduce el boletín (P1 obtuvo ~62 % contra 71 % en 2024), por eso se usa la media simple y así se rotula en la leyenda. Un mes incompleto no se promedia (cambiaría la base). |

## Ficha 4 — Mes pico y mes valle (bloque B)

| Campo | Contenido |
|---|---|
| 1. Nombre | Mes pico y mes valle de ocupación por año |
| 2. Definición de negocio | Identifica la temporada más alta y la más baja de cada año para planificar promoción en meses valle y capacidad en meses pico. |
| 3. Fórmula | Pico(a) = argmax<sub>m∈a</sub> O(d, m); Valle(a) = argmin<sub>m∈a</sub> O(d, m). Empates: todos los meses empatados. |
| 4. Implementación | `oo.picos_valles(serie)`: por cada `anio` de `serie.dropna()`, `g[np.isclose(g["indice_pct"], g["indice_pct"].max())]` (pico) y `.min()` (valle). Se dibujan con triángulos ▲/▼ y su valor. |
| 5. Agregación y granularidad | Origen: departamento × mes. Cálculo: departamento × año (selección de meses, no promedio). |
| 6. Unidad | Mes calendario y porcentaje (%). |
| 7. Fuente | OCUPACIÓN → `ocupacion.parquet`: `anio_mes`, `indice_pct`. |
| 8. Reglas y exclusiones | Solo sobre meses observados (los NaN no compiten). Con la vista «solo meses del filtro», pico y valle se calculan dentro del rango visible. Resultado 2023–2025: picos may-2023 (47 %), jun-2024 (70 %), dic-2025 (71 %); valles nov-2023 (18 %), ene-2024 (27 %), mar-2025 (46 %). |

## Ficha 5 — Brecha de ocupación frente al promedio departamental (resumen ejecutivo)

| Campo | Contenido |
|---|---|
| 1. Nombre | Brecha anual de ocupación (puntos porcentuales) |
| 2. Definición de negocio | Mide cuánto se acerca o aleja Alta Verapaz del departamento típico; resume la lectura del bloque B para el resumen ejecutivo. |
| 3. Fórmula | B(a) = (1/12) Σ<sub>m∈a</sub> O(AV, m) − (1/12) Σ<sub>m∈a</sub> P(m), solo años con 12 meses. |
| 4. Implementación | `oo.resumen_anual_ocupacion(serie, promedio)`: media de `indice_pct` por año (solo `count == 12`) para cada serie; `brecha_pp = departamento − promedio_departamental`. |
| 5. Agregación y granularidad | Origen: departamento × mes. Cálculo: departamento × año (media de 12 índices). |
| 6. Unidad | Puntos porcentuales (pp). |
| 7. Fuente | OCUPACIÓN → `ocupacion.parquet`: `departamento`, `anio_mes`, `indice_pct`. |
| 8. Reglas y exclusiones | Es una media de índices mensuales, no un índice anual ponderado por noches disponibles. Hereda las reglas de las fichas 2 y 3. |

## Ficha 6 — Visitantes del mes en la ventana coincidente (bloque C, panel superior)

| Campo | Contenido |
|---|---|
| 1. Nombre | Visitantes únicos del mes (subdestino y tipo), sep–dic 2025 |
| 2. Definición de negocio | Afluencia del subdestino en los únicos meses en que también hay ocupación, para leer ambas series lado a lado. |
| 3. Fórmula | V(s, t, m) = V(s, t, m, "mas_de_1_dia") + V(s, t, m, "menos_de_1_dia"), m ∈ {sep, oct, nov, dic 2025} ∩ rango del filtro. |
| 4. Implementación | `oo.meses_cruce(f.mes_ini, f.mes_fin)` = `VENTANA_CRUCE[(VENTANA_CRUCE >= ini) & (VENTANA_CRUCE <= fin)]`; `oo.datos_cruce(mov, ocup, s, t, meses)` (lanza `ValueError` con cualquier mes fuera de sep–dic 2025) → `oo.visitantes_mes(mov, s, t, meses)`: `groupby(["anio_mes","segmento"])["visitantes"].agg(lambda x: x.sum(min_count=len(x))).unstack("segmento").sum(axis=1, min_count=2)`. Los meses que `cobertura` marca sin dato pasan a NaN (`m3.construir_cruce`). |
| 5. Agregación y granularidad | Origen: subdestino × mes × tipo × segmento. Cálculo: subdestino × tipo × mes (suma de los dos segmentos dentro del mes). |
| 6. Unidad | Personas (visitantes únicos del mes). |
| 7. Fuente | MOVILIDAD → `movilidad_subdestino_mes.parquet`: `destino_clave`, `subdestino`, `tipo`, `anio_mes`, `segmento`, `visitantes`. |
| 8. Reglas y exclusiones | **Solo sep–dic 2025** (regla 6). La fuente no tiene «total destino»: se usa el subdestino del filtro global o el elegido con clic en el bloque D. No se suman meses, subdestinos ni tipos. Un mes sin los dos segmentos es «Sin dato». Fuera de la ventana el gráfico dice «Sin dato · el rango elegido no incluye la ventana sep–dic 2025». |

## Ficha 7 — Co-movimiento afluencia–ocupación (bloque C, lectura)

| Campo | Contenido |
|---|---|
| 1. Nombre | Cambios mensuales en la misma dirección (descriptivo, n = 4) |
| 2. Definición de negocio | Lectura honesta de si la afluencia y la ocupación se mueven juntas en la ventana coincidente, sin afirmar una relación estadística que 4 meses no permiten. |
| 3. Fórmula | Para cada m = 2..4: ΔV<sub>m</sub> = V<sub>m</sub> − V<sub>m−1</sub>, ΔO<sub>m</sub> = O<sub>m</sub> − O<sub>m−1</sub>; coinciden = Σ<sub>m</sub> 𝟙[sign(ΔV<sub>m</sub>) = sign(ΔO<sub>m</sub>)] sobre los cambios con ambos datos. Se reportan también ΔV en % y ΔO en pp. |
| 4. Implementación | `oo.describir_relacion(cruce)`: recorre los meses ordenados, `_signo(dv)`/`_signo(do)` ∈ {sube, baja, igual, sin dato}; `coinciden += int(sv == so)` si ambos tienen dato; devuelve también el mes máximo de cada serie. Texto: `m3.texto_cruce(rel, s, t)`. **No calcula correlación.** |
| 5. Agregación y granularidad | Origen: subdestino × tipo × mes (V) y departamento × mes (O). Cálculo: pares de meses consecutivos. |
| 6. Unidad | Conteo de cambios («k de 3»), % (visitantes) y pp (ocupación). |
| 7. Fuente | Fichas 2 y 6. |
| 8. Reglas y exclusiones | Con n = 4 no se calcula ni se reporta correlación, ni se infiere causalidad: el texto en pantalla lo advierte. Los universos son distintos (personas en un subdestino vs. hotelería formal del departamento). |

## Ficha 8 — Afluencia por subdestino (bloque D)

| Campo | Contenido |
|---|---|
| 1. Nombre | Visitantes por subdestino: promedio mensual de los meses observados o mes seleccionado |
| 2. Definición de negocio | Compara el volumen de Cobán (urbano, servicios) con Lanquín y Cuevas de Candelaria (naturaleza) para un tipo de visitante, sin construir un total del destino. |
| 3. Fórmula | Promedio: V̄(s, t) = (1/\|M<sub>s</sub>\|) Σ<sub>m∈M<sub>s</sub></sub> V(s, t, m), M<sub>s</sub> = meses del rango con dato (cobertura de movilidad). Mes: V(s, t, m*). |
| 4. Implementación | `oo.afluencia_subdestinos(mov, tipo, meses, mes)`: para cada `s` en `SUBDESTINOS`, `serie = visitantes_mes(mov, s, tipo, meses)`; promedio `serie.dropna().mean()` con `n_meses = len(serie.dropna())`, o `serie.get(mes)`. `meses = cb.meses_con_dato(cob, "movilidad_mensual", f.mes_ini, f.mes_fin)`. Figura `m3.fig_subdestinos` (lanza `ValueError` si recibe una fila «Total»). |
| 5. Agregación y granularidad | Origen: subdestino × mes × tipo × segmento. Cálculo: subdestino × tipo (promedio de meses) o subdestino × tipo × mes. |
| 6. Unidad | Visitantes únicos por mes (personas). |
| 7. Fuente | MOVILIDAD → `movilidad_subdestino_mes.parquet`; COBERTURA → `cobertura.parquet` (`fuente == "movilidad_mensual"`). |
| 8. Reglas y exclusiones | **Prohibido sumar subdestinos; no hay barra «Total»** (una persona puede estar en varios subdestinos: nota visible). No se suman meses (se promedian). Nacionales y extranjeros nunca juntos (filtro «Tipo»); los nacionales llevan factor de expansión. Mes sin dato: «Sin dato». |

## Ficha 9 — Afluencia relativa (bloque D, etiqueta de cada barra)

| Campo | Contenido |
|---|---|
| 1. Nombre | Afluencia relativa al subdestino mayor |
| 2. Definición de negocio | Expresa el peso de cada subdestino frente al principal, para dimensionar a Lanquín y Candelaria respecto de Cobán. |
| 3. Fórmula | R(s, t) = V̄(s, t) / max<sub>s'</sub> V̄(s', t) × 100. |
| 4. Implementación | `out["relativo_pct"] = out["visitantes"] / out["visitantes"].max(skipna=True) * 100` (en `oo.afluencia_subdestinos`). |
| 5. Agregación y granularidad | Igual que la ficha 8. |
| 6. Unidad | Porcentaje del subdestino mayor (%). |
| 7. Fuente | Ficha 8. |
| 8. Reglas y exclusiones | No es una participación sobre un total (el total no existe). Se calcula dentro de un mismo tipo; no es un % de extranjeros. |

## Ficha 10 — Índice estacional de ocupación (bloque E, panel superior)

| Campo | Contenido |
|---|---|
| 1. Nombre | Índice estacional de ocupación por año |
| 2. Definición de negocio | Forma de la temporada hotelera de cada año (qué meses están por encima o por debajo de lo normal del año), independiente del nivel. |
| 3. Fórmula | IE<sub>O</sub>(a, m) = O(d, m) / [(1/12) Σ<sub>m'∈a</sub> O(d, m')] × 100. |
| 4. Implementación | `oo.indice_estacional_ocupacion(serie)`: solo años con 12 meses; `df["indice_pct"] / df.groupby("anio")["indice_pct"].transform("mean") * 100`. |
| 5. Agregación y granularidad | Origen: departamento × mes. Cálculo: departamento × año × mes calendario. |
| 6. Unidad | Índice (media del año = 100). |
| 7. Fuente | OCUPACIÓN → `ocupacion.parquet`: `anio_mes`, `indice_pct`. |
| 8. Reglas y exclusiones | Un año incompleto no se indexa. El año elegido con clic en el bloque A se resalta. |

## Ficha 11 — Índice estacional compuesto de visitantes (bloque E, panel inferior)

| Campo | Contenido |
|---|---|
| 1. Nombre | Perfil estacional compuesto de visitantes |
| 2. Definición de negocio | Forma de la temporada de visitantes del subdestino en los meses con cobertura, para contrastarla con la de la ocupación. |
| 3. Fórmula | IE<sub>V</sub>(m) = V(s, t, m) / [(1/\|M\|) Σ<sub>m'∈M</sub> V(s, t, m')] × 100, con M = meses observados del rango (sep–dic 2025 y mar–ago 2026). |
| 4. Implementación | `oo.indice_estacional_visitantes(mov, s, t, meses)`: `serie = visitantes_mes(...).dropna()`; lanza `ValueError` si un mes calendario se repite (impide comparar 2025 contra 2026); `visitantes / visitantes.mean() * 100`, unido a los meses 1–12 (ene y feb quedan NaN). |
| 5. Agregación y granularidad | Origen: subdestino × mes × tipo × segmento. Cálculo: subdestino × tipo × mes calendario. |
| 6. Unidad | Índice (media de meses observados = 100). |
| 7. Fuente | MOVILIDAD → `movilidad_subdestino_mes.parquet`; COBERTURA → `cobertura.parquet`. |
| 8. Reglas y exclusiones | Mezcla años (sep–dic de 2025 y mar–ago de 2026): se advierte en pantalla y el tooltip indica el mes de origen. Ningún mes calendario se repite, así que no hay comparación interanual (regla 9). Ene y feb: «Sin dato». La comparación con la ocupación es de forma, no de nivel. |

## Ficha 12 — Indicador de cobertura por fuente (encabezado, todas las pestañas)

| Campo | Contenido |
|---|---|
| 1. Nombre | Cobertura por fuente en el rango seleccionado |
| 2. Definición de negocio | Dice al lector qué fuentes respaldan el período que está mirando, para que la ausencia de medición no se lea como ausencia del fenómeno. |
| 3. Fórmula | Para la fuente f y el rango R: n<sub>con</sub> = \|{m∈R : tiene_dato(f,m)}\|, n<sub>comp</sub> = \|{m∈R : cobertura_completa(f,m)}\|. Estado = completa si n<sub>comp</sub> = \|R\|; sin dato si n<sub>con</sub> = 0; parcial en otro caso. |
| 4. Implementación | `cb.estado_fuentes(cob, f.mes_ini, f.mes_fin)`: `sub = cob[(cob["fuente"] == clave) & cob["anio_mes"].isin(rango)]`; `con = sub.loc[sub["tiene_dato"], "anio_mes"]`; `completos = sub["cobertura_completa"].sum()`. Chips: `indicador_cobertura.chips(estado, f)` (✓ verde, ◐ verde claro, — gris) con tooltip `cb.texto_tooltip(fila)` («período cubierto por la fuente» y meses sin dato). |
| 5. Agregación y granularidad | Origen: fuente × mes. Cálculo: fuente × rango del filtro. |
| 6. Unidad | Estado categórico y número de meses con dato. |
| 7. Fuente | COBERTURA → `cobertura.parquet`: `fuente`, `anio_mes`, `tiene_dato`, `cobertura_completa`. Fuentes del Grupo 4: `movilidad_mensual`, `movilidad_diaria`, `ocupacion`, `oferta_corte_anual`, `migracion`. |
| 8. Reglas y exclusiones | La oferta es anual: un mes «con dato» significa que el año tiene corte; 2026 cuenta como parcial. La base diaria es parcial si un mes tiene solo algunos días. La tabla cubre 2017–2026 (la migración existe desde 2009, pero el tooltip muestra el tramo de la tabla). La cobertura es por fuente, no por destino: la movilidad diaria de Alta Verapaz no tiene jul-2025, aunque otros destinos sí (fuera del calendario del filtro). Fuentes extra de otros grupos (Tikal, AIMM) aparecen al final si la tabla las trae. |
