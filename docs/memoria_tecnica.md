# Memoria técnica — Observatorio de Inteligencia Turística

**Destino:** Cobán y Alta Verapaz · **Curso:** CC3084 Data Science, UVG · **Grupo 4**

## 1. Resumen ejecutivo

El observatorio apoya a INGUAT en la lectura integrada de movilidad, capacidad formal y estacionalidad de Cobán y Alta Verapaz. El reto territorial no asume que los tres polígonos sean sumables: compara Cobán, Lanquín y Cuevas de Candelaria como perfiles distintos.

- La ocupación hotelera de Alta Verapaz pasó de 31.5 % en 2023 a 56.9 % en 2025; diciembre de 2025 alcanzó 71 % y marzo de 2025 fue el valle (46 %).
- Entre los cortes de 2022 y 2025, las habitaciones formales crecieron 3.5 % (2,967 a 3,070), frente a un aumento de 25.4 puntos porcentuales en la ocupación media. La oferta no incluye Airbnb.
- En los diez meses observados, Cobán promedia 4,548 visitantes extranjeros y 224,389 nacionales por mes; los universos no se suman porque los nacionales son cifras expandidas de telefonía móvil.
- En el pronóstico de extranjeros de Cobán, la validación leave-one-out sobre ocho meses produce MAPE de 19.2 %, RMSE de 1,020 y MAE de 825 visitantes. Las estimaciones de enero–febrero de 2026 se distinguen de los observados.

El principal límite es la cobertura: movilidad mensual está disponible en sep–dic 2025 y mar–ago 2026, mientras ocupación cubre ene-2023 a dic-2025. El tablero hace visibles estos huecos como «Sin dato» y no como ceros.

## 2. Marco de turismo sostenible e inteligencia de destino

