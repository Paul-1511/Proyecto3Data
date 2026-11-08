"""Métricas analíticas del Observatorio (Módulos 1 y 2).

Todas las funciones reciben datos YA FILTRADOS (ver ``app/utils/datos.py``) de UNA sola
serie territorial: un subdestino y un tipo de visitante. Si el DataFrame mezcla subdestinos
o tipos se lanza ``ValueError``, porque sumarlos daría resultados engañosos (una persona
puede estar en varios subdestinos; nacionales y extranjeros no se suman).

Reglas comunes:
* Ausencia de dato != cero: los ``NaN`` nunca se tratan como 0. Una suma con algún ``NaN``
  se considera desconocida (NaN) y el resultado indefinido es ``NaN``.
* Nunca se promedia ``permanencia_prom`` ni ninguna cifra ya promediada.
* Los DataFrames de entrada no se modifican.
* No se aceptan estimaciones: si el DataFrame trae ``es_estimacion == True`` se rechaza.
* Mensual y diario son universos distintos: ninguna función mezcla visitantes mensuales
  con presencia diaria.
"""
from __future__ import annotations

from typing import NamedTuple, Sequence

import numpy as np
import pandas as pd

SEG_MAS_1_DIA = "mas_de_1_dia"          # P1: categorías excluyentes; por convención, turista
SEG_MENOS_1_DIA = "menos_de_1_dia"      # P1: categorías excluyentes; por convención, excursionista
SEGMENTOS = (SEG_MAS_1_DIA, SEG_MENOS_1_DIA)
EVENTO_REGULAR = "Regular"
DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


# ----------------------------------------------------------------------- utilidades
def _validar(df: pd.DataFrame, columnas: Sequence[str]) -> None:
    """Exige columnas, rechaza estimaciones y mezclas de subdestino/tipo."""
    requeridas = [*columnas, "subdestino", "tipo"]
    faltan = [c for c in requeridas if c not in df.columns]
    if faltan:
        raise KeyError(f"Faltan columnas: {faltan}")
    if "es_estimacion" in df.columns and df["es_estimacion"].fillna(False).astype(bool).any():
        raise ValueError("Los datos incluyen estimaciones (es_estimacion=True); no se tratan como observaciones.")
    for col in ("subdestino", "tipo"):
        valores = sorted(df[col].dropna().unique().tolist())
        if len(valores) > 1:
            raise ValueError(
                f"Se recibieron varios valores de {col!r} {valores}; filtre una sola serie "
                "(no se suman subdestinos ni tipos).")


def _suma_estricta(serie: pd.Series) -> float:
    """Suma que devuelve NaN si falta algún valor (una suma parcial subestimaría)."""
    return float(serie.sum(min_count=len(serie))) if len(serie) else np.nan


def _validar_segmentos(df: pd.DataFrame) -> None:
    desconocidos = set(df["segmento"].dropna().unique()) - set(SEGMENTOS)
    if desconocidos:
        raise ValueError(f"Segmentos desconocidos: {sorted(desconocidos)}")


def _visitantes_por_mes_y_segmento(df: pd.DataFrame) -> pd.DataFrame:
    """Visitantes por mes (filas) y segmento (columnas). Mes sin fila del segmento -> NaN."""
    if df.empty:
        return pd.DataFrame(columns=list(SEGMENTOS), dtype=float)
    serie = df.groupby(["anio_mes", "segmento"])["visitantes"].agg(_suma_estricta)
    if serie.empty:
        return pd.DataFrame(columns=list(SEGMENTOS), dtype=float)
    return serie.unstack("segmento").reindex(columns=list(SEGMENTOS)).sort_index()


