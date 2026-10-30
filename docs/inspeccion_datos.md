# Inspección de datos (P1, parte 1)

Fecha: 28-oct-2026. Fuente: archivos entregados por el curso. Todo lo descrito aquí se verificó
leyendo los archivos reales. Las fuentes extra del Módulo 4 (encuestas, AIMM, Tikal) se inspeccionan en la parte 2.

## Hallazgos que cambian cómo se procesa (leer primero)

| # | Hallazgo | Consecuencia |
|---|----------|--------------|
| 1 | **La base de migración NO tiene desagregación diaria.** Solo trae `Año` y `Mes cod` (210 meses, 2009-01 a 2026-06). La guía de datos dice "mensual y diaria". | `migracion_diaria` no existe. El pronóstico trabaja a nivel mensual (que es lo que pide: el pronóstico se limita a la base mensual). **Reportar a la coordinación del curso.** |
| 2 | **No existe fila de "total del destino"** en la movilidad. La guía dice que el total "debe solicitarse, no construirse sumando". | El ETL nunca suma subdestinos. Se entrega todo a nivel subdestino-mes. Falta definir cómo mostrar el KPI de nivel destino. **Pregunta pendiente para la coordinación.** |
| 3 | En ambos archivos de movilidad la columna `destino` es el **subdestino** (polígono) y `sub_grupo` es la agrupación. El destino turístico es la **hoja**. | Se renombra: `destino_clave/destino_nombre` (hoja) y `subdestino` (columna original `destino`). |
| 4 | La tabla de ejemplo de Atitlán de la guía de datos **suma meses** (Panajachel = 2,261,392 = Σ de 10 meses) y calcula el % extranjero como extranjeros/total. Ambas prácticas están prohibidas en la propia guía. | Se reproduce exactamente (2,261,392; 8.4 %; 5.55) solo para validar el ETL. **No usar esa tabla como KPI.** |
| 5 | Migración: solo `Turista` + `Excursionista` son visitantes. `Viajero` (cruce fronterizo, tránsito) y `Cruceristas` no. | Se marca `es_visitante`. El driver del pronóstico es `visitantes = turistas + excursionistas`. |
| 6 | Migración: quiebre metodológico 2022→2023 y cambio de granularidad de `País` (226 países hasta 2022; 27 agrupaciones desde 2023). | `periodo_metodologico` en todas las tablas. El perfil estacional se construye con 2023+. |
| 7 | Migración sí trae **enero-junio 2026 observados** (aunque la movilidad no cubre ene-feb 2026). | El pronóstico ene-feb 2026 usa migración observada de esos meses × factor de reparto. |
| 8 | Diario: nombre de país dañado (`ESPAAA` = España). | Corrección explícita en `etl/utils.py`; se prueba. |
| 9 | Diario: cobertura **no continua**: abr-2025 (10 días), jun-2025 (4), jul-2025 (2), sep-2025 a dic-2025 completos, mar-2026 a ago-2026 completos, sep-2026 (4 días). Ene-feb 2026 ausentes. | Tabla `cobertura` con `dias_con_dato` y `cobertura_completa` por mes. |
| 10 | Mensual: 89 filas con `visitantes == 0` (2 sin `dias_persona`); 30 filas con `pais` nulo y 22 con la cadena `'Null'`. | Ceros descartados; país nulo → `tipo = sin_dato` (cuenta en el volumen, no en rankings de país). |

## Movilidad mensual (`BD_moviidad_mensual.xlsx`)
- 6 hojas: Antigua, Peten, Atitlan, Izabal, Alta Verapaz, Playas Pacifico. 24,872 filas.
- Columnas: `destino` (subdestino), `sub_grupo`, `anio`, `mes`, `pais`, `es_consecutivo`, `fecha`, `visitantes`, `dias_persona`, `permanencia_prom`.
- Grano: subdestino × mes × país × segmento. `fecha` = primer día del mes.
- Meses con dato (idénticos en las 6 hojas): 2025-09 a 2025-12 y 2026-03 a 2026-08 → 10 meses.
- Subdestinos: Antigua (Antigua Guatemala, Jocotenango, Volcán Acatenango Fuego); Petén (El Remate y alrededores, Isla de Flores, Mundo Maya Aeropuerto); Atitlán (10 municipios); Izabal (Livingston, Río Dulce); Alta Verapaz (Cobán, Cuevas de Candelaria, Lanquín); Pacífico (El Paredón, Las Lisas, Monterrico, Puerto de San José).
- `es_consecutivo`: `mayor a 1 dia` / `menor a 1 dia`. En `menor a 1 dia` se cumple `dias_persona == visitantes` (100 % de filas); en `mayor a 1 dia`, `dias_persona >= visitantes` (100 %).
- Nacionales = `pais == 'Guatemala'` (500 filas; llevan factor de expansión).

## Movilidad diaria (`BD_moviidad_diario.xlsx`)
- 214,214 filas. Grano: subdestino × fecha × país. Medida: `cantidad_visitantes` (presencia; trae decimales).
- Eventos: Regular, Semana Santa, Festival de las Flores, Fiestas Agostinas, Festival de las Luces, Día del Ejército, 20 de Octubre, Año Nuevo, 15 de Septiembre, Día de los Santos.
- Rango: 2025-04-11 a 2026-09-15 (324 fechas distintas).
- Nombres en MAYÚSCULAS y sin acentos; se homologan contra el mensual.