Un observatorio de turismo sostenible convierte datos periódicos en evidencia para gobernanza, gestión de impactos y decisiones verificables. La red [INSTO de ONU Turismo](https://www.unwto.org/sustainable-development/international-network-of-sustainable-tourism-observatories) promueve observatorios locales que monitorizan sostenibilidad y apoyan decisiones basadas en datos. Este tablero adopta esa lógica: cobertura explícita, trazabilidad de cada indicador y límites de interpretación.

Como referencia de diseño institucional, el modelo de [Destinos Turísticos Inteligentes de SEGITTUR](https://www.segittur.es/sala-de-prensa/notas-de-prensa/mas-de-cuarenta-destinos-reciben-el-distintivo-dti-en-fitur/) organiza la gestión en gobernanza, innovación, tecnología, sostenibilidad y accesibilidad. Su página de [normalización](https://www.segittur.es/destinos-turisticos-inteligentes/proyectos-destinos/normalizacion-destinos-inteligentes/) incluye la UNE 178502:2022 de indicadores y herramientas y la UNE 178509 de recogida, explotación y análisis de datos turísticos. No se afirma que Cobán sea miembro de estas redes: se usan como referentes metodológicos.

## 3. Stack tecnológico y justificación

El proyecto utiliza Python 3.11, pandas y pyarrow para transformar los archivos institucionales a Parquet; Plotly Dash y dash-bootstrap-components para una aplicación reactiva; y Docker Compose para despliegue reproducible. Dash conserva una arquitectura Python única para ETL, cálculo y visuales interactivos con callbacks verificables por pytest. Parquet reduce tiempo de lectura y conserva tipos frente a releer libros Excel. Docker aísla dependencias y monta solamente `data/processed/` en modo lectura. Streamlit y Shiny no se eligieron porque el encargo fijó Dash y el patrón actual requiere callbacks, IDs y pruebas unitarias explícitas.

## 4. Arquitectura y modelo de datos

`etl/run_all.py` procesa los archivos de `data/raw/`, genera Parquet en `data/processed/` y actualiza cobertura. `app/utils/datos.py` limita las tablas que la aplicación puede leer y aplica filtros sin mutar datos. `app/main.py` concentra filtros globales (rango, tipo y subdestino); cada módulo solo los lee. `theme.py` establece paleta, contraste y rótulos de ausencia/estimación.

El modelo separa movilidad mensual por subdestino, mes, tipo y segmento; movilidad diaria por subdestino, fecha y país; ocupación por departamento y mes; y oferta por departamento, tipo y corte anual. La granularidad impide usos indebidos: la base diaria mide presencia y no se suma para producir un mes; los subdestinos no se suman para crear un total inexistente.

## 5. Catálogo de indicadores

Las fichas completas de ocho campos por indicador están en:

- `docs/fichas_modulo1_2.md`: demanda, mercados, estadía, eventos, patrón semanal y pronóstico.
- `docs/fichas_modulo3.md`: capacidad, ocupación, cruce sep–dic 2025, afluencia relativa, estacionalidad y cobertura.
- `docs/fichas_modulo4.md`: perfil territorial, intensidad de sábado y mercado emisor principal.

Cada ficha declara nombre, uso de negocio, fórmula, expresión implementada, granularidad, unidad, archivo/columnas de origen y reglas/exclusiones. La evidencia de cumplimiento transversal está en `docs/checklist_final.md`.

## 6. Desarrollo y resolución del reto: Cobán frente a naturaleza

El Módulo 4 aborda el contraste entre Cobán como centro urbano de servicios y Lanquín/Cuevas de Candelaria como subdestinos de naturaleza. El primer gráfico compara promedio mensual y proporción de visitantes de más de un día sin construir una barra total. El segundo compara la presencia media de sábado con lunes–viernes: es útil para anticipar presión operativa, pero declara que presencia diaria no equivale a visitantes únicos mensuales. El tercero identifica el mercado extranjero principal mediante participación mensual media dentro de cada subdestino.

Las cifras se actualizan con el rango y tipo globales, mientras la comparación conserva los tres subdestinos a propósito. Esto evita que seleccionar Cobán en el encabezado oculte Lanquín y Candelaria en un gráfico diseñado para contrastarlos. El cuadro «Lectura para INGUAT» entrega tres frases con cifras exactas del filtro.

## 7. Supuestos, limitaciones y calidad

La oferta y ocupación corresponden al departamento Alta Verapaz, no exclusivamente a los polígonos de Cobán, Lanquín y Cuevas. La oferta es inventario anual de hotel, hospedaje y pensión; no incorpora plataformas digitales. La movilidad tiene diez meses observados y sin fila de total de destino. Los nacionales incluyen factor de expansión y se muestran separados de extranjeros. Migración cambia metodología entre 2022 y 2023; el pronóstico usa ocho meses con ambas fuentes y su intervalo es orientativo.

El detalle de cobertura, tratamiento y calidad por fuente se conserva en `docs/seccion_supuestos_y_limitaciones.md`. La única intersección afluencia–ocupación permitida es sep–dic 2025 y se describe sin correlación ni causalidad (n = 4).

## 8. Alcance incluido y descartado

Se incluyeron indicadores de movilidad mensual y diaria, mercados extranjeros, estadía ponderada, ocupación, oferta formal, eventos, estacionalidad y pronóstico. Se descartaron totales de destino construidos, sumas de visitantes entre meses, porcentajes de extranjeros sobre un supuesto total y conversiones de presencia diaria a visitantes mensuales. No se publicaron encuestas, Tikal ni AIMM porque esos archivos no fueron entregados al Grupo 4; tampoco se expone gasto, tarjetas, plataformas externas, microdatos ni botones de descarga.

## 9. Recomendaciones para INGUAT

1. Preparar capacidad y movilidad de fin de semana en Lanquín: la presencia de sábado es mayor que la laboral y debe monitorearse junto con servicios locales, no como total mensual.
2. Diseñar promoción de temporada baja antes de marzo: en 2025 la ocupación departamental fue 46 %, frente al pico de 71 % de diciembre.
3. Priorizar mensajes diferenciados por territorio y mercado: Cobán concentra el volumen, mientras Lanquín y Candelaria tienen peso relativo mayor en extranjeros frente a Cobán.
4. Monitorear octubre como un caso de desalineación: en 2025 ocupación cayó 13 pp mientras cinco de seis series de movilidad subieron; investigar alojamiento informal, excursionismo y distribución territorial antes de inferir una causa.
5. Incorporar en una siguiente fase noches reservadas por tipo de alojamiento, disponibilidad de plataformas, ocupación submunicipal, aforo de atractivos, agua/residuos y percepción de residentes.

## 10. Anexos reproducibles

**Estructura:** `etl/` transforma; `app/` contiene interfaz y cálculos; `tests/` valida; `docs/` documenta; `data/raw/` y `data/processed/` no se versionan.

**Dependencias:** ver `requirements.txt`. **Despliegue:** instalar Docker Desktop, clonar el repositorio privado, colocar los archivos fuente en `data/raw/`, ejecutar `python -m etl.run_all` y después `docker compose up --build`. La sección «Inicio desde cero» de `README.md` incluye diagnóstico para Docker y Parquet faltantes.

Transformaciones reproducibles clave: `etl/movilidad.py` normaliza movilidad y elimina filas con visitantes cero; `app/utils/metricas.py:estadia_ponderada` ejecuta `Σ dias_persona / Σ visitantes` solo para `mas_de_1_dia`; `app/modulo4.py:presencia_fin_semana` agrega primero por fecha y después promedia por día de semana. Todas tienen pruebas en `tests/`.
