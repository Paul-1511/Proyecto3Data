# Módulos 1 y 2: Demanda y mercados; Dinámica y pronóstico

Sección de diseño de P2 para el Observatorio de Inteligencia Turística de INGUAT, Grupo 4: Cobán y Alta Verapaz.
Las fichas de cada indicador están en `docs/fichas_modulo1_2.md` y la paleta en `docs/paleta.md`.

## 1. Objetivo

- **Módulo 1 — Demanda y mercados.** Responder cuántos visitantes recibe cada subdestino de Alta Verapaz (`Coban`, `Lanquin` y `Cuevas De Candelaria`), cuánto tiempo se quedan, qué parte pernocta y de qué países vienen, separando siempre nacionales y extranjeros.
- **Módulo 2 — Dinámica temporal, eventos y pronóstico.** Mostrar cómo varía la presencia día a día, qué efecto tienen los feriados y festividades, qué días de la semana concentran la afluencia y cuál es la estimación de los dos meses sin cobertura de telefonía (enero y febrero de 2026).

## 2. Arquitectura de componentes y callbacks

```
app/main.py        app Dash, encabezado, filtros globales, dcc.Store, pestañas, descubrimiento de módulos
app/theme.py       paleta, plantilla Plotly, subtítulos, figura «Sin dato», contraste AA
app/modulo1.py     layout() + registrar_callbacks(app)   (IDs m1-)
app/modulo2.py     layout() + registrar_callbacks(app)   (IDs m2-)
app/utils/datos.py     carga cacheada de Parquet y filtros
app/utils/metricas.py  estadía, proporciones, promedio mensual, lift, patrón semanal
```

- `main.py` importa `app.modulo1`…`app.modulo4` por nombre; si el archivo no existe muestra «En construcción». Los módulos nunca importan `main.py`, por lo que no hay dependencias circulares.
- **Un solo callback escribe el filtro global** (en `main.py`); los módulos solo lo leen con `Input("store-filtros", "data")` y `Filtros.desde_dict(estado)`.
- **Módulo 1** (5 callbacks): selección de mercado, KPI (6 salidas), gráficos de segmento y estadía, ranking con texto de selección y panel de nacionales. El clic en una barra del ranking guarda el mercado en `m1-seleccion`, que actualiza «Turista vs. excursionista» y «Estadía por mes». La selección se borra al cambiar cualquier filtro global o con «Quitar selección».
- **Módulo 2** (4 callbacks): opciones de eventos, serie diaria con lift, patrón semanal con mapa de calor y pronóstico. El selector `m2-eventos` actualiza la serie (sombreado y marcas), el lift, el patrón semanal y el mapa de calor; `m2-modo` cambia los días incluidos en los dos últimos. El callback de opciones lee el valor del selector solo como `State`, así que no hay ciclos.
- Cada módulo tiene sus funciones de preparación y gráficos como funciones puras, separadas de los callbacks, y esto permite probarlas con datos sintéticos.

## 3. Filtros globales

| Filtro | Valores | Comportamiento |
|---|---|---|
| Rango de meses | Calendario completo entre el primer y el último mes observado de Alta Verapaz | Los meses sin cobertura (p. ej. enero y febrero de 2026) se marcan en gris cursiva y se avisan bajo el selector. |
| Tipo | `extranjero` o `nacional` | Selección única; no existe «Todos» que los sume. |
| Subdestino | `Coban`, `Cuevas De Candelaria`, `Lanquin` | Selección única; no existe «Todos» que los sume. |

Las opciones salen de los datos (`movilidad_subdestino_mes` filtrada a `destino_clave == "alta_verapaz"` y a tipos extranjero/nacional) y los valores iniciales siempre pertenecen a ellas. El estado `{mes_ini, mes_fin, tipo, subdestino}` se serializa como texto (`"YYYY-MM"`) en `store-filtros`.

## 4. Decisiones de diseño visual

