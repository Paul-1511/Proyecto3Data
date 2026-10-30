# Contrato de datos (`data/processed/`)

_Generado por `python -m etl.generar_contrato` a partir del esquema real de los parquet. Todas las fechas son `datetime64`; `anio_mes` = primer día del mes._

## Reglas para quien consume estas tablas
1. Una fila ausente significa **sin dato**, nunca cero. Consulte `cobertura` antes de graficar.
2. No sume `visitantes` entre meses, ni entre subdestinos, ni la base diaria para obtener el mes. **No existe total de destino** en la fuente.
3. Estadía: `dias_persona.sum() / visitantes.sum()` solo con `segmento == 'mas_de_1_dia'`. No promedie `permanencia_prom`.
4. Nacionales y extranjeros siempre separados (`tipo`). `sin_dato` se ignora en rankings de país. No calcule % extranjeros como extranjeros / total.
5. Migración: para visitantes use `es_visitante == True` (Turista + Excursionista). Mensual, no diaria. Quiebre 2022→2023.
6. Toda cifra con `es_estimacion == True` se rotula 'Estimación' y se dibuja en otro color.
7. Ocupación ∩ afluencia solo sep-dic 2025. La oferta es inventario anual (no tendencia); su 2026 es parcial.
8. Encuestas: solo % dentro de segmento, nunca totales ni total del destino; Antigua y Petén no se comparan; gasto = gasto declarado.
9. Pasajeros (personas) y operaciones (aeronaves) nunca en el mismo eje; cruces y Poptún no son tráfico del aeropuerto.
10. La oferta de alojamiento no es el denominador numérico del índice de ocupación (no calcular habitaciones ocupadas = índice × oferta).

## Índice

