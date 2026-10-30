# Arquitectura y modelo de datos, y pronóstico ene–feb 2026

## 1. Arquitectura de datos

**Formato.** Archivos Parquet (columnar, tipado, ~10× más pequeño que los Excel y con lectura rápida en Dash).
No se usa base de datos relacional: el volumen es bajo (la tabla más grande, `movilidad_diaria`, tiene 214 mil filas), el
tablero es de solo lectura y el despliegue en Docker se simplifica con archivos montados como volumen.

**Flujo.** `data/raw/` (Excel y CSV del curso, no versionados) → `etl/` (scripts reproducibles, `python -m etl.run_all`)
→ `data/processed/*.parquet` (34 tablas, no versionadas) → `app/` (Dash, solo lectura).

**Relación entre tablas.** Todas se relacionan por una tabla de fechas común, `dim_fecha` (un día por fila, 2009-2026), a
través de `fecha` (diario) o `anio_mes` (mensual, primer día del mes). Los destinos se identifican con `destino_clave`
(`antigua`, `peten`, `atitlan`, `alta_verapaz`, `izabal`, `pacifico`), que enlaza movilidad, ocupación y oferta. El
departamento base de cada destino está en `etl/config.py` (Costa del Pacífico = Escuintla + Santa Rosa).

```
dim_fecha ──< movilidad_diaria (fecha)            ──┐
          ──< movilidad_mensual / _subdestino_mes ──┼─ destino_clave ── ocupacion_destino / oferta_destino
          ──< migracion_* , ocupacion, tikal_mensual, aimm_* (anio_mes)
cobertura (fuente × mes)  →  decide si un mes es "sin dato"
pronostico_* → estimaciones y errores de ene-feb 2026
encuesta_* → cortes transversales (sin eje temporal)
```

**Estructura de carpetas.**

```
observatorio-inguat/
├── data/raw/ , data/processed/     # NO versionadas (.gitignore)
├── etl/   config.py utils.py dim_fecha.py migracion.py movilidad.py ocupacion_oferta.py
│          tikal_aimm.py encuestas.py cobertura.py pronostico.py run_all.py generar_contrato.py checklist_p1.py
├── app/   (tablero Dash: lo construyen P2, P3 y P4)
├── tests/ (pytest: 42 pruebas)
└── docs/  inspeccion_datos.md, data_contract.md, esta sección, PROGRESO_P1.md
```

El esquema completo (columnas y tipos) está en `docs/data_contract.md`, generado desde los archivos reales.

## 2. Hallazgos de los datos que condicionan el modelo
- No existe fila de **total del destino**; la guía prohíbe sumar subdestinos. Todo se calcula por **subdestino × tipo** (nacional / extranjero).
- La migración es **mensual** (no diaria) y llega a **junio de 2026**: el factor de reparto se calcula con **8 meses** (sep-dic 2025 y mar-jun 2026), no con los 10 de movilidad.
- Los visitantes nacionales llevan factor de expansión; los extranjeros no: se modelan por separado.
- Quiebre metodológico de migración 2022→2023: se usan solo datos desde 2023 (para el desglose por mercado).

## 3. Método de estimación

Sea *s* una serie (subdestino, tipo), *O* el conjunto de 8 meses observados, *V<sub>s,m</sub>* los visitantes del subdestino y
*M<sub>m</sub>* las entradas migratorias de visitantes (turistas + excursionistas) en el mes *m*.

1. **Factor de reparto (razón agregada):** f<sub>s</sub> = Σ<sub>m∈O</sub> V<sub>s,m</sub> / Σ<sub>m∈O</sub> M<sub>m</sub>
2. **Estimación:** V̂<sub>s,t</sub> = f<sub>s</sub> · M<sub>t</sub>, con *t* ∈ {ene-2026, feb-2026} (M<sub>t</sub> observada: 300,664 y 236,844).
3. **Variante por mercado emisor (solo extranjeros):** f<sub>s,g</sub> = (1/|O|) Σ<sub>m</sub> V<sub>s,g,m</sub>/M<sub>g,m</sub> y V̂<sub>s,t</sub> = Σ<sub>g</sub> f<sub>s,g</sub> · M<sub>g,t</sub>,
   con 11 mercados con grupo propio en la migración (EE. UU., México, El Salvador, Honduras, Canadá, Alemania, Francia, España, Reino Unido, Colombia, Costa Rica) y "Otros". Responde a la advertencia de la guía: la composición por mercado varía entre destinos.
4. **Validación leave-one-out:** para cada mes observado *h*, se calcula el factor sin ese mes, se predice *h* y se compara con lo observado.
5. **Variantes comparadas:** razón media, razón agregada, razón mediana, por mercado (extranjeros) y una **línea base sin migración** (promedio de los meses observados).
6. **Elección:** una variante por tipo, la de menor MAPE mediano entre las variantes con migración (evita sobreajustar por serie).
7. **Intervalo:** V̂ ± 1.96·RMSE<sub>LOO</sub> de la serie, recortado en 0. Con *n* = 8 es orientativo.
8. **Coherencia intramensual:** la correlación entre visitantes mensuales y presencia diaria media (meses con cobertura diaria completa) tiene mediana 0.92 en 50 series (mínimo 0.36): la base diaria acompaña bien al volumen mensual. La base diaria no se proyecta. Los feriados de ene-feb no se estiman: se declaran ausentes.

