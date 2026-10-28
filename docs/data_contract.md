# Contrato de datos (`data/processed/`)

**Estado: PARTE 1 (28-oct).** Tablas de ocupación, oferta, pronóstico y fuentes extra se agregan en la parte 2.
Todas las fechas son `datetime64`. `anio_mes` = primer día del mes. Los parquet se generan con `python -m etl.run_all`.

## Reglas para quien consume estas tablas
1. Una fila ausente significa **sin dato**, nunca cero. Consulte `cobertura` antes de graficar.
2. No sume `visitantes` entre meses, ni entre subdestinos, ni la base diaria para obtener el mes.
3. Estadía: use `dias_persona.sum() / visitantes.sum()` solo con `segmento == 'mas_de_1_dia'`. No promedie `permanencia_prom`.
4. Nacionales y extranjeros siempre separados (`tipo`). `sin_dato` se ignora en rankings de país.
5. Migración: para visitantes use `es_visitante == True` (Turista + Excursionista).

## dim_fecha  (6,574 filas, 2009-01-01 a 2026-12-31, un día por fila)
`fecha, anio, mes, nombre_mes, anio_mes, dia, dia_semana (0=lunes), nombre_dia, es_fin_de_semana (sáb/dom), semana_iso, dias_en_mes`

## movilidad_mensual  (24,783 filas) — grano: subdestino × mes × país × segmento
| columna | descripción |
|---|---|
| destino_clave, destino_nombre | hoja de origen: antigua, peten, atitlan, alta_verapaz, izabal, pacifico |
| subdestino | polígono (columna `destino` original) |
| anio, mes, anio_mes | periodo |
| pais | país de residencia (nulo si `tipo = sin_dato`) |
| tipo | nacional / extranjero / sin_dato |
| segmento | `mas_de_1_dia` / `menos_de_1_dia` |
| visitantes | visitantes únicos del mes en ese subdestino |
| dias_persona | días-persona |
| permanencia_prom | **NO usar para promediar**; solo trazabilidad |
Cobertura: 2025-09 a 2025-12 y 2026-03 a 2026-08. **No hay total de destino**; no se construye por suma.

## movilidad_subdestino_mes  (1,052 filas) — grano: subdestino × mes × tipo × segmento
`destino_clave, destino_nombre, subdestino, anio, mes, anio_mes, tipo, segmento, visitantes, dias_persona, estadia_ponderada`
`estadia_ponderada = dias_persona / visitantes` y solo se llena en `mas_de_1_dia` (vacía en `menos_de_1_dia`).

## movilidad_diaria  (214,214 filas) — grano: subdestino × fecha × país
`destino_clave, destino_nombre, subdestino, fecha, anio, mes, anio_mes, dia_semana_num, dia_semana, semana, pais, tipo, evento, es_regular, presencia`
`presencia` es presencia por día (puede traer decimales). **No es comparable con `visitantes` mensual ni se suma para obtener el mes.**
Cobertura: continua sep-2025 a dic-2025 y mar-2026 a ago-2026; parcial en abr/jun/jul-2025 y sep-2026 (ver `cobertura`).

## migracion_total_mensual  (210 filas) — grano: mes
`anio_mes, anio, mes, periodo_metodologico, excursionistas, turistas, visitantes`
Cobertura: 2009-01 a 2026-06. Quiebre 2022→2023: no comparar niveles entre periodos. **Es mensual; no hay base diaria.**

## migracion_mensual  (9,221 filas) — grano: mes × vía × frontera × tipo_viajero
`anio_mes, anio, mes, periodo_metodologico, via, frontera, tipo_viajero, es_visitante, viajeros`

## migracion_mensual_pais  (30,373 filas) — grano: mes × país/agrupación × tipo (solo visitantes)
`anio_mes, anio, mes, periodo_metodologico, pais, tipo_viajero, viajeros`. Desde 2023 `pais` es una agrupación de mercado.

## cobertura  (180 filas) — grano: fuente × mes (2022-01 a 2026-12)
`fuente, anio_mes, tiene_dato, dias_con_dato, dias_en_mes, cobertura_completa`
Fuentes hoy: movilidad_mensual, movilidad_diaria, migracion. (Ocupación y oferta: parte 2.)
