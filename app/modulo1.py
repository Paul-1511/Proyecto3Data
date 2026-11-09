"""Módulo 1 — Demanda y mercados (Cobán y Alta Verapaz).

Integración (patrón de app/main.py): ``layout()`` y ``registrar_callbacks(app)``. El módulo solo
LEE el filtro global ``store-filtros`` (rango de meses, tipo, subdestino). Todos sus IDs llevan
el prefijo ``m1-``.

Qué responde a qué
* Tarjetas KPI, «Turista vs. excursionista» y «Estadía por mes»: siguen el filtro global
  (rango de meses, tipo y subdestino).
* Ranking de mercados extranjeros y panel de nacionales: cada uno muestra SU universo
  (extranjero / nacional) para el subdestino y los meses del filtro; no se mezclan ni se suman.
* Clic en una barra del ranking -> ``m1-seleccion`` -> «Turista vs. excursionista» y «Estadía por
  mes» pasan a mostrar solo ese mercado (si el tipo global es extranjero). La selección se borra
  al cambiar cualquier filtro global o con el botón «Quitar selección».

Decisiones metodológicas
* Solo ``destino_clave == 'alta_verapaz'`` y sus tres subdestinos; tipos extranjero/nacional.
* Los cálculos viven en ``app/utils/metricas.py``. Aquí solo hay preparación de datos y gráficos.
  «Días-persona promedio mensual» reutiliza ``promedio_mensual_visitantes`` pasando días-persona
  como columna de valor (misma regla: meses con ambos segmentos, media de meses, sin sumar).
* Ranking de mercados: PROMEDIO mensual de cada mercado sobre los meses en que aparece con dato
  (se informa ``n_meses``). Una fila ausente no se interpreta como cero. ``sin_dato`` y países
  nulos se excluyen. Nunca se suman visitantes entre meses.
* Nacionales: la fuente no trae una desagregación fiable de nacionalidades nacionales, por lo que
  se muestran como un solo universo (serie mensual del subdestino).
* Ausencia de dato: meses sin cobertura aparecen con la anotación «Sin dato», nunca como 0.
* Sin descargas ni tablas de microdatos.
"""
from __future__ import annotations

from dataclasses import replace
from typing import NamedTuple, Optional

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, ctx, dcc, html

from app import theme
from app.theme import ID_STORE_FILTROS
from app.utils import cobertura, datos, metricas
from app.utils.datos import Filtros

DESTINO_CLAVE = "alta_verapaz"
SUBDESTINOS_AV = ("Coban", "Cuevas De Candelaria", "Lanquin")
TIPOS = ("extranjero", "nacional")
N_TOP = 10

FUENTE_SUB = "movilidad_subdestino_mes"
FUENTE_PAIS = "movilidad_mensual"

ID_SELECCION = "m1-seleccion"
ID_LIMPIAR = "m1-limpiar"
ID_SELECCION_TEXTO = "m1-seleccion-texto"
ID_G_SEGMENTOS = "m1-grafico-segmentos"
ID_G_ESTADIA = "m1-grafico-estadia"
ID_G_RANKING = "m1-grafico-ranking"
ID_G_NACIONALES = "m1-grafico-nacionales"
IDS_KPI = ("m1-kpi-visitantes", "m1-kpi-diaspersona", "m1-kpi-estadia")

_CONFIG_GRAFICO = {"displayModeBar": False}   # sin barra de herramientas ni exportaciones
_SIN_DATO_PAIS = {"sin_dato", "sin dato", "sindato"}


# ------------------------------------------------------------------------ datos
def _leer(nombre: str, columnas: list) -> pd.DataFrame:
    """Lee un parquet; si no existe devuelve una tabla vacía (la UI mostrará «Sin dato»)."""
    try:
        return datos.cargar(nombre)
    except FileNotFoundError:
        return pd.DataFrame({c: pd.Series(dtype="datetime64[ns]" if c == "anio_mes" else object)
                             for c in columnas})


def _leer_sub() -> pd.DataFrame:
    # P3: solo meses con cobertura de movilidad mensual (los demás quedan «Sin dato»).
    return cobertura.solo_con_cobertura(_leer(FUENTE_SUB, ["destino_clave", "subdestino", "anio_mes", "tipo",
                                                           "segmento", "visitantes", "dias_persona"]),
                                        "movilidad_mensual")