| tabla | filas | grano | descripción |
|---|---:|---|---|
| `dim_fecha` | 6,574 | fecha | Un día por fila 2009-2026. Tabla de fechas común. |
| `migracion_total_mensual` | 210 | mes | Visitantes (turistas + excursionistas) que ingresan al país por mes. Driver del pronóstico. Quiebre 2022→2023. |
| `migracion_mensual` | 9,221 | mes × vía × frontera × tipo_viajero | Ingresos por mes × vía × frontera × tipo de viajero. |
| `migracion_mensual_pais` | 30,373 | mes × país × tipo_viajero | Visitantes por mes × país/agrupación. Desde 2023 `pais` es una agrupación de mercado. |
| `movilidad_mensual` | 24,783 | subdestino × mes × país × segmento | Visitantes únicos del mes por subdestino y país. 10 meses: 2025-09..12 y 2026-03..08. Sin total de destino. |
| `movilidad_subdestino_mes` | 1,052 | subdestino × mes × tipo × segmento | Movilidad mensual por subdestino, tipo y segmento; trae `estadia_ponderada` (solo `mas_de_1_dia`). |
| `movilidad_diaria` | 214,214 | subdestino × fecha × país | Presencia por día. No comparable con el mensual ni se suma para obtener el mes. Cobertura continua sep-dic 2025 y mar-ago 2026. |
| `ocupacion` | 792 | departamento × mes | Índice de ocupación hotelera mensual 2023-2025 por departamento (fracción 0-1 y `indice_pct`). |
| `ocupacion_destino` | 216 | destino × mes | Ocupación por destino. Pacífico = Escuintla + Santa Rosa ponderado por habitaciones de la oferta. |
| `oferta` | 330 | departamento × tipo × año | Inventario de alojamiento (cortes anuales 2022-2025 + corte parcial 2026). `repite_valor_anio_previo` marca valores idénticos al año previo. |
| `oferta_destino` | 90 | destino × tipo × año | Oferta agregada por destino (suma de departamentos del destino). |
| `tikal_mensual` | 116 | mes | Ingresos con boleto al Parque Nacional Tikal 2017-2026. `cero_dudoso` (ene-2017) = NaN; `cierre_pandemia` = ceros reales abr-sep 2020. |
| `aimm_pasajeros_segmento` | 216 | mes × flujo × segmento | Pasajeros AIMM por flujo y segmento (doméstico/internacional/privado). Solo 2022, 2024 y 2025. |
| `aimm_pasajeros_aerolinea` | 504 | mes × aerolínea × flujo | Pasajeros AIMM por aerolínea y flujo, 2023 a abr-2026. No incluye 'Total Mes Aerolínea' (duplicaría). |
| `aimm_pasajeros_total` | 52 | mes | Total mensual de pasajeros AIMM 2022-abr 2026 (2023 y 2026 reconstruidos desde aerolíneas, sin segmento). |
| `aimm_operaciones` | 768 | mes × operador × tipo_operacion | Operaciones (aeronaves, no personas) del AIMM por operador y tipo. 2026 parcial (ene-abr). |
| `aimm_operaciones_aux` | 76 | mes × categoría | Cruces (sobrevuelos) y Aeródromo Poptún. NO sumar al tráfico del aeropuerto. |
| `encuesta_antigua_datos` | 510 | encuestado | Encuesta de visitante Antigua 2025 (510 casos, marzo). Columnas en minúsculas; incluye textos libres. No se versiona. |
| `encuesta_antigua_diccionario` | 117 | variable | Diccionario de la encuesta de Antigua (% respondido, valores distintos). |
| `encuesta_antigua_satisfaccion` | 17,170 | encuestado × ítem | Satisfacción 1-5 en formato largo (solo respuestas válidas; NaN = filtro del cuestionario). |
| `encuesta_antigua_satisfaccion_resumen` | 158 | ítem × segmento | % insatisfecho/neutral/satisfecho por ítem y SEGMENTO. Sin total del destino. |
| `encuesta_antigua_gasto_declarado` | 510 | encuestado | Gasto DECLARADO (Q) por encuestado. Categorías 1-6 sin etiqueta en el diccionario. |
| `encuesta_peten_datos` | 500 | encuestado | Encuesta de visitante Petén 2025 (500 casos, mayo). Columnas en minúsculas. |
| `encuesta_peten_diccionario` | 163 | variable | Diccionario de la encuesta de Petén. |
| `encuesta_peten_satisfaccion` | 18,429 | encuestado × ítem | Satisfacción 1-5 en formato largo (códigos sin prefijo T_). |
| `encuesta_peten_satisfaccion_resumen` | 396 | ítem × segmento | % insatisfecho/neutral/satisfecho por ítem y SEGMENTO. Sin total del destino. |
| `encuesta_peten_gasto_declarado` | 500 | encuestado | Gasto DECLARADO (Q) por encuestado. |
| `encuesta_residentes_tabulados` | 640 | destino × variable × respuesta | Tabulados de la encuesta a residentes (Antigua y Petén). Solo porcentajes; sin microdato. |
| `pronostico_ene_feb_2026` | 100 | subdestino × tipo × mes | ESTIMACIÓN de visitantes de ene y feb 2026 por subdestino y tipo, con intervalo y errores de validación. |
| `pronostico_validacion` | 225 | subdestino × tipo × variante | MAPE, RMSE y MAE leave-one-out por serie y variante (incluye línea base sin migración). |
| `pronostico_loo_detalle` | 1,800 | serie × variante × mes | Observado vs predicho de cada mes ocultado en la validación (para graficar). |
| `pronostico_resumen_modelo` | 2 | tipo | Variante elegida por tipo y su error mediano; compara con la línea base. |
| `pronostico_chequeo_diario` | 50 | subdestino × tipo | Correlación entre visitantes mensuales y presencia diaria media (meses con cobertura diaria completa). |
| `cobertura` | 960 | fuente × mes | Qué fuente tiene dato en cada mes 2017-2026. Úsela para rotular 'sin dato'. |

## dim_fecha

Un día por fila 2009-2026. Tabla de fechas común.

- Grano: fecha
- Filas: 6,574

| columna | tipo |
|---|---|
| `fecha` | timestamp[us] |
| `anio` | int32 |
| `mes` | int32 |
| `nombre_mes` | large_string |
| `anio_mes` | timestamp[us] |
| `dia` | int32 |
| `dia_semana` | int32 |
| `nombre_dia` | large_string |
| `es_fin_de_semana` | bool |
| `semana_iso` | int64 |
| `dias_en_mes` | int32 |

## migracion_total_mensual

Visitantes (turistas + excursionistas) que ingresan al país por mes. Driver del pronóstico. Quiebre 2022→2023.

- Grano: mes
- Filas: 210

