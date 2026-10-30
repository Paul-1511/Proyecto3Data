"""Fuentes del reto de Petén: visitantes al Parque Nacional Tikal y Aeropuerto Internacional Mundo Maya (AIMM).

HALLAZGOS (ver docs/inspeccion_datos.md):
  Tikal
    * Conteo real de ingresos con boleto, 2017-01 a 2026-08 (116 meses). total = nacionales + extranjeros + otros.
    * Nombres de mes con distinta capitalización ('julio'); la columna 'otros ' trae un espacio al final.
    * Ceros de abril a septiembre de 2020 = cierre por pandemia (valor real, se conserva como 0 y se marca).
      Enero 2017 = 0 es dudoso (febrero 2017 también es anormalmente bajo): se marca `cero_dudoso` y el valor
      pasa a NaN (sin dato).
  AIMM
    * Consolidado (pasajeros por segmento) cubre 2022, 2024 y 2025. 2023 NO está: se reconstruye SOLO el total
      desde el archivo de aerolíneas (que coincide exacto con el consolidado en 2024 y 2025, mes a mes).
    * El archivo de aerolíneas cubre 2023 a abril de 2026; 'Total Mes Aerolínea' es entrada+salida repetido en
      cada fila: se descarta (sumarlo duplicaría).
    * Pasajeros (personas) y operaciones (aeronaves) son magnitudes distintas: nunca van en el mismo eje.
    * Cruces (sobrevuelos) y Aeródromo Poptún NO son tráfico del aeropuerto: se guardan en tabla aparte.
    * Los pasajeros incluyen entrada y salida. Para aproximar llegadas, use solo `flujo == 'Entrada'`.
"""
import pandas as pd

from etl import config
from etl.utils import clave, exigir_columnas, guardar, leer_excel, log


def _mes_num(s: pd.Series) -> pd.Series:
    m = s.map(lambda x: config.MESES_ES.get(clave(x)))
    if m.isna().any():
        raise ValueError(f"Meses no reconocidos: {s[m.isna()].unique()}")
    return m.astype(int)


def tikal() -> pd.DataFrame:
    d = leer_excel(config.F_TIKAL).parse("Datos")
    d.columns = [c.strip() for c in d.columns]
    exigir_columnas(d, ["año", "mes", "nacionales", "extranjeros", "otros", "descripcion_otros", "total"], "Tikal")
    d = d.rename(columns={"año": "anio"})
    d["mes"] = _mes_num(d.mes)
    d["anio_mes"] = pd.to_datetime(dict(year=d.anio, month=d.mes, day=1))
    if not ((d.nacionales + d.extranjeros + d.otros) == d.total).all():
        raise ValueError("Tikal: total != nacionales + extranjeros + otros")
    d["descripcion_otros"] = d.descripcion_otros.str.strip().str.lower().replace({"sd": None})
    d["cierre_pandemia"] = (d.anio == 2020) & d.mes.between(4, 9) & (d.total == 0)
    d["cero_dudoso"] = (d.total == 0) & ~d.cierre_pandemia
    for c in ["nacionales", "extranjeros", "otros", "total"]:
        d[c] = d[c].astype(float).mask(d.cero_dudoso)
    out = d[["anio", "mes", "anio_mes", "nacionales", "extranjeros", "otros", "descripcion_otros", "total",
             "cierre_pandemia", "cero_dudoso"]].sort_values("anio_mes").reset_index(drop=True)
    log.info("tikal: %s meses, %s a %s; cero_dudoso=%s, cierre_pandemia=%s", len(out),
             out.anio_mes.min().strftime("%Y-%m"), out.anio_mes.max().strftime("%Y-%m"),
             int(out.cero_dudoso.sum()), int(out.cierre_pandemia.sum()))
    return out


def aimm_consolidado() -> pd.DataFrame:
    c = leer_excel(config.F_AIMM_CONSOLIDADO).parse("Base Consolidada", header=2)
    exigir_columnas(c, ["Año", "Mes", "N° Mes", "Tipo de Flujo", "Tipo de Pasajero", "Pasajeros"], "AIMM consolidado")
    c = c.rename(columns={"Año": "anio", "N° Mes": "mes", "Tipo de Flujo": "flujo", "Tipo de Pasajero": "segmento",
                          "Pasajeros": "pasajeros"})
    c["anio_mes"] = pd.to_datetime(dict(year=c.anio, month=c.mes, day=1))
    return c[["anio", "mes", "anio_mes", "flujo", "segmento", "pasajeros"]]


