"""Módulo 3 — Oferta hotelera y desagregación territorial (Cobán y Alta Verapaz).

Integración (patrón de app/main.py): ``layout()`` y ``registrar_callbacks(app)``. Solo LEE el filtro
global ``store-filtros``. Todos los IDs llevan el prefijo ``m3-``. Los cálculos viven en
``app/utils/oferta_ocupacion.py``; aquí solo hay figuras, layout y callbacks.

Bloques
A. Capacidad instalada 2022–2025 (departamento): barras agrupadas por año (cortes anuales de
   inventario; NO línea de tendencia). 2026 solo si se pide, marcado como corte parcial.
B. Ocupación mensual 2023–2025 del departamento, con el promedio simple departamental opcional y
   los meses pico/valle de cada año. Sin proyecciones.
C. Ventana coincidente sep–dic 2025: afluencia de UN subdestino y UN tipo vs índice de ocupación, en
   dos paneles alineados (no doble eje). Sin correlación (n = 4): solo se describe.
D. Subdestinos: afluencia relativa de los tres subdestinos (mes elegido o promedio de meses
   observados). Nunca se suman; no hay barra «Total».
E. Estacionalidad: índice estacional de la ocupación (por año) frente al perfil compuesto de visitantes.

Qué responde a qué (interacción)
* Filtro global (rango de meses, tipo, subdestino) -> B (vista «solo rango»), C, D y E.
* Clic en una barra de A (un año)          -> B sombrea ese año y E resalta su curva.
* Clic en un mes de C (o de B en sep–dic 2025) -> D muestra ese mes.
* Clic en una barra de D (un subdestino)   -> C y E pasan a ese subdestino.
* «Quitar selección» borra las tres selecciones; cambiar el filtro global borra la de subdestino.

Reglas: ausencia de dato -> «Sin dato» (nunca 0); cada visual declara período y fuente; la oferta y la
ocupación son del departamento, no del destino; la oferta no incluye plataformas digitales (Airbnb).
"""
from __future__ import annotations

from typing import Any, Optional

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, dcc, html
from plotly.subplots import make_subplots

from app import theme
from app.theme import ID_STORE_FILTROS
from app.utils import cobertura as cb
from app.utils import datos
from app.utils import oferta_ocupacion as oo
from app.utils.datos import Filtros

# Fuentes (nombre de archivo de origen, para los subtítulos)
SRC_OFERTA = "oferta_hotelera_2022_2026.csv"
SRC_OCUPACION = "indice_ocupacion_mensual_2023_2025_1.csv"
SRC_MOVILIDAD = "BD_moviidad_mensual.xlsx (hoja Alta Verapaz)"

# IDs
ID_METRICA = "m3-metrica-oferta"
ID_INCLUIR_2026 = "m3-incluir-2026"
ID_G_CAPACIDAD = "m3-grafico-capacidad"
ID_COMPARAR = "m3-comparar-promedio"
ID_VISTA_OCUP = "m3-vista-ocupacion"
ID_G_OCUPACION = "m3-grafico-ocupacion"
ID_G_CRUCE = "m3-grafico-cruce"
ID_TEXTO_CRUCE = "m3-texto-cruce"
ID_MES_SUB = "m3-mes-subdestinos"
ID_G_SUBDESTINOS = "m3-grafico-subdestinos"
ID_G_ESTACIONAL = "m3-grafico-estacionalidad"
ID_ANIO_SEL = "m3-anio-seleccion"
ID_SUB_SEL = "m3-subdestino-seleccion"
ID_LIMPIAR = "m3-limpiar"
ID_SELECCION_TEXTO = "m3-seleccion-texto"

_CONFIG_GRAFICO = {"displayModeBar": False}   # sin barra de herramientas ni descargas

# Colores. Años de oferta: escala secuencial (más oscuro = más reciente; el año es ordinal).
COLOR_ANIO = {2022: theme.SECUENCIAL[2], 2023: theme.SECUENCIAL[3], 2024: theme.SECUENCIAL[4],
              2025: theme.SECUENCIAL[5], 2026: theme.SECUENCIAL[5]}
COLOR_PROMEDIO = theme.CATEGORICOS[4]                 # gris azulado: referencia
COLOR_PICO, COLOR_VALLE = theme.CATEGORICOS[1], theme.CATEGORICOS[3]
COLOR_OCUPACION = theme.CATEGORICOS[1]
COLOR_RESALTE = theme.COLOR_OBSERVADO
COLOR_ATENUADO = theme.SECUENCIAL[2]
SOMBRA_VENTANA = "rgba(86, 180, 233, 0.16)"
SOMBRA_ANIO = "rgba(68, 84, 106, 0.10)"
ORDEN_TIPO_ALOJ = ("Hotel", "Hospedaje", "Pensión")
MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

NOTA_AIRBNB = "No incluye plataformas digitales (Airbnb): solo hoteles, hospedajes y pensiones registrados."
NOTA_N4 = ("Con solo 4 meses coincidentes (n = 4) no se calcula una correlación ni se infiere causalidad: "
           "solo se describe si las dos series se mueven en la misma dirección.")


# =========================================================================== datos
_VACIAS = {
    "oferta": ["anio", "departamento", "tipo_alojamiento", "establecimientos", "habitaciones", "plazas_cama",
               "es_corte_parcial", "repite_valor_anio_previo"],
    "ocupacion": ["departamento", "anio_mes", "indice_pct"],
    "movilidad_subdestino_mes": ["destino_clave", "subdestino", "tipo", "anio_mes", "segmento", "visitantes"],
}