def _leer_pais() -> pd.DataFrame:
    return cobertura.solo_con_cobertura(_leer(FUENTE_PAIS, ["destino_clave", "subdestino", "anio_mes", "pais",
                                                            "tipo", "segmento", "visitantes", "dias_persona"]),
                                        "movilidad_mensual")


def solo_alta_verapaz(df: pd.DataFrame) -> pd.DataFrame:
    """Filas de Alta Verapaz, de sus tres subdestinos y de tipo extranjero/nacional (copia)."""
    if "destino_clave" not in df.columns:
        raise KeyError("La tabla debe tener la columna 'destino_clave'.")
    mascara = (df["destino_clave"] == DESTINO_CLAVE) & df["subdestino"].isin(SUBDESTINOS_AV) \
        & df["tipo"].isin(TIPOS)
    return df.loc[mascara].copy()


def serie_completa(f: Filtros) -> bool:
    """True si hay UN subdestino y UN tipo (condición para no sumar territorios ni tipos)."""
    return f.subdestino is not None and f.tipo is not None


def preparar(df: pd.DataFrame, f: Filtros, tipo: Optional[str] = None) -> pd.DataFrame:
    """Alta Verapaz + filtros globales. ``tipo`` reemplaza el tipo del filtro (p. ej. para rankings)."""
    if tipo is not None:
        f = replace(f, tipo=tipo)
    return datos.filtrar_mensual(solo_alta_verapaz(df), f)


def mercado_efectivo(seleccion: Optional[str], f: Filtros) -> Optional[str]:
    """La selección de mercado solo aplica con tipo global extranjero."""
    return seleccion if (seleccion and f.tipo == "extranjero") else None


def serie_para_graficos(df_sub: pd.DataFrame, df_pais: pd.DataFrame, f: Filtros,
                        mercado: Optional[str] = None) -> pd.DataFrame:
    """Datos de los gráficos de segmento/estadía: subdestino-tipo, o un mercado si hay selección."""
    if mercado is None:
        return preparar(df_sub, f)
    base = preparar(df_pais, f)
    return base[base["pais"] == mercado].copy()


def _exigir_serie_unica(df: pd.DataFrame) -> None:
    for col in ("subdestino", "tipo"):
        if col not in df.columns:
            raise KeyError(f"Falta la columna {col!r}.")
        if df[col].dropna().nunique() > 1:
            raise ValueError(f"Se recibieron varios valores de {col!r}: no se suman subdestinos ni tipos.")


def _suma_estricta(s: pd.Series) -> float:
    return float(s.sum(min_count=len(s))) if len(s) else np.nan


def visitantes_mensuales(df: pd.DataFrame) -> pd.Series:
    """Visitantes por mes (suma de los dos segmentos del mes), solo meses con ambos segmentos."""
    _exigir_serie_unica(df)
    if df.empty:
        return pd.Series(dtype=float)
    tabla = df.groupby(["anio_mes", "segmento"])["visitantes"].agg(_suma_estricta).unstack("segmento")
    return tabla.reindex(columns=list(metricas.SEGMENTOS)).dropna().sum(axis=1)


def _es_sin_dato(pais) -> bool:
    return pd.isna(pais) or str(pais).strip().lower() in _SIN_DATO_PAIS


def ranking_mercados(df: pd.DataFrame, n: int = N_TOP) -> pd.DataFrame:
    """Top ``n`` mercados por visitantes PROMEDIO MENSUAL.

    ``df`` es movilidad_mensual de un subdestino y un tipo. Para cada mercado se suman los
    segmentos dentro de cada mes (suma estricta: un nulo invalida ese mes) y se promedian los
    meses en que el mercado tiene dato. Devuelve ``pais, promedio_mensual, n_meses``.
    No suma entre meses; excluye ``sin_dato`` y países nulos.
    """
    _exigir_serie_unica(df)
    columnas = ["pais", "promedio_mensual", "n_meses"]
    base = df[["pais", "anio_mes", "visitantes"]]
    base = base[np.array([not _es_sin_dato(p) for p in base["pais"]], dtype=bool)]
    if base.empty:
        return pd.DataFrame(columns=columnas)
    por_mes = base.groupby(["pais", "anio_mes"])["visitantes"].agg(_suma_estricta).dropna()
    if por_mes.empty:
        return pd.DataFrame(columns=columnas)
    r = por_mes.groupby(level="pais").agg(["mean", "count"]).reset_index()
    r.columns = columnas
    r["n_meses"] = r["n_meses"].astype(int)
    return r.sort_values(["promedio_mensual", "pais"], ascending=[False, True]).head(n).reset_index(drop=True)