## 4. Resultados de la validación (leave-one-out, 8 meses)

| Tipo | Variante elegida | Series | MAPE mediano | MAPE medio | RMSE mediano | MAE mediano | MAPE mediano línea base | ¿Migración mejora a la base? |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Extranjero | por mercado | 25 | **21.2 %** | 23.6 % | 1,558 | 1,330 | 34.8 % | **Sí** |
| Nacional | razón agregada | 25 | **15.2 %** | 17.3 % | 14,607 | 13,062 | 10.6 % | **No** |

MAPE mediano de las variantes (extranjeros): base 34.8 %, razón media 27.9 %, razón agregada 28.0 %, razón mediana 26.4 %, **por mercado 21.2 %**.
(Nacionales: base 10.6 %, razón agregada 15.2 %, media 15.5 %, mediana 18.2 %.)

Por destino (MAPE mediano de la variante elegida): Cobán y Alta Verapaz 19.2 % (ext.) / 15.5 % (nac.); Costa del Pacífico 38.5 % / 25.7 %;
La Antigua Guatemala 32.8 % / 8.5 %; Lago de Atitlán 16.7 % / 15.3 %; Río Dulce y Livingston 15.9 % / 19.0 %; Tikal y Flores 25.3 % / 12.2 %.
Peores series: Las Lisas (45 %), El Paredón (43 %) y Volcán Acatenango Fuego (41 %), extranjeros.

**Lectura honesta.**
- Para **extranjeros** el ingreso migratorio sí explica el volumen y el desglose por mercado reduce el error de 35 % a 21 %: la estimación es defendible.
- Para **nacionales** la migración **no aporta**: el promedio simple lo hace mejor (10.6 % vs 15.2 %). Es esperable (los residentes no ingresan al país). Se publica la estimación por migración que pide la guía, pero la tabla `pronostico_ene_feb_2026` trae también `estimacion_base_sin_migracion` y `migracion_mejora_a_la_base`; el tablero debe advertirlo.
- Las estimaciones por subdestino **no se suman** (doble conteo).

## 5. Fichas técnicas

### 5.1 Factor de reparto
| Campo | Contenido |
|---|---|
| 1. Nombre | Factor de reparto del destino |
| 2. Definición de negocio | Proporción de los ingresos migratorios de visitantes que se observa como visitantes en un subdestino. Permite repartir el ingreso nacional entre destinos y, con él, estimar meses sin telefonía. |
| 3. Fórmula | f<sub>s</sub> = Σ<sub>m∈O</sub> V<sub>s,m</sub> / Σ<sub>m∈O</sub> M<sub>m</sub>;  por mercado: f<sub>s,g</sub> = (1/|O|) Σ<sub>m</sub> V<sub>s,g,m</sub>/M<sub>g,m</sub> |
| 4. Código | `tr_v.sum() / tr_m.sum()` (`etl/pronostico.py::_pred`, variante `razon_agregada`); `(mk["V"] / mk["M"]).mean(axis=0)` (variante `mercado`) |
| 5. Agregación | Origen: subdestino × mes × país (movilidad) y mes × mercado (migración). Cálculo: subdestino × tipo, sobre 8 meses |
| 6. Unidad | Ratio (visitantes del subdestino por visitante que ingresa al país) |
| 7. Fuentes | `BD_moviidad_mensual.xlsx` (todas las hojas; `visitantes`, `pais`, `fecha`); `Base_Migracion_2009-2026jun.xlsx` hoja `Datos` (`Año`, `Mes cod`, `Tipo de Viajero`, `País`, `Viajero`) |
| 8. Reglas | Solo meses con ambas fuentes (sep-dic 2025, mar-jun 2026); solo `Turista` + `Excursionista`; nacionales y extranjeros por separado; no se suman subdestinos ni meses; ausencia de un mes en la serie = sin dato (no cero) |

### 5.2 Estimación mensual (ene–feb 2026)
| Campo | Contenido |
|---|---|
| 1. Nombre | Estimación de visitantes (ene–feb 2026) |
| 2. Definición de negocio | Visitantes que habría registrado la telefonía en los dos meses sin cobertura. Cierra el hueco del perfil estacional. Siempre rotulada "Estimación". |
| 3. Fórmula | V̂<sub>s,t</sub> = f<sub>s</sub> · M<sub>t</sub> (extranjeros: Σ<sub>g</sub> f<sub>s,g</sub>·M<sub>g,t</sub>);  intervalo V̂ ± 1.96·RMSE<sub>LOO</sub> |
| 4. Código | `est = _pred(v, g.to_numpy(float), mt.loc[obs_m].to_numpy(float), float(mt.loc[t]), mk)`; `lim_inf = max(est - Z*rmse, 0)` |
| 5. Agregación | Subdestino × tipo × mes |
| 6. Unidad | Personas (visitantes únicos del mes) |
| 7. Fuentes | Las del factor + migración ene-feb 2026 (`Año`, `Mes cod`, `Viajero`) |
| 8. Reglas | `es_estimacion = True`; color distinto; no sumar subdestinos; no proyectar la base diaria; feriados de ene-feb declarados ausentes; mostrar el error de validación junto a la cifra |