def _leer(nombre: str) -> pd.DataFrame:
    """Lee un parquet; si falta devuelve una tabla vacía (los gráficos mostrarán «Sin dato»)."""
    try:
        return datos.cargar(nombre)
    except FileNotFoundError:
        cols = _VACIAS[nombre]
        return pd.DataFrame({c: pd.Series(dtype="datetime64[ns]" if c == "anio_mes" else object) for c in cols})


def subdestino_efectivo(seleccion: Optional[str], f: Filtros) -> Optional[str]:
    """El subdestino elegido con clic en D manda; si no hay, el del filtro global."""
    return seleccion if seleccion in oo.SUBDESTINOS else f.subdestino


def meses_filtro(f: Filtros) -> pd.DatetimeIndex:
    if f.mes_ini is None or f.mes_fin is None:
        return pd.DatetimeIndex([], name="anio_mes")
    return datos.rango_meses(f.mes_ini, f.mes_fin)


def meses_movilidad(cob: pd.DataFrame, f: Filtros) -> pd.DatetimeIndex:
    """Meses del rango con cobertura de movilidad mensual (según la tabla de cobertura)."""
    if f.mes_ini is None or f.mes_fin is None or cob.empty:
        return pd.DatetimeIndex([], name="anio_mes")
    return cb.meses_con_dato(cob, "movilidad_mensual", f.mes_ini, f.mes_fin)


def opciones_mes(meses_mov: pd.DatetimeIndex) -> list:
    """Opciones del selector de mes de D: promedio + cada mes con dato."""
    return ([{"label": "Promedio de los meses observados del rango", "value": oo.PROMEDIO}]
            + [{"label": theme.etiqueta_mes(m), "value": f"{m:%Y-%m}"} for m in meses_mov])


def mes_desde_click(click: Any) -> Optional[str]:
    """'YYYY-MM' del punto clicado (customdata o x). None si no se puede leer."""
    try:
        p = click["points"][0]
    except (TypeError, KeyError, IndexError):
        return None
    valor = p.get("customdata", p.get("x"))
    if isinstance(valor, (list, tuple)):
        valor = valor[0] if valor else None
    try:
        return f"{pd.Timestamp(valor):%Y-%m}" if valor is not None else None
    except (ValueError, TypeError):
        return None


def valor_desde_click(click: Any) -> Any:
    """customdata del punto clicado (año de A o subdestino de D)."""
    try:
        valor = click["points"][0]["customdata"]
    except (TypeError, KeyError, IndexError):
        return None
    if isinstance(valor, (list, tuple)):
        valor = valor[0] if valor else None
    return valor


def alternar(actual: Any, nuevo: Any) -> Any:
    """Clic sobre lo ya seleccionado lo deselecciona."""
    return None if nuevo is None or nuevo == actual else nuevo


# ======================================================================== utilidades
def _base(fig: go.Figure, titulo: str, subtitulo: str, altura: int = 380, **kw) -> go.Figure:
    fig.update_layout(template=theme.PLANTILLA, height=altura,
                      title=dict(text=theme.titulo_con_subtitulo(titulo, subtitulo)), **kw)
    return fig


def _nota_pie(fig: go.Figure, texto: str, y: float = -0.28) -> None:
    fig.add_annotation(text=texto, xref="paper", yref="paper", x=0, y=y, xanchor="left", yanchor="top",
                       showarrow=False, align="left", font=dict(size=11, color=theme.TEXTO_SECUNDARIO))


def _fmt(v: float, dec: int = 0) -> str:
    return theme.ETIQUETA_SIN_DATO if pd.isna(v) else f"{v:,.{dec}f}"


# ================================================================ A. capacidad
def fig_capacidad(cap: pd.DataFrame, metrica: str, anio_sel: Optional[int] = None) -> go.Figure:
    """Barras agrupadas: x = tipo de alojamiento, una barra por corte anual (no es tendencia)."""
    nombre_met = oo.METRICAS_OFERTA.get(metrica, metrica)
    titulo = f"Capacidad instalada: {nombre_met.lower()} por tipo de alojamiento"
    anios = sorted(cap["anio"].unique()) if len(cap) else []
    rango = (f"{anios[0]}–{max(a for a in anios if a <= 2025)}" if any(a <= 2025 for a in anios)
             else "sin cortes")
    sub = (f"Alta Verapaz (departamento) · Cortes anuales {rango}"
           + (" + 2026 parcial" if 2026 in anios else "") + f" · Fuente: {SRC_OFERTA}")
    if cap.empty or cap[metrica].isna().all():
        return theme.figura_sin_dato(titulo, sub)
    tipos = [t for t in ORDEN_TIPO_ALOJ if t in set(cap["tipo_alojamiento"])] + \
        sorted(set(cap["tipo_alojamiento"]) - set(ORDEN_TIPO_ALOJ))
    fig = go.Figure()
    for anio in anios:
        d = cap[cap["anio"] == anio].set_index("tipo_alojamiento").reindex(tipos)
        parcial = bool(d["es_corte_parcial"].fillna(False).any())
        nombre = f"{anio} · corte parcial (T1)" if parcial else str(anio)
        opacidad = 1.0 if anio_sel in (None, anio) else 0.35
        marcador = dict(color=COLOR_ANIO.get(anio, theme.COLOR_OBSERVADO), opacity=opacidad,
                        line=dict(color=theme.FONDO, width=1))
        if parcial:
            marcador.update(color=theme.FONDO, line=dict(color=COLOR_ANIO[2026], width=1.5),
                            pattern=dict(shape="/", fgcolor=COLOR_ANIO[2026], size=6, solidity=0.35))
        repite = d["repite_valor_anio_previo"].fillna(False).map({True: " · repite el valor del año previo",
                                                                  False: ""})
        fig.add_bar(x=tipos, y=d[metrica], name=nombre, marker=marcador, customdata=[anio] * len(tipos),
                    text=repite, textposition="none",
                    hovertemplate=f"<b>%{{x}}</b> · corte {nombre}<br>{nombre_met}: %{{y:,.0f}}%{{text}}"
                                  "<extra></extra>")
    _base(fig, titulo, sub, altura=400, barmode="group", bargap=0.25, bargroupgap=0.06,
          yaxis=dict(title=dict(text=f"{nombre_met} (inventario al corte)"), rangemode="tozero",
                     tickformat=",.0f"),
          legend=dict(title=dict(text="Corte anual"), orientation="h", y=-0.15),
          margin=dict(b=110))
    _nota_pie(fig, NOTA_AIRBNB, y=-0.33)
    return fig