def ranking_extranjeros(df_pais: pd.DataFrame, f: Filtros, n: int = N_TOP) -> pd.DataFrame:
    """Ranking de mercados EXTRANJEROS del subdestino y meses del filtro (ignora el tipo global)."""
    if f.subdestino is None:
        return pd.DataFrame(columns=["pais", "promedio_mensual", "n_meses"])
    return ranking_mercados(preparar(df_pais, f, tipo="extranjero"), n)


# ------------------------------------------------------------------ interacción
def mercado_desde_click(click_data) -> Optional[str]:
    """Nombre del mercado de una barra clicada (``customdata[0]`` o, si falta, el eje y)."""
    try:
        punto = click_data["points"][0]
        cd = punto.get("customdata")
        if cd:
            return str(cd[0])
        return str(punto["y"]) if punto.get("y") else None
    except (TypeError, KeyError, IndexError):
        return None


def seleccion_desde_evento(disparador, click_data) -> Optional[str]:
    """Nueva selección: el clic en el ranking fija el mercado; cualquier otro disparador la borra."""
    return mercado_desde_click(click_data) if disparador == ID_G_RANKING else None


# -------------------------------------------------------------------------- KPI
class Kpi(NamedTuple):
    valor: str
    detalle: str


def _kpi(valor: float, n_meses: int, periodo: str, formato: str, unidad: str = "") -> Kpi:
    if n_meses == 0 or pd.isna(valor):
        return Kpi(theme.ETIQUETA_SIN_DATO, f"0 meses observados · {periodo}")
    return Kpi(f"{valor:{formato}}{unidad}", f"{n_meses} meses observados · {periodo}")


def tarjetas_kpi(df: pd.DataFrame, f: Filtros) -> list:
    """Los tres KPI (visitantes/mes, días-persona/mes, estadía) a partir de datos ya filtrados."""
    periodo = theme.subtitulo_periodo(f.mes_ini, f.mes_fin, FUENTE_SUB)
    if not serie_completa(f) or df.empty:
        return [Kpi(theme.ETIQUETA_SIN_DATO, f"0 meses observados · {periodo}")] * 3
    vis = metricas.promedio_mensual_visitantes(df)
    dias = metricas.promedio_mensual_visitantes(df.assign(visitantes=df["dias_persona"]))
    estadia = metricas.estadia_ponderada(df)
    solo_mas = df[(df["segmento"] == metricas.SEG_MAS_1_DIA) & df["dias_persona"].notna()
                  & df["visitantes"].notna()]
    return [
        _kpi(vis.promedio, vis.n_meses, periodo, ",.0f"),
        _kpi(dias.promedio, dias.n_meses, periodo, ",.0f"),
        _kpi(estadia, int(solo_mas["anio_mes"].nunique()), periodo, ".2f", " días"),
    ]


# ---------------------------------------------------------------------- gráficos
def _subtitulo(f: Filtros, fuente: str, tipo: Optional[str] = None, extra: Optional[str] = None) -> str:
    partes = [theme.subtitulo_periodo(f.mes_ini, f.mes_fin, fuente), f.subdestino, tipo or f.tipo, extra]
    return " · ".join(str(p) for p in partes if p)


def _meses_rango(df: pd.DataFrame, f: Filtros) -> pd.DatetimeIndex:
    ini = f.mes_ini if f.mes_ini is not None else (df["anio_mes"].min() if len(df) else None)
    fin = f.mes_fin if f.mes_fin is not None else (df["anio_mes"].max() if len(df) else None)
    if ini is None or fin is None or pd.isna(ini) or pd.isna(fin):
        return pd.DatetimeIndex([])
    return datos.rango_meses(ini, fin)


def _anotar_sin_dato(fig: go.Figure, etiquetas: list, faltan) -> None:
    """Rotula «Sin dato» sobre los meses sin cobertura (el eje conserva el mes, sin barra ni punto)."""
    for etiqueta, falta in zip(etiquetas, faltan):
        if falta:
            fig.add_annotation(x=etiqueta, y=0.5, xref="x", yref="paper", text=theme.ETIQUETA_SIN_DATO,
                               textangle=-90, showarrow=False,
                               font=dict(size=11, color=theme.COLOR_SIN_DATO_TEXTO))


def _eje_meses(fig: go.Figure, etiquetas: list) -> None:
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=etiquetas)


