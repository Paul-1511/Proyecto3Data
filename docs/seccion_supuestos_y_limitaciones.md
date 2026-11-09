# Supuestos, limitaciones y calidad de las fuentes

Sección de la memoria técnica (Grupo 4 — Cobán y Alta Verapaz). Cada punto dice qué se supuso, por qué y cómo se ve en el
tablero. Las cifras salen de los archivos de datos (no de los boletines PDF) y se pueden reproducir con
`python -m etl.run_all` y las funciones citadas.

## a) Consolidación departamental: destino ≠ departamento

- **Qué pasa.** La ocupación (`indice_ocupacion_mensual_2023_2025_1.csv`) y la oferta (`oferta_hotelera_2022_2026.csv`) se
  registran por **departamento**. El destino turístico «Cobán y Alta Verapaz» son tres polígonos de telefonía (Cobán, Lanquín y
  Cuevas de Candelaria) dentro del departamento de Alta Verapaz.
- **Supuesto.** Usamos el departamento de **Alta Verapaz** completo como aproximación de la oferta y la ocupación del destino.
  No hace falta consolidar departamentos: eso solo aplica a la Costa del Pacífico (Escuintla + Santa Rosa), que no es nuestro
  destino. La tabla `ocupacion_destino` de P1 ya trae ese caso (ponderado por habitaciones), pero el Módulo 3 no la usa.
- **Consecuencia.** La ocupación y la oferta **no se atribuyen a Cobán**: incluyen hoteles de municipios fuera de los tres
  polígonos. Todos los gráficos del Módulo 3 dicen «Alta Verapaz (departamento)».
- **Promedio nacional.** El archivo de ocupación no trae fila nacional (22 departamentos × 36 meses). La línea de comparación
  es la **media simple de los 22 departamentos** y se rotula «no es el índice nacional oficial». P1 verificó que ponderar por
  la oferta tampoco reproduce el boletín (~62 % contra 71 % en 2024).
- **Total del destino.** La movilidad no trae una fila de total del destino, y la guía prohíbe construirlo sumando
  subdestinos. Por eso el cruce del bloque C se hace por subdestino y tipo (el del filtro o el elegido con clic), no contra un
  «total destino». Queda como pregunta abierta para la coordinación del curso.

## b) Discontinuidad de la telefonía (movilidad)

- **Cobertura.** La movilidad mensual tiene **sep–dic 2025** y **mar–ago 2026** (10 meses). Ene–feb 2026 no tienen dato. La base
  diaria de Alta Verapaz tiene además días sueltos de abr-2025 (10 días), jun-2025 (4) y sep-2026 (4), fuera del calendario
  del filtro.
- **Sin comparación interanual.** Ningún mes calendario aparece en los dos años: no se compara un mes de 2025 con el mismo
  mes de 2026. El perfil estacional compuesto del bloque E combina sep–dic de 2025 con mar–ago de 2026. Se advierte en
  pantalla y `oo.indice_estacional_visitantes` lanza un error si un mes calendario se repitiera.
- **En el tablero.** Ene–feb 2026 se muestran como «Sin dato» (huecos en las líneas, nunca 0). El indicador de cobertura del
  encabezado marca la movilidad como parcial (◐) si el rango incluye esos meses.

## c) Universo hotelero formal vs. plataformas digitales

- La oferta registra solo **hoteles, hospedajes y pensiones** formales. **No incluye alojamiento de plataformas digitales
  (Airbnb)** ni casas particulares. La nota está visible en el bloque A.
- La ocupación mide solo esa hotelería formal. La movilidad mide personas presentes en un polígono, se alojen donde se alojen
  (hotel, casa propia o de familiares, Airbnb o de paso). **Oferta y demanda miden universos distintos.** Por eso no se
  calculan «habitaciones ocupadas = índice × oferta» ni tasas de visitantes por habitación.
- P1 comprobó que la oferta tampoco es el denominador del índice: (habitaciones disponibles del boletín ÷ 366 ÷ habitaciones
  de la oferta) da 0.25 en Alta Verapaz.

## d) La oferta es un corte anual; 2026 es parcial

- La columna `trimestre` vale 4 en 2022–2025 y 1 en 2026: son **cortes anuales de inventario**, no una serie trimestral ni
  mensual. Con cuatro cortes completos no se estima tendencia ni estacionalidad: se grafican **barras agrupadas por año**,
  no una línea.