# ================================================================ B. ocupación
def fig_ocupacion(serie: pd.DataFrame, promedio: Optional[pd.DataFrame], picos: pd.DataFrame,
                  meses_sel: Optional[pd.DatetimeIndex] = None, anio_sel: Optional[int] = None,
                  periodo: Optional[str] = None) -> go.Figure:
    """Serie mensual continua del índice (%), con promedio departamental opcional y picos/valles."""
    titulo = "Ocupación hotelera mensual — Alta Verapaz (departamento)"
    datos_ok = serie.dropna(subset=["indice_pct"])
    if periodo is None:
        periodo = (theme.subtitulo_periodo(serie["anio_mes"].min(), serie["anio_mes"].max(), SRC_OCUPACION)
                   if len(serie) else f"Fuente: {SRC_OCUPACION}")
    if datos_ok.empty:
        return theme.figura_sin_dato(titulo, periodo,
                                     mensaje="Sin dato · la ocupación cubre ene 2023 – dic 2025")
    fig = go.Figure()
    # Ventana de cruce con movilidad (sep–dic 2025) y año seleccionado en A
    x0, x1 = serie["anio_mes"].min(), serie["anio_mes"].max()
    vi, vf = oo.VENTANA_CRUCE.min(), oo.VENTANA_CRUCE.max()
    if vf >= x0 and vi <= x1:
        fig.add_vrect(x0=max(vi, x0) - pd.Timedelta(days=15), x1=min(vf, x1) + pd.Timedelta(days=15),
                      fillcolor=SOMBRA_VENTANA, line_width=0, layer="below",
                      annotation_text="Ventana con movilidad", annotation_position="top left",
                      annotation_font=dict(size=10, color=theme.TEXTO_SECUNDARIO))
    if anio_sel is not None and x0.year <= int(anio_sel) <= x1.year:
        fig.add_vrect(x0=pd.Timestamp(f"{anio_sel}-01-01") - pd.Timedelta(days=15),
                      x1=pd.Timestamp(f"{anio_sel}-12-01") + pd.Timedelta(days=15),
                      fillcolor=SOMBRA_ANIO, line_width=0, layer="below",
                      annotation_text=f"Año {anio_sel} (seleccionado en capacidad)",
                      annotation_position="bottom left",
                      annotation_font=dict(size=10, color=theme.TEXTO_SECUNDARIO))
    if promedio is not None and promedio["indice_pct"].notna().any():
        fig.add_scatter(x=promedio["anio_mes"], y=promedio["indice_pct"], mode="lines", connectgaps=False,
                        name="Promedio simple de 22 departamentos (no es el índice nacional oficial)",
                        line=dict(color=COLOR_PROMEDIO, width=2, dash="dot"),
                        customdata=promedio["anio_mes"].dt.strftime("%Y-%m"),
                        hovertemplate="%{x|%b %Y}<br>Promedio departamental: %{y:.1f} %<extra></extra>")
    fig.add_scatter(x=serie["anio_mes"], y=serie["indice_pct"], mode="lines+markers", connectgaps=False,
                    name="Alta Verapaz", line=dict(color=theme.COLOR_OBSERVADO, width=2.5),
                    marker=dict(size=6), customdata=serie["anio_mes"].dt.strftime("%Y-%m"),
                    hovertemplate="%{x|%b %Y}<br>Alta Verapaz: %{y:.0f} %<extra></extra>")
    for tipo, simbolo, color, nombre, pos in (("pico", "triangle-up", COLOR_PICO, "Mes pico del año", "top center"),
                                              ("valle", "triangle-down", COLOR_VALLE, "Mes valle del año",
                                               "bottom center")):
        d = picos[picos["tipo"] == tipo] if len(picos) else picos
        if len(d):
            fig.add_scatter(x=d["anio_mes"], y=d["indice_pct"], mode="markers+text", name=nombre,
                            marker=dict(symbol=simbolo, size=12, color=color,
                                        line=dict(color=theme.FONDO, width=2)),
                            text=[f"{v:.0f} %" for v in d["indice_pct"]], textposition=pos,
                            textfont=dict(size=11, color=theme.TEXTO),
                            customdata=d["anio_mes"].dt.strftime("%Y-%m"),
                            hovertemplate="%{x|%b %Y}<br>" + nombre + ": %{y:.0f} %<extra></extra>")
    _base(fig, titulo, periodo, altura=420, hovermode="x unified",
          yaxis=dict(range=[0, 100], ticksuffix=" %", title=dict(text="Índice de ocupación (%)")),
          xaxis=dict(dtick="M3", tickformat="%b %Y"), legend=dict(orientation="h", y=-0.2))
    return fig