def _base(fig: go.Figure, titulo: str, subtitulo: str, **kw) -> go.Figure:
    fig.update_layout(template=theme.PLANTILLA, title=dict(text=theme.titulo_con_subtitulo(titulo, subtitulo)),
                      height=360, **kw)
    return fig


def fig_segmentos(df: pd.DataFrame, f: Filtros, mercado: Optional[str] = None) -> go.Figure:
    """Barras apiladas 100 %: proporción mensual de más / menos de 1 día (sin totales de período)."""
    titulo = "Turista vs. excursionista por mes (más / menos de 1 día)"
    sub = _subtitulo(f, FUENTE_PAIS if mercado else FUENTE_SUB, extra=f"Mercado: {mercado}" if mercado else None)
    if not serie_completa(f) or df.empty:
        return theme.figura_sin_dato(titulo, sub)
    meses = _meses_rango(df, f)
    props = datos.reindexar_meses(metricas.proporcion_turista_excursionista(df), meses)
    cols = ["prop_mas_de_1_dia", "prop_menos_de_1_dia"]
    if props[cols].isna().all().all():
        return theme.figura_sin_dato(titulo, sub)
    etiquetas = [theme.etiqueta_mes(m) for m in meses]
    fig = go.Figure()
    for col, nombre, color in (("prop_mas_de_1_dia", "Más de 1 día", theme.COLOR_OBSERVADO),
                               ("prop_menos_de_1_dia", "Menos de 1 día", theme.CATEGORICOS[2])):
        fig.add_bar(x=etiquetas, y=props[col] * 100, name=nombre, marker_color=color,
                    hovertemplate="%{x}<br>" + nombre + ": %{y:.1f} %<extra></extra>")
    _base(fig, titulo, sub, barmode="stack",
          yaxis=dict(range=[0, 100], ticksuffix=" %", title=dict(text="% de visitantes del mes")))
    _eje_meses(fig, etiquetas)
    _anotar_sin_dato(fig, etiquetas, props[cols].isna().all(axis=1))
    return fig


def fig_estadia(df: pd.DataFrame, f: Filtros, mercado: Optional[str] = None) -> go.Figure:
    """Estadía media ponderada de cada mes (solo «más de 1 día»); meses sin dato quedan en hueco."""
    titulo = "Estadía media ponderada por mes (más de 1 día)"
    sub = _subtitulo(f, FUENTE_PAIS if mercado else FUENTE_SUB, extra=f"Mercado: {mercado}" if mercado else None)
    if not serie_completa(f) or df.empty:
        return theme.figura_sin_dato(titulo, sub)
    meses = _meses_rango(df, f)
    valores = [metricas.estadia_ponderada(df[df["anio_mes"] == m]) for m in meses]
    if not len(valores) or all(pd.isna(v) for v in valores):
        return theme.figura_sin_dato(titulo, sub)
    etiquetas = [theme.etiqueta_mes(m) for m in meses]
    fig = go.Figure(go.Scatter(x=etiquetas, y=valores, mode="lines+markers", connectgaps=False,
                               line=dict(color=theme.COLOR_OBSERVADO, width=2.5), name="Estadía media",
                               hovertemplate="%{x}<br>%{y:.2f} días<extra></extra>"))
    _base(fig, titulo, sub, showlegend=False,
          yaxis=dict(rangemode="tozero", title=dict(text="Días (Σ días-persona ÷ Σ visitantes)")))
    _eje_meses(fig, etiquetas)
    _anotar_sin_dato(fig, etiquetas, [pd.isna(v) for v in valores])
    return fig


def fig_ranking(rank: pd.DataFrame, f: Filtros, seleccionado: Optional[str] = None) -> go.Figure:
    """Barras horizontales del top de mercados extranjeros (promedio mensual)."""
    titulo = f"Top {N_TOP} mercados emisores extranjeros"
    sub = _subtitulo(f, FUENTE_PAIS, tipo="extranjero", extra="promedio mensual de los meses con dato")
    if rank.empty:
        return theme.figura_sin_dato(titulo, sub)
    if seleccionado:
        colores = [theme.COLOR_OBSERVADO if p == seleccionado else theme.SECUENCIAL[3] for p in rank["pais"]]
    else:
        colores = theme.COLOR_OBSERVADO
    fig = go.Figure(go.Bar(
        x=rank["promedio_mensual"], y=rank["pais"], orientation="h", marker_color=colores,
        customdata=[[p, int(n)] for p, n in zip(rank["pais"], rank["n_meses"])],
        hovertemplate="%{y}<br>Promedio mensual: %{x:,.0f}<br>Meses con dato: %{customdata[1]}<extra></extra>"))
    _base(fig, titulo, sub, showlegend=False, clickmode="event",
          xaxis=dict(title=dict(text="Visitantes únicos, promedio mensual")))
    fig.update_yaxes(autorange="reversed")
    return fig