### 5.3 MAPE (error porcentual absoluto medio)
| Campo | Contenido |
|---|---|
| 1. Nombre | MAPE leave-one-out |
| 2. Definición de negocio | Error relativo típico con que el modelo reproduce meses ya observados; indica cuánto confiar en la estimación. |
| 3. Fórmula | MAPE = (100/n) Σ<sub>h</sub> \|V̂<sub>h</sub> − V<sub>h</sub>\| / V<sub>h</sub> |
| 4. Código | `np.mean(np.abs(e[ok] / obs[ok])) * 100` con `e = est - obs`, `ok = obs != 0` |
| 5. Agregación | Por serie (subdestino × tipo × variante); resumen por tipo con la mediana de series |
| 6. Unidad | Porcentaje (%) |
| 7. Fuentes | `pronostico_validacion`, `pronostico_loo_detalle` (derivadas de movilidad y migración) |
| 8. Reglas | n = 8 meses; se excluyen observados iguales a cero; el MAPE agregado se reporta como mediana entre series |

### 5.4 RMSE
| Campo | Contenido |
|---|---|
| 1. Nombre | RMSE leave-one-out |
| 2. Definición de negocio | Error típico en personas; penaliza los errores grandes. Se usa para el intervalo. |
| 3. Fórmula | RMSE = √[ (1/n) Σ<sub>h</sub> (V̂<sub>h</sub> − V<sub>h</sub>)² ] |
| 4. Código | `np.sqrt(np.mean(e ** 2))` |
| 5. Agregación | Por serie × variante; resumen: mediana entre series |
| 6. Unidad | Personas |
| 7. Fuentes | `pronostico_validacion` |
| 8. Reglas | n = 8; depende del tamaño de la serie, no comparar entre subdestinos de distinto volumen |

### 5.5 MAE
| Campo | Contenido |
|---|---|
| 1. Nombre | MAE leave-one-out |
| 2. Definición de negocio | Error absoluto promedio en personas, fácil de comunicar. |
| 3. Fórmula | MAE = (1/n) Σ<sub>h</sub> \|V̂<sub>h</sub> − V<sub>h</sub>\| |
| 4. Código | `np.mean(np.abs(e))` |
| 5. Agregación | Por serie × variante; resumen: mediana entre series |
| 6. Unidad | Personas |
| 7. Fuentes | `pronostico_validacion` |
| 8. Reglas | n = 8; misma advertencia de escala que el RMSE |

### 5.6 Estadía media ponderada (cálculo en el ETL)
| Campo | Contenido |
|---|---|
| 1. Nombre | Estadía media ponderada |
| 2. Definición de negocio | Días promedio que permanece quien pernocta; mide la profundidad de la estadía en cada subdestino. |
| 3. Fórmula | Estadía<sub>s,m</sub> = Σ días-persona / Σ visitantes, solo segmento > 1 día |
| 4. Código | `np.where(g.segmento == "mas_de_1_dia", g.dias_persona / g.visitantes, np.nan)` (`etl/movilidad.py::construir_subdestino_mes`) |
| 5. Agregación | Origen: subdestino × mes × país × segmento; cálculo: subdestino × mes × tipo |
| 6. Unidad | Días por visitante |
| 7. Fuentes | `BD_moviidad_mensual.xlsx`: `dias_persona`, `visitantes`, `es_consecutivo`, `destino`, `pais` |
| 8. Reglas | Solo `mas_de_1_dia`; prohibido promediar `permanencia_prom` (en Panajachel el promedio simple da 2.46 y el ponderado 5.55); para agrupar varios meses se vuelve a dividir sumas, no se promedian razones |

## 6. Supuestos y limitaciones del pronóstico
- 8 meses de entrenamiento: sin estacionalidad propia de cada destino ni validación fuera de muestra más allá del leave-one-out; el intervalo es orientativo.
- El factor mezcla un bloque de 2025 (sep-dic) con uno de 2026 (mar-jun): ningún mes observado es enero ni febrero, de modo que el factor se extrapola a meses con un calendario (feriados, vacaciones) que la telefonía no registró.
- Dentro de un subdestino-mes se suman los segmentos `>1 día` y `<1 día`; se asume que una persona cae en un solo segmento.
- Se estima por subdestino porque no existe el total del destino; sumar sería doble conteo.
- La telefonía no cubre jul-ago 2026 en la migración (llega a junio): esos meses sirven de movilidad observada pero no de entrenamiento.