def aimm_aerolineas() -> pd.DataFrame:
    a = leer_excel(config.F_AIMM_AEROLINEAS).parse("Base de Datos")
    exigir_columnas(a, ["Año", "mes_numero", "Aerolínea", "Tipo de Flujo", "Pasajeros", "Total Mes Aerolínea"],
                    "AIMM aerolíneas")
    chk = a.groupby(["Año", "mes_numero", "Aerolínea"]).agg(p=("Pasajeros", "sum"), t=("Total Mes Aerolínea", "first"))
    if not (chk.p == chk.t).all():
        raise ValueError("AIMM aerolíneas: 'Total Mes Aerolínea' no es entrada+salida")
    a = a.rename(columns={"Año": "anio", "mes_numero": "mes", "Aerolínea": "aerolinea", "Tipo de Flujo": "flujo",
                          "Pasajeros": "pasajeros"})
    a["anio_mes"] = pd.to_datetime(dict(year=a.anio, month=a.mes, day=1))
    return a[["anio", "mes", "anio_mes", "aerolinea", "flujo", "pasajeros"]]  # sin 'Total Mes Aerolínea'


def aimm_total_mensual(cons: pd.DataFrame, aero: pd.DataFrame) -> pd.DataFrame:
    """Total mensual de pasajeros (personas). Fuente: consolidado si existe, si no aerolíneas."""
    t_c = cons.groupby(["anio_mes", "flujo"], as_index=False).pasajeros.sum()
    t_a = aero.groupby(["anio_mes", "flujo"], as_index=False).pasajeros.sum()
    comunes = t_c.merge(t_a, on=["anio_mes", "flujo"], suffixes=("_cons", "_aero"))
    if len(comunes) == 0 or not (comunes.pasajeros_cons == comunes.pasajeros_aero).all():
        raise ValueError("AIMM: el consolidado y el archivo de aerolíneas no coinciden en meses comunes")
    log.info("AIMM: consolidado y aerolíneas coinciden en %s meses-flujo comunes", len(comunes))
    t_c["fuente"] = "consolidado"
    t_a = t_a[~t_a.anio_mes.isin(t_c.anio_mes)].assign(fuente="aerolineas")
    t = pd.concat([t_c, t_a], ignore_index=True)
    w = t.pivot_table(index=["anio_mes", "fuente"], columns="flujo", values="pasajeros", aggfunc="sum").reset_index()
    w.columns.name = None
    w = w.rename(columns={"Entrada": "pasajeros_entrada", "Salida": "pasajeros_salida"})
    w["pasajeros_total"] = w.pasajeros_entrada + w.pasajeros_salida
    w["anio"], w["mes"] = w.anio_mes.dt.year, w.anio_mes.dt.month
    w["tiene_segmento"] = w.fuente.eq("consolidado")
    return w[["anio", "mes", "anio_mes", "fuente", "tiene_segmento", "pasajeros_entrada", "pasajeros_salida",
              "pasajeros_total"]].sort_values("anio_mes").reset_index(drop=True)


def aimm_operaciones() -> tuple[pd.DataFrame, pd.DataFrame]:
    xl = leer_excel(config.F_AIMM_OPERACIONES)
    o = xl.parse("Base de Operaciones", header=2)
    exigir_columnas(o, ["Año", "N° Mes", "Operador", "Tipo de Operación", "Operaciones"], "AIMM operaciones")
    o = o.rename(columns={"Año": "anio", "N° Mes": "mes", "Operador": "operador", "Tipo de Operación": "tipo_operacion",
                          "Operaciones": "operaciones"})
    o["anio_mes"] = pd.to_datetime(dict(year=o.anio, month=o.mes, day=1))
    x = xl.parse("Aux (Cruces y Poptún)", header=2)
    exigir_columnas(x, ["Año", "N° Mes", "Categoría", "Operaciones"], "AIMM operaciones aux")
    x = x.rename(columns={"Año": "anio", "N° Mes": "mes", "Categoría": "categoria", "Operaciones": "operaciones"})
    x["anio_mes"] = pd.to_datetime(dict(year=x.anio, month=x.mes, day=1))
    cols = ["anio", "mes", "anio_mes"]
    return o[cols + ["operador", "tipo_operacion", "operaciones"]], x[cols + ["categoria", "operaciones"]]


def run() -> dict[str, pd.DataFrame]:
    t = tikal()
    cons, aero = aimm_consolidado(), aimm_aerolineas()
    tot = aimm_total_mensual(cons, aero)
    ops, aux = aimm_operaciones()
    out = {"tikal_mensual": t, "aimm_pasajeros_segmento": cons, "aimm_pasajeros_aerolinea": aero,
           "aimm_pasajeros_total": tot, "aimm_operaciones": ops, "aimm_operaciones_aux": aux}
    for k, v in out.items():
        guardar(v, k)
    return out
