# Checklist de aceptación de P1

| estado | criterio | evidencia |
|:--:|---|---|
| [x] | ETL reproducible: las 34 tablas existen | 34/34 parquet en data/processed/ |
| [x] | Ninguna tabla vacía | todas con filas |
| [x] | pytest pasa | 42 passed in 0.77s |
| [x] | Movilidad sin ceros ni filas inventadas en ene-feb 2026 | 24,783 filas, todas con visitantes > 0 |
| [x] | Cobertura declara ene-feb 2026 como sin dato | movilidad_mensual: tiene_dato = False |
| [x] | Cero dudoso de Tikal convertido a NaN | 1 mes(es) |
| [x] | Pronóstico solo ene-feb 2026 y rotulado es_estimacion | 100 filas |
| [x] | MAPE, RMSE y MAE reportados (leave-one-out) | extranjero: MAPE mediano 21.2 % (base 34.8 %); nacional: MAPE mediano 15.2 % (base 10.6 %) |
| [x] | Línea base sin migración incluida para comparar | variante base_promedio |
| [x] | No se construye total de destino por suma de subdestinos | 25 subdestinos estimados por separado |
| [x] | data_contract.md documenta las 34 tablas | generado desde los parquet |
| [x] | Fichas técnicas con los 8 campos | 6 fichas × 8 campos |
| [x] | HANDOFF_P1, inspección, progreso y README presentes | ok |
| [x] | .gitignore bloquea datos originales y procesados | data/raw, data/processed, xlsx, csv, parquet |
| [x] | Tablas derivadas de encuestas sin textos libres | solo variables codificadas |
| [~] | Verificaciones de git (commits, tag, datos no versionados) | ejecuta este checklist dentro del repositorio del equipo |

**Resultado:** 0 criterio(s) sin cumplir; 1 pendiente(s).