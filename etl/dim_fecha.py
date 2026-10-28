"""Tabla de fechas común. Todas las demás tablas se relacionan por `fecha` o `anio_mes`."""
import pandas as pd

from etl import config
from etl.utils import guardar

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def construir() -> pd.DataFrame:
    f = pd.DataFrame({"fecha": pd.date_range(config.FECHA_INI, config.FECHA_FIN, freq="D")})
    f["anio"] = f.fecha.dt.year
    f["mes"] = f.fecha.dt.month
    f["nombre_mes"] = f.mes.map(lambda m: MESES[m - 1])
    f["anio_mes"] = f.fecha.dt.to_period("M").dt.to_timestamp()  # primer día del mes
    f["dia"] = f.fecha.dt.day
    f["dia_semana"] = f.fecha.dt.dayofweek  # 0 = lunes ... 6 = domingo
    f["nombre_dia"] = f.dia_semana.map(lambda d: DIAS[d])
    f["es_fin_de_semana"] = f.dia_semana >= 5
    f["semana_iso"] = f.fecha.dt.isocalendar().week.astype(int)
    f["dias_en_mes"] = f.fecha.dt.days_in_month
    return f


def run() -> pd.DataFrame:
    df = construir()
    guardar(df, "dim_fecha")
    return df
