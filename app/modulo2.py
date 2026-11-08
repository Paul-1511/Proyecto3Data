"""Módulo 2 — Dinámica temporal, eventos y pronóstico (Cobán y Alta Verapaz).

Integración (patrón de app/main.py): ``layout()`` y ``registrar_callbacks(app)``; solo LEE el filtro
global ``store-filtros``. Todos los IDs llevan el prefijo ``m2-``.

Visualizaciones
* Serie diaria de presencia con eventos seleccionados sombreados y tramos sin dato en gris.
* Tabla de lift por evento (``metricas.lift_evento``).
* Patrón semanal (``metricas.patron_semanal``) y mapa de calor día de semana × mes.
* Pronóstico ene–feb 2026 (estimaciones de P1, sin entrenar nada aquí) con banda de error y MAPE/RMSE/MAE.

Interacciones: el selector de eventos (``m2-eventos``) actualiza serie (sombreado y marcas), lift,
patrón semanal y mapa de calor; el selector de modo (``m2-modo``) cambia qué días entran al patrón
semanal y al mapa de calor (todos / solo regulares / solo días de los eventos seleccionados).
Los filtros globales (meses, tipo, subdestino) gobiernan todo salvo el rango de meses del panel de
pronóstico, que siempre muestra la serie completa observada + la estimación para dar contexto.

Decisiones metodológicas
* Presencia diaria != visitantes únicos mensuales: nunca se suma para reconstruir el mes ni se
  grafica en el mismo eje que la serie mensual. Por fecha se suman los países de UNA sola serie
  (subdestino × tipo), nunca subdestinos ni tipos.
* Un día sin fila es «Sin dato» (hueco), no cero.
* Lift: días del evento contra días regulares del mismo día de la semana (ver metricas.lift_evento).
* Pronóstico: se muestran las estimaciones de P1 tal cual; solo ene–feb 2026; no se suman
  subdestinos; nacionales y extranjeros se separan por el filtro de tipo.
* Sin descargas ni tablas de microdatos.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional, Sequence

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

from app import theme
from app.modulo1 import preparar, serie_completa, solo_alta_verapaz, visitantes_mensuales
from app.theme import ID_STORE_FILTROS
from app.utils import datos, metricas
from app.utils.datos import Filtros

FUENTE_DIARIA = "movilidad_diaria"
FUENTE_SUB = "movilidad_subdestino_mes"
FUENTE_PRON = "pronostico_ene_feb_2026"
FUENTE_RESUMEN = "pronostico_resumen_modelo"

MESES_PRONOSTICO = pd.DatetimeIndex(["2026-01-01", "2026-02-01"])
UMBRAL_MAPE_ALTO = 40.0   # % ; P1 recomienda mostrar el error junto a las series con MAPE > 40 %
MIN_DIAS_ETIQUETA_SIN_DATO = 7

COLOR_SOMBREADO_EVENTO = "rgba(86, 180, 233, 0.28)"    # CATEGORICOS[2] translúcido
COLOR_SOMBREADO_SIN_DATO = "rgba(154, 160, 166, 0.22)"  # COLOR_SIN_DATO translúcido
COLOR_HEATMAP_SIN_DATO = "rgba(154, 160, 166, 0.35)"

MODOS = {"todos": "Todos los días", "regulares": "Solo días regulares",
         "eventos": "Solo días de los eventos seleccionados"}
DIAS_ETIQUETA = [d.capitalize() for d in metricas.DIAS_SEMANA]

ID_EVENTOS = "m2-eventos"
ID_MODO = "m2-modo"
ID_G_SERIE = "m2-grafico-serie"
ID_LIFT = "m2-lift"
ID_G_SEMANAL = "m2-grafico-semanal"
ID_G_HEATMAP = "m2-grafico-heatmap"
ID_G_PRON = "m2-grafico-pronostico"
ID_PRON_METRICAS = "m2-pron-metricas"
ID_PRON_AVISO = "m2-pron-aviso"

_CONFIG_GRAFICO = {"displayModeBar": False}


# ------------------------------------------------------------------------ datos
def _leer(nombre: str, columnas: list) -> pd.DataFrame:
    """Lee un parquet; si no existe devuelve una tabla vacía tipada (la UI mostrará «Sin dato»)."""
    try:
        return datos.cargar(nombre)
    except FileNotFoundError:
        tiempo = {"anio_mes", "fecha"}
        return pd.DataFrame({c: pd.Series(dtype="datetime64[ns]" if c in tiempo else object)
                             for c in columnas})


def _leer_diaria() -> pd.DataFrame:
    return _leer(FUENTE_DIARIA, ["destino_clave", "subdestino", "fecha", "anio_mes", "pais", "tipo",
                                 "evento", "es_regular", "presencia"])


def _leer_sub() -> pd.DataFrame:
    return _leer(FUENTE_SUB, ["destino_clave", "subdestino", "anio_mes", "tipo", "segmento",
                              "visitantes", "dias_persona"])


def _leer_pron() -> pd.DataFrame:
    return _leer(FUENTE_PRON, ["destino_clave", "subdestino", "tipo", "anio_mes", "estimacion", "lim_inf",
                               "lim_sup", "metodo", "mape_loo", "rmse_loo", "mae_loo", "n_loo",
                               "es_estimacion", "migracion_mejora_a_la_base", "mape_loo_base", "nota"])


def _leer_resumen() -> pd.DataFrame:
    return _leer(FUENTE_RESUMEN, ["tipo", "mape_mediano", "mape_mediano_base_sin_migracion"])


def preparar_diaria(df: pd.DataFrame, f: Filtros) -> pd.DataFrame:
    """Movilidad diaria de Alta Verapaz con los filtros globales (el último mes se incluye completo)."""
    if not serie_completa(f):
        return solo_alta_verapaz(df).iloc[0:0]
    return datos.filtrar_diaria(solo_alta_verapaz(df), f)


def _serie_unica(df: pd.DataFrame) -> None:
    for col in ("subdestino", "tipo"):
        if col in df.columns and df[col].dropna().nunique() > 1:
            raise ValueError(f"Se recibieron varios valores de {col!r}: no se suman subdestinos ni tipos.")


def serie_diaria(df: pd.DataFrame) -> pd.DataFrame:
    """Presencia por fecha de UNA serie (suma de países del mismo día). Índice = fecha.

    Columnas: presencia, evento, es_regular, dow. Días con presencia nula se omiten (hueco, no 0).
    """
    _serie_unica(df)
    if df.empty:
        return pd.DataFrame(columns=["presencia", "evento", "es_regular", "dow"])
    return metricas._presencia_por_fecha(df, con_evento=True)


def eventos_disponibles(df: pd.DataFrame) -> list:
    """Eventos (sin «Regular») presentes en los datos, en orden de primera aparición."""
    if df.empty:
        return []
    d = df.loc[~df["es_regular"].fillna(False).astype(bool) & df["evento"].notna(), ["evento", "fecha"]]
    d = d[d["evento"] != metricas.EVENTO_REGULAR]
    return d.groupby("evento")["fecha"].min().sort_values().index.tolist()


def podar_eventos(actual: Optional[Sequence], disponibles: Sequence) -> list:
    """Conserva de la selección actual solo los eventos que siguen disponibles."""
    return [e for e in (actual or []) if e in disponibles]


# ----------------------------------------------------------------------- utilidades
def _subtitulo(f: Filtros, fuente: str, extra: Optional[str] = None) -> str:
    partes = [theme.subtitulo_periodo(f.mes_ini, f.mes_fin, fuente), f.subdestino, f.tipo, extra]
    return " · ".join(str(p) for p in partes if p)


def _meses_rango(df: pd.DataFrame, f: Filtros) -> pd.DatetimeIndex:
    ini = f.mes_ini if f.mes_ini is not None else (df["anio_mes"].min() if len(df) else None)
    fin = f.mes_fin if f.mes_fin is not None else (df["anio_mes"].max() if len(df) else None)
    if ini is None or fin is None or pd.isna(ini) or pd.isna(fin):
        return pd.DatetimeIndex([])
    return datos.rango_meses(ini, fin)


def _tramos(fechas) -> list:
    """Tramos de días consecutivos [(inicio, fin), ...] de un conjunto de fechas."""
    fechas = pd.DatetimeIndex(sorted(set(fechas)))
    if len(fechas) == 0:
        return []
    cortes = np.where(np.diff(fechas.values) > np.timedelta64(1, "D"))[0]
    inicios = [0, *(cortes + 1)]
    fines = [*cortes, len(fechas) - 1]
    return [(fechas[i], fechas[j]) for i, j in zip(inicios, fines)]


def _rect(fig: go.Figure, ini: pd.Timestamp, fin: pd.Timestamp, color: str) -> None:
    mitad = pd.Timedelta(hours=12)
    fig.add_shape(type="rect", xref="x", yref="paper", y0=0, y1=1, line=dict(width=0), layer="below",
                  x0=(ini - mitad).isoformat(), x1=(fin + mitad).isoformat(), fillcolor=color)


def _anotar_sin_dato_categorias(fig: go.Figure, etiquetas: list, faltan) -> None:
    for etiqueta, falta in zip(etiquetas, faltan):
        if falta:
            fig.add_annotation(x=etiqueta, y=0.5, xref="x", yref="paper", text=theme.ETIQUETA_SIN_DATO,
                               textangle=-90, showarrow=False,
                               font=dict(size=11, color=theme.COLOR_SIN_DATO_TEXTO))


def _base(fig: go.Figure, titulo: str, subtitulo: str, altura: int = 380, **kw) -> go.Figure:
    fig.update_layout(template=theme.PLANTILLA, title=dict(text=theme.titulo_con_subtitulo(titulo, subtitulo)),
                      height=altura, **kw)
    return fig


# ---------------------------------------------------------------- serie diaria
def fig_serie(df: pd.DataFrame, f: Filtros, eventos: Optional[Sequence] = None) -> go.Figure:
    """Presencia diaria; eventos seleccionados sombreados; tramos sin dato en gris (huecos, no ceros)."""
    eventos = list(eventos or [])
    titulo = "Presencia diaria"
    sub = _subtitulo(f, FUENTE_DIARIA, "presencia diaria, no visitantes únicos mensuales")
    if not serie_completa(f) or df.empty:
        return theme.figura_sin_dato(titulo, sub)
    dias = serie_diaria(df)
    if dias.empty:
        return theme.figura_sin_dato(titulo, sub)
    ini = f.mes_ini if f.mes_ini is not None else dias.index.min().to_period("M").to_timestamp()
    fin_mes = f.mes_fin if f.mes_fin is not None else dias.index.max().to_period("M").to_timestamp()
    rango = pd.date_range(ini, fin_mes + pd.DateOffset(months=1) - pd.Timedelta(days=1), freq="D")
    serie = dias["presencia"].reindex(rango)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rango, y=serie.to_numpy(), mode="lines", connectgaps=False,
                             name="Presencia diaria (observado)", line=dict(color=theme.COLOR_OBSERVADO, width=1.8),
                             hovertemplate="%{x|%d %b %Y}<br>Presencia: %{y:,.1f}<extra></extra>"))
    marcados = dias[~dias["es_regular"]]
    if eventos:
        marcados = marcados[marcados["evento"].isin(eventos)]
    if not marcados.empty:
        fig.add_trace(go.Scatter(x=marcados.index, y=marcados["presencia"].to_numpy(), mode="markers",
                                 name="Día de evento", text=marcados["evento"].to_numpy(),
                                 marker=dict(color=theme.CATEGORICOS[3], symbol="diamond", size=8),
                                 hovertemplate="%{x|%d %b %Y}<br>%{text}<br>Presencia: %{y:,.1f}<extra></extra>"))
    for evento in eventos:   # sombreado de cada tramo consecutivo de días del evento
        for t_ini, t_fin in _tramos(dias.index[dias["evento"] == evento]):
            _rect(fig, t_ini, t_fin, COLOR_SOMBREADO_EVENTO)
            fig.add_annotation(x=(t_ini + (t_fin - t_ini) / 2).isoformat(), xref="x", y=1, yref="paper",
                               text=evento, showarrow=False, yanchor="bottom",
                               font=dict(size=10, color=theme.TEXTO_SECUNDARIO))
    for t_ini, t_fin in _tramos(serie.index[serie.isna()]):   # días sin dato
        _rect(fig, t_ini, t_fin, COLOR_SOMBREADO_SIN_DATO)
        if (t_fin - t_ini).days + 1 >= MIN_DIAS_ETIQUETA_SIN_DATO:
            fig.add_annotation(x=(t_ini + (t_fin - t_ini) / 2).isoformat(), xref="x", y=0.5, yref="paper",
                               text=theme.ETIQUETA_SIN_DATO, showarrow=False,
                               font=dict(size=12, color=theme.COLOR_SIN_DATO_TEXTO))
    _base(fig, titulo, sub, yaxis=dict(title=dict(text="Personas presentes por día")),
          xaxis=dict(type="date"), hovermode="x unified")
    return fig


# ------------------------------------------------------------------------- lift
LIFT_COLUMNAS = ["evento", "lift_pct", "media_evento", "media_regular", "n_dias_evento", "n_dias_regular"]


def tabla_lift(df: pd.DataFrame, disponibles: Sequence, seleccion: Sequence) -> pd.DataFrame:
    """Lift de los eventos seleccionados (o de todos los disponibles si no hay selección)."""
    eventos = list(seleccion) if seleccion else list(disponibles)
    filas = []
    for ev in eventos:
        r = metricas.lift_evento(df, ev)
        filas.append(dict(evento=ev, lift_pct=r.lift_pct, media_evento=r.media_evento,
                          media_regular=r.media_regular, n_dias_evento=r.n_dias_evento,
                          n_dias_regular=r.n_dias_regular))
    out = pd.DataFrame(filas, columns=LIFT_COLUMNAS)
    return out.sort_values(["lift_pct", "evento"], ascending=[False, True], na_position="last").reset_index(drop=True)


def _num(valor: float, formato: str = ",.1f") -> str:
    return theme.ETIQUETA_SIN_DATO if pd.isna(valor) else f"{valor:{formato}}"


def render_lift(tabla: pd.DataFrame, f: Filtros, mostrando_todos: bool) -> html.Div:
    """Tabla HTML de lift; los eventos sin días comparables salen como «Sin dato», nunca 0 %."""
    titulo = html.H3("Lift por evento", className="h6")
    sub = html.P(_subtitulo(f, FUENTE_DIARIA), className="small", style={"color": theme.TEXTO_SECUNDARIO})
    if tabla.empty:
        return html.Div([titulo, sub, dbc.Alert("No hay días de evento en el período y la serie elegidos: "
                                                f"{theme.ETIQUETA_SIN_DATO}.", color="light")])
    estilo_sin = {"color": theme.COLOR_SIN_DATO_TEXTO, "fontStyle": "italic"}
    filas = []
    for r in tabla.itertuples():
        sin = pd.isna(r.lift_pct)
        filas.append(html.Tr([
            html.Td(r.evento),
            html.Td(theme.ETIQUETA_SIN_DATO if sin else f"{r.lift_pct:+.1f} %", style=estilo_sin if sin else None),
            html.Td(_num(r.media_evento)),
            html.Td(_num(r.media_regular)),
            html.Td(f"{r.n_dias_evento} / {r.n_dias_regular}"),
        ]))
    cabecera = html.Thead(html.Tr([html.Th(t) for t in (
        "Evento", "Lift", "Presencia media del evento", "Media de días regulares comparables",
        "Días usados (evento / regulares)")]))
    nota = ("Lift = (media del evento ÷ media de días regulares del mismo día de la semana − 1) × 100. "
            "Es presencia diaria; con pocos días el valor es muy variable. ")
    if mostrando_todos:
        nota += "Sin eventos seleccionados se muestran todos los disponibles."
    return html.Div([titulo, sub,
                     dbc.Table([cabecera, html.Tbody(filas)], size="sm", hover=True, responsive=True),
                     html.P(nota, className="small", style={"color": theme.TEXTO_SECUNDARIO})])


# ----------------------------------------------------- patrón semanal y mapa de calor
def patron_modo(df: pd.DataFrame, modo: str, eventos: Optional[Sequence]) -> Optional[pd.DataFrame]:
    """Patrón semanal según el modo. ``None`` si el modo «eventos» no tiene eventos seleccionados."""
    if modo == "eventos":
        if not eventos:
            return None
        return metricas.patron_semanal(df[df["evento"].isin(eventos)])
    return metricas.patron_semanal(df, solo_regulares=(modo == "regulares"))


def fig_semanal(df: pd.DataFrame, f: Filtros, modo: str = "regulares",
                eventos: Optional[Sequence] = None) -> go.Figure:
    """Barras lunes–domingo (fin de semana resaltado) con presencia media y número de días."""
    titulo = "Patrón semanal de presencia"
    sub = _subtitulo(f, FUENTE_DIARIA, MODOS.get(modo, modo).lower())
    if not serie_completa(f) or df.empty:
        return theme.figura_sin_dato(titulo, sub)
    patron = patron_modo(df, modo, eventos)
    if patron is None:
        return theme.figura_sin_dato(titulo, sub, mensaje="Seleccione al menos un evento")
    if patron["presencia_media"].isna().all():
        return theme.figura_sin_dato(titulo, sub)
    fin_semana = patron["dia_semana_num"] >= 5
    fig = go.Figure()
    for nombre, mascara, color in (("Lunes a viernes", ~fin_semana, theme.SECUENCIAL[3]),
                                   ("Sábado y domingo", fin_semana, theme.COLOR_OBSERVADO)):
        y = patron["presencia_media"].where(mascara)
        fig.add_bar(x=DIAS_ETIQUETA, y=y.to_numpy(), name=nombre, marker_color=color,
                    customdata=patron["n_dias"].to_numpy(),
                    text=[f"{n} d" if m and n else "" for n, m in zip(patron["n_dias"], mascara)],
                    textposition="outside",
                    hovertemplate="%{x}<br>Presencia media: %{y:,.1f}<br>Días observados: %{customdata}<extra></extra>")
    _base(fig, titulo, sub, barmode="overlay", yaxis=dict(title=dict(text="Presencia media por día")))
    fig.update_xaxes(categoryorder="array", categoryarray=DIAS_ETIQUETA)
    _anotar_sin_dato_categorias(fig, DIAS_ETIQUETA, patron["presencia_media"].isna().to_numpy())
    return fig


def matriz_dia_mes(df: pd.DataFrame, meses: pd.DatetimeIndex, modo: str, eventos: Optional[Sequence]):
    """(z, n): presencia media y días observados por día de la semana (filas) y mes (columnas).

    Se calcula con ``patron_semanal`` mes a mes; sin dato -> NaN (nunca 0). ``None`` si el modo
    «eventos» no tiene eventos seleccionados.
    """
    if modo == "eventos" and not eventos:
        return None
    z = np.full((7, len(meses)), np.nan)
    n = np.zeros((7, len(meses)), dtype=int)
    for j, mes in enumerate(meses):
        patron = patron_modo(df[df["anio_mes"] == mes], modo, eventos)
        z[:, j] = patron["presencia_media"].to_numpy()
        n[:, j] = patron["n_dias"].to_numpy()
    return z, n


def fig_heatmap(df: pd.DataFrame, f: Filtros, modo: str = "regulares",
                eventos: Optional[Sequence] = None) -> go.Figure:
    """Mapa de calor de presencia media: día de la semana × mes (solo movilidad diaria)."""
    titulo = "Presencia media por día de la semana y mes"
    sub = _subtitulo(f, FUENTE_DIARIA, MODOS.get(modo, modo).lower())
    if not serie_completa(f) or df.empty:
        return theme.figura_sin_dato(titulo, sub)
    meses = _meses_rango(df, f)
    resultado = matriz_dia_mes(df, meses, modo, eventos)
    if resultado is None:
        return theme.figura_sin_dato(titulo, sub, mensaje="Seleccione al menos un evento")
    z, n = resultado
    if z.size == 0 or np.isnan(z).all():
        return theme.figura_sin_dato(titulo, sub)
    etiquetas = [theme.etiqueta_mes(m) for m in meses]
    fig = go.Figure(go.Heatmap(
        z=z, x=etiquetas, y=DIAS_ETIQUETA, customdata=n, colorscale=theme.ESCALA_VOLUMEN, hoverongaps=False,
        xgap=1, ygap=1, colorbar=dict(title=dict(text="Presencia media")),
        hovertemplate="%{y} · %{x}<br>Presencia media: %{z:,.1f}<br>Días observados: %{customdata}<extra></extra>"))
    _base(fig, titulo, sub, plot_bgcolor=COLOR_HEATMAP_SIN_DATO)   # celdas sin dato = gris
    fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=DIAS_ETIQUETA)
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=etiquetas)
    _anotar_sin_dato_categorias(fig, etiquetas, np.isnan(z).all(axis=0))
    return fig


# ------------------------------------------------------------------- pronóstico
def datos_pronostico(pron: pd.DataFrame, f: Filtros) -> pd.DataFrame:
    """Estimaciones de P1 de UNA serie (subdestino × tipo), solo ene y feb 2026.

    Ignora el rango de meses global. No suma subdestinos ni mezcla tipos.
    """
    base = solo_alta_verapaz(pron)
    if not serie_completa(f):
        return base.iloc[0:0]
    est = datos.filtrar_mensual(base, replace(f, mes_ini=None, mes_fin=None))
    est = est[est["es_estimacion"].fillna(False).astype(bool) & est["anio_mes"].isin(MESES_PRONOSTICO)]
    return est.sort_values("anio_mes").reset_index(drop=True)


def fig_pronostico(obs: pd.Series, est: pd.DataFrame, f: Filtros) -> go.Figure:
    """Serie mensual observada + estimación ene–feb 2026 (color exclusivo, punteada, con banda)."""
    titulo = "Visitantes mensuales: observado y estimación"
    if not serie_completa(f) or (len(obs) == 0 and est.empty):
        return theme.figura_sin_dato(titulo, _subtitulo(replace(f, mes_ini=None, mes_fin=None), FUENTE_SUB))
    todos = list(obs.index) + list(est["anio_mes"])
    meses = datos.rango_meses(min(todos), max(todos))
    etiquetas = [theme.etiqueta_mes(m) for m in meses]
    est_txt = ("Estimación: " + " y ".join(theme.etiqueta_mes(m) for m in est["anio_mes"])
               if not est.empty else "sin estimación disponible")
    sub = " · ".join([theme.subtitulo_periodo(meses[0], meses[-1], f"{FUENTE_SUB} + {FUENTE_PRON}"),
                      str(f.subdestino), str(f.tipo), est_txt])

    obs_y = obs.reindex(meses).to_numpy(dtype=float)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=etiquetas, y=obs_y, mode="lines+markers", connectgaps=False, name="Observado",
                             line=dict(color=theme.COLOR_OBSERVADO, width=2.5),
                             hovertemplate="%{x}<br>Observado: %{y:,.0f}<extra></extra>"))
    est_y = np.full(len(meses), np.nan)
    if not est.empty:
        e = est.set_index("anio_mes").reindex(meses)
        est_y = e["estimacion"].to_numpy(dtype=float)
        estilo = theme.estilo_estimacion()
        fig.add_trace(go.Scatter(x=etiquetas, y=e["lim_sup"].to_numpy(dtype=float), mode="lines",
                                 line=dict(width=0), showlegend=False, hoverinfo="skip", connectgaps=False))
        fig.add_trace(go.Scatter(x=etiquetas, y=e["lim_inf"].to_numpy(dtype=float), mode="lines",
                                 line=dict(width=0), fill="tonexty", fillcolor=estilo["fillcolor"],
                                 name="Intervalo ≈ ±1.96×RMSE (orientativo)", hoverinfo="skip",
                                 connectgaps=False))
        fig.add_trace(go.Scatter(
            x=etiquetas, y=est_y, mode="lines+markers+text", connectgaps=False,
            name=theme.rotulo_estimacion(), line=estilo["line"],
            marker=dict(color=theme.COLOR_ESTIMACION, symbol="diamond", size=10),
            text=[theme.rotulo_estimacion() if not np.isnan(v) else "" for v in est_y],
            textposition="top center", textfont=dict(color=theme.COLOR_ESTIMACION_TEXTO),
            customdata=np.column_stack([e["lim_inf"].to_numpy(dtype=float), e["lim_sup"].to_numpy(dtype=float)]),
            hovertemplate="%{x}<br>Estimación: %{y:,.0f}<br>Intervalo: %{customdata[0]:,.0f} – "
                          "%{customdata[1]:,.0f}<extra></extra>"))
    _base(fig, titulo, sub, yaxis=dict(rangemode="tozero", title=dict(text="Visitantes únicos del mes")))
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=etiquetas)
    _anotar_sin_dato_categorias(fig, etiquetas, np.isnan(obs_y) & np.isnan(est_y))
    return fig


def tarjetas_error(est: pd.DataFrame) -> dbc.Row:
    """MAPE, RMSE y MAE (leave-one-out) de la serie y variante mostradas."""
    sin = theme.ETIQUETA_SIN_DATO
    if est.empty:
        valores, detalle = [sin, sin, sin], "Sin estimación disponible"
    else:
        r = est.iloc[0]
        valores = [f"{r['mape_loo']:.1f} %", f"{r['rmse_loo']:,.0f} visitantes", f"{r['mae_loo']:,.0f} visitantes"]
        detalle = f"Validación leave-one-out · {int(r['n_loo'])} meses · variante {r['metodo']}"
    return dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([html.Div(nombre, className="small fw-semibold"),
                                       html.Div(valor, className="h4 mb-0"),
                                       html.Div(detalle, className="small",
                                                style={"color": theme.TEXTO_SECUNDARIO})]),
                         className="h-100 shadow-sm"), xs=12, md=4, className="mb-2")
        for nombre, valor in zip(("MAPE", "RMSE", "MAE"), valores)])


def aviso_pronostico(est: pd.DataFrame, resumen: pd.DataFrame, f: Filtros) -> list:
    """Advertencias metodológicas del panel de pronóstico."""
    if est.empty:
        return [dbc.Alert(f"Sin estimación disponible para esta serie ({theme.ETIQUETA_SIN_DATO}).", color="light")]
    r = est.iloc[0]
    nota = r["nota"] if "nota" in est.columns and pd.notna(r["nota"]) else ""
    avisos = [dbc.Alert([html.Strong(f"{theme.rotulo_estimacion()} (no observada). "),
                         f"Método: variante «{r['metodo']}» (factor de reparto × entradas migratorias del mes). {nota}"],
                        color="light", className="small")]
    if f.tipo == "nacional" and not bool(r["migracion_mejora_a_la_base"]):
        fila = resumen[resumen["tipo"] == "nacional"] if "tipo" in resumen.columns else resumen.iloc[0:0]
        if not fila.empty:
            comparacion = (f"MAPE mediano entre subdestinos: {fila.iloc[0]['mape_mediano']:.1f} % con migración "
                           f"frente a {fila.iloc[0]['mape_mediano_base_sin_migracion']:.1f} % de la línea base")
        else:
            comparacion = (f"MAPE de esta serie: {r['mape_loo']:.1f} % con migración frente a "
                           f"{r['mape_loo_base']:.1f} % de la línea base")
        avisos.append(dbc.Alert(
            "Nacionales: la migración mide el ingreso al país y no explica a los visitantes nacionales; "
            f"la línea base sin migración obtuvo menor error ({comparacion}). Tome la estimación como orientativa.",
            color="warning", className="small"))
    if r["mape_loo"] > UMBRAL_MAPE_ALTO:
        avisos.append(dbc.Alert(f"Error alto: MAPE de esta serie {r['mape_loo']:.1f} % (> {UMBRAL_MAPE_ALTO:.0f} %). "
                                "Interprete la estimación con cautela.", color="warning", className="small"))
    return avisos


# ------------------------------------------------------------------------ layout
def _leyenda() -> html.Div:
    def chip(color, texto):
        return html.Span([html.Span("■ ", style={"color": color}), texto], className="me-3")
    return html.Div([chip(theme.COLOR_OBSERVADO, "Observado"), chip(theme.COLOR_ESTIMACION, "Estimación"),
                     chip(theme.COLOR_SIN_DATO, "Sin dato")],
                    className="small mb-2", style={"color": theme.TEXTO_SECUNDARIO})


def _grafico(id_: str) -> dbc.Card:
    return dbc.Card(dbc.CardBody(dcc.Graph(id=id_, config=_CONFIG_GRAFICO)), className="h-100 shadow-sm")


def layout():
    """Layout estático del módulo; los callbacks lo llenan según el filtro global."""
    return html.Div([
        html.H2("Dinámica temporal, eventos y pronóstico", className="h4 mt-3"),
        html.P("Presencia diaria, efecto de eventos, patrón semanal y estimación de ene–feb 2026. La presencia "
               "diaria no equivale a los visitantes únicos mensuales y no se suma para obtenerlos.",
               style={"color": theme.TEXTO_SECUNDARIO}),
        _leyenda(),
        dbc.Card(dbc.CardBody(dbc.Row([
            dbc.Col([html.Label("Eventos", htmlFor=ID_EVENTOS, className="fw-semibold"),
                     dcc.Dropdown(id=ID_EVENTOS, multi=True, options=[], value=[],
                                  placeholder="Seleccione uno o varios eventos")], xs=12, lg=7,
                    className="mb-3 mb-lg-0"),
            dbc.Col([html.Label("Días incluidos en patrón semanal y mapa de calor", className="fw-semibold"),
                     dbc.RadioItems(id=ID_MODO, value="regulares",
                                    options=[{"label": v, "value": k} for k, v in MODOS.items()])],
                    xs=12, lg=5),
        ])), className="mb-3 shadow-sm"),
        dbc.Row([dbc.Col(_grafico(ID_G_SERIE), xs=12, className="mb-3")]),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody(html.Div(id=ID_LIFT)), className="h-100 shadow-sm"),
                    xs=12, lg=5, className="mb-3"),
            dbc.Col(_grafico(ID_G_SEMANAL), xs=12, lg=7, className="mb-3"),
        ]),
        dbc.Row([dbc.Col(_grafico(ID_G_HEATMAP), xs=12, className="mb-3")]),
        html.H3("Pronóstico enero–febrero 2026", className="h5 mt-2"),
        dbc.Row([dbc.Col([_grafico(ID_G_PRON), html.Div(id=ID_PRON_METRICAS, className="mt-3"),
                          html.Div(id=ID_PRON_AVISO)], xs=12, className="mb-3")]),
    ])


# --------------------------------------------------------------------- callbacks
def registrar_callbacks(app) -> None:
    """Registra los callbacks del módulo (solo leen ``store-filtros``)."""

    @app.callback(
        Output(ID_EVENTOS, "options"),
        Output(ID_EVENTOS, "value"),
        Input(ID_STORE_FILTROS, "data"),
        State(ID_EVENTOS, "value"),
    )
    def _eventos(estado, actual):
        f = Filtros.desde_dict(estado)
        disponibles = eventos_disponibles(preparar_diaria(_leer_diaria(), f))
        return [{"label": e, "value": e} for e in disponibles], podar_eventos(actual, disponibles)

    @app.callback(
        Output(ID_G_SERIE, "figure"),
        Output(ID_LIFT, "children"),
        Input(ID_STORE_FILTROS, "data"),
        Input(ID_EVENTOS, "value"),
    )
    def _serie_y_lift(estado, eventos):
        f = Filtros.desde_dict(estado)
        df = preparar_diaria(_leer_diaria(), f)
        disponibles = eventos_disponibles(df)
        seleccion = podar_eventos(eventos, disponibles)
        tabla = tabla_lift(df, disponibles, seleccion)
        return fig_serie(df, f, seleccion), render_lift(tabla, f, mostrando_todos=not seleccion)

    @app.callback(
        Output(ID_G_SEMANAL, "figure"),
        Output(ID_G_HEATMAP, "figure"),
        Input(ID_STORE_FILTROS, "data"),
        Input(ID_EVENTOS, "value"),
        Input(ID_MODO, "value"),
    )
    def _semanal_y_heatmap(estado, eventos, modo):
        f = Filtros.desde_dict(estado)
        df = preparar_diaria(_leer_diaria(), f)
        seleccion = podar_eventos(eventos, eventos_disponibles(df))
        return fig_semanal(df, f, modo, seleccion), fig_heatmap(df, f, modo, seleccion)

    @app.callback(
        Output(ID_G_PRON, "figure"),
        Output(ID_PRON_METRICAS, "children"),
        Output(ID_PRON_AVISO, "children"),
        Input(ID_STORE_FILTROS, "data"),
    )
    def _pronostico(estado):
        f = Filtros.desde_dict(estado)
        est = datos_pronostico(_leer_pron(), f)
        sin_rango = replace(f, mes_ini=None, mes_fin=None)
        obs = (visitantes_mensuales(preparar(_leer_sub(), sin_rango)) if serie_completa(f)
               else pd.Series(dtype=float))
        return (fig_pronostico(obs, est, f), tarjetas_error(est),
                aviso_pronostico(est, _leer_resumen(), f))