# ---------------------------------------------------------------------- 1. estadía
def estadia_ponderada(df: pd.DataFrame) -> float:
    """Estadía media = Σ dias_persona / Σ visitantes, solo del segmento ``mas_de_1_dia``.

    Las filas con ``dias_persona`` o ``visitantes`` nulos se excluyen de AMBAS sumas (para que
    numerador y denominador cubran las mismas filas). Devuelve ``NaN`` si no quedan filas o si
    Σ visitantes <= 0. Nunca usa ``permanencia_prom``.
    Columnas: segmento, dias_persona, visitantes (+ subdestino y tipo, de una sola serie).
    """
    _validar(df, ("segmento", "dias_persona", "visitantes"))
    seg = df.loc[df["segmento"] == SEG_MAS_1_DIA, ["dias_persona", "visitantes"]].dropna()
    if seg.empty:
        return float("nan")
    if (seg < 0).any().any():
        raise ValueError("dias_persona y visitantes no pueden ser negativos.")
    denominador = seg["visitantes"].sum()
    if denominador <= 0:
        return float("nan")
    return float(seg["dias_persona"].sum() / denominador)


# ------------------------------------------------------ 2. turista vs excursionista
def proporcion_turista_excursionista(df: pd.DataFrame) -> pd.DataFrame:
    """Proporción mensual de ``mas_de_1_dia`` y ``menos_de_1_dia`` (fracciones 0-1).

    Una fila por mes con ``anio_mes``, ``prop_mas_de_1_dia`` y ``prop_menos_de_1_dia``.
    Cada mes se calcula por separado; NO se construye un total de visitantes del período.
    Si a un mes le falta un segmento (o tiene nulos) o su total es 0, ambas proporciones son
    ``NaN`` (nunca 0).
    """
    _validar(df, ("anio_mes", "segmento", "visitantes"))
    _validar_segmentos(df)
    base = _visitantes_por_mes_y_segmento(df)
    total = base[SEG_MAS_1_DIA] + base[SEG_MENOS_1_DIA]   # NaN si falta cualquiera
    valido = total > 0
    return pd.DataFrame({
        "anio_mes": base.index,
        "prop_mas_de_1_dia": (base[SEG_MAS_1_DIA] / total).where(valido).to_numpy(),
        "prop_menos_de_1_dia": (base[SEG_MENOS_1_DIA] / total).where(valido).to_numpy(),
    }).reset_index(drop=True)


# ------------------------------------------------------ 3. promedio mensual de visitantes
class PromedioMensual(NamedTuple):
    """Media mensual y número de meses observados que intervinieron."""
    promedio: float
    n_meses: int


def promedio_mensual_visitantes(df: pd.DataFrame) -> PromedioMensual:
    """Media de los visitantes mensuales observados de UN subdestino y UN tipo.

    Dentro de cada mes se suman los dos segmentos (categorías excluyentes según P1); luego se
    promedian los meses. No se suma entre meses ni entre subdestinos. Un mes entra solo si
    tiene dato de AMBOS segmentos y sin nulos: una fila ausente es "sin dato", no cero.
    Devuelve ``PromedioMensual(promedio, n_meses)``; sin meses válidos, ``(NaN, 0)``.
    """
    _validar(df, ("anio_mes", "segmento", "visitantes"))
    _validar_segmentos(df)
    validos = _visitantes_por_mes_y_segmento(df).dropna()
    if validos.empty:
        return PromedioMensual(float("nan"), 0)
    por_mes = validos.sum(axis=1)
    return PromedioMensual(float(por_mes.mean()), int(len(por_mes)))


# ----------------------------------------------------------------- utilidades diarias
def _presencia_por_fecha(diaria: pd.DataFrame, con_evento: bool) -> pd.DataFrame:
    """Una fila por día: presencia sumada entre países (de la MISMA serie), sin duplicar por país."""
    cols = ["fecha", "presencia"] + (["evento", "es_regular"] if con_evento else [])
    d = diaria[cols].copy()
    d["fecha"] = pd.to_datetime(d["fecha"]).dt.normalize()
    g = d.groupby("fecha")
    out = g["presencia"].agg(_suma_estricta).to_frame()
    if con_evento:
        if (g["evento"].nunique(dropna=False) > 1).any():
            raise ValueError("Hay fechas con más de un evento distinto.")
        out["evento"] = g["evento"].first()
        out["es_regular"] = g["es_regular"].first().fillna(False).astype(bool)
    out["dow"] = out.index.dayofweek   # 0 = lunes
    return out.dropna(subset=["presencia"])   # días sin dato se excluyen, no valen 0