# ================================================================== C. cruce
def fig_cruce(cruce: pd.DataFrame, subdestino: Optional[str], tipo: Optional[str], periodo: str,
              mensaje_vacio: Optional[str] = None) -> go.Figure:
    """Dos paneles alineados (misma escala de tiempo, ejes Y separados): afluencia y ocupación."""
    nombre = oo.nombre_subdestino(subdestino) if subdestino else "—"
    titulo = f"Afluencia vs. ocupación · ventana sep–dic 2025 · {nombre} ({tipo or '—'})"
    if cruce is None or cruce.empty or cruce[["visitantes", "ocupacion_pct"]].isna().all().all():
        return theme.figura_sin_dato(titulo, periodo, mensaje=mensaje_vacio or theme.ETIQUETA_SIN_DATO, altura=460)
    etiquetas = [theme.etiqueta_mes(m) for m in cruce["anio_mes"]]
    claves = list(cruce["anio_mes"].dt.strftime("%Y-%m"))
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.14,
                        subplot_titles=(f"Visitantes únicos del mes · {nombre}, {tipo}",
                                        "Índice de ocupación hotelera · Alta Verapaz (departamento)"))
    fig.add_bar(x=etiquetas, y=cruce["visitantes"], name="Visitantes (personas)", customdata=claves,
                marker=dict(color=theme.COLOR_OBSERVADO), row=1, col=1,
                hovertemplate="%{x}<br>Visitantes: %{y:,.0f}<extra></extra>")
    fig.add_scatter(x=etiquetas, y=cruce["ocupacion_pct"], mode="lines+markers", connectgaps=False,
                    name="Ocupación (%)", customdata=claves, row=2, col=1,
                    line=dict(color=COLOR_OCUPACION, width=2.5), marker=dict(size=9),
                    hovertemplate="%{x}<br>Ocupación: %{y:.0f} %<extra></extra>")
    _base(fig, titulo, periodo, altura=480, showlegend=False, margin=dict(t=110))
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=etiquetas)
    fig.update_yaxes(title_text="Personas", tickformat=",.0f", rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title_text="Ocupación (%)", ticksuffix=" %", range=[0, 100], row=2, col=1)
    fig.update_annotations(font=dict(size=12, color=theme.TEXTO_SECUNDARIO), selector=dict(xref="paper"))
    return fig


def texto_cruce(rel: Optional[dict], subdestino: Optional[str], tipo: Optional[str]) -> list:
    """Lectura descriptiva (honesta) del cruce: dirección de los cambios, sin correlación."""
    aviso = dbc.Alert([html.Strong("Lectura con n = 4. "), NOTA_N4], color="warning", className="small mb-2")
    if not rel or rel["n_meses"] == 0:
        return [aviso, html.P("No hay meses de la ventana sep–dic 2025 en el rango elegido.",
                              className="small mb-0", style={"color": theme.COLOR_SIN_DATO_TEXTO})]
    flecha = {"sube": "↑", "baja": "↓", "igual": "=", "sin dato": "sin dato"}
    items = []
    for c in rel["cambios"]:
        if "sin dato" in (c["visitantes"], c["ocupacion"]):
            items.append(html.Li(f"{theme.etiqueta_mes(c['mes'])}: sin dato en una de las series."))
            continue
        misma = "misma dirección" if c["visitantes"] == c["ocupacion"] else "direcciones opuestas"
        items.append(html.Li(
            f"{theme.etiqueta_mes(c['mes'])}: visitantes {flecha[c['visitantes']]} "
            f"{c['dif_visitantes_pct']:+.1f} %, ocupación {flecha[c['ocupacion']]} "
            f"{c['dif_ocupacion_pp']:+.0f} pp ({misma})."))
    resumen = (f"{oo.nombre_subdestino(subdestino)} ({tipo}): en {rel['coinciden']} de {rel['comparables']} "
               "cambios mensuales las dos series se movieron en la misma dirección.")
    if rel["mes_max_visitantes"] is not None and rel["mes_max_ocupacion"] is not None:
        resumen += (f" Máximo de visitantes: {theme.etiqueta_mes(rel['mes_max_visitantes'])}; "
                    f"máximo de ocupación: {theme.etiqueta_mes(rel['mes_max_ocupacion'])}.")
    return [aviso, html.P(resumen, className="small mb-1"), html.Ul(items, className="small mb-1"),
            html.P("La ocupación es del departamento y solo mide hotelería formal; los visitantes son de un "
                   "subdestino y de telefonía móvil: miden universos distintos.", className="small mb-0",
                   style={"color": theme.TEXTO_SECUNDARIO})]


