"""Tema visual del Observatorio: paleta, plantilla Plotly y utilidades de rotulado.

Reglas de color (ver docs/paleta.md):
* COLOR_ESTIMACION (y sus variantes) es EXCLUSIVO de cifras estimadas: nunca se
  usa para dato observado, categorías ni escalas de volumen.
* COLOR_SIN_DATO (gris) representa ausencia de dato; la ausencia nunca se dibuja como 0.
* Los textos usan solo pares de color que cumplen contraste WCAG AA (>= 4.5:1).

Este módulo solo depende de plotly y pandas (no de Dash).
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# --------------------------------------------------------------------------- IDs
# Identificadores compartidos con los módulos (P2/P3/P4). Los módulos deben usar
# estas constantes y no redefinir los IDs de los filtros globales.
ID_STORE_FILTROS = "store-filtros"      # dcc.Store con {mes_ini, mes_fin, tipo, subdestino}
ID_SLOT_COBERTURA = "slot-cobertura"    # espacio reservado al indicador de cobertura (P3)

# ------------------------------------------------------------------------ colores
# Neutros e institucionales
FONDO = "#FFFFFF"
FONDO_PAGINA = "#F5F7FA"
ENCABEZADO = "#0B3C5D"
TEXTO_SOBRE_ENCABEZADO = "#FFFFFF"
TEXTO = "#1F2933"
TEXTO_SECUNDARIO = "#4B5563"
COLOR_GRILLA = "#E5E7EB"
COLOR_EJE = "#9CA3AF"

# Dato observado (color primario) y categorías (base Okabe-Ito, apta para daltonismo).
# Se omiten el naranja y el amarillo de Okabe-Ito para no acercarse al color de estimación.
COLOR_OBSERVADO = "#0072B2"
CATEGORICOS = ("#0072B2", "#009E73", "#56B4E9", "#CC79A7", "#44546A")

# Escala secuencial para volumen (claro = poco, oscuro = mucho). Solo azules.
SECUENCIAL = ("#EAF2F8", "#C6DBEF", "#9ECAE1", "#6BAED6", "#3182BD", "#08519C")
ESCALA_VOLUMEN = [[i / (len(SECUENCIAL) - 1), c] for i, c in enumerate(SECUENCIAL)]

# EXCLUSIVO de estimaciones
COLOR_ESTIMACION = "#D55E00"
COLOR_ESTIMACION_BANDA = "rgba(213, 94, 0, 0.18)"   # banda de error / relleno
COLOR_ESTIMACION_TEXTO = "#A33F00"                  # variante oscura para texto (AA)
COLORES_ESTIMACION = frozenset({COLOR_ESTIMACION.lower(), COLOR_ESTIMACION_BANDA.lower(),
                                COLOR_ESTIMACION_TEXTO.lower()})

# Ausencia de dato
COLOR_SIN_DATO = "#9AA0A6"          # relleno / líneas
COLOR_SIN_DATO_TEXTO = "#5F6368"    # texto (AA sobre blanco)

ETIQUETA_ESTIMACION = "Estimación"
ETIQUETA_SIN_DATO = "Sin dato"

# Indicador de cobertura por fuente (P3): chips claros sobre el encabezado oscuro.
# Verde = la fuente tiene dato; gris = sin dato. El estado también va en texto (✓ / ◐ / —),
# así que no depende solo del color.
COBERTURA_TEXTO = "#0F5132"          # verde oscuro (texto de chips con dato)
COBERTURA_FONDO = "#D1E7DD"          # verde claro (dato completo)
COBERTURA_PARCIAL_FONDO = "#F1F8F4"  # verde muy claro + borde discontinuo (dato parcial)
COBERTURA_SIN_DATO_FONDO = "#E5E7EB"  # gris (sin dato)

# Pares (nombre, texto, fondo) que se usan para texto y deben cumplir AA.
PARES_TEXTO_AA = (
    ("texto/fondo", TEXTO, FONDO),
    ("texto/fondo_pagina", TEXTO, FONDO_PAGINA),
    ("texto_secundario/fondo", TEXTO_SECUNDARIO, FONDO),
    ("texto_secundario/fondo_pagina", TEXTO_SECUNDARIO, FONDO_PAGINA),
    ("encabezado", TEXTO_SOBRE_ENCABEZADO, ENCABEZADO),
    ("estimacion_texto/fondo", COLOR_ESTIMACION_TEXTO, FONDO),
    ("estimacion_texto/fondo_pagina", COLOR_ESTIMACION_TEXTO, FONDO_PAGINA),
    ("sin_dato_texto/fondo", COLOR_SIN_DATO_TEXTO, FONDO),
    ("sin_dato_texto/fondo_pagina", COLOR_SIN_DATO_TEXTO, FONDO_PAGINA),
    ("cobertura/completa", COBERTURA_TEXTO, COBERTURA_FONDO),
    ("cobertura/parcial", COBERTURA_TEXTO, COBERTURA_PARCIAL_FONDO),
    ("cobertura/sin_dato", COLOR_SIN_DATO_TEXTO, COBERTURA_SIN_DATO_FONDO),
)

FUENTE = "Inter, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"


# ---------------------------------------------------------------------- contraste
def _canal_lineal(c: int) -> float:
    x = c / 255
    return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4


def luminancia_relativa(hex_color: str) -> float:
    """Luminancia relativa WCAG 2.x de un color '#RRGGBB'."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Color HEX inválido: {hex_color!r}")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _canal_lineal(r) + 0.7152 * _canal_lineal(g) + 0.0722 * _canal_lineal(b)