| columna | tipo |
|---|---|
| `anio_mes` | timestamp[us] |
| `anio` | int64 |
| `mes` | int64 |
| `periodo_metodologico` | large_string |
| `excursionistas` | double |
| `turistas` | double |
| `visitantes` | double |

## migracion_mensual

Ingresos por mes × vía × frontera × tipo de viajero.

- Grano: mes × vía × frontera × tipo_viajero
- Filas: 9,221

| columna | tipo |
|---|---|
| `anio_mes` | timestamp[us] |
| `anio` | int64 |
| `mes` | int64 |
| `periodo_metodologico` | large_string |
| `via` | large_string |
| `frontera` | large_string |
| `tipo_viajero` | large_string |
| `es_visitante` | bool |
| `viajeros` | double |

## migracion_mensual_pais

Visitantes por mes × país/agrupación. Desde 2023 `pais` es una agrupación de mercado.

- Grano: mes × país × tipo_viajero
- Filas: 30,373

| columna | tipo |
|---|---|
| `anio_mes` | timestamp[us] |
| `anio` | int64 |
| `mes` | int64 |
| `periodo_metodologico` | large_string |
| `pais` | large_string |
| `tipo_viajero` | large_string |
| `viajeros` | double |

## movilidad_mensual

Visitantes únicos del mes por subdestino y país. 10 meses: 2025-09..12 y 2026-03..08. Sin total de destino.

- Grano: subdestino × mes × país × segmento
- Filas: 24,783

| columna | tipo |
|---|---|
| `destino_clave` | large_string |
| `destino_nombre` | large_string |
| `subdestino` | large_string |
| `anio` | int64 |
| `mes` | int64 |
| `anio_mes` | timestamp[us] |
| `pais` | large_string |
| `tipo` | large_string |
| `segmento` | large_string |
| `visitantes` | double |
| `dias_persona` | double |
| `permanencia_prom` | double |

## movilidad_subdestino_mes

Movilidad mensual por subdestino, tipo y segmento; trae `estadia_ponderada` (solo `mas_de_1_dia`).

- Grano: subdestino × mes × tipo × segmento
- Filas: 1,052

| columna | tipo |
|---|---|
| `destino_clave` | large_string |
| `destino_nombre` | large_string |
| `subdestino` | large_string |
| `anio` | int64 |
| `mes` | int64 |
| `anio_mes` | timestamp[us] |
| `tipo` | large_string |
| `segmento` | large_string |
| `visitantes` | double |
| `dias_persona` | double |
| `estadia_ponderada` | double |

## movilidad_diaria

Presencia por día. No comparable con el mensual ni se suma para obtener el mes. Cobertura continua sep-dic 2025 y mar-ago 2026.

- Grano: subdestino × fecha × país
- Filas: 214,214

| columna | tipo |
|---|---|
| `destino_clave` | large_string |
| `destino_nombre` | large_string |
| `subdestino` | large_string |
| `fecha` | timestamp[us] |
| `anio` | int64 |
| `mes` | int64 |
| `anio_mes` | timestamp[us] |
| `dia_semana_num` | int64 |
| `dia_semana` | large_string |
| `semana` | int64 |
| `pais` | large_string |
| `tipo` | large_string |
| `evento` | large_string |
| `es_regular` | bool |
| `presencia` | double |

## ocupacion

Índice de ocupación hotelera mensual 2023-2025 por departamento (fracción 0-1 y `indice_pct`).

- Grano: departamento × mes
- Filas: 792

| columna | tipo |
|---|---|
| `departamento` | large_string |
| `anio` | int64 |
| `mes` | int64 |
| `anio_mes` | timestamp[us] |
| `indice_ocupacion` | double |
| `indice_pct` | double |

## ocupacion_destino

Ocupación por destino. Pacífico = Escuintla + Santa Rosa ponderado por habitaciones de la oferta.

- Grano: destino × mes
- Filas: 216

| columna | tipo |
|---|---|
| `destino_clave` | large_string |
| `destino_nombre` | large_string |
| `departamentos` | large_string |
| `metodo` | large_string |
| `anio` | int64 |
| `mes` | int64 |
| `anio_mes` | timestamp[us] |
| `indice_ocupacion` | double |
| `indice_pct` | double |

## oferta