- Paleta categórica de base Okabe-Ito, secuencial azul para volumen, bermellón **exclusivo** para estimaciones y gris para «Sin dato» (detalle y justificación en `docs/paleta.md`). Los textos usan solo pares con contraste WCAG AA, verificado en pruebas.
- Cada gráfico lleva en el subtítulo el período, la fuente, el subdestino y el tipo; la presencia diaria lo declara expresamente como «no visitantes únicos mensuales».
- Una leyenda común distingue «Observado», «Estimación» y «Sin dato». La estimación se señala además por línea punteada, banda y rótulo, de modo que no depende solo del color.
- Diseño responsivo con columnas de `dash-bootstrap-components`. Los gráficos no muestran barra de herramientas y no hay botones de descarga ni tablas de microdatos.

## 5. Tratamiento de la ausencia de cobertura

- La movilidad mensual cubre sep–dic 2025 y mar–ago 2026 (10 meses); la diaria es continua en esos mismos tramos. El resto es **«Sin dato»**, no cero.
- Los meses o días ausentes aparecen como huecos (`NaN`, `connectgaps=False`), con anotación «Sin dato» o franjas grises. Los promedios solo usan meses válidos e informan cuántos fueron.
- Si no hay filas para el filtro elegido se muestra `figura_sin_dato` y las tarjetas dicen «Sin dato». Si faltan los Parquet, la app arranca con un aviso y todo en «Sin dato».
- El indicador de cobertura por fuente en la barra superior es responsabilidad de P3; hoy existe solo el espacio reservado.

## 6. Separación de nacionales y extranjeros

- Nunca se suman ni se calcula el porcentaje de extranjeros sobre el total. Los nacionales llevan factor de expansión y los extranjeros no, por lo que sus volúmenes no son comparables entre sí.
- El filtro de tipo gobierna las tarjetas, «Turista vs. excursionista», «Estadía por mes», la presencia diaria, el patrón semanal, el mapa de calor y el pronóstico.
- El ranking muestra siempre mercados extranjeros y el panel de nacionales muestra siempre el universo nacional (como una sola serie, sin desagregar por origen), ambos para el subdestino y los meses del filtro. Se acompañan de la advertencia sobre el factor de expansión.
- El pronóstico se muestra por separado según el tipo. Para nacionales se advierte que la línea base sin migración tuvo menor error que el método con migración.

## 7. Supuestos y limitaciones metodológicas

1. **No existe total del destino.** Todos los indicadores son por subdestino y tipo; una persona puede estar contada en varios subdestinos.
2. **Segmentos.** «Más de 1 día» y «menos de 1 día» se tratan como categorías excluyentes (supuesto de P1) y se llaman turista y excursionista solo por convención.
3. **Un mes entra en promedios y proporciones solo si tiene los dos segmentos sin nulos.** La ausencia de un segmento se trata como falta de dato, no como cero.
4. **Ranking de mercados:** promedia los meses en que cada mercado tiene dato. Si una fila ausente en un mes con cobertura equivaliera a cero visitantes, el promedio de un mercado poco frecuente quedaría sobrestimado; el número de meses con dato se muestra para poder interpretarlo.
5. **Selección de mercado:** usa `movilidad_mensual` y exige los dos segmentos en cada mes; un mercado con un solo segmento en un mes aparece como «Sin dato» en las proporciones de ese mes.
6. **Presencia diaria ≠ visitantes mensuales.** Son medidas distintas y no se combinan ni se suman. Se agrega por fecha sumando países de una sola serie.
7. **Lift:** compara días del evento con días regulares del mismo día de la semana; con pocos días el valor es muy variable y los eventos sin día comparable salen como «Sin dato».
8. **Pronóstico:** son las estimaciones de P1 (factor de reparto × entradas migratorias, validadas con leave-one-out sobre 8 meses). El tablero no entrena modelos. El intervalo ≈ ±1.96 × RMSE es orientativo. El panel de pronóstico ignora el rango de meses global para mostrar siempre la serie completa. No se suman estimaciones de subdestinos.
9. **Hojas de estilo externas:** el tema Bootstrap se descarga desde un CDN en el navegador; sin internet la app funciona pero se ve sin estilos.
10. **Dependencia interna:** el Módulo 2 usa `metricas._presencia_por_fecha`, función no pública de `metricas.py`.

