"""Genera docs/data_contract.md leyendo el esquema REAL de data/processed/*.parquet.
Uso:  python -m etl.generar_contrato      (correr después de python -m etl.run_all)
Las descripciones están aquí; las columnas y tipos salen de los archivos para que nunca se desfasen."""
import pandas as pd
import pyarrow.parquet as pq

from etl import config

REGLAS = """## Reglas para quien consume estas tablas
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
"""

DESC = {
    "dim_fecha": ("Un día por fila 2009-2026. Tabla de fechas común.", "fecha"),
    "migracion_total_mensual": ("Visitantes (turistas + excursionistas) que ingresan al país por mes. Driver del pronóstico. Quiebre 2022→2023.", "mes"),
    "migracion_mensual": ("Ingresos por mes × vía × frontera × tipo de viajero.", "mes × vía × frontera × tipo_viajero"),
    "migracion_mensual_pais": ("Visitantes por mes × país/agrupación. Desde 2023 `pais` es una agrupación de mercado.", "mes × país × tipo_viajero"),
    "movilidad_mensual": ("Visitantes únicos del mes por subdestino y país. 10 meses: 2025-09..12 y 2026-03..08. Sin total de destino.", "subdestino × mes × país × segmento"),
    "movilidad_subdestino_mes": ("Movilidad mensual por subdestino, tipo y segmento; trae `estadia_ponderada` (solo `mas_de_1_dia`).", "subdestino × mes × tipo × segmento"),
    "movilidad_diaria": ("Presencia por día. No comparable con el mensual ni se suma para obtener el mes. Cobertura continua sep-dic 2025 y mar-ago 2026.", "subdestino × fecha × país"),
    "ocupacion": ("Índice de ocupación hotelera mensual 2023-2025 por departamento (fracción 0-1 y `indice_pct`).", "departamento × mes"),
    "ocupacion_destino": ("Ocupación por destino. Pacífico = Escuintla + Santa Rosa ponderado por habitaciones de la oferta.", "destino × mes"),
    "oferta": ("Inventario de alojamiento (cortes anuales 2022-2025 + corte parcial 2026). `repite_valor_anio_previo` marca valores idénticos al año previo.", "departamento × tipo × año"),
    "oferta_destino": ("Oferta agregada por destino (suma de departamentos del destino).", "destino × tipo × año"),
    "tikal_mensual": ("Ingresos con boleto al Parque Nacional Tikal 2017-2026. `cero_dudoso` (ene-2017) = NaN; `cierre_pandemia` = ceros reales abr-sep 2020.", "mes"),
    "aimm_pasajeros_segmento": ("Pasajeros AIMM por flujo y segmento (doméstico/internacional/privado). Solo 2022, 2024 y 2025.", "mes × flujo × segmento"),
    "aimm_pasajeros_aerolinea": ("Pasajeros AIMM por aerolínea y flujo, 2023 a abr-2026. No incluye 'Total Mes Aerolínea' (duplicaría).", "mes × aerolínea × flujo"),
    "aimm_pasajeros_total": ("Total mensual de pasajeros AIMM 2022-abr 2026 (2023 y 2026 reconstruidos desde aerolíneas, sin segmento).", "mes"),
    "aimm_operaciones": ("Operaciones (aeronaves, no personas) del AIMM por operador y tipo. 2026 parcial (ene-abr).", "mes × operador × tipo_operacion"),
    "aimm_operaciones_aux": ("Cruces (sobrevuelos) y Aeródromo Poptún. NO sumar al tráfico del aeropuerto.", "mes × categoría"),
    "encuesta_antigua_datos": ("Encuesta de visitante Antigua 2025 (510 casos, marzo). Columnas en minúsculas; incluye textos libres. No se versiona.", "encuestado"),
    "encuesta_antigua_diccionario": ("Diccionario de la encuesta de Antigua (% respondido, valores distintos).", "variable"),
    "encuesta_antigua_satisfaccion": ("Satisfacción 1-5 en formato largo (solo respuestas válidas; NaN = filtro del cuestionario).", "encuestado × ítem"),
    "encuesta_antigua_satisfaccion_resumen": ("% insatisfecho/neutral/satisfecho por ítem y SEGMENTO. Sin total del destino.", "ítem × segmento"),
    "encuesta_antigua_gasto_declarado": ("Gasto DECLARADO (Q) por encuestado. Categorías 1-6 sin etiqueta en el diccionario.", "encuestado"),
    "encuesta_peten_datos": ("Encuesta de visitante Petén 2025 (500 casos, mayo). Columnas en minúsculas.", "encuestado"),
    "encuesta_peten_diccionario": ("Diccionario de la encuesta de Petén.", "variable"),
    "encuesta_peten_satisfaccion": ("Satisfacción 1-5 en formato largo (códigos sin prefijo T_).", "encuestado × ítem"),
    "encuesta_peten_satisfaccion_resumen": ("% insatisfecho/neutral/satisfecho por ítem y SEGMENTO. Sin total del destino.", "ítem × segmento"),
    "encuesta_peten_gasto_declarado": ("Gasto DECLARADO (Q) por encuestado.", "encuestado"),
    "encuesta_residentes_tabulados": ("Tabulados de la encuesta a residentes (Antigua y Petén). Solo porcentajes; sin microdato.", "destino × variable × respuesta"),
    "pronostico_ene_feb_2026": ("ESTIMACIÓN de visitantes de ene y feb 2026 por subdestino y tipo, con intervalo y errores de validación.", "subdestino × tipo × mes"),
    "pronostico_validacion": ("MAPE, RMSE y MAE leave-one-out por serie y variante (incluye línea base sin migración).", "subdestino × tipo × variante"),
    "pronostico_loo_detalle": ("Observado vs predicho de cada mes ocultado en la validación (para graficar).", "serie × variante × mes"),
    "pronostico_resumen_modelo": ("Variante elegida por tipo y su error mediano; compara con la línea base.", "tipo"),
    "pronostico_chequeo_diario": ("Correlación entre visitantes mensuales y presencia diaria media (meses con cobertura diaria completa).", "subdestino × tipo"),
    "cobertura": ("Qué fuente tiene dato en cada mes 2017-2026. Úsela para rotular 'sin dato'.", "fuente × mes"),
}