# ============================================================= D. subdestinos
def fig_subdestinos(af: pd.DataFrame, tipo: Optional[str], periodo: str, resaltado: Optional[str] = None,
                    detalle: str = "") -> go.Figure:
    """Una barra por subdestino (sin «Total»). Etiqueta: % respecto del subdestino mayor."""
    titulo = f"Afluencia relativa por subdestino · {tipo or '—'} (no se suman)"
    sub = " · ".join(p for p in (periodo, detalle) if p)
    if af is None or af.empty or af["visitantes"].isna().all():
        return theme.figura_sin_dato(titulo, sub)
    if "Total" in set(af["subdestino"]) or "Total" in set(af["nombre"]):
        raise ValueError("No se admite una barra «Total» construida por suma de subdestinos.")
    colores = [COLOR_RESALTE if (resaltado is None or s == resaltado) else COLOR_ATENUADO for s in af["subdestino"]]
    textos = ["" if pd.isna(r) else f"{r:.0f} % del mayor" for r in af["relativo_pct"]]
    fig = go.Figure(go.Bar(
        x=af["nombre"], y=af["visitantes"], customdata=af["subdestino"], marker=dict(color=colores),
        text=textos, textposition="outside", textfont=dict(color=theme.TEXTO, size=12), cliponaxis=False,
        hovertext=[f"{n}<br>Visitantes: {_fmt(v)}<br>Meses con dato: {k}" for n, v, k
                   in zip(af["nombre"], af["visitantes"], af["n_meses"])],
        hovertemplate="%{hovertext}<extra></extra>"))
    _base(fig, titulo, sub, altura=400, showlegend=False,
          yaxis=dict(title=dict(text="Visitantes únicos por mes (personas)"), tickformat=",.0f",
                     rangemode="tozero"),
          margin=dict(b=90))
    fig.update_xaxes(type="category")
    _nota_pie(fig, "Una persona puede estar contada en varios subdestinos: no se suman para formar un total.",
              y=-0.2)
    return fig


# =========================================================== E. estacionalidad
def fig_estacionalidad(ie_ocup: pd.DataFrame, ie_vis: pd.DataFrame, subdestino: Optional[str],
                       tipo: Optional[str], periodo_vis: str, anio_sel: Optional[int] = None) -> go.Figure:
    """Dos paneles con el mismo eje de meses calendario: ocupación (por año) y visitantes (compuesto)."""
    nombre = oo.nombre_subdestino(subdestino) if subdestino else "—"
    titulo = "Estacionalidad: ocupación hotelera vs. visitantes (índice, media = 100)"
    sub = f"Ocupación ene 2023 – dic 2025 · Visitantes: {periodo_vis} · {nombre}, {tipo or '—'}"
    if (ie_ocup is None or ie_ocup.empty) and (ie_vis is None or ie_vis["indice_estacional"].isna().all()):
        return theme.figura_sin_dato(titulo, sub, altura=480)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.14,
                        subplot_titles=("Ocupación de Alta Verapaz por año (media del año = 100)",
                                        f"Visitantes de {nombre}, {tipo} · perfil compuesto "
                                        "(media de meses observados = 100)"))
    # Tres canales de distinción (tono, trazo y marcador) evitan que los años se
    # confundan cuando las curvas se cruzan.
    estilos_anio = {
        2023: dict(color=theme.CATEGORICOS[2], dash="solid", symbol="circle"),
        2024: dict(color=theme.CATEGORICOS[1], dash="dash", symbol="square"),
        2025: dict(color=theme.CATEGORICOS[3], dash="dot", symbol="diamond"),
    }
    if ie_ocup is not None and len(ie_ocup):
        for anio, d in ie_ocup.groupby("anio"):
            ancho = 3.5 if anio_sel == anio else (1.5 if anio_sel is not None else 2.2)
            estilo = estilos_anio.get(anio, dict(color=theme.COLOR_OBSERVADO, dash="solid", symbol="circle"))
            fig.add_scatter(x=[MESES_CORTOS[m - 1] for m in d["mes"]], y=d["indice_estacional"],
                            mode="lines+markers", name=f"Ocupación {anio}", row=1, col=1,
                            line=dict(color=estilo["color"], width=ancho, dash=estilo["dash"]),
                            marker=dict(size=7, color=estilo["color"], symbol=estilo["symbol"]),
                            customdata=d["indice_pct"],
                            hovertemplate=f"%{{x}} {anio}<br>Índice estacional: %{{y:.0f}}"
                                          "<br>Ocupación: %{customdata:.0f} %<extra></extra>")
    if ie_vis is not None and ie_vis["indice_estacional"].notna().any():
        origen = [theme.etiqueta_mes(m) if pd.notna(m) else theme.ETIQUETA_SIN_DATO for m in ie_vis["anio_mes"]]
        fig.add_scatter(x=[MESES_CORTOS[m - 1] for m in ie_vis["mes"]], y=ie_vis["indice_estacional"],
                        mode="lines+markers", connectgaps=False, name="Visitantes (perfil compuesto)",
                        row=2, col=1, line=dict(color=theme.COLOR_OBSERVADO, width=2.5), marker=dict(size=8),
                        customdata=origen,
                        hovertemplate="%{x} · dato de %{customdata}<br>Índice: %{y:.0f}<extra></extra>")
    for fila in (1, 2):
        fig.add_hline(y=100, line=dict(color=theme.COLOR_EJE, width=1, dash="dot"), row=fila, col=1)
    _base(fig, titulo, sub, altura=520, margin=dict(t=110, b=80), legend=dict(orientation="h", y=-0.12))
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=list(MESES_CORTOS))
    fig.update_yaxes(title_text="Índice", row=1, col=1)
    fig.update_yaxes(title_text="Índice", row=2, col=1)
    fig.update_annotations(font=dict(size=12, color=theme.TEXTO_SECUNDARIO), selector=dict(xref="paper"))
    return fig