Inventario de alojamiento (cortes anuales 2022-2025 + corte parcial 2026). `repite_valor_anio_previo` marca valores idénticos al año previo.

- Grano: departamento × tipo × año
- Filas: 330

| columna | tipo |
|---|---|
| `anio` | int64 |
| `corte_trimestre` | int64 |
| `departamento` | large_string |
| `tipo_alojamiento` | large_string |
| `establecimientos` | int64 |
| `habitaciones` | int64 |
| `plazas_cama` | int64 |
| `es_corte_parcial` | bool |
| `repite_valor_anio_previo` | bool |

## oferta_destino

Oferta agregada por destino (suma de departamentos del destino).

- Grano: destino × tipo × año
- Filas: 90

| columna | tipo |
|---|---|
| `destino_clave` | large_string |
| `destino_nombre` | large_string |
| `departamentos` | large_string |
| `anio` | int64 |
| `tipo_alojamiento` | large_string |
| `es_corte_parcial` | bool |
| `establecimientos` | int64 |
| `habitaciones` | int64 |
| `plazas_cama` | int64 |

## tikal_mensual

Ingresos con boleto al Parque Nacional Tikal 2017-2026. `cero_dudoso` (ene-2017) = NaN; `cierre_pandemia` = ceros reales abr-sep 2020.

- Grano: mes
- Filas: 116

| columna | tipo |
|---|---|
| `anio` | int64 |
| `mes` | int64 |
| `anio_mes` | timestamp[us] |
| `nacionales` | double |
| `extranjeros` | double |
| `otros` | double |
| `descripcion_otros` | string |
| `total` | double |
| `cierre_pandemia` | bool |
| `cero_dudoso` | bool |

## aimm_pasajeros_segmento

Pasajeros AIMM por flujo y segmento (doméstico/internacional/privado). Solo 2022, 2024 y 2025.

- Grano: mes × flujo × segmento
- Filas: 216

| columna | tipo |
|---|---|
| `anio` | int64 |
| `mes` | int64 |
| `anio_mes` | timestamp[us] |
| `flujo` | large_string |
| `segmento` | large_string |
| `pasajeros` | int64 |

## aimm_pasajeros_aerolinea

Pasajeros AIMM por aerolínea y flujo, 2023 a abr-2026. No incluye 'Total Mes Aerolínea' (duplicaría).

- Grano: mes × aerolínea × flujo
- Filas: 504

| columna | tipo |
|---|---|
| `anio` | int64 |
| `mes` | int64 |
| `anio_mes` | timestamp[us] |
| `aerolinea` | large_string |
| `flujo` | large_string |
| `pasajeros` | int64 |

## aimm_pasajeros_total

Total mensual de pasajeros AIMM 2022-abr 2026 (2023 y 2026 reconstruidos desde aerolíneas, sin segmento).

- Grano: mes
- Filas: 52

| columna | tipo |
|---|---|
| `anio` | int32 |
| `mes` | int32 |
| `anio_mes` | timestamp[us] |
| `fuente` | large_string |
| `tiene_segmento` | bool |
| `pasajeros_entrada` | int64 |
| `pasajeros_salida` | int64 |
| `pasajeros_total` | int64 |

## aimm_operaciones

Operaciones (aeronaves, no personas) del AIMM por operador y tipo. 2026 parcial (ene-abr).

- Grano: mes × operador × tipo_operacion
- Filas: 768

| columna | tipo |
|---|---|
| `anio` | int64 |
| `mes` | int64 |
| `anio_mes` | timestamp[us] |
| `operador` | large_string |
| `tipo_operacion` | large_string |
| `operaciones` | int64 |

## aimm_operaciones_aux

Cruces (sobrevuelos) y Aeródromo Poptún. NO sumar al tráfico del aeropuerto.

- Grano: mes × categoría
- Filas: 76

| columna | tipo |
|---|---|
| `anio` | int64 |
| `mes` | int64 |
| `anio_mes` | timestamp[us] |
| `categoria` | large_string |
| `operaciones` | int64 |

## encuesta_antigua_datos

Encuesta de visitante Antigua 2025 (510 casos, marzo). Columnas en minúsculas; incluye textos libres. No se versiona.

- Grano: encuestado
- Filas: 510

- Columnas: 117 (ver `encuesta_antigua_diccionario`)