def fig_nacionales(df: pd.DataFrame, f: Filtros) -> go.Figure:
    """Visitantes nacionales por mes del subdestino (universo separado; sin desagregar por origen)."""
    titulo = "Visitantes nacionales por mes"
    if f.subdestino is None or df.empty:
        return theme.figura_sin_dato(titulo, _subtitulo(f, FUENTE_SUB, tipo="nacional"))
    prom = metricas.promedio_mensual_visitantes(df)
    extra = (f"promedio mensual {prom.promedio:,.0f} ({prom.n_meses} meses)" if prom.n_meses else None)
    sub = _subtitulo(f, FUENTE_SUB, tipo="nacional", extra=extra)
    mensual = visitantes_mensuales(df)
    meses = _meses_rango(df, f)
    if len(mensual) == 0 or len(meses) == 0:
        return theme.figura_sin_dato(titulo, sub)
    serie = mensual.reindex(meses)
    etiquetas = [theme.etiqueta_mes(m) for m in meses]
    fig = go.Figure(go.Bar(x=etiquetas, y=serie.to_numpy(), marker_color=theme.CATEGORICOS[1],
                           name="Nacionales", hovertemplate="%{x}<br>%{y:,.0f} visitantes<extra></extra>"))
    _base(fig, titulo, sub, showlegend=False, yaxis=dict(title=dict(text="Visitantes únicos del mes")))
    _eje_meses(fig, etiquetas)
    _anotar_sin_dato(fig, etiquetas, serie.isna().to_numpy())
    return fig


def texto_seleccion(seleccion: Optional[str], f: Filtros) -> str:
    """Mensaje bajo el ranking sobre el estado de la selección."""
    if seleccion and f.tipo != "extranjero":
        return (f"Mercado seleccionado: {seleccion}. El filtro global es «{f.tipo}»: "
                "la selección no se aplica a los gráficos de segmento y estadía.")
    if seleccion:
        return (f"Mercado seleccionado: {seleccion}. Los gráficos «Turista vs. excursionista» y "
                "«Estadía por mes» muestran solo este mercado.")
    return ("Haga clic en una barra para ver ese mercado en «Turista vs. excursionista» y "
            "«Estadía por mes».")


# ------------------------------------------------------------------------ layout
def _tarjeta(id_base: str, titulo: str, ayuda: str) -> dbc.Card:
    return dbc.Card(dbc.CardBody([
        html.Div([
            html.Span(titulo, className="small fw-semibold"),
            html.Span(" ⓘ", id=f"{id_base}-info", tabIndex=0, role="img", **{"aria-label": "Ver fórmula"},
                      style={"cursor": "help", "color": theme.COLOR_OBSERVADO}),
        ]),
        html.Div(theme.ETIQUETA_SIN_DATO, id=f"{id_base}-valor", className="h2 mb-0",
                 style={"color": theme.TEXTO}),
        html.Div("", id=f"{id_base}-detalle", className="small",
                 style={"color": theme.TEXTO_SECUNDARIO}),
        dbc.Tooltip(ayuda, target=f"{id_base}-info", placement="bottom"),
    ]), className="h-100 shadow-sm")


def _grafico(id_: str) -> dbc.Card:
    return dbc.Card(dbc.CardBody(dcc.Graph(id=id_, config=_CONFIG_GRAFICO)), className="h-100 shadow-sm")


