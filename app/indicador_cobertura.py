"""Indicador de cobertura por fuente (barra superior, visible en todas las pestañas).

Una fila de «chips», uno por fuente (movilidad, movilidad diaria, ocupación, oferta, migración y las
fuentes extra que traiga la tabla). Cada chip dice si la fuente tiene dato en el rango de meses del
filtro global:

* ✓ verde       -> dato en todo el rango
* ◐ verde claro -> dato parcial (algunos meses, o meses incompletos)
* — gris        -> sin dato en el rango (no es cero)

El tooltip muestra el período que cubre la fuente y los meses del rango sin dato.

Integración: ``main.py`` llama a ``registrar_callbacks(app)``; el callback lee ``store-filtros`` y
escribe en ``slot-cobertura`` (solo este módulo escribe ahí). La lógica vive en
``app/utils/cobertura.py``.
"""
from __future__ import annotations

from typing import Optional

import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, html

from app import theme
from app.theme import ID_SLOT_COBERTURA, ID_STORE_FILTROS
from app.utils import cobertura as cb
from app.utils.datos import Filtros

PREFIJO_CHIP = "cob-chip-"
SIMBOLOS = {cb.COMPLETA: "✓", cb.PARCIAL: "◐", cb.SIN_DATO: "—"}
TEXTO_ESTADO = {cb.COMPLETA: "con dato", cb.PARCIAL: "dato parcial", cb.SIN_DATO: "sin dato"}

_BASE_CHIP = {"display": "inline-block", "borderRadius": "999px", "padding": "2px 10px",
              "margin": "2px 4px 2px 0", "fontSize": "12px", "fontWeight": 600, "cursor": "help",
              "whiteSpace": "nowrap", "border": "1px solid transparent"}


def estilo_chip(estado: str) -> dict:
    """Estilo del chip según el estado (pares de color AA definidos en theme)."""
    if estado == cb.COMPLETA:
        extra = {"backgroundColor": theme.COBERTURA_FONDO, "color": theme.COBERTURA_TEXTO}
    elif estado == cb.PARCIAL:
        extra = {"backgroundColor": theme.COBERTURA_PARCIAL_FONDO, "color": theme.COBERTURA_TEXTO,
                 "border": f"1px dashed {theme.COBERTURA_TEXTO}"}
    else:
        extra = {"backgroundColor": theme.COBERTURA_SIN_DATO_FONDO, "color": theme.COLOR_SIN_DATO_TEXTO,
                 "fontWeight": 500}
    return {**_BASE_CHIP, **extra}


def chips(estado: pd.DataFrame, f: Optional[Filtros] = None) -> html.Div:
    """Componente con un chip por fuente y su tooltip. ``estado`` = ``cobertura.estado_fuentes``."""
    if estado is None or estado.empty:
        return html.Div("Cobertura: sin tabla de cobertura (ejecute el ETL).", className="small",
                        style={"color": theme.TEXTO_SOBRE_ENCABEZADO})
    periodo = (theme.subtitulo_periodo(f.mes_ini, f.mes_fin)
               if f is not None and f.mes_ini is not None else "Período: todo")
    hijos = []
    for _, fila in estado.iterrows():
        id_chip = f"{PREFIJO_CHIP}{fila['fuente']}"
        texto = f"{SIMBOLOS[fila['estado']]} {fila['etiqueta']}"
        hijos.append(html.Span(
            texto, id=id_chip, tabIndex=0, style=estilo_chip(fila["estado"]),
            **{"aria-label": f"{fila['etiqueta']}: {TEXTO_ESTADO[fila['estado']]}",
               "data-estado": fila["estado"]}))
        hijos.append(dbc.Tooltip(cb.texto_tooltip(fila), target=id_chip, placement="bottom"))
    return html.Div([
        html.Div(f"Cobertura por fuente · {periodo}", className="small mb-1",
                 style={"color": theme.TEXTO_SOBRE_ENCABEZADO, "opacity": 0.9}),
        html.Div(hijos, role="list", **{"aria-label": "Cobertura de datos por fuente"}),
    ])


def contenido(estado_filtros: Optional[dict], cob: Optional[pd.DataFrame] = None) -> html.Div:
    """Chips para el estado del Store de filtros (función pura salvo la lectura de la tabla)."""
    f = Filtros.desde_dict(estado_filtros)
    cob = cb.cargar() if cob is None else cob
    return chips(cb.estado_fuentes(cob, f.mes_ini, f.mes_fin), f)


def registrar_callbacks(app) -> None:
    """El slot del encabezado se actualiza con cada cambio del filtro global."""

    @app.callback(Output(ID_SLOT_COBERTURA, "children"), Input(ID_STORE_FILTROS, "data"))
    def _indicador(estado):
        return contenido(estado)