## encuesta_antigua_diccionario

Diccionario de la encuesta de Antigua (% respondido, valores distintos).

- Grano: variable
- Filas: 117

| columna | tipo |
|---|---|
| `columna` | large_string |
| `pregunta` | large_string |
| `tipo` | large_string |
| `% respondido` | double |
| `valores distintos` | int64 |

## encuesta_antigua_satisfaccion

Satisfacción 1-5 en formato largo (solo respuestas válidas; NaN = filtro del cuestionario).

- Grano: encuestado × ítem
- Filas: 17,170

| columna | tipo |
|---|---|
| `id` | int64 |
| `destino` | large_string |
| `genero` | large_string |
| `edad` | large_string |
| `procedencia` | large_string |
| `es_pernocta` | bool |
| `lugar` | null |
| `segmento_cuota` | null |
| `item` | large_string |
| `pregunta` | large_string |
| `valor` | int64 |

## encuesta_antigua_satisfaccion_resumen

% insatisfecho/neutral/satisfecho por ítem y SEGMENTO. Sin total del destino.

- Grano: ítem × segmento
- Filas: 158

| columna | tipo |
|---|---|
| `destino` | large_string |
| `item` | large_string |
| `pregunta` | large_string |
| `dimension` | large_string |
| `segmento` | large_string |
| `n_validos` | int64 |
| `media` | double |
| `pct_insatisfecho` | double |
| `pct_neutral` | double |
| `pct_satisfecho` | double |
| `n_bajo` | bool |

## encuesta_antigua_gasto_declarado

Gasto DECLARADO (Q) por encuestado. Categorías 1-6 sin etiqueta en el diccionario.

- Grano: encuestado
- Filas: 510

| columna | tipo |
|---|---|
| `id` | int64 |
| `destino` | large_string |
| `procedencia` | large_string |
| `es_pernocta` | bool |
| `moneda_declarada` | large_string |
| `personas_gasto` | double |
| `noches` | double |
| `gasto_declarado_total_q` | double |
| `gasto_declarado_por_persona_q` | double |
| `gasto_declarado_por_persona_noche_q` | double |
| `categoria_1_q` | double |
| `categoria_2_q` | double |
| `categoria_3_q` | double |
| `categoria_4_q` | double |
| `categoria_5_q` | double |
| `categoria_6_q` | double |
| `declaro_gasto` | bool |

## encuesta_peten_datos

Encuesta de visitante Petén 2025 (500 casos, mayo). Columnas en minúsculas.

- Grano: encuestado
- Filas: 500

- Columnas: 163 (ver `encuesta_peten_diccionario`)

## encuesta_peten_diccionario

Diccionario de la encuesta de Petén.

- Grano: variable
- Filas: 163

| columna | tipo |
|---|---|
| `columna` | large_string |
| `pregunta` | large_string |
| `tipo` | large_string |
| `% respondido` | double |
| `valores distintos` | int64 |

## encuesta_peten_satisfaccion

Satisfacción 1-5 en formato largo (códigos sin prefijo T_).

- Grano: encuestado × ítem
- Filas: 18,429

| columna | tipo |
|---|---|
| `id` | int64 |
| `destino` | large_string |
| `genero` | large_string |
| `edad` | large_string |
| `procedencia` | large_string |
| `es_pernocta` | bool |
| `lugar` | large_string |
| `segmento_cuota` | large_string |
| `item` | large_string |
| `pregunta` | large_string |
| `valor` | int64 |

## encuesta_peten_satisfaccion_resumen

% insatisfecho/neutral/satisfecho por ítem y SEGMENTO. Sin total del destino.

- Grano: ítem × segmento
- Filas: 396

| columna | tipo |
|---|---|
| `destino` | large_string |
| `item` | large_string |
| `pregunta` | large_string |
| `dimension` | large_string |
| `segmento` | large_string |
| `n_validos` | int64 |
| `media` | double |
| `pct_insatisfecho` | double |
| `pct_neutral` | double |
| `pct_satisfecho` | double |
| `n_bajo` | bool |

## encuesta_peten_gasto_declarado

Gasto DECLARADO (Q) por encuestado.

- Grano: encuestado
- Filas: 500