- **2026** es el corte del primer trimestre. En el país, 31 de 66 combinaciones departamento × tipo (47 %) repiten
  exactamente el valor de 2025. En Alta Verapaz ninguna lo repite en 2026, pero «Pensión» ya repetía en 2025 el valor de 2024.
  El corte 2026 se excluye por defecto y, si se activa, va rayado y rotulado «corte parcial (T1)». El tooltip avisa cuando un
  valor repite el del año previo.

## e) Encuestas sin factor de expansión

- El Grupo 4 **no recibió encuestas** (son de Antigua y Petén), así que el tablero no las usa.
- Aplica igual para la memoria: las encuestas son cortes transversales por cuotas, **sin factor de expansión**. Sus
  resultados solo pueden reportarse como % dentro de segmento, nunca como totales de visitantes ni como total del destino. Las
  de Antigua y Petén no se comparan entre sí.
- No confundir con la movilidad: los **nacionales** de telefonía **sí** llevan factor de expansión y los extranjeros no. Por eso
  se reportan siempre por separado y no se calcula el % de extranjeros como extranjeros ÷ total.

## f) Ruptura metodológica de la migración 2022–2023

- `Base_Migracion_2009-2026jun.xlsx` cambia de método en 2023. El país pasa de 226 países a 27 agrupaciones de mercado, y el
  nivel no es comparable: 3.23 M de visitantes en 2022 frente a 2.92 M en 2023, una caída que no refleja el turismo real.
- Todas las tablas traen `periodo_metodologico` (`<=2022` / `>=2023`). El perfil y el desglose por mercado del pronóstico solo
  usan 2023 en adelante. La migración es **mensual**, aunque la guía la describe con desagregación diaria.

## g) El pronóstico se basa en pocos meses observados

- La movilidad tiene **10 meses observados**, pero la migración llega a **junio de 2026**. Solo **8** de esos 10 meses tienen
  ambas fuentes (sep–dic 2025 y mar–jun 2026), así que el factor de reparto y la validación leave-one-out usan 8 meses
  (`docs/seccion_arquitectura_y_pronostico.md`). La consigna de P3 habla de «10 meses observados»: es el total de
  movilidad, no el de entrenamiento.
- Con tan pocos meses no hay estacionalidad propia del destino ni validación fuera de muestra. Ningún mes de entrenamiento
  es enero o febrero, así que el factor se extrapola a meses con feriados y vacaciones distintos. El intervalo es
  orientativo. En Alta Verapaz el MAPE mediano es 19.2 % en extranjeros y 15.5 % en nacionales. En nacionales, la migración no
  mejora a un promedio simple; el Módulo 2 lo advierte.
- Toda cifra de ene–feb 2026 es **Estimación** (color y rótulo propios). El Módulo 3 no muestra estimaciones.

## h) Base diaria vs. base mensual: medidas distintas

- La base **mensual** cuenta **visitantes únicos del mes**. La base **diaria** cuenta **presencia por día**: la misma persona
  aparece todos los días que estuvo. Sumar los días no da el total del mes. Tampoco se suman visitantes de varios meses
  para un total del período (una persona puede volver), ni subdestinos (una persona puede estar en varios).
- Por eso el tablero usa la diaria solo para patrones dentro del mes (eventos, día de la semana; Módulo 2). Los volúmenes y
  promedios mensuales (Módulos 1 y 3) salen de la mensual. Los promedios del período son **medias de meses**, no sumas.

## Calidad de las fuentes (resumen)

| Fuente | Cobertura usada | Grano | Problemas encontrados | Tratamiento |
|---|---|---|---|---|
| Movilidad mensual | sep–dic 2025, mar–ago 2026 | subdestino × mes × país × segmento | sin total del destino; 89 filas con `visitantes == 0` en el paquete; país nulo o `'Null'` | ceros descartados; país nulo → `sin_dato`; nunca se suman subdestinos |
| Movilidad diaria | ídem (+ días sueltos) | subdestino × día × país | `ESPAAA` = España; meses incompletos | nombre corregido; `cobertura_completa` por mes |
| Ocupación | ene 2023 – dic 2025 | departamento × mes | índice como fracción (0–1); sin fila nacional | `indice_pct`; promedio simple rotulado |
| Oferta | cortes 2022–2025 (+2026 parcial) | departamento × tipo × año | columna `trimestre` engañosa; 2026 repite valores | corte anual; 2026 excluido o marcado |
| Migración | 2017–jun 2026 en la tabla de cobertura (2009 en origen) | mes × vía × país | quiebre 2022→2023; sin desagregación diaria | `periodo_metodologico`; perfil con 2023+ |
