"""Módulo 4 — Reto territorial: Cobán urbano frente a naturaleza.

El reto del Grupo 4 contrasta perfiles de movilidad de Cobán (servicios urbanos)
con Lanquín y Cuevas de Candelaria (naturaleza). Cada serie conserva un único
subdestino y un único tipo de visitante: las barras son comparaciones, nunca un
total construido del destino.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import Input, Output, dcc, html
from plotly.subplots import make_subplots

from app import theme
from app.theme import ID_STORE_FILTROS
from app.utils import datos, metricas
from app.utils.datos import Filtros

DESTINO = "alta_verapaz"
SUBDESTINOS = ("Coban", "Lanquin", "Cuevas De Candelaria")
NOMBRES = {"Coban": "Cobán", "Lanquin": "Lanquín", "Cuevas De Candelaria": "Cuevas de Candelaria"}
ID_G_PERFIL = "m4-grafico-perfil"
ID_G_FIN_SEMANA = "m4-grafico-fin-semana"
ID_G_MERCADOS = "m4-grafico-mercados"
ID_LECTURA = "m4-lectura-inguat"
_CONFIG = {"displayModeBar": False}


def _leer(nombre: str, columnas: list[str]) -> pd.DataFrame:
    try:
        return datos.cargar(nombre)
    except FileNotFoundError:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in columnas})


def _base_mensual(df: pd.DataFrame, f: Filtros, tipo: Optional[str] = None) -> pd.DataFrame:
    """Filtra movilidad mensual sin permitir mezclas para una serie territorial."""
    tipo = tipo or f.tipo
    m = ((df["destino_clave"] == DESTINO) & df["subdestino"].isin(SUBDESTINOS)
         & (df["tipo"] == tipo))
    # El reto compara los tres subdestinos: conserva rango/tipo global pero no restringe
    # la comparación al subdestino elegido en el encabezado.
    return datos.filtrar_mensual(df.loc[m].copy(), Filtros(f.mes_ini, f.mes_fin, tipo, None))


def visitantes_por_mes(df: pd.DataFrame, subdestino: str) -> pd.Series:
    """Σ de segmentos dentro de cada mes; falta uno => NaN, nunca cero."""
    d = df[df["subdestino"] == subdestino]
    if d.empty:
        return pd.Series(dtype=float, name="visitantes")
    tabla = d.groupby(["anio_mes", "segmento"])["visitantes"].sum(min_count=1).unstack("segmento")
    tabla = tabla.reindex(columns=list(metricas.SEGMENTOS))
    return tabla.sum(axis=1, min_count=2).rename("visitantes")


def perfil_territorial(df: pd.DataFrame) -> pd.DataFrame:
    """Promedios mensuales y proporción de turistas para cada subdestino, sin total."""
    filas = []
    for sub in SUBDESTINOS:
        d = df[df["subdestino"] == sub]
        serie = visitantes_por_mes(d, sub)
        prop = metricas.proporcion_turista_excursionista(d) if not d.empty else pd.DataFrame()
        filas.append({"subdestino": sub, "nombre": NOMBRES[sub],
                      "promedio_mensual": serie.mean() if len(serie) else np.nan,
                      "n_meses": int(serie.notna().sum()),
                      "prop_mas_1": prop["prop_mas_de_1_dia"].mean() if len(prop) else np.nan})
    return pd.DataFrame(filas)


def fig_perfil(df: pd.DataFrame, f: Filtros) -> go.Figure:
    titulo = "Perfil territorial: volumen mensual y visitantes de más de 1 día"
    periodo = theme.subtitulo_periodo(f.mes_ini, f.mes_fin, "movilidad_subdestino_mes")
    if df["promedio_mensual"].notna().sum() == 0:
        return theme.figura_sin_dato(titulo, periodo)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Promedio mensual", "Más de 1 día"))
    # El tipo global define el color. La posición y la etiqueta ya identifican el subdestino;
    # usar tres colores sin leyenda introduciría una codificación visual innecesaria.
    color_tipo = theme.COLOR_NACIONAL if f.tipo == "nacional" else theme.COLOR_EXTRANJERO
    fig.add_bar(x=df["nombre"], y=df["promedio_mensual"], marker_color=color_tipo, row=1, col=1,
                customdata=np.c_[df["n_meses"]],
                hovertemplate="%{x}<br>Promedio: %{y:,.0f}<br>Meses: %{customdata[0]}<extra></extra>")
    fig.add_bar(x=df["nombre"], y=df["prop_mas_1"] * 100, marker_color=color_tipo, row=1, col=2,
                hovertemplate="%{x}<br>Más de 1 día: %{y:.1f} %<extra></extra>")
    fig.update_layout(template=theme.PLANTILLA, height=410,
                      title=dict(text=theme.titulo_con_subtitulo(titulo, periodo)), showlegend=False,
                      margin=dict(b=70))
    fig.update_yaxes(title_text="Visitantes únicos promedio/mes", tickformat=",.0f", row=1, col=1)
    fig.update_yaxes(title_text="% de visitantes del mes", ticksuffix=" %", range=[0, 100], row=1, col=2)
    return fig


def presencia_fin_semana(diaria: pd.DataFrame, f: Filtros) -> pd.DataFrame:
    """Media diaria de sábado y de lunes–viernes; la fuente diaria no se suma al mes."""
    d = diaria[(diaria["destino_clave"] == DESTINO) & diaria["subdestino"].isin(SUBDESTINOS)
               & (diaria["tipo"] == f.tipo)].copy()
    d = datos.filtrar_diaria(d, Filtros(f.mes_ini, f.mes_fin, f.tipo, None))
    filas = []
    for sub in SUBDESTINOS:
        s = d[d["subdestino"] == sub]
        por_dia = s.groupby("fecha")["presencia"].sum(min_count=1).dropna()
        sab = por_dia[por_dia.index.dayofweek == 5]
        hab = por_dia[por_dia.index.dayofweek < 5]
        filas.append({"subdestino": sub, "nombre": NOMBRES[sub], "sabado": sab.mean(), "laborables": hab.mean(),
                      "ratio": sab.mean() / hab.mean() if len(hab) and hab.mean() > 0 else np.nan,
                      "n_sabados": len(sab), "n_laborables": len(hab)})
    return pd.DataFrame(filas)


def fig_fin_semana(df: pd.DataFrame, f: Filtros) -> go.Figure:
    titulo = "Presencia diaria: sábado frente a lunes–viernes"
    periodo = theme.subtitulo_periodo(f.mes_ini, f.mes_fin, "movilidad_diaria")
    if df[["sabado", "laborables"]].notna().sum().sum() == 0:
        return theme.figura_sin_dato(titulo, periodo)
    fig = go.Figure()
    fig.add_bar(name="Lunes–viernes", x=df["nombre"], y=df["laborables"], marker_color=theme.CATEGORICOS[0])
    fig.add_bar(name="Sábado", x=df["nombre"], y=df["sabado"], marker_color=theme.CATEGORICOS[3],
                text=[f"×{v:.2f}" if pd.notna(v) else "Sin dato" for v in df["ratio"]], textposition="outside")
    fig.update_layout(template=theme.PLANTILLA, height=410, barmode="group",
                      title=dict(text=theme.titulo_con_subtitulo(titulo, periodo)),
                      yaxis=dict(title="Personas presentes por día", tickformat=",.0f"),
                      legend=dict(orientation="h", y=-0.14, x=0), margin=dict(b=88))
    return fig


def mercado_principal(mensual: pd.DataFrame, f: Filtros) -> pd.DataFrame:
    """Mercado extranjero principal por subdestino usando media mensual, sin sumar meses."""
    d = mensual[(mensual["destino_clave"] == DESTINO) & mensual["subdestino"].isin(SUBDESTINOS)
                & (mensual["tipo"] == "extranjero")].copy()
    d = datos.filtrar_mensual(d, Filtros(f.mes_ini, f.mes_fin, "extranjero", None))
    d = d[~d["pais"].fillna("").str.lower().isin({"sin dato", "no disponible", "desconocido"})]
    filas = []
    for sub in SUBDESTINOS:
        s = d[d["subdestino"] == sub]
        por_pais = s.groupby(["anio_mes", "pais"])["visitantes"].sum(min_count=1)
        tot = por_pais.groupby(level="anio_mes").sum(min_count=1)
        if por_pais.empty or tot.empty:
            filas.append({"subdestino": sub, "nombre": NOMBRES[sub], "pais": None, "participacion": np.nan})
            continue
        participacion = por_pais.div(tot, level="anio_mes")
        prom = participacion.groupby(level="pais").mean().sort_values(ascending=False)
        filas.append({"subdestino": sub, "nombre": NOMBRES[sub], "pais": prom.index[0],
                      "participacion": float(prom.iloc[0])})
    return pd.DataFrame(filas)


def fig_mercados(df: pd.DataFrame, f: Filtros) -> go.Figure:
    titulo = "Mercado emisor extranjero principal por subdestino"
    periodo = theme.subtitulo_periodo(f.mes_ini, f.mes_fin, "movilidad_mensual")
    if df["participacion"].notna().sum() == 0:
        return theme.figura_sin_dato(titulo, periodo)
    etiquetas = [f"{pais}<br>{valor * 100:.1f} %" if pd.notna(valor) else "Sin dato"
                 for pais, valor in zip(df["pais"], df["participacion"])]
    fig = go.Figure(go.Bar(x=df["nombre"], y=df["participacion"] * 100, marker_color=theme.COLOR_EXTRANJERO,
                           text=etiquetas, textposition="outside",
                           hovertemplate="%{x}<br>Mercado principal: %{text}<br>Participación mensual media: %{y:.1f} %<extra></extra>"))
    fig.update_layout(template=theme.PLANTILLA, height=410, showlegend=False,
                      title=dict(text=theme.titulo_con_subtitulo(titulo, periodo)),
                      yaxis=dict(title="Participación mensual media", ticksuffix=" %", range=[0, 100]), margin=dict(b=70))
    fig.add_annotation(text="Solo extranjeros. Es una proporción dentro de cada subdestino y mes; no es un total del destino.",
                       xref="paper", yref="paper", x=0, y=-0.2, xanchor="left", showarrow=False,
                       font=dict(size=11, color=theme.TEXTO_SECUNDARIO))
    return fig


def lectura_inguat(perfil: pd.DataFrame, fines: pd.DataFrame, mercados: pd.DataFrame, tipo: str) -> list:
    """Tres frases con cifras exactas para la lectura ejecutiva del reto."""
    def fila(df, sub): return df.loc[df["subdestino"] == sub].iloc[0]
    cob, lan, cue = (fila(perfil, s) for s in SUBDESTINOS)
    base = (f"Con visitantes {tipo}s, Cobán promedia {cob.promedio_mensual:,.0f} personas al mes; "
            f"Lanquín {lan.promedio_mensual:,.0f} y Cuevas de Candelaria {cue.promedio_mensual:,.0f}." )
    fin = fila(fines, "Lanquin")
    semana = f"En Lanquín, la presencia del sábado equivale a ×{fin.ratio:.2f} la de lunes–viernes."
    mer = fila(mercados, "Coban")
    mercado = (f"Para extranjeros, el mercado principal de Cobán es {mer.pais} con {mer.participacion * 100:.1f} % "
               "de participación mensual media." if pd.notna(mer.participacion) else
               "No hay mercado emisor extranjero con cobertura suficiente para el rango seleccionado.")
    return [base, semana, mercado]


def _grafico(id_: str) -> dbc.Card:
    return dbc.Card(dbc.CardBody(dcc.Graph(id=id_, config=_CONFIG)), className="shadow-sm")


def _grafico_con_nota(id_: str, nota: str) -> dbc.Card:
    """Nota HTML separada: no compite por el margen inferior de la figura Plotly."""
    return dbc.Card(dbc.CardBody([
        dcc.Graph(id=id_, config=_CONFIG),
        html.P(nota, className="small mb-0 mt-1", style={"color": theme.TEXTO_SECUNDARIO}),
    ]), className="shadow-sm")


def layout():
    return html.Div([
        html.H2("Reto de Cobán y Alta Verapaz", className="h4 mt-3"),
        html.P("Contraste entre Cobán, centro urbano de servicios, y Lanquín y Cuevas de Candelaria, "
               "subdestinos de naturaleza. Las comparaciones no construyen un total del destino.",
               style={"color": theme.TEXTO_SECUNDARIO}),
        dbc.Alert([html.Strong("Lectura para INGUAT. "), html.Ul(id=ID_LECTURA, className="mb-0 mt-1")],
                  color="light", className="small"),
        dbc.Row([dbc.Col(_grafico_con_nota(
                    ID_G_PERFIL,
                    "Cada barra es un subdestino; se muestran promedios de meses observados y no se suman territorios."),
                    xs=12, lg=6, className="mb-3"),
                 dbc.Col(_grafico_con_nota(
                    ID_G_FIN_SEMANA,
                    "× indica la razón sábado / lunes-viernes. Es presencia diaria, no visitantes únicos mensuales."),
                    xs=12, lg=6, className="mb-3")]),
        html.H3("Concentración de mercados", className="h5 mt-3"),
        _grafico(ID_G_MERCADOS),
        html.P("Fuentes usadas: movilidad mensual y diaria. Ocupación y oferta se reportan en el módulo 3 a nivel "
               "departamental, por lo que no se atribuyen a un subdestino en este reto.", className="small mt-2",
               style={"color": theme.TEXTO_SECUNDARIO}),
    ])


def registrar_callbacks(app) -> None:
    @app.callback(Output(ID_G_PERFIL, "figure"), Output(ID_G_FIN_SEMANA, "figure"), Output(ID_G_MERCADOS, "figure"),
                  Output(ID_LECTURA, "children"), Input(ID_STORE_FILTROS, "data"))
    def _actualizar(estado):
        f = Filtros.desde_dict(estado)
        mensual = _leer("movilidad_subdestino_mes", ["destino_clave", "subdestino", "tipo", "anio_mes", "segmento", "visitantes"])
        diaria = _leer("movilidad_diaria", ["destino_clave", "subdestino", "tipo", "fecha", "presencia"])
        pais = _leer("movilidad_mensual", ["destino_clave", "subdestino", "tipo", "anio_mes", "pais", "visitantes"])
        perfil = perfil_territorial(_base_mensual(mensual, f))
        fines = presencia_fin_semana(diaria, f)
        mercados = mercado_principal(pais, f)
        lectura = [html.Li(x) for x in lectura_inguat(perfil, fines, mercados, f.tipo or "")]
        return fig_perfil(perfil, f), fig_fin_semana(fines, f), fig_mercados(mercados, f), lectura