## 8. Justificación de las visualizaciones adicionales

- **Estadía media ponderada por mes (Módulo 1).** La tarjeta resume un solo número para el rango; la serie mensual permite ver si la permanencia cambia por temporada y, con un mercado seleccionado, si un país se queda más o menos que el conjunto. Usa la misma función de estadía, sin cálculos nuevos.
- **Mapa de calor día de la semana × mes (Módulo 2).** El patrón semanal promedia todo el rango; el mapa muestra si ese patrón cambia entre meses (por temporada o festividades) y deja ver de un vistazo qué combinaciones no tienen cobertura.

## 9. Hallazgos cuantitativos para el resumen ejecutivo

Las cifras provienen de los resultados ya documentados por P1 en `HANDOFF_P1.md` (sección «Reto del Grupo 4 en cifras») y `docs/seccion_arquitectura_y_pronostico.md`, calculados sobre los Parquet procesados y los 10 meses observados con la misma regla de promedio de meses y de estadía ponderada que usa el tablero. En esta entrega no se ejecutó código para recalcularlas: antes de citarlas en la memoria deben cotejarse con las tarjetas del tablero (rango completo, un tipo y un subdestino a la vez).

**Hallazgo 1 — Escalas muy distintas entre extranjeros y nacionales, y entre subdestinos.** Promedio mensual de visitantes (10 meses observados):

| Subdestino | Extranjeros por mes | Nacionales por mes |
|---|---:|---:|
| Cobán | 4,548 | 224,389 |
| Lanquín | 1,814 | 20,685 |
| Cuevas de Candelaria | 1,460 | 50,079 |

Cobán concentra el mayor volumen en ambos universos. Las dos columnas no son comparables entre sí (los nacionales llevan factor de expansión) y los subdestinos no se suman.

**Hallazgo 2 — La estadía de los nacionales es mayor que la de los extranjeros en los tres subdestinos.** Estadía media ponderada (más de 1 día), en días:

| Subdestino | Extranjeros | Nacionales |
|---|---:|---:|
| Cobán | 2.75 | 5.88 |
| Lanquín | 2.41 | 3.30 |
| Cuevas de Candelaria | 1.50 | 3.14 |

Cobán es también el subdestino donde más se quedan los nacionales. Se reportan por tipo; no se promedian entre tipos.

**Hallazgo 3 — El sábado es el día de mayor presencia diaria media en los tres subdestinos** (resultado de P1 sobre `movilidad_diaria`). Es la base para programar servicios y promoción de fin de semana. La cifra exacta de cada subdestino depende del tipo y del modo (todos los días o solo regulares) elegidos en el patrón semanal, por lo que debe leerse en el Módulo 2 antes de citarla.

**Confiabilidad del pronóstico (dato de apoyo).** El MAPE mediano de la variante elegida para Cobán y Alta Verapaz es 19.2 % en extranjeros y 15.5 % en nacionales (`docs/seccion_arquitectura_y_pronostico.md`). Para el conjunto de destinos, la línea base sin migración da 10.6 % frente a 15.2 % con migración en nacionales, y 34.8 % frente a 21.2 % en extranjeros (`docs/checklist_p1.md`). Los lifts por evento no se citan porque no existe un resultado previamente calculado y verificado; se leen en la tabla del Módulo 2.

## 10. Estado de las pruebas

Resultados confirmados por el equipo: datos 32 pruebas aprobadas, infraestructura Dash 35, métricas 30, Módulo 1 21 y Módulo 2 32. La app con Docker se comprobó visualmente con datos reales. No se realizaron otras verificaciones de integración.