## Migración (`Base_Migracion_2009-2026jun.xlsx`)
- Hoja `Datos`: 161,036 filas; columnas `Año, Mes cod, Mes, Vía, Frontera, País, Región, Región dos, Regiones OMT, MCEO, Agrupación Residencia, Tipo de Viajero, Viajero`.
- Columnas de región con basura (`'0'`, `'0x2a'`): no se usan.
- Hoja `Notas`: documenta el origen, el quiebre 2022→2023, y que es de uso exclusivamente académico.

## Ocupación (`indice_ocupacion_mensual_2023_2025_1.csv`)
792 filas = 22 departamentos × 36 meses (2023-01 a 2025-12), sin nulos. `indice_ocupacion` es una **fracción** (0.15 a 0.98), no porcentaje.

## Oferta (`oferta_hotelera_2022_2026.csv`)
330 filas = 22 departamentos × 3 tipos (Hospedaje, Hotel, Pensión) × 5 cortes. La columna `trimestre` vale 4 en 2022-2025 y 1 en 2026: son cortes anuales (2026 es un corte parcial, primer trimestre). Sin nulos. Los nombres de departamento coinciden con ocupación.

## Pendiente de inspeccionar (parte 2)
Encuestas de visitante (Antigua, Petén), tabulados de residentes, AIMM (3 archivos), Tikal 2017-2026.

---
# Parte 2 (29-oct): fuentes restantes y hallazgos adicionales

| # | Hallazgo | Consecuencia |
|---|----------|--------------|
| 11 | **La oferta hotelera no es el denominador numérico de la ocupación.** Contra los boletines, (habitaciones disponibles del boletín ÷ 366 ÷ habitaciones de la oferta) va de 0.25 a 1.25 según departamento (Sacatepéquez 1.25, Alta Verapaz 0.25). Los pesos de la oferta dan un índice nacional de ~62 % frente al 71 % del boletín 2024. | No se calcula "habitaciones ocupadas = índice × oferta" ni un índice nacional ponderado por oferta. Solo se pondera para unir Escuintla + Santa Rosa (pesos 65.6 % vs 65.1 % del boletín). Los índices departamentales sí coinciden exactos con el boletín (Sacatepéquez 2024 verificado mes a mes). |
| 12 | Oferta: en 2026, **31 de 66** combinaciones depto×tipo (47 %) repiten exactamente el valor de 2025, como advierte la guía. En 2023-2025 repiten 3, 5 y 7. | `repite_valor_anio_previo` y `es_corte_parcial`. El corte 2026 no se usa como serie. |
| 13 | Tikal: `otros ` con espacio final; meses con capitalización mixta. Ceros abr-sep 2020 (cierre por pandemia, 6 meses). Enero 2017 = 0 es dudoso (feb-2017 también bajo). `descripcion_otros = 'sd'` describe la categoría "otros", no ausencia de dato. | Cierres de 2020 = 0 real (marcados `cierre_pandemia`, **supuesto a confirmar con la cátedra**); enero 2017 → NaN (`cero_dudoso`). |
| 14 | AIMM: el consolidado **no tiene 2023**. El archivo de aerolíneas sí (2023 a abr-2026) y coincide exacto con el consolidado en 48 meses-flujo comunes (2024 y 2025). `Total Mes Aerolínea` es entrada+salida repetido en cada fila. | 2023 y ene-abr 2026 se reconstruyen solo en total (sin segmento). Se descarta `Total Mes Aerolínea`. Los pasajeros incluyen entrada y salida. |
| 15 | AIMM operaciones: 2026 parcial (ene-abr); cruces (17,738) y Poptún (1,103) en hoja aparte. | Tabla `aimm_operaciones_aux` separada; nunca se suma al tráfico. |
| 16 | **La migración solo llega a junio de 2026**: de los 10 meses de movilidad, solo 8 tienen también migración (sep-dic 2025 y mar-jun 2026). | El factor de reparto y la validación usan 8 meses, no 10. |
| 17 | Encuestas: 40 ítems de escala 1-5 en cada una; Antigua trae centinela `-1` en P71 (63 casos) y P11A; las etiquetas de Antigua se derivaron de Petén (la nota metodológica pide verificarlas); 34 % de Antigua sin gasto en Q. | `-1` → NaN. Antigua: 172 de 510 no tienen gasto en Q (`declaro_gasto = False`): **verificar con la cátedra si es filtro o falta**. Categorías de gasto 1-6 sin etiqueta. |
| 18 | Encuestas: ninguna fila de resumen es "total del destino". Solo segmentos (procedencia, pernocta, lugar y cuota en Petén). | `n_bajo` marca segmentos con menos de 30 casos. |
| 19 | Residentes: 640 filas (Antigua 292, Petén 348); `porcentaje = casos / base × 100` se cumple en todas. | Se copian tal cual a `encuesta_residentes_tabulados`. |
| 20 | `Asignacion_Archivos_por_Grupo_Observatorio.xlsx` confirma las hojas y subdestinos de cada grupo; menciona una "BD_COMPLEMENTARIA (Parquet)" que **no vino en la carpeta**. | No se usa; se anota como fuente opcional ausente. |

## Pendiente de confirmar con la coordinación del curso
1. ¿Cómo se obtiene el **total del destino**? No hay fila de total en movilidad y la guía prohíbe sumar subdestinos.
2. La migración **no trae datos diarios** aunque la guía lo diga.
3. Antigua: ¿los gastos en Q vacíos (172 casos) son filtro del cuestionario o dato faltante? ¿Qué categorías son P70a_01 a P70a_06?
4. ¿Los ceros de Tikal abr-sep 2020 y enero 2017 se interpretan como cierre y dato ausente?
