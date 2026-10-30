"""Ocupación hotelera (índice mensual por departamento) y oferta de alojamiento (cortes anuales).

HALLAZGOS (ver docs/inspeccion_datos.md):
  * `indice_ocupacion` es una FRACCIÓN (0.15-0.98). Se conserva como fracción y se añade `indice_pct`.
  * La oferta NO es trimestral aunque la columna se llame `trimestre`: son cortes anuales (4 en
    2022-2025; 2026 = corte parcial del primer trimestre). Es inventario, no flujo.
  * La guía advierte que ~la mitad de las combinaciones depto×tipo de 2026 repiten el valor del año
    previo: se marca con `repite_valor_anio_previo`.
  * Costa del Pacífico = Escuintla + Santa Rosa. El índice consolidado es el promedio de los índices
    ponderado por habitaciones instaladas del corte anual (aproximación a habitaciones disponibles).
  * Ninguno incluye alojamiento de plataformas digitales (Airbnb).
  * OJO: la oferta (habitaciones registradas) NO es el denominador numérico del índice de ocupación.
    Contrastada con los boletines, la razón (habitaciones disponibles del boletín / 366 / habitaciones de
    la oferta) va de 0.25 a 1.25 según el departamento. Por eso NO se calcula 'habitaciones ocupadas =
    índice × oferta' ni se construye un índice nacional ponderado por la oferta (daría ~62 % vs 71 % del
    boletín 2024). La ponderación solo se usa para unir Escuintla + Santa Rosa, donde los pesos de la
    oferta (65.6 %) coinciden con los del boletín (65.1 %).
"""
import numpy as np
import pandas as pd

from etl import config
from etl.utils import exigir_columnas, guardar, log


def cargar_oferta() -> pd.DataFrame:
    df = pd.read_csv(config.RAW / config.F_OFERTA)
    exigir_columnas(df, ["anio", "trimestre", "departamento", "tipo_alojamiento", "establecimientos",
                         "habitaciones", "plazas_cama"], config.F_OFERTA)
    df = df.rename(columns={"trimestre": "corte_trimestre"})
    df["es_corte_parcial"] = df.anio.eq(2026)
    df = df.sort_values(["departamento", "tipo_alojamiento", "anio"]).reset_index(drop=True)
    g = df.groupby(["departamento", "tipo_alojamiento"])
    igual = np.ones(len(df), dtype=bool)
    for c in ["establecimientos", "habitaciones", "plazas_cama"]:
        igual &= (df[c] == g[c].shift(1)).fillna(False).to_numpy()
    df["repite_valor_anio_previo"] = igual
    return df


def cargar_ocupacion() -> pd.DataFrame:
    df = pd.read_csv(config.RAW / config.F_OCUPACION)
    exigir_columnas(df, ["anio", "mes", "departamento", "indice_ocupacion"], config.F_OCUPACION)
    df["anio_mes"] = pd.to_datetime(dict(year=df.anio, month=df.mes, day=1))
    df["indice_pct"] = df.indice_ocupacion * 100
    return df[["departamento", "anio", "mes", "anio_mes", "indice_ocupacion", "indice_pct"]]


def _ponderar(df: pd.DataFrame, hab: pd.DataFrame) -> pd.DataFrame:
    """Índice ponderado por habitaciones del corte anual del mismo año, por (anio, mes, anio_mes)."""
    d = df.merge(hab, on=["departamento", "anio"], how="left")
    if d.habitaciones.isna().any():
        raise ValueError("Ocupación sin habitaciones de oferta para algún departamento/año")
    d["w"] = d.indice_ocupacion * d.habitaciones
    g = d.groupby(["anio", "mes", "anio_mes"], as_index=False).agg(w=("w", "sum"), hab=("habitaciones", "sum"))
    g["indice_ocupacion"] = g.w / g.hab
    g["indice_pct"] = g.indice_ocupacion * 100
    return g[["anio", "mes", "anio_mes", "indice_ocupacion", "indice_pct"]]


def ocupacion_por_destino(ocup: pd.DataFrame, oferta: pd.DataFrame) -> pd.DataFrame:
    hab = oferta.groupby(["departamento", "anio"], as_index=False).habitaciones.sum()
    filas = []
    for _, (key, nombre, deptos) in config.DESTINOS.items():
        sub = ocup[ocup.departamento.isin(deptos)]
        faltan = set(deptos) - set(sub.departamento)
        if faltan:
            raise ValueError(f"Ocupación: departamentos sin datos para {nombre}: {faltan}")
        if len(deptos) == 1:
            o = sub.assign(destino_clave=key, destino_nombre=nombre, metodo="departamento",
                           departamentos=deptos[0])
        else:
            o = _ponderar(sub, hab[hab.departamento.isin(deptos)])
            o = o.assign(destino_clave=key, destino_nombre=nombre, metodo="ponderado_por_habitaciones",
                         departamentos=" + ".join(deptos))
        filas.append(o[["destino_clave", "destino_nombre", "departamentos", "metodo", "anio", "mes", "anio_mes",
                        "indice_ocupacion", "indice_pct"]])
    return pd.concat(filas, ignore_index=True)


def oferta_por_destino(oferta: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for _, (key, nombre, deptos) in config.DESTINOS.items():
        o = (oferta[oferta.departamento.isin(deptos)]
             .groupby(["anio", "tipo_alojamiento", "es_corte_parcial"], as_index=False)
             [["establecimientos", "habitaciones", "plazas_cama"]].sum())
        o.insert(0, "departamentos", " + ".join(deptos))
        o.insert(0, "destino_nombre", nombre)
        o.insert(0, "destino_clave", key)
        filas.append(o)
    return pd.concat(filas, ignore_index=True)


def run() -> dict[str, pd.DataFrame]:
    oferta = cargar_oferta()
    ocup = cargar_ocupacion()
    log.info("oferta: %s filas, repiten valor previo: %s de %s en 2026",
             len(oferta), int(oferta[oferta.anio == 2026].repite_valor_anio_previo.sum()),
             int((oferta.anio == 2026).sum()))
    out = {
        "ocupacion": ocup,
        "ocupacion_destino": ocupacion_por_destino(ocup, oferta),
        "oferta": oferta,
        "oferta_destino": oferta_por_destino(oferta),
    }
    for k, v in out.items():
        guardar(v, k)
    return out
