"""Tabla de cobertura: una fila por (fuente, anio_mes) que indica si la fuente tiene dato.
Alimenta el indicador de cobertura del tablero y evita leer 'sin dato' como 'cero'.
Fuentes: movilidad (mensual y diaria), migración, ocupación, oferta (corte anual), Tikal, AIMM (pasajeros y
operaciones). Las encuestas son cortes transversales de una sola ola y NO forman parte de la cobertura temporal."""
import pandas as pd

from etl import config
from etl.utils import guardar


def _meses() -> pd.DatetimeIndex:
    return pd.date_range(config.COBERTURA_INI + "-01", config.COBERTURA_FIN + "-01", freq="MS")


def construir(movilidad_mensual: pd.DataFrame, movilidad_diaria: pd.DataFrame,
              migracion_total: pd.DataFrame, extras: dict[str, pd.Series] | None = None,
              oferta_anios: dict[int, bool] | None = None) -> pd.DataFrame:
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

    # Oferta: corte ANUAL (inventario). Se marca como dato en los meses de los años con corte; el corte parcial
    # de 2026 (primer trimestre) se marca con cobertura incompleta.
    for m in meses:
        if oferta_anios and m.year in oferta_anios:
            filas.append(("oferta_corte_anual", m, True, None))
        else:
            filas.append(("oferta_corte_anual", m, False, None))

    c = pd.DataFrame(filas, columns=["fuente", "anio_mes", "tiene_dato", "dias_con_dato"])
    c["dias_en_mes"] = c.anio_mes.dt.days_in_month
    c["granularidad"] = c.fuente.map(lambda f: "diaria" if f == "movilidad_diaria"
                                     else "anual" if f == "oferta_corte_anual" else "mensual")
    c["cobertura_completa"] = c.tiene_dato
    parcial = c.fuente.eq("oferta_corte_anual") & c.anio_mes.dt.year.eq(2026)
    c.loc[parcial, "cobertura_completa"] = False
    mask = c.fuente == "movilidad_diaria"
    c.loc[mask, "cobertura_completa"] = c.loc[mask, "dias_con_dato"] == c.loc[mask, "dias_en_mes"]
    return c


def run(movilidad_mensual, movilidad_diaria, migracion_total, extras=None, oferta_anios=None) -> pd.DataFrame:
    c = construir(movilidad_mensual, movilidad_diaria, migracion_total, extras, oferta_anios)
    guardar(c, "cobertura")
    return c