# ------------------------------------------------------------------------- 4. lift
class Lift(NamedTuple):
    """Resultado de ``lift_evento``.

    ``media_regular`` es la presencia regular esperada: promedio de las medias regulares de
    cada día de semana, ponderado por los días del evento en ese día de semana.
    """
    lift_pct: float
    media_evento: float
    media_regular: float
    n_dias_evento: int
    n_dias_regular: int


_LIFT_VACIO = Lift(float("nan"), float("nan"), float("nan"), 0, 0)


def lift_evento(diaria: pd.DataFrame, evento: str) -> Lift:
    """Lift de un evento: ``(media_evento / media_regular - 1) * 100`` (%).

    * Se agrega ``presencia`` por fecha (suma entre países de la misma serie) ANTES de promediar.
    * Día regular = ``es_regular == True``. Para comparar días equivalentes, cada día del evento
      se contrasta con la media de los días regulares del MISMO día de la semana.
    * Los días del evento cuyo día de semana no tiene días regulares se excluyen (no comparables).
    * Si no hay días comparables, o la media regular esperada es <= 0, el lift es ``NaN``.
    * Los días con presencia nula no se cuentan.
    Es presencia DIARIA: no se compara con visitantes mensuales.
    """
    _validar(diaria, ("fecha", "evento", "es_regular", "presencia"))
    if evento == EVENTO_REGULAR:
        raise ValueError("'Regular' es la referencia, no un evento.")
    if diaria.empty:
        return _LIFT_VACIO
    dias = _presencia_por_fecha(diaria, con_evento=True)
    del_evento = dias[dias["evento"] == evento]
    if del_evento["es_regular"].any():
        raise ValueError(f"El evento {evento!r} tiene días marcados como regulares.")
    regulares = dias[dias["es_regular"]]
    media_por_dow = regulares.groupby("dow")["presencia"].mean()
    comparables = del_evento[del_evento["dow"].isin(media_por_dow.index)]
    if comparables.empty:
        return _LIFT_VACIO
    media_evento = float(comparables["presencia"].mean())
    media_regular = float(comparables["dow"].map(media_por_dow).mean())
    n_regular = int(regulares["dow"].isin(set(comparables["dow"])).sum())
    if not media_regular > 0:
        return Lift(float("nan"), media_evento, media_regular, int(len(comparables)), n_regular)
    return Lift((media_evento / media_regular - 1) * 100, media_evento, media_regular,
                int(len(comparables)), n_regular)


# ------------------------------------------------------------------ 5. patrón semanal
def patron_semanal(diaria: pd.DataFrame, solo_regulares: bool = False) -> pd.DataFrame:
    """Presencia media por día de la semana (lunes a domingo, siempre 7 filas).

    Columnas: ``dia_semana_num`` (0=lunes), ``dia_semana``, ``presencia_media``, ``n_dias``
    (fechas distintas promediadas). Primero se agrega por fecha (no se promedian filas por
    país). Un día de la semana sin datos queda con ``NaN`` y ``n_dias = 0``. Con
    ``solo_regulares=True`` se excluyen los días con evento. Es presencia DIARIA.
    """
    extra = ("es_regular",) if solo_regulares else ()
    _validar(diaria, ("fecha", "presencia", *extra))
    base = diaria[diaria["es_regular"].fillna(False).astype(bool)] if solo_regulares else diaria
    if base.empty:
        dias = pd.DataFrame({"presencia": pd.Series(dtype=float), "dow": pd.Series(dtype=int)})
    else:
        dias = _presencia_por_fecha(base, con_evento=False)
    medias = dias.groupby("dow")["presencia"].agg(["mean", "count"]).reindex(range(7))
    return pd.DataFrame({
        "dia_semana_num": list(range(7)),
        "dia_semana": list(DIAS_SEMANA),
        "presencia_media": medias["mean"].to_numpy(dtype=float),
        "n_dias": medias["count"].fillna(0).astype(int).to_numpy(),
    })