# ============================================================== composición
def construir_ocupacion(ocup: pd.DataFrame, f: Filtros, comparar: bool, vista: str,
                        anio_sel: Optional[int]) -> go.Figure:
    """Figura B según la vista: serie completa 2023–2025 o solo los meses del filtro global."""
    serie = oo.serie_ocupacion(ocup)
    prom = oo.promedio_departamental(ocup) if comparar else None
    if vista == "rango":
        meses = meses_filtro(f)
        meses = meses[(meses >= oo.OCUPACION_INI) & (meses <= oo.OCUPACION_FIN)]
        periodo = theme.subtitulo_periodo(f.mes_ini, f.mes_fin, SRC_OCUPACION)
        if len(meses) == 0:
            return theme.figura_sin_dato(
                "Ocupación hotelera mensual — Alta Verapaz (departamento)", periodo,
                mensaje="Sin dato en el rango · la ocupación cubre ene 2023 – dic 2025", altura=420)
        serie = serie[serie["anio_mes"].isin(meses)]
        prom = prom[prom["anio_mes"].isin(meses)] if prom is not None else None
    else:
        periodo = theme.subtitulo_periodo(oo.OCUPACION_INI, oo.OCUPACION_FIN, SRC_OCUPACION)
    return fig_ocupacion(serie, prom, oo.picos_valles(serie), anio_sel=anio_sel, periodo=periodo)


def construir_cruce(mov: pd.DataFrame, ocup: pd.DataFrame, cob: pd.DataFrame, f: Filtros,
                    subdestino: Optional[str]):
    """(figura C, texto C). Solo meses del filtro dentro de sep–dic 2025 y con cobertura."""
    meses = oo.meses_cruce(f.mes_ini, f.mes_fin)
    periodo = (theme.subtitulo_periodo(meses.min(), meses.max(), f"{SRC_MOVILIDAD} + {SRC_OCUPACION}")
               if len(meses) else "Ventana coincidente: sep 2025 – dic 2025")
    if not len(meses) or subdestino is None or f.tipo is None:
        msg = ("Sin dato · el rango elegido no incluye la ventana sep–dic 2025"
               if not len(meses) else theme.ETIQUETA_SIN_DATO)
        return fig_cruce(None, subdestino, f.tipo, periodo, mensaje_vacio=msg), texto_cruce(None, subdestino, f.tipo)
    cruce = oo.datos_cruce(mov, ocup, subdestino, f.tipo, meses)
    if not cob.empty:   # meses que la tabla de cobertura marca sin dato -> NaN (nunca 0)
        sin_mov = cb.meses_sin_dato(cob, "movilidad_mensual", meses.min(), meses.max())
        sin_oc = cb.meses_sin_dato(cob, "ocupacion", meses.min(), meses.max())
        cruce.loc[cruce["anio_mes"].isin(sin_mov), "visitantes"] = np.nan
        cruce.loc[cruce["anio_mes"].isin(sin_oc), "ocupacion_pct"] = np.nan
    return fig_cruce(cruce, subdestino, f.tipo, periodo), texto_cruce(oo.describir_relacion(cruce), subdestino,
                                                                        f.tipo)


def construir_subdestinos(mov: pd.DataFrame, cob: pd.DataFrame, f: Filtros, mes: Optional[str],
                          resaltado: Optional[str]) -> go.Figure:
    meses = meses_movilidad(cob, f) if not cob.empty else meses_filtro(f)
    if mes in (None, oo.PROMEDIO):
        periodo = theme.subtitulo_periodo(f.mes_ini, f.mes_fin, SRC_MOVILIDAD)
        detalle = f"Promedio mensual de {len(meses)} meses observados (no es suma)"
        mes = oo.PROMEDIO
    else:
        periodo = theme.subtitulo_periodo(mes, mes, SRC_MOVILIDAD)
        detalle = "Mes seleccionado"
    if f.tipo is None or len(meses) == 0:
        return fig_subdestinos(None, f.tipo, periodo, resaltado, detalle)
    return fig_subdestinos(oo.afluencia_subdestinos(mov, f.tipo, meses, mes), f.tipo, periodo, resaltado, detalle)


def construir_estacionalidad(mov: pd.DataFrame, ocup: pd.DataFrame, cob: pd.DataFrame, f: Filtros,
                             subdestino: Optional[str], anio_sel: Optional[int]) -> go.Figure:
    meses = meses_movilidad(cob, f) if not cob.empty else meses_filtro(f)
    ie_ocup = oo.indice_estacional_ocupacion(oo.serie_ocupacion(ocup))
    periodo_vis = cb.texto_tramos(meses) if len(meses) else theme.ETIQUETA_SIN_DATO
    ie_vis = (oo.indice_estacional_visitantes(mov, subdestino, f.tipo, meses)
              if subdestino and f.tipo and len(meses) else None)
    return fig_estacionalidad(ie_ocup, ie_vis, subdestino, f.tipo, periodo_vis, anio_sel)


def texto_seleccion(anio: Optional[int], sub: Optional[str], mes: Optional[str]) -> str:
    partes = []
    if anio is not None:
        partes.append(f"año {anio} (capacidad → ocupación y estacionalidad)")
    if sub:
        partes.append(f"subdestino {oo.nombre_subdestino(sub)} (subdestinos → cruce y estacionalidad)")
    if mes and mes != oo.PROMEDIO:
        partes.append(f"mes {theme.etiqueta_mes(mes)} (cruce → subdestinos)")
    if not partes:
        return ("Sin selección. Haga clic en un año de «Capacidad», en un mes del «Cruce» o en un "
                "subdestino para filtrar los demás gráficos.")
    return "Selección activa: " + "; ".join(partes) + "."


