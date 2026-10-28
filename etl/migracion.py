"""Flujo migratorio de entradas al país (Base_Migracion_2009-2026jun.xlsx, hoja 'Datos').

HALLAZGOS que condicionan el procesamiento (ver docs/inspeccion_datos.md):
  * La granularidad real es MENSUAL (columnas Año y Mes cod). No existe columna de día.
  * Solo 'Turista' + 'Excursionista' son visitantes. 'Viajero' (trabajo fronterizo, tránsito) y
    'Cruceristas' (solo hasta 2022) NO se cuentan como visitantes.
  * Quiebre metodológico 2022->2023: los niveles no son comparables; el perfil estacional
    debe construirse con 2023 en adelante.
  * Desde 2023 la columna País viene por agrupación de mercado (27 grupos) en vez de país individual.
  * 'Viajero' trae decimales (estimaciones expandidas): se conservan como float.
"""
import pandas as pd

from etl import config
from etl.utils import exigir_columnas, guardar, leer_excel, log

COLUMNAS = ["Año", "Mes cod", "Vía", "Frontera", "País", "Tipo de Viajero", "Viajero"]


def cargar() -> pd.DataFrame:
    df = leer_excel(config.F_MIGRACION).parse("Datos")
    exigir_columnas(df, COLUMNAS, "Base_Migracion/Datos")
    df = df.rename(columns={
        "Año": "anio", "Mes cod": "mes", "Vía": "via", "Frontera": "frontera",
        "País": "pais", "Tipo de Viajero": "tipo_viajero", "Viajero": "viajeros",
    })[["anio", "mes", "via", "frontera", "pais", "tipo_viajero", "viajeros"]]
    df["anio_mes"] = pd.to_datetime(dict(year=df.anio, month=df.mes, day=1))
    df["es_visitante"] = df.tipo_viajero.isin(config.MIG_TIPOS_VISITANTE)
    df["periodo_metodologico"] = df.anio.map(
        lambda a: f">={config.MIG_ANIO_QUIEBRE}" if a >= config.MIG_ANIO_QUIEBRE else f"<={config.MIG_ANIO_QUIEBRE - 1}"
    )
    return df


def run() -> dict[str, pd.DataFrame]:
    df = cargar()
    meses = df.anio_mes.nunique()
    log.info("migración: %s filas, %s meses (%s a %s)", f"{len(df):,}", meses,
             df.anio_mes.min().strftime("%Y-%m"), df.anio_mes.max().strftime("%Y-%m"))

    # Mensual por vía y frontera (sumar es válido: son conteos de eventos de ingreso)
    gb = ["anio_mes", "anio", "mes", "periodo_metodologico", "via", "frontera", "tipo_viajero", "es_visitante"]
    mensual = df.groupby(gb, as_index=False, observed=True).viajeros.sum()

    # Mensual por país/agrupación, solo visitantes
    pais = (df[df.es_visitante]
            .groupby(["anio_mes", "anio", "mes", "periodo_metodologico", "pais", "tipo_viajero"], as_index=False)
            .viajeros.sum())

    # Total nacional de visitantes por mes (Turista + Excursionista): driver del pronóstico
    total = (df[df.es_visitante]
             .pivot_table(index=["anio_mes", "anio", "mes", "periodo_metodologico"],
                          columns="tipo_viajero", values="viajeros", aggfunc="sum")
             .reset_index())
    total.columns.name = None
    total = total.rename(columns={"Turista": "turistas", "Excursionista": "excursionistas"})
    total["visitantes"] = total.turistas.fillna(0) + total.excursionistas.fillna(0)

    guardar(mensual, "migracion_mensual")
    guardar(pais, "migracion_mensual_pais")
    guardar(total, "migracion_total_mensual")
    return {"mensual": mensual, "pais": pais, "total": total}
