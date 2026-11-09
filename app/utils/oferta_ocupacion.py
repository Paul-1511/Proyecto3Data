"""Cálculos del Módulo 3 (oferta hotelera, ocupación y desagregación territorial).

Funciones puras (sin Dash) para poder probarlas con datos sintéticos. Reglas que respetan:

* La oferta es INVENTARIO con un corte por año (2022-2025). El corte de 2026 es parcial (primer
  trimestre; ~la mitad de las combinaciones repite el valor de 2025): se excluye salvo que se pida
  explícitamente, y entonces va marcado como parcial. No se construye una tendencia.
* La oferta y la ocupación son del DEPARTAMENTO (Alta Verapaz), no del destino Cobán.
* La oferta no es el denominador del índice de ocupación: no se calculan habitaciones ocupadas.
* No existe índice nacional en el archivo: el «promedio departamental» es la media simple de los
  departamentos del archivo y se rotula así (no es el índice nacional oficial).
* Cruce afluencia–ocupación: SOLO sep–dic 2025. Con n = 4 no se calcula correlación; solo se
  describe la dirección de los cambios mes a mes.
* Subdestinos: nunca se suman entre sí; no hay fila «Total». Nacionales y extranjeros por separado.
* Ausencia de dato != cero: los meses sin dato quedan NaN.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from app.utils import datos, metricas

DEPARTAMENTO = "Alta Verapaz"
DESTINO_CLAVE = "alta_verapaz"
SUBDESTINOS = ("Coban", "Lanquin", "Cuevas De Candelaria")
NOMBRES_SUBDESTINO = {"Coban": "Cobán", "Lanquin": "Lanquín", "Cuevas De Candelaria": "Cuevas de Candelaria"}
TIPOS = ("extranjero", "nacional")
METRICAS_OFERTA = {"establecimientos": "Establecimientos", "habitaciones": "Habitaciones",
                   "plazas_cama": "Plazas cama"}
ANIOS_OFERTA = (2022, 2023, 2024, 2025)
ANIO_PARCIAL = 2026
OCUPACION_INI, OCUPACION_FIN = pd.Timestamp("2023-01-01"), pd.Timestamp("2025-12-01")
VENTANA_CRUCE = pd.date_range("2025-09-01", "2025-12-01", freq="MS", name="anio_mes")
PROMEDIO = "promedio"   # valor del selector de mes en «Subdestinos»


def nombre_subdestino(sub: str) -> str:
    """Nombre con tildes para los rótulos (los datos traen 'Coban', 'Lanquin')."""
    return NOMBRES_SUBDESTINO.get(sub, sub)


def _exigir(df: pd.DataFrame, columnas: Iterable[str]) -> None:
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        raise KeyError(f"Faltan columnas: {faltan}")


# ===================================================================== A. capacidad
def capacidad_por_anio(oferta: pd.DataFrame, departamento: str = DEPARTAMENTO,
                       incluir_parcial: bool = False) -> pd.DataFrame:
    """Inventario por (año, tipo de alojamiento) del departamento. Un corte por año.

    Sin ``incluir_parcial`` solo quedan 2022-2025. Con él se agrega 2026 marcado ``es_corte_parcial``.
    No se rellenan años faltantes ni se interpolan.
    """
    _exigir(oferta, ["anio", "departamento", "tipo_alojamiento", *METRICAS_OFERTA])
    df = oferta[oferta["departamento"] == departamento].copy()
    anios = list(ANIOS_OFERTA) + ([ANIO_PARCIAL] if incluir_parcial else [])
    df = df[df["anio"].isin(anios)]
    if "es_corte_parcial" not in df.columns:
        df["es_corte_parcial"] = df["anio"].eq(ANIO_PARCIAL)
    if "repite_valor_anio_previo" not in df.columns:
        df["repite_valor_anio_previo"] = False
    if df.duplicated(["anio", "tipo_alojamiento"]).any():
        raise ValueError("La oferta debe tener un único corte por año y tipo de alojamiento.")
    cols = ["anio", "tipo_alojamiento", *METRICAS_OFERTA, "es_corte_parcial", "repite_valor_anio_previo"]
    return df[cols].sort_values(["anio", "tipo_alojamiento"]).reset_index(drop=True)


def total_departamento_por_anio(cap: pd.DataFrame, metrica: str) -> pd.Series:
    """Inventario total del departamento por año = Σ tipos de alojamiento del MISMO corte.

    Sumar tipos dentro de un año es válido (inventario disjunto); nunca se suman años.
    """
    if metrica not in METRICAS_OFERTA:
        raise ValueError(f"Métrica de oferta inválida: {metrica!r}")
    return cap.groupby("anio")[metrica].sum(min_count=1)


def variacion_pct(inicial: float, final: float) -> float:
    """(final − inicial) / inicial × 100; NaN si falta un extremo o el inicial es 0."""
    if pd.isna(inicial) or pd.isna(final) or inicial == 0:
        return float("nan")
    return float((final - inicial) / inicial * 100)


def variacion_capacidad(cap: pd.DataFrame, metrica: str, anio_ini: int = 2022,
                        anio_fin: int = 2025) -> pd.DataFrame:
    """Cambio entre dos cortes anuales por tipo y para el total del departamento (comparación de
    dos inventarios, no tendencia)."""
    piv = cap[cap["anio"].isin([anio_ini, anio_fin])].pivot(index="tipo_alojamiento", columns="anio",
                                                            values=metrica)
    piv = piv.reindex(columns=[anio_ini, anio_fin])
    tot = total_departamento_por_anio(cap[cap["anio"].isin([anio_ini, anio_fin])], metrica)
    piv.loc["Total departamento"] = [tot.get(anio_ini, np.nan), tot.get(anio_fin, np.nan)]
    out = piv.rename(columns={anio_ini: "inicial", anio_fin: "final"}).reset_index()
    out["variacion_pct"] = [variacion_pct(a, b) for a, b in zip(out["inicial"], out["final"])]
    return out


# ===================================================================== B. ocupación
def serie_ocupacion(ocup: pd.DataFrame, departamento: str = DEPARTAMENTO,
                    meses: Optional[Iterable] = None) -> pd.DataFrame:
    """Índice mensual (en %) del departamento, con TODOS los meses del rango (faltantes = NaN)."""
    _exigir(ocup, ["departamento", "anio_mes", "indice_pct"])
    df = ocup.loc[ocup["departamento"] == departamento, ["anio_mes", "indice_pct"]]
    meses = datos.rango_meses(OCUPACION_INI, OCUPACION_FIN) if meses is None else meses
    return datos.reindexar_meses(df, meses)


def promedio_departamental(ocup: pd.DataFrame, meses: Optional[Iterable] = None) -> pd.DataFrame:
    """Media SIMPLE de los índices departamentales por mes (no es el índice nacional oficial).

    Devuelve ``anio_mes, indice_pct, n_departamentos``. Un mes solo se informa si todos los
    departamentos del archivo tienen dato ese mes (si no, NaN: un promedio parcial cambiaría de base).
    """
    _exigir(ocup, ["departamento", "anio_mes", "indice_pct"])
    total = ocup["departamento"].nunique()
    g = ocup.groupby("anio_mes").agg(indice_pct=("indice_pct", "mean"),
                                     n_departamentos=("indice_pct", "count")).reset_index()
    g.loc[g["n_departamentos"] < total, "indice_pct"] = np.nan
    meses = datos.rango_meses(OCUPACION_INI, OCUPACION_FIN) if meses is None else meses
    return datos.reindexar_meses(g, meses)


def picos_valles(serie: pd.DataFrame) -> pd.DataFrame:
    """Mes pico (máximo) y valle (mínimo) de cada año. Empates: se marcan todos los meses empatados.

    ``serie`` = salida de ``serie_ocupacion``. Los NaN no compiten.
    """
    df = serie.dropna(subset=["indice_pct"]).copy()
    if df.empty:
        return pd.DataFrame(columns=["anio", "tipo", "anio_mes", "indice_pct"])
    df["anio"] = df["anio_mes"].dt.year
    filas = []
    for anio, g in df.groupby("anio"):
        for tipo, valor in (("pico", g["indice_pct"].max()), ("valle", g["indice_pct"].min())):
            for _, r in g[np.isclose(g["indice_pct"], valor)].iterrows():
                filas.append(dict(anio=anio, tipo=tipo, anio_mes=r["anio_mes"], indice_pct=r["indice_pct"]))
    return pd.DataFrame(filas).sort_values(["anio_mes", "tipo"]).reset_index(drop=True)


def resumen_anual_ocupacion(serie: pd.DataFrame, promedio: pd.DataFrame) -> pd.DataFrame:
    """Media de los 12 índices mensuales de cada año (depto y promedio departamental) y su brecha en pp.

    Solo años con los 12 meses; es una media de índices (no un índice anual ponderado por noches).
    """
    def _anual(df):
        d = df.dropna(subset=["indice_pct"]).assign(anio=lambda x: x["anio_mes"].dt.year)
        g = d.groupby("anio")["indice_pct"].agg(["mean", "count"])
        return g.loc[g["count"] == 12, "mean"]
    out = pd.DataFrame({"departamento": _anual(serie), "promedio_departamental": _anual(promedio)})
    out["brecha_pp"] = out["departamento"] - out["promedio_departamental"]
    return out.reset_index().rename(columns={"index": "anio"})


# ============================================================ movilidad (C, D, E)
def solo_destino(mov: pd.DataFrame) -> pd.DataFrame:
    """Filas de Alta Verapaz, sus tres subdestinos y tipos extranjero/nacional (copia)."""
    _exigir(mov, ["destino_clave", "subdestino", "tipo", "anio_mes", "segmento", "visitantes"])
    m = (mov["destino_clave"] == DESTINO_CLAVE) & mov["subdestino"].isin(SUBDESTINOS) & mov["tipo"].isin(TIPOS)
    return mov.loc[m].copy()


def visitantes_mes(mov: pd.DataFrame, subdestino: str, tipo: str,
                   meses: Optional[Iterable] = None) -> pd.Series:
    """Visitantes únicos por mes de UN subdestino y UN tipo (Σ de los dos segmentos del mes).

    Un mes sin los dos segmentos queda NaN. Con ``meses`` se reindexa (meses sin dato = NaN).
    Nunca se suman meses, subdestinos ni tipos.
    """
    df = solo_destino(mov)
    df = df[(df["subdestino"] == subdestino) & (df["tipo"] == tipo)]
    if df.empty:
        idx = pd.DatetimeIndex(list(meses) if meses is not None else [], name="anio_mes")
        return pd.Series(np.nan, index=idx, name="visitantes", dtype=float)
    tabla =(df.groupby(["anio_mes", "segmento"])["visitantes"]
             .agg(lambda s: s.sum(min_count=len(s))).unstack("segmento")
             .reindex(columns=list(metricas.SEGMENTOS)))
    serie = tabla.sum(axis=1, min_count=len(metricas.SEGMENTOS))
    serie.index = pd.DatetimeIndex(serie.index, name="anio_mes")
    serie.name = "visitantes"
    if meses is not None:
        serie = serie.reindex(pd.DatetimeIndex(list(meses), name="anio_mes"))
    return serie.sort_index()


# ========================================================== C. ventana coincidente
def meses_cruce(mes_ini: Any = None, mes_fin: Any = None) -> pd.DatetimeIndex:
    """Meses del filtro dentro de la ventana sep–dic 2025 (puede quedar vacío)."""
    if mes_ini is None and mes_fin is None:
        return VENTANA_CRUCE
    ini = pd.Timestamp(mes_ini if mes_ini is not None else mes_fin).to_period("M").to_timestamp()
    fin = pd.Timestamp(mes_fin if mes_fin is not None else mes_ini).to_period("M").to_timestamp()
    return VENTANA_CRUCE[(VENTANA_CRUCE >= ini) & (VENTANA_CRUCE <= fin)]


def datos_cruce(mov: pd.DataFrame, ocup: pd.DataFrame, subdestino: str, tipo: str,
                meses: Iterable) -> pd.DataFrame:
    """Afluencia (visitantes del subdestino y tipo) e índice de ocupación del departamento, por mes.

    Solo se aceptan meses de la ventana sep–dic 2025: cualquier otro mes lanza ``ValueError``.
    """
    meses = pd.DatetimeIndex(list(meses), name="anio_mes")
    fuera = meses.difference(VENTANA_CRUCE)
    if len(fuera):
        raise ValueError("El cruce afluencia–ocupación solo admite sep–dic 2025; "
                         f"recibió {[f'{m:%Y-%m}' for m in fuera]}.")
    vis = visitantes_mes(mov, subdestino, tipo, meses)
    oc = serie_ocupacion(ocup, meses=meses).set_index("anio_mes")["indice_pct"]
    return pd.DataFrame({"anio_mes": meses, "visitantes": vis.to_numpy(), "ocupacion_pct": oc.to_numpy()})


def _signo(x: float) -> str:
    if pd.isna(x):
        return "sin dato"
    return "sube" if x > 0 else "baja" if x < 0 else "igual"


def describir_relacion(cruce: pd.DataFrame) -> dict:
    """Descripción honesta de la relación (sin correlación): dirección de cada cambio mes a mes.

    Devuelve ``n_meses``, ``cambios`` (lista de dicts con mes y dirección de cada serie),
    ``coinciden`` (cambios en la misma dirección), ``comparables`` (cambios con ambos datos),
    ``mes_max_visitantes`` y ``mes_max_ocupacion``.
    """
    df = cruce.sort_values("anio_mes").reset_index(drop=True)
    completos = df.dropna(subset=["visitantes", "ocupacion_pct"])
    cambios, coinciden, comparables = [], 0, 0
    for i in range(1, len(df)):
        dv = df.loc[i, "visitantes"] - df.loc[i - 1, "visitantes"]
        do = df.loc[i, "ocupacion_pct"] - df.loc[i - 1, "ocupacion_pct"]
        sv, so = _signo(dv), _signo(do)
        cambios.append(dict(mes=df.loc[i, "anio_mes"], visitantes=sv, ocupacion=so,
                            dif_visitantes_pct=variacion_pct(df.loc[i - 1, "visitantes"], df.loc[i, "visitantes"]),
                            dif_ocupacion_pp=float(do) if not pd.isna(do) else float("nan")))
        if "sin dato" not in (sv, so):
            comparables += 1
            coinciden += int(sv == so)
    def _mes_max(col):
        s = completos.set_index("anio_mes")[col]
        return s.idxmax() if len(s) else None
    return dict(n_meses=len(completos), cambios=cambios, coinciden=coinciden, comparables=comparables,
                mes_max_visitantes=_mes_max("visitantes"), mes_max_ocupacion=_mes_max("ocupacion_pct"))


# ================================================================= D. subdestinos
def afluencia_subdestinos(mov: pd.DataFrame, tipo: str, meses: Iterable, mes: Any = PROMEDIO) -> pd.DataFrame:
    """Afluencia de cada subdestino para UN tipo. Nunca incluye una fila «Total».

    * ``mes == 'promedio'``: media de los visitantes mensuales sobre los meses del rango con dato
      (se informa ``n_meses``; no se suman meses).
    * ``mes`` = un mes: visitantes de ese mes (NaN si no hay dato).

    ``relativo_pct`` = valor / valor del subdestino mayor × 100 (afluencia relativa).
    """
    meses = pd.DatetimeIndex(list(meses), name="anio_mes")
    filas = []
    for sub in SUBDESTINOS:
        serie = visitantes_mes(mov, sub, tipo, meses)
        if mes == PROMEDIO or mes is None:
            obs = serie.dropna()
            valor, n = (float(obs.mean()), len(obs)) if len(obs) else (float("nan"), 0)
        else:
            m = pd.Timestamp(mes).to_period("M").to_timestamp()
            valor = float(serie.get(m, np.nan)) if m in serie.index else float("nan")
            n = int(not pd.isna(valor))
        filas.append(dict(subdestino=sub, nombre=nombre_subdestino(sub), tipo=tipo, visitantes=valor, n_meses=n))
    out = pd.DataFrame(filas)
    maximo = out["visitantes"].max(skipna=True)
    out["relativo_pct"] = out["visitantes"] / maximo * 100 if pd.notna(maximo) and maximo > 0 else np.nan
    return out


# ================================================================ E. estacionalidad
def indice_estacional_ocupacion(serie: pd.DataFrame) -> pd.DataFrame:
    """Índice estacional de ocupación por año: índice del mes / media de los 12 meses del año × 100.

    Devuelve ``anio, mes, indice_pct, indice_estacional``. Solo años con los 12 meses.
    """
    df = serie.dropna(subset=["indice_pct"]).copy()
    df["anio"], df["mes"] = df["anio_mes"].dt.year, df["anio_mes"].dt.month
    completos = df.groupby("anio")["mes"].transform("count") == 12
    df = df[completos]
    df["indice_estacional"] = df["indice_pct"] / df.groupby("anio")["indice_pct"].transform("mean") * 100
    return df[["anio", "mes", "anio_mes", "indice_pct", "indice_estacional"]].reset_index(drop=True)


def indice_estacional_visitantes(mov: pd.DataFrame, subdestino: str, tipo: str,
                                 meses: Iterable) -> pd.DataFrame:
    """Perfil estacional COMPUESTO de visitantes: visitantes del mes / media de los meses observados × 100.

    Los meses observados mezclan 2025 (sep–dic) y 2026 (mar–ago); ningún mes calendario se repite,
    así que no hay comparación interanual. Devuelve una fila por mes calendario (1-12) con
    ``anio_mes`` de origen; los meses sin dato (ene, feb) quedan NaN.
    """
    serie = visitantes_mes(mov, subdestino, tipo, meses).dropna()
    base = pd.DataFrame({"mes": range(1, 13)})
    if serie.empty:
        return base.assign(anio_mes=pd.NaT, visitantes=np.nan, indice_estacional=np.nan)
    if serie.index.month.duplicated().any():
        raise ValueError("El perfil compuesto no admite el mismo mes calendario de dos años "
                         "(no se compara 2025 contra 2026).")
    df = pd.DataFrame({"anio_mes": serie.index, "visitantes": serie.to_numpy()})
    df["mes"] = df["anio_mes"].dt.month
    df["indice_estacional"] = df["visitantes"] / df["visitantes"].mean() * 100
    return base.merge(df, on="mes", how="left")
