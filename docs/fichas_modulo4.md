# Fichas técnicas — Módulo 4: reto de Cobán y Alta Verapaz

El reto contrasta el perfil urbano de servicios de Cobán con Lanquín y Cuevas de Candelaria, vinculados a naturaleza. Cada visual respeta el tipo seleccionado; no hay total de destino ni suma de subdestinos.

## 1. Perfil territorial de volumen y permanencia

1. **Nombre:** visitantes únicos promedio por mes y proporción de más de un día.
2. **Uso INGUAT:** dimensiona diferencias de escala y de pernocta entre los tres subdestinos para orientar promoción y servicios.
3. **Fórmula:** \(\bar V_{s,t}=|M_s|^{-1}\sum_{m\in M_s}V_{s,t,m}\); \(P_{s,t}=|M_s|^{-1}\sum_m V^{>1}_{s,t,m}/(V^{>1}_{s,t,m}+V^{<1}_{s,t,m})\).
4. **Código:** `m4.visitantes_por_mes` suma exactamente ambos segmentos dentro del mes (`min_count=2`); `m4.perfil_territorial` aplica `.mean()` a meses válidos.
5. **Granularidad:** subdestino × tipo × mes × segmento → subdestino × tipo.
6. **Unidad:** personas promedio/mes y porcentaje.
7. **Fuente:** `movilidad_subdestino_mes.parquet`: `destino_clave`, `subdestino`, `tipo`, `anio_mes`, `segmento`, `visitantes`.
8. **Reglas:** los meses sin ambos segmentos quedan NaN; no se suman meses, tipos ni subdestinos.

## 2. Intensidad de sábado

1. **Nombre:** razón de presencia diaria de sábado frente a lunes–viernes.
2. **Uso INGUAT:** identifica presión de fin de semana para programación de movilidad, guías y servicios.
3. **Fórmula:** \(R_{s,t}=\overline{D}_{sábado}/\overline{D}_{lunes-viernes}\).
4. **Código:** `m4.presencia_fin_semana`: `groupby("fecha")["presencia"].sum(min_count=1)` antes de las medias por día de semana.
5. **Granularidad:** subdestino × fecha × país → subdestino × día.
6. **Unidad:** personas presentes por día y razón adimensional.
7. **Fuente:** `movilidad_diaria.parquet`: `destino_clave`, `subdestino`, `fecha`, `tipo`, `pais`, `presencia`.
8. **Reglas:** presencia diaria no se suma para obtener visitantes mensuales; días sin dato se excluyen.

## 3. Mercado emisor extranjero principal

1. **Nombre:** mercado principal y participación mensual media.
2. **Uso INGUAT:** prioriza comunicación y alianzas de mercados para cada perfil territorial.
3. **Fórmula:** \(q_{s,p}=|M|^{-1}\sum_m V_{s,p,m}/\sum_{p'}V_{s,p',m}\); se reporta \(\arg\max_p q_{s,p}\).
4. **Código:** `m4.mercado_principal` calcula proporciones por mes con `por_pais.div(tot, level="anio_mes")` y luego `.groupby("pais").mean()`.
5. **Granularidad:** subdestino × país × mes × segmento → subdestino × país.
6. **Unidad:** porcentaje de participación mensual media.
7. **Fuente:** `movilidad_mensual.parquet`: `destino_clave`, `subdestino`, `anio_mes`, `pais`, `tipo`, `segmento`, `visitantes`.
8. **Reglas:** solo extranjeros; no es porcentaje de extranjeros del destino y se excluye «sin dato».
