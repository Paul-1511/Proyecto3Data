"""Movilidad por telefonía móvil: BD_moviidad_mensual.xlsx y BD_moviidad_diario.xlsx.

HALLAZGOS que condicionan el procesamiento (ver docs/inspeccion_datos.md):
  * En ambos archivos la columna `destino` es en realidad el SUBDESTINO (polígono) y `sub_grupo`
    es la agrupación. El destino turístico es la HOJA del Excel.
  * NO existe fila de 'total del destino'. Esta tabla nunca construye totales de destino por suma
    de subdestinos (regla 4). Todos los cálculos se entregan a nivel subdestino-mes.
  * El mensual reporta visitantes únicos del mes; el diario, presencia por día. Medidas distintas.
  * Mensual: 'es_consecutivo' = segmento de estadía ('mayor/menor a 1 dia').
  * Nombres de país con distinta forma entre archivos (mensual 'Title Case', diario MAYÚSCULAS)
    y un nombre dañado en diario ('ESPAAA' = España). Se unifican con `clave_corregida`.
  * pais vacío o la cadena 'Null' -> tipo 'sin_dato' (se conservan, no entran a rankings de país).
  * Filas con visitantes == 0 (89, de las cuales 2 sin dias_persona) se descartan: no aportan información.
"""
import numpy as np
import pandas as pd

from etl import config
from etl.utils import (clave, clave_corregida, exigir_columnas, guardar, leer_excel, log,
                       tipo_procedencia)

COLS_MENSUAL = ["destino", "sub_grupo", "anio", "mes", "pais", "es_consecutivo", "fecha",
                "visitantes", "dias_persona", "permanencia_prom"]
COLS_DIARIO = ["destino", "sub_grupo", "anio", "mes", "idfecha", "dia_semana", "pais", "Week",
               "evento", "cantidad_visitantes"]

DIAS_SEMANA = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
NOMBRE_DIA = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}


def _cargar_hojas(archivo: str, columnas: list[str]) -> pd.DataFrame:
    xl = leer_excel(archivo)
    frames = []
    for hoja, (key, nombre, _) in config.DESTINOS.items():
        if hoja not in xl.sheet_names:
            raise ValueError(f"{archivo}: falta la hoja '{hoja}'. Hojas: {xl.sheet_names}")
        d = xl.parse(hoja)
        exigir_columnas(d, columnas, f"{archivo}/{hoja}")
        d["destino_clave"], d["destino_nombre"] = key, nombre
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def _catalogos(mensual_raw: pd.DataFrame):
    """Nombres canónicos de subdestino y de país tomados del archivo mensual."""
    sub = (mensual_raw.dropna(subset=["destino"])
           .drop_duplicates("destino").assign(k=lambda d: d.destino.map(clave))
           .set_index("k").destino.to_dict())
    pais = {}
    for p in mensual_raw.pais.dropna().unique():
        if tipo_procedencia(p) != "sin_dato":
            pais[clave_corregida(p)] = p
    return sub, pais


def construir_mensual() -> tuple[pd.DataFrame, dict, dict]:
    raw = _cargar_hojas(config.F_MOV_MENSUAL, COLS_MENSUAL)
    sub_cat, pais_cat = _catalogos(raw)

    df = raw.copy()
    n0 = len(df)
    df = df[df.visitantes > 0].copy()
    log.info("movilidad mensual: %s filas; descartadas %s con visitantes==0", f"{n0:,}", n0 - len(df))

    desconocido = set(df.es_consecutivo.unique()) - set(config.SEGMENTOS)
    if desconocido:
        raise ValueError(f"Valores nuevos en es_consecutivo: {desconocido}")
    df["segmento"] = df.es_consecutivo.map(config.SEGMENTOS)
    df["tipo"] = df.pais.map(tipo_procedencia)
    df["pais"] = df.apply(lambda r: pais_cat.get(clave_corregida(r.pais)) if r.tipo != "sin_dato" else None, axis=1)
    df["subdestino"] = df.destino.map(lambda s: sub_cat[clave(s)])
    df["anio_mes"] = pd.to_datetime(dict(year=df.anio, month=df.mes, day=1))

    out = df[["destino_clave", "destino_nombre", "subdestino", "anio", "mes", "anio_mes", "pais", "tipo",
              "segmento", "visitantes", "dias_persona", "permanencia_prom"]].reset_index(drop=True)
    return out, sub_cat, pais_cat


def construir_subdestino_mes(m: pd.DataFrame) -> pd.DataFrame:
    """Subdestino-mes por tipo y segmento. Suma países (válido: cada persona tiene un solo país).
    La estadía ponderada se calcula SOLO en el segmento 'mas_de_1_dia' como Σdías-persona / Σvisitantes.
    NO se suman subdestinos ni meses."""
    g = (m.groupby(["destino_clave", "destino_nombre", "subdestino", "anio", "mes", "anio_mes", "tipo", "segmento"],
                   as_index=False).agg(visitantes=("visitantes", "sum"), dias_persona=("dias_persona", "sum")))
    g["estadia_ponderada"] = np.where(g.segmento == "mas_de_1_dia", g.dias_persona / g.visitantes, np.nan)
    return g


def construir_diario(pais_cat: dict, sub_cat: dict) -> pd.DataFrame:
    raw = _cargar_hojas(config.F_MOV_DIARIO, COLS_DIARIO)
    df = raw.copy()

    df["subdestino"] = df.destino.map(lambda s: sub_cat.get(clave(s)))
    sin_match = df[df.subdestino.isna()].destino.unique()
    if len(sin_match):
        raise ValueError(f"Subdestinos del diario sin equivalente en el mensual: {sin_match}")

    df["tipo"] = df.pais.map(tipo_procedencia)
    df["pais"] = df.apply(lambda r: pais_cat.get(clave_corregida(r.pais)) if r.tipo != "sin_dato" else None, axis=1)
    no_mapeados = df[(df.tipo != "sin_dato") & df.pais.isna()]
    if len(no_mapeados):
        log.warning("diario: %s filas con país sin equivalente en el mensual", len(no_mapeados))

    df["fecha"] = pd.to_datetime(df.idfecha)
    df["dia_semana_num"] = df.dia_semana.map(lambda s: DIAS_SEMANA[clave(s)])
    df["dia_semana"] = df.dia_semana_num.map(NOMBRE_DIA)
    df["anio_mes"] = df.fecha.dt.to_period("M").dt.to_timestamp()
    df["es_regular"] = df.evento.str.strip().str.lower().eq("regular")

    out = df.rename(columns={"Week": "semana", "cantidad_visitantes": "presencia"})[[
        "destino_clave", "destino_nombre", "subdestino", "fecha", "anio", "mes", "anio_mes", "dia_semana_num",
        "dia_semana", "semana", "pais", "tipo", "evento", "es_regular", "presencia"]].reset_index(drop=True)
    return out


def run() -> dict[str, pd.DataFrame]:
    mensual, sub_cat, pais_cat = construir_mensual()
    sub_mes = construir_subdestino_mes(mensual)
    diario = construir_diario(pais_cat, sub_cat)
    guardar(mensual, "movilidad_mensual")
    guardar(sub_mes, "movilidad_subdestino_mes")
    guardar(diario, "movilidad_diaria")
    return {"mensual": mensual, "subdestino_mes": sub_mes, "diaria": diario}
