# HANDOFF P1 → P2

**Estado:** P1 completo. Tag `handoff-p1`. Todo corre con `python -m etl.run_all` (≈ 40 s) y `pytest` (42 pruebas).

## Cómo arrancar
```bash
pip install -r requirements.txt
# copiar los archivos del curso a data/raw/ (mismos nombres)
python -m etl.run_all          # genera 34 parquet en data/processed/
python -m etl.generar_contrato # regenera docs/data_contract.md
pytest
```
`docs/data_contract.md` describe cada tabla (grano, columnas, tipos). Léalo antes de programar.

## Qué entrega P1
- 34 tablas en `data/processed/`: fechas, migración, movilidad (mensual, subdestino-mes, diaria), ocupación, oferta, Tikal, AIMM, encuestas, residentes, cobertura y pronóstico.
- Pronóstico ene-feb 2026 por subdestino × tipo, con intervalo y errores (MAPE, RMSE, MAE) leave-one-out.
- `docs/seccion_arquitectura_y_pronostico.md` (modelo de datos, método, resultados y 6 fichas técnicas).
- `docs/inspeccion_datos.md` (20 hallazgos) y `docs/checklist_p1.md`.

## Lo que P2 puede asumir
- `movilidad_subdestino_mes` ya trae `estadia_ponderada` bien calculada: úsela, no recalcule promediando.
- `cobertura` indica qué fuente tiene dato en cada mes; la usa el indicador de cobertura.
- Los nombres de país están unificados entre mensual y diario (`ESPAAA` corregido).
- `pronostico_ene_feb_2026.es_estimacion` es siempre `True`: dibujar con el color de "Estimación".

## Decisiones que conviene conocer
1. **Todo es por subdestino**: la fuente no trae total del destino y la guía prohíbe sumar. El KPI "visitantes promedio por mes" del Módulo 1 debe definirse (ver pregunta pendiente 1).
2. **Migración es mensual** (no diaria) y termina en junio 2026: el factor de reparto usa 8 meses.
3. **Extranjeros**: variante por mercado emisor (MAPE mediano 21.2 %, la línea base da 34.8 %). **Nacionales**: la migración no mejora a la línea base (15.2 % vs 10.6 %); la tabla trae `estimacion_base_sin_migracion` y `migracion_mejora_a_la_base`. El tablero debe advertirlo.
4. Ocupación: el índice es fracción (0-1); `indice_pct` ya viene en %. La oferta **no** es el denominador de la ocupación (no calcular habitaciones ocupadas).
5. Tikal: enero 2017 = NaN (`cero_dudoso`); abr-sep 2020 = 0 real (`cierre_pandemia`).
6. AIMM: 2023 y ene-abr 2026 solo tienen total (sin segmento). Pasajeros incluyen entrada y salida. Cruces y Poptún están aparte.
7. Encuestas: solo % por segmento (`*_satisfaccion_resumen` ya viene así), sin total del destino. Gasto = declarado.

## Problemas conocidos / preguntas abiertas para la coordinación del curso
1. ¿Cómo se obtiene el **total del destino**? No existe fila de total.
2. La guía dice que la migración tiene desagregación diaria; **no la tiene**.
3. Antigua: 172 de 510 encuestados sin gasto en Q; categorías de gasto 1-6 sin etiqueta. ¿Filtro o dato faltante?
4. Tikal: ¿los ceros de abr-sep 2020 y enero 2017 se interpretan como cierre y dato ausente (supuesto actual)?
5. `BD_COMPLEMENTARIA (Parquet)` aparece en la asignación de archivos pero no vino en la carpeta.
6. Series con MAPE > 40 %: Las Lisas, El Paredón y Volcán Acatenango Fuego (extranjeros). Mostrar su error junto a la cifra.

## Para P2
`app/` está vacío salvo los `__init__.py`. Cree ahí `main.py`, `theme.py`, `utils/` y los módulos 1 y 2. Los datos se leen de `data/processed/` (solo lectura).