# ==================================================================== layout
def _tarjeta(hijos: list) -> dbc.Card:
    # La tarjeta puede incluir una nota posterior a la gráfica. Una altura forzada la hacía
    # invadir la siguiente sección en pantallas anchas.
    return dbc.Card(dbc.CardBody(hijos), className="shadow-sm")


def _grafico(id_: str) -> dcc.Graph:
    return dcc.Graph(id=id_, config=_CONFIG_GRAFICO)


def _nota(texto: str) -> html.P:
    return html.P(texto, className="small mb-0 mt-2", style={"color": theme.TEXTO_SECUNDARIO})


def layout():
    """Layout estático del módulo; los callbacks lo llenan según el filtro global y los clics."""
    return html.Div([
        dcc.Store(id=ID_ANIO_SEL, data=None),
        dcc.Store(id=ID_SUB_SEL, data=None),
        html.H2("Oferta hotelera y desagregación territorial", className="h4 mt-3"),
        html.P("La oferta y la ocupación son del departamento de Alta Verapaz (el destino Cobán no es el "
               "departamento). La afluencia proviene de telefonía móvil por subdestino.",
               style={"color": theme.TEXTO_SECUNDARIO}),
        dbc.Alert("Mensaje clave: la ocupación hotelera de Alta Verapaz alcanzó 71 % en diciembre de 2025.",
                  color="light", className="small py-2"),
        dbc.Alert([
            html.Span(id=ID_SELECCION_TEXTO, className="me-2"),
            dbc.Button("Quitar selección", id=ID_LIMPIAR, size="sm", color="secondary", outline=True,
                       n_clicks=0),
        ], color="light", className="small py-2"),

        html.H3("A. Capacidad instalada (inventario anual)", className="h5 mt-2"),
        _tarjeta([
            dbc.Row([
                dbc.Col([html.Label("Medida", className="fw-semibold small"),
                         dbc.RadioItems(id=ID_METRICA, inline=True, value="habitaciones",
                                        options=[{"label": v, "value": k} for k, v in oo.METRICAS_OFERTA.items()])],
                        xs=12, md=7),
                dbc.Col(dbc.Checklist(id=ID_INCLUIR_2026, switch=True, value=[],
                                      options=[{"label": "Mostrar 2026 (corte parcial del 1.er trimestre)",
                                                "value": "2026"}]),
                        xs=12, md=5, className="mt-2 mt-md-4"),
            ]),
            _grafico(ID_G_CAPACIDAD),
            _nota("Cortes anuales de inventario (uno por año): se comparan años, no se dibuja una tendencia. "
                  "2026 es un corte parcial y cerca de la mitad de las combinaciones del país repiten el valor de "
                  "2025: por eso se excluye por defecto. " + NOTA_AIRBNB + " Haga clic en un año para resaltarlo "
                  "en la ocupación y la estacionalidad."),
        ]),

        html.H3("B. Ocupación hotelera mensual 2023–2025", className="h5 mt-4"),
        _tarjeta([
            dbc.Row([
                dbc.Col(dbc.Checklist(id=ID_COMPARAR, switch=True, value=["promedio"],
                                      options=[{"label": "Comparar con el promedio simple de los 22 departamentos",
                                                "value": "promedio"}]), xs=12, md=7),
                dbc.Col(dbc.RadioItems(id=ID_VISTA_OCUP, inline=True, value="completa",
                                       options=[{"label": "Serie completa 2023–2025", "value": "completa"},
                                                {"label": "Solo meses del filtro", "value": "rango"}]),
                        xs=12, md=5),
            ]),
            _grafico(ID_G_OCUPACION),
            _nota("Serie observada, sin proyecciones. El archivo no trae un índice nacional: la línea punteada es "
                  "la media simple de los 22 departamentos y no equivale al índice nacional oficial. Triángulos: mes "
                  "pico y mes valle de cada año. La banda celeste marca sep–dic 2025, único período con movilidad."),
        ]),

        html.H3("C. Ventana coincidente: afluencia vs. ocupación (sep–dic 2025)", className="h5 mt-4"),
        dbc.Row([
            dbc.Col(_tarjeta([_grafico(ID_G_CRUCE),
                              _nota("Dos paneles alineados por mes con ejes separados (personas y %). No existe "
                                    "un total del destino en la fuente: se muestra el subdestino y el tipo del "
                                    "filtro (o el subdestino elegido en «Subdestinos»). Haga clic en un mes para "
                                    "verlo en «Subdestinos».")]), xs=12, lg=7, className="mb-3"),
            dbc.Col(_tarjeta([html.H4("Lectura del cruce", className="h6"), html.Div(id=ID_TEXTO_CRUCE)]),
                    xs=12, lg=5, className="mb-3"),
        ]),

        html.H3("D. Subdestinos: afluencia relativa", className="h5 mt-2"),
        _tarjeta([
            html.Label("Mes", htmlFor=ID_MES_SUB, className="fw-semibold small"),
            dcc.Dropdown(id=ID_MES_SUB, value=oo.PROMEDIO, clearable=False, options=[]),
            _grafico(ID_G_SUBDESTINOS),
            _nota("Cobán, Lanquín y Cuevas de Candelaria se comparan entre sí; nunca se suman (una persona puede "
                  "estar en varios). Nacionales y extranjeros se ven por separado con el filtro «Tipo»; los "
                  "nacionales llevan factor de expansión. Haga clic en una barra para usar ese subdestino en el "
                  "cruce y la estacionalidad."),
        ]),

        html.H3("E. Estacionalidad de la ocupación frente a la de los visitantes", className="h5 mt-4"),
        _tarjeta([
            _grafico(ID_G_ESTACIONAL),
            _nota("Cada serie se divide entre su propia media (= 100) para comparar la forma de la temporada, no el "
                  "volumen. El perfil de visitantes es compuesto: sep–dic vienen de 2025 y mar–ago de 2026 (ningún "
                  "mes se repite, no hay comparación interanual); ene y feb no tienen cobertura."),
        ]),
    ])