| columna | tipo |
|---|---|
| `id` | int64 |
| `destino` | large_string |
| `procedencia` | large_string |
| `es_pernocta` | bool |
| `moneda_declarada` | large_string |
| `personas_gasto` | int64 |
| `noches` | double |
| `gasto_declarado_total_q` | double |
| `gasto_declarado_por_persona_q` | double |
| `gasto_declarado_por_persona_noche_q` | double |
| `categoria_1_q` | double |
| `categoria_2_q` | double |
| `categoria_3_q` | double |
| `categoria_4_q` | double |
| `categoria_5_q` | double |
| `categoria_6_q` | double |
| `declaro_gasto` | bool |

## encuesta_residentes_tabulados

Tabulados de la encuesta a residentes (Antigua y Petén). Solo porcentajes; sin microdato.

- Grano: destino × variable × respuesta
- Filas: 640

| columna | tipo |
|---|---|
| `destino` | large_string |
| `variable` | large_string |
| `pregunta` | large_string |
| `respuesta` | large_string |
| `casos` | int64 |
| `base` | int64 |
| `porcentaje` | double |

## pronostico_ene_feb_2026

ESTIMACIÓN de visitantes de ene y feb 2026 por subdestino y tipo, con intervalo y errores de validación.

- Grano: subdestino × tipo × mes
- Filas: 100

| columna | tipo |
|---|---|
| `destino_clave` | large_string |
| `destino_nombre` | large_string |
| `subdestino` | large_string |
| `tipo` | large_string |
| `anio_mes` | timestamp[us] |
| `estimacion` | double |
| `lim_inf` | double |
| `lim_sup` | double |
| `metodo` | large_string |
| `mape_loo` | double |
| `rmse_loo` | double |
| `mae_loo` | double |
| `n_loo` | int64 |
| `driver_migracion_visitantes` | double |
| `es_estimacion` | bool |
| `estimacion_base_sin_migracion` | double |
| `mape_loo_base` | double |
| `migracion_mejora_a_la_base` | bool |
| `nota` | large_string |

## pronostico_validacion

MAPE, RMSE y MAE leave-one-out por serie y variante (incluye línea base sin migración).

- Grano: subdestino × tipo × variante
- Filas: 225

| columna | tipo |
|---|---|
| `destino_clave` | large_string |
| `destino_nombre` | large_string |
| `subdestino` | large_string |
| `tipo` | large_string |
| `variante` | large_string |
| `n_loo` | int64 |
| `mape` | double |
| `rmse` | double |
| `mae` | double |
| `es_elegida` | bool |

## pronostico_loo_detalle

Observado vs predicho de cada mes ocultado en la validación (para graficar).

- Grano: serie × variante × mes
- Filas: 1,800

| columna | tipo |
|---|---|
| `destino_clave` | large_string |
| `subdestino` | large_string |
| `tipo` | large_string |
| `variante` | large_string |
| `anio_mes` | timestamp[us] |
| `observado` | double |
| `predicho` | double |
| `error_pct` | double |

## pronostico_resumen_modelo

Variante elegida por tipo y su error mediano; compara con la línea base.

- Grano: tipo
- Filas: 2

| columna | tipo |
|---|---|
| `tipo` | large_string |
| `variante_elegida` | large_string |
| `series` | int64 |
| `mape_mediano` | double |
| `mape_medio` | double |
| `rmse_mediano` | double |
| `mae_mediano` | double |
| `mape_mediano_base_sin_migracion` | double |
| `migracion_mejora_a_la_base` | bool |

## pronostico_chequeo_diario

Correlación entre visitantes mensuales y presencia diaria media (meses con cobertura diaria completa).

- Grano: subdestino × tipo
- Filas: 50

| columna | tipo |
|---|---|
| `subdestino` | large_string |
| `tipo` | large_string |
| `meses` | int64 |
| `correlacion_mensual_vs_presencia_diaria` | double |

## cobertura

Qué fuente tiene dato en cada mes 2017-2026. Úsela para rotular 'sin dato'.

- Grano: fuente × mes
- Filas: 960

| columna | tipo |
|---|---|
| `fuente` | large_string |
| `anio_mes` | timestamp[us] |
| `tiene_dato` | bool |
| `dias_con_dato` | double |
| `dias_en_mes` | int32 |
| `granularidad` | large_string |
| `cobertura_completa` | bool |
