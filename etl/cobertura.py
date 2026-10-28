"""Tabla de cobertura: una fila por (fuente, anio_mes) que indica si la fuente tiene dato.
Alimenta el indicador de cobertura del tablero y evita leer 'sin dato' como 'cero'.
Las fuentes de ocupación y oferta se agregan en la parte 2 del ETL."""
import pandas as pd

from etl import config
from etl.utils import guardar


def _meses() -> pd.DatetimeIndex:
    return pd.date_range(config.COBERTURA_INI + "-01", config.COBERTURA_FIN + "-01", freq="MS")


def construir(movilidad_mensual: pd.DataFrame, movilidad_diaria: pd.DataFrame,
              migracion_total: pd.DataFrame, extras: dict[str, pd.Series] | None = None) -> pd.DataFrame:
    meses = _meses()
    filas = []

    obs_m = set(movilidad_mensual.anio_mes.unique())
    filas += [("movilidad_mensual", m, m in obs_m, None) for m in meses]

    dias = movilidad_diaria.groupby("anio_mes").fecha.nunique()
    for m in meses:
        d = int(dias.get(m, 0))
        filas.append(("movilidad_diaria", m, d > 0, d))

    obs_g = set(migracion_total.anio_mes.unique())
    filas += [("migracion", m, m in obs_g, None) for m in meses]

    for nombre, serie_meses in (extras or {}).items():
        obs = set(pd.to_datetime(serie_meses).unique())
        filas += [(nombre, m, m in obs, None) for m in meses]

    c = pd.DataFrame(filas, columns=["fuente", "anio_mes", "tiene_dato", "dias_con_dato"])
    c["dias_en_mes"] = c.anio_mes.dt.days_in_month
    c["cobertura_completa"] = c.tiene_dato
    mask = c.fuente == "movilidad_diaria"
    c.loc[mask, "cobertura_completa"] = c.loc[mask, "dias_con_dato"] == c.loc[mask, "dias_en_mes"]
    return c


def run(movilidad_mensual, movilidad_diaria, migracion_total, extras=None) -> pd.DataFrame:
    c = construir(movilidad_mensual, movilidad_diaria, migracion_total, extras)
    guardar(c, "cobertura")
    return c