# ================================================================== callbacks
def registrar_callbacks(app) -> None:
    """Registra los callbacks del módulo (solo leen ``store-filtros``)."""

    @app.callback(Output(ID_ANIO_SEL, "data"),
                  Input(ID_G_CAPACIDAD, "clickData"), Input(ID_LIMPIAR, "n_clicks"),
                  State(ID_ANIO_SEL, "data"), prevent_initial_call=True)
    def _anio(click, _n, actual):
        if ctx.triggered_id == ID_LIMPIAR:
            return None
        nuevo = valor_desde_click(click)
        return alternar(actual, int(nuevo) if nuevo is not None else None)

    @app.callback(Output(ID_SUB_SEL, "data"),
                  Input(ID_G_SUBDESTINOS, "clickData"), Input(ID_LIMPIAR, "n_clicks"),
                  Input(ID_STORE_FILTROS, "data"), State(ID_SUB_SEL, "data"), prevent_initial_call=True)
    def _sub(click, _n, _estado, actual):
        if ctx.triggered_id != ID_G_SUBDESTINOS:
            return None
        nuevo = valor_desde_click(click)
        return alternar(actual, nuevo if nuevo in oo.SUBDESTINOS else None)

    @app.callback(Output(ID_MES_SUB, "options"), Output(ID_MES_SUB, "value"),
                  Input(ID_STORE_FILTROS, "data"), Input(ID_G_CRUCE, "clickData"),
                  Input(ID_G_OCUPACION, "clickData"), Input(ID_LIMPIAR, "n_clicks"),
                  State(ID_MES_SUB, "value"))
    def _meses(estado, click_cruce, click_ocup, _n, actual):
        f = Filtros.desde_dict(estado)
        meses = meses_movilidad(cb.cargar(), f)
        validos = {f"{m:%Y-%m}" for m in meses}
        valor = actual if actual in validos else oo.PROMEDIO
        if ctx.triggered_id == ID_LIMPIAR:
            valor = oo.PROMEDIO
        elif ctx.triggered_id in (ID_G_CRUCE, ID_G_OCUPACION):
            mes = mes_desde_click(click_cruce if ctx.triggered_id == ID_G_CRUCE else click_ocup)
            if mes in validos:      # un mes sin movilidad (p. ej. 2024) no cambia la vista
                valor = mes
        return opciones_mes(meses), valor

    @app.callback(Output(ID_G_CAPACIDAD, "figure"),
                  Input(ID_METRICA, "value"), Input(ID_INCLUIR_2026, "value"), Input(ID_ANIO_SEL, "data"))
    def _capacidad(metrica, incluir, anio):
        cap = oo.capacidad_por_anio(_leer("oferta"), incluir_parcial="2026" in (incluir or []))
        return fig_capacidad(cap, metrica or "habitaciones", anio)

    @app.callback(Output(ID_G_OCUPACION, "figure"),
                  Input(ID_STORE_FILTROS, "data"), Input(ID_COMPARAR, "value"), Input(ID_VISTA_OCUP, "value"),
                  Input(ID_ANIO_SEL, "data"))
    def _ocupacion(estado, comparar, vista, anio):
        f = Filtros.desde_dict(estado)
        return construir_ocupacion(_leer("ocupacion"), f, "promedio" in (comparar or []), vista or "completa", anio)

    @app.callback(Output(ID_G_CRUCE, "figure"), Output(ID_TEXTO_CRUCE, "children"),
                  Input(ID_STORE_FILTROS, "data"), Input(ID_SUB_SEL, "data"))
    def _cruce(estado, sub_sel):
        f = Filtros.desde_dict(estado)
        return construir_cruce(_leer("movilidad_subdestino_mes"), _leer("ocupacion"), cb.cargar(), f,
                               subdestino_efectivo(sub_sel, f))

    @app.callback(Output(ID_G_SUBDESTINOS, "figure"),
                  Input(ID_STORE_FILTROS, "data"), Input(ID_MES_SUB, "value"), Input(ID_SUB_SEL, "data"))
    def _subdestinos(estado, mes, sub_sel):
        f = Filtros.desde_dict(estado)
        return construir_subdestinos(_leer("movilidad_subdestino_mes"), cb.cargar(), f, mes,
                                     subdestino_efectivo(sub_sel, f))

    @app.callback(Output(ID_G_ESTACIONAL, "figure"),
                  Input(ID_STORE_FILTROS, "data"), Input(ID_SUB_SEL, "data"), Input(ID_ANIO_SEL, "data"))
    def _estacional(estado, sub_sel, anio):
        f = Filtros.desde_dict(estado)
        return construir_estacionalidad(_leer("movilidad_subdestino_mes"), _leer("ocupacion"), cb.cargar(), f,
                                        subdestino_efectivo(sub_sel, f), anio)

    @app.callback(Output(ID_SELECCION_TEXTO, "children"),
                  Input(ID_ANIO_SEL, "data"), Input(ID_SUB_SEL, "data"), Input(ID_MES_SUB, "value"))
    def _texto(anio, sub, mes):
        return texto_seleccion(anio, sub, mes)