def layout():
    """Layout estático del módulo; los callbacks lo llenan según el filtro global."""
    return html.Div([
        dcc.Store(id=ID_SELECCION, data=None),
        html.H2("Demanda y mercados", className="h4 mt-3"),
        html.P("Visitantes de Cobán y Alta Verapaz por subdestino. Las cifras siguen el rango de meses, "
               "el tipo de visitante y el subdestino elegidos arriba.", style={"color": theme.TEXTO_SECUNDARIO}),
        dbc.Row([
            dbc.Col(_tarjeta(IDS_KPI[0], "Visitantes promedio por mes",
                             "Media de los visitantes únicos mensuales observados. Dentro de cada mes se suman "
                             "los dos segmentos; los meses no se suman entre sí ni se suman subdestinos."),
                    xs=12, md=4, className="mb-3"),
            dbc.Col(_tarjeta(IDS_KPI[1], "Días-persona promedio por mes",
                             "Media mensual de días-persona observados (suma de los dos segmentos dentro de cada "
                             "mes). No se suman meses ni subdestinos."),
                    xs=12, md=4, className="mb-3"),
            dbc.Col(_tarjeta(IDS_KPI[2], "Estadía media ponderada",
                             "Estadía media = Σ días-persona ÷ Σ visitantes, solo del segmento «más de 1 día». "
                             "No es el promedio de la permanencia ya calculada."),
                    xs=12, md=4, className="mb-3"),
        ]),
        dbc.Row([
            dbc.Col(_grafico(ID_G_SEGMENTOS), xs=12, lg=6, className="mb-3"),
            dbc.Col(_grafico(ID_G_ESTADIA), xs=12, lg=6, className="mb-3"),
        ]),
        dbc.Row([
            dbc.Col([
                _grafico(ID_G_RANKING),
                html.Div([
                    html.Span(id=ID_SELECCION_TEXTO, className="small me-2",
                              style={"color": theme.TEXTO_SECUNDARIO}),
                    dbc.Button("Quitar selección", id=ID_LIMPIAR, size="sm", color="secondary",
                               outline=True, n_clicks=0),
                ], className="mt-2"),
            ], xs=12, lg=7, className="mb-3"),
            dbc.Col([
                _grafico(ID_G_NACIONALES),
                dbc.Alert("Los visitantes nacionales provienen de telefonía móvil con factor de expansión: "
                          "son cifras expandidas, no conteos directos. Se muestran aparte de los extranjeros "
                          "y no se desagregan por origen.", color="light", className="small mt-2 mb-0"),
            ], xs=12, lg=5, className="mb-3"),
        ]),
        html.P("Notas: el ranking promedia solo los meses en que cada mercado tiene dato; no suma meses y excluye "
               "«sin_dato». Los meses sin cobertura aparecen como «Sin dato», nunca como cero. "
               "«Más de 1 día» y «menos de 1 día» son los segmentos de la fuente.",
               className="small", style={"color": theme.TEXTO_SECUNDARIO}),
    ])


# --------------------------------------------------------------------- callbacks
def registrar_callbacks(app) -> None:
    """Registra los callbacks del módulo (solo leen ``store-filtros``)."""

    @app.callback(
        Output(ID_SELECCION, "data"),
        Input(ID_G_RANKING, "clickData"),
        Input(ID_LIMPIAR, "n_clicks"),
        Input(ID_STORE_FILTROS, "data"),
        prevent_initial_call=True,
    )
    def _seleccion(click, _n, _estado):
        return seleccion_desde_evento(ctx.triggered_id, click)

    @app.callback(
        [Output(f"{i}-{s}", "children") for i in IDS_KPI for s in ("valor", "detalle")],
        Input(ID_STORE_FILTROS, "data"),
    )
    def _kpis(estado):
        f = Filtros.desde_dict(estado)
        kpis = tarjetas_kpi(preparar(_leer_sub(), f), f)
        return [x for k in kpis for x in (k.valor, k.detalle)]

    @app.callback(
        Output(ID_G_SEGMENTOS, "figure"),
        Output(ID_G_ESTADIA, "figure"),
        Input(ID_STORE_FILTROS, "data"),
        Input(ID_SELECCION, "data"),
    )
    def _graficos_serie(estado, seleccion):
        f = Filtros.desde_dict(estado)
        mercado = mercado_efectivo(seleccion, f)
        df = serie_para_graficos(_leer_sub(), _leer_pais(), f, mercado)
        return fig_segmentos(df, f, mercado), fig_estadia(df, f, mercado)

    @app.callback(
        Output(ID_G_RANKING, "figure"),
        Output(ID_SELECCION_TEXTO, "children"),
        Input(ID_STORE_FILTROS, "data"),
        Input(ID_SELECCION, "data"),
    )
    def _ranking(estado, seleccion):
        f = Filtros.desde_dict(estado)
        return fig_ranking(ranking_extranjeros(_leer_pais(), f), f, seleccion), texto_seleccion(seleccion, f)

    @app.callback(Output(ID_G_NACIONALES, "figure"), Input(ID_STORE_FILTROS, "data"))
    def _nacionales(estado):
        f = Filtros.desde_dict(estado)
        return fig_nacionales(preparar(_leer_sub(), f, tipo="nacional"), f)