def main() -> None:
    partes = ["# Contrato de datos (`data/processed/`)\n",
              "_Generado por `python -m etl.generar_contrato` a partir del esquema real de los parquet. "
              "Todas las fechas son `datetime64`; `anio_mes` = primer día del mes._\n", REGLAS]
    faltan = []
    for ruta in sorted(config.PROC.glob("*.parquet")):
        n = ruta.stem
        if n not in DESC:
            faltan.append(n)
            continue
    if faltan:
        raise SystemExit(f"Tablas sin descripción en DESC: {faltan}")
    partes.append("## Índice\n\n| tabla | filas | grano | descripción |\n|---|---:|---|---|")
    meta = {}
    for n, (d, grano) in DESC.items():
        ruta = config.PROC / f"{n}.parquet"
        if not ruta.exists():
            raise SystemExit(f"Falta la tabla documentada {n}. Corra python -m etl.run_all")
        pf = pq.ParquetFile(ruta)
        meta[n] = pf
        partes.append(f"| `{n}` | {pf.metadata.num_rows:,} | {grano} | {d} |")
    partes.append("")
    for n, (d, grano) in DESC.items():
        pf = meta[n]
        sch = pf.schema_arrow
        partes.append(f"## {n}\n\n{d}\n\n- Grano: {grano}\n- Filas: {pf.metadata.num_rows:,}\n")
        if n.endswith("_datos"):
            partes.append(f"- Columnas: {len(sch)} (ver `{n.replace('_datos', '_diccionario')}`)\n")
        else:
            partes.append("| columna | tipo |\n|---|---|")
            partes += [f"| `{f.name}` | {f.type} |" for f in sch]
            partes.append("")
    (config.ROOT / "docs" / "data_contract.md").write_text("\n".join(partes), encoding="utf-8")
    print(f"docs/data_contract.md escrito con {len(DESC)} tablas")


if __name__ == "__main__":
    main()