def razon_contraste(color_a: str, color_b: str) -> float:
    """Razón de contraste WCAG entre dos colores (1 a 21)."""
    la, lb = luminancia_relativa(color_a), luminancia_relativa(color_b)
    claro, oscuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (oscuro + 0.05)


def cumple_aa(texto: str, fondo: str, texto_grande: bool = False) -> bool:
    """True si el par cumple WCAG AA (4.5:1; 3:1 para texto grande)."""
    return razon_contraste(texto, fondo) >= (3.0 if texto_grande else 4.5)


# ----------------------------------------------------------------------- plantilla
NOMBRE_PLANTILLA = "observatorio"

_eje = dict(gridcolor=COLOR_GRILLA, linecolor=COLOR_EJE, zeroline=False,
            ticks="outside", tickcolor=COLOR_EJE, automargin=True,
            title=dict(font=dict(size=12, color=TEXTO_SECUNDARIO)))

PLANTILLA = go.layout.Template(
    layout=go.Layout(
        font=dict(family=FUENTE, size=13, color=TEXTO),
        colorway=list(CATEGORICOS),
        paper_bgcolor=FONDO,
        plot_bgcolor=FONDO,
        margin=dict(l=56, r=24, t=72, b=56),
        title=dict(x=0, xanchor="left", font=dict(size=16, color=TEXTO)),
        xaxis=_eje,
        yaxis=_eje,
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0, font=dict(size=12)),
        hoverlabel=dict(font=dict(family=FUENTE, size=12), bgcolor=FONDO, bordercolor=COLOR_EJE),
        colorscale=dict(sequential=ESCALA_VOLUMEN),
    )
)
pio.templates[NOMBRE_PLANTILLA] = PLANTILLA


def aplicar_plantilla(fig: go.Figure) -> go.Figure:
    """Aplica la plantilla común a una figura y la devuelve."""
    fig.update_layout(template=PLANTILLA)
    return fig


# ------------------------------------------------------------- rótulos y subtítulos
_MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def etiqueta_mes(valor: Any, corta: bool = False) -> str:
    """'sep 2025' (o 'sep 25' si ``corta``) a partir de una fecha o texto 'YYYY-MM'."""
    ts = pd.Timestamp(valor)
    if pd.isna(ts):
        raise ValueError(f"Mes inválido: {valor!r}")
    anio = f"{ts.year % 100:02d}" if corta else str(ts.year)
    return f"{_MESES[ts.month - 1]} {anio}"


def subtitulo_periodo(mes_ini: Any = None, mes_fin: Any = None, fuente: Optional[str] = None) -> str:
    """Texto de período para el subtítulo de cada visual (regla 11).

    Ej.: 'Período: sep 2025 – dic 2025 · Fuente: movilidad_mensual'.
    """
    if mes_ini is None and mes_fin is None:
        texto = "Período: sin definir"
    else:
        ini = etiqueta_mes(mes_ini if mes_ini is not None else mes_fin)
        fin = etiqueta_mes(mes_fin if mes_fin is not None else mes_ini)
        texto = f"Período: {ini}" if ini == fin else f"Período: {ini} – {fin}"
    return f"{texto} · Fuente: {fuente}" if fuente else texto


def titulo_con_subtitulo(titulo: str, subtitulo: Optional[str] = None) -> str:
    """Título Plotly con subtítulo en una segunda línea más pequeña."""
    return f"{titulo}<br><sup>{subtitulo}</sup>" if subtitulo else titulo


def rotulo_estimacion(texto: Optional[str] = None) -> str:
    """'Estimación' o '<texto> · Estimación' (regla 5)."""
    return f"{texto} · {ETIQUETA_ESTIMACION}" if texto else ETIQUETA_ESTIMACION


def estilo_estimacion() -> dict:
    """Estilo común de trazos de estimación: línea punteada + banda, solo color de estimación.

    Uso: ``go.Scatter(line=estilo['line'], ...)`` y ``fillcolor=estilo['fillcolor']`` en la banda.
    El trazo discontinuo evita depender solo del color para distinguir la estimación.
    """
    return {"line": dict(color=COLOR_ESTIMACION, dash="dash", width=2.5),
            "fillcolor": COLOR_ESTIMACION_BANDA}


def figura_sin_dato(titulo: str, periodo: Optional[str] = None, mensaje: str = ETIQUETA_SIN_DATO,
                    altura: int = 320) -> go.Figure:
    """Figura vacía con el rótulo 'Sin dato' (nunca ejes en cero ni líneas planas).

    ``periodo`` es el subtítulo de período (ver ``subtitulo_periodo``).
    """
    fig = go.Figure()
    fig.update_layout(
        template=PLANTILLA,
        title=dict(text=titulo_con_subtitulo(titulo, periodo)),
        height=altura,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[dict(text=mensaje, xref="paper", yref="paper", x=0.5, y=0.5,
                          showarrow=False, font=dict(size=22, color=COLOR_SIN_DATO_TEXTO))],
    )
    return fig
