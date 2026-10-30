"""Utilidades compartidas por el ETL."""
from __future__ import annotations

import logging
import unicodedata
from pathlib import Path

import pandas as pd

from etl import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("etl")


def sin_acentos(s) -> str:
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()


def clave(s) -> str:
    """Clave de comparación: minúsculas, sin acentos, espacios colapsados."""
    return " ".join(sin_acentos(s).strip().lower().split())


# Nombres con codificación dañada en la fuente (clave dañada -> clave correcta)
CORRECCIONES_NOMBRE = {"espaaa": "espana"}


def clave_corregida(s) -> str:
    k = clave(s)
    return CORRECCIONES_NOMBRE.get(k, k)


def tipo_procedencia(pais) -> str:
    """nacional (Guatemala, lleva factor de expansión) / extranjero / sin_dato."""
    if pais is None or (isinstance(pais, float) and pd.isna(pais)):
        return "sin_dato"
    k = clave(pais)
    if k in ("", "null", "nan", "none"):
        return "sin_dato"
    return "nacional" if k == "guatemala" else "extranjero"


def leer_excel(nombre: str, **kw) -> pd.ExcelFile:
    ruta = config.RAW / nombre
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró {ruta}. Coloque los datos del curso en data/raw/ "
            f"con el nombre exacto '{nombre}'."
        )
    return pd.ExcelFile(ruta, **kw)


def exigir_columnas(df: pd.DataFrame, columnas: list[str], origen: str) -> None:
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        raise ValueError(f"{origen}: faltan columnas {faltan}. Columnas presentes: {list(df.columns)}")


def guardar(df: pd.DataFrame, nombre: str) -> Path:
    config.PROC.mkdir(parents=True, exist_ok=True)
    ruta = config.PROC / f"{nombre}.parquet"
    try:
        df.to_parquet(ruta, index=False)
    except Exception:  # columnas object con tipos mezclados (p. ej. encuestas): se guardan como texto
        df = df.copy()
        for c in df.select_dtypes(include="object").columns:
            df[c] = df[c].map(lambda v: None if pd.isna(v) else str(v)).astype("string")
        df.to_parquet(ruta, index=False)
    log.info("escrito %s  (%s filas, %s columnas)", ruta.name, f"{len(df):,}", df.shape[1])
    return ruta
