"""Aplicación Dash del Observatorio de Inteligencia Turística — Cobán y Alta Verapaz.

Ejecución local:  python -m app.main      (http://localhost:8050)
Producción:       gunicorn app.main:server

PATRÓN PARA AGREGAR UN MÓDULO (P3/P4) SIN TOCAR main.py
--------------------------------------------------------
Cree ``app/modulo3.py`` (o modulo4.py; modulo1/2 son de P2) con esta forma. main.py
lo descubre por nombre, inserta su layout en la pestaña correspondiente y llama a
``registrar_callbacks``. Mientras el archivo no exista se muestra "En construcción".

    from dash import Input, Output, dcc, html
    from app.theme import ID_STORE_FILTROS, figura_sin_dato, subtitulo_periodo
    from app.utils import datos
    from app.utils.datos import Filtros

    def layout():                                   # sin argumentos; devuelve un componente
        return html.Div([dcc.Graph(id="m3-serie")])  # prefije TODOS sus ids con "m3-"

    def registrar_callbacks(app):                   # opcional; recibe la instancia Dash
        @app.callback(Output("m3-serie", "figure"), Input(ID_STORE_FILTROS, "data"))
        def _serie(estado):
            f = Filtros.desde_dict(estado)          # mes_ini, mes_fin, tipo, subdestino
            df = datos.filtrar_mensual(datos.cargar("ocupacion"), f)
            if df.empty:                            # sin cobertura: "Sin dato", jamás 0
                return figura_sin_dato("Ocupación", subtitulo_periodo(f.mes_ini, f.mes_fin))
            ...

Filtros globales: el único estado compartido es el dcc.Store ``store-filtros``. Los módulos
solo LO LEEN (Input); nunca escriben en él. Un filtro ``None`` es "sin restricción", no
"sumar": no agregue subdestinos ni tipos entre sí. Cada módulo debe verificar que sus IDs no
choquen con los demás (crear_app lanza ValueError si hay IDs repetidos).
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional, Sequence

import dash_bootstrap_components as dbc
import pandas as pd
from dash import Dash, Input, Output, dcc, html

from app import indicador_cobertura, theme
from app.theme import ID_SLOT_COBERTURA, ID_STORE_FILTROS
from app.utils import datos
from app.utils.datos import Filtros

TITULO = "Observatorio de Inteligencia Turística — Cobán y Alta Verapaz"
FUENTE_OPCIONES = "movilidad_subdestino_mes"   # de aquí salen meses, tipos y subdestinos
DESTINO_CLAVE = "alta_verapaz"                 # única clave de destino del Grupo 4
TIPOS_VALIDOS = ("extranjero", "nacional")     # excluye 'sin_dato'; nunca se suman entre sí

ID_FILTRO_MESES = "filtro-meses"
ID_FILTRO_TIPO = "filtro-tipo"
ID_FILTRO_SUBDESTINO = "filtro-subdestino"
ID_PERIODO_CUBIERTO = "periodo-cubierto"
ID_PERIODO_SELECCIONADO = "periodo-seleccionado"
ID_AVISO_HUECOS = "aviso-huecos"
ID_TABS = "tabs-modulos"


@dataclass(frozen=True)
class Modulo:
    """Pestaña del tablero. ``archivo`` es el módulo Python que la implementa."""
    id: str
    etiqueta: str
    archivo: str


MODULOS = (
    Modulo("demanda", "1 Demanda y mercados", "app.modulo1"),
    Modulo("dinamica", "2 Dinámica y pronóstico", "app.modulo2"),
    Modulo("oferta", "3 Oferta y territorio", "app.modulo3"),
    Modulo("reto", "4 Reto de Cobán y Alta Verapaz", "app.modulo4"),
)


# ------------------------------------------------------------------------ opciones
@dataclass(frozen=True, eq=False)
class Opciones:
    """Valores disponibles para los filtros, leídos de los datos (no inventados)."""
    meses: pd.DatetimeIndex
    tipos: tuple
    subdestinos: tuple

    @property
    def vacio(self) -> bool:
        return len(self.meses) == 0 or not self.tipos or not self.subdestinos


def cargar_opciones(df: Optional[pd.DataFrame] = None) -> Opciones:
    """Meses observados, tipos y subdestinos de Alta Verapaz.

    Sin ``df`` lee el parquet; si falta, devuelve vacío. Solo se usan filas con
    ``destino_clave == DESTINO_CLAVE`` y ``tipo`` en ``TIPOS_VALIDOS`` (se excluyen otros
    destinos y ``sin_dato``). La tabla compartida trae todos los destinos: sin este filtro
    los selectores mostrarían destinos ajenos al Grupo 4.
    """
    if df is None:
        try:
            df = datos.cargar(FUENTE_OPCIONES)
        except FileNotFoundError:
            return Opciones(pd.DatetimeIndex([]), (), ())
    if "destino_clave" not in df.columns:
        raise KeyError("La tabla de opciones debe tener la columna 'destino_clave'.")
    df = df[(df["destino_clave"] == DESTINO_CLAVE) & df["tipo"].isin(TIPOS_VALIDOS)]
    presentes = set(datos.tipos_disponibles(df))
    return Opciones(datos.meses_observados(df),
                    tuple(t for t in TIPOS_VALIDOS if t in presentes),
                    tuple(datos.subdestinos_disponibles(df)))


def valores_iniciales(opciones: Opciones) -> Filtros:
    """Filtros iniciales: todo el rango observado, UN tipo y UN subdestino (nunca sumados)."""
    if opciones.vacio:
        return Filtros()
    tipo = "extranjero" if "extranjero" in opciones.tipos else opciones.tipos[0]  # siempre en opciones
    return Filtros(mes_ini=opciones.meses.min(), mes_fin=opciones.meses.max(),
                   tipo=tipo, subdestino=opciones.subdestinos[0])


def calendario(opciones: Opciones) -> pd.DatetimeIndex:
    """Todos los meses entre el primero y el último observado (incluye los huecos)."""
    if len(opciones.meses) == 0:
        return pd.DatetimeIndex([])
    return datos.rango_meses(opciones.meses.min(), opciones.meses.max())


def meses_sin_cobertura(mes_ini: Any, mes_fin: Any, observados: pd.DatetimeIndex) -> list:
    """Meses del rango [mes_ini, mes_fin] que no tienen dato en ``observados``."""
    rango = datos.rango_meses(mes_ini, mes_fin)
    return list(rango.difference(pd.DatetimeIndex(observados)))


def texto_cobertura(opciones: Opciones) -> str:
    """Resumen del período cubierto por la fuente de movilidad (encabezado)."""
    if len(opciones.meses) == 0:
        return "Sin datos de movilidad cargados"
    return (f"Movilidad: {theme.etiqueta_mes(opciones.meses.min())} – "
            f"{theme.etiqueta_mes(opciones.meses.max())} · {len(opciones.meses)} meses observados")


def estado_desde_controles(rango: Any, tipo: Optional[str], subdestino: Optional[str],
                           meses_cal: pd.DatetimeIndex, observados: pd.DatetimeIndex):
    """Convierte los controles en (estado del Store, texto de período, aviso de huecos).

    Función pura (sin Dash) para poder probarla. ``rango`` son dos índices del calendario.
    """
    if len(meses_cal) == 0:
        return Filtros(tipo=tipo, subdestino=subdestino).a_dict(), "Período: sin datos", ""
    n = len(meses_cal)
    try:
        i, j = sorted(int(v) for v in rango)
    except (TypeError, ValueError):
        i, j = 0, n - 1
    i, j = max(0, min(i, n - 1)), max(0, min(j, n - 1))
    ini, fin = meses_cal[i], meses_cal[j]
    filtros = Filtros(mes_ini=ini, mes_fin=fin, tipo=tipo, subdestino=subdestino)
    huecos = meses_sin_cobertura(ini, fin, observados)
    aviso = ""
    if huecos:
        aviso = ("Sin dato de movilidad en: " + ", ".join(theme.etiqueta_mes(m) for m in huecos)
                 + ". Se muestran como «Sin dato», nunca como 0.")
    return filtros.a_dict(), theme.subtitulo_periodo(ini, fin), aviso


# ------------------------------------------------------------------------- módulos
def importar_modulo(nombre: str):
    """Importa ``nombre`` si existe; devuelve None si ese archivo aún no está creado."""
    try:
        return importlib.import_module(nombre)
    except ModuleNotFoundError as exc:
        if exc.name == nombre:
            return None
        raise  # el módulo existe pero falla una de sus importaciones: no ocultarlo


def descubrir_implementaciones() -> dict:
    """{id_modulo: módulo Python} para los módulos ya implementados."""
    encontrados = {}
    for m in MODULOS:
        impl = importar_modulo(m.archivo)
        if impl is not None:
            if not callable(getattr(impl, "layout", None)):
                raise AttributeError(f"{m.archivo} debe definir layout().")
            encontrados[m.id] = impl
    return encontrados


def en_construccion(modulo: Modulo) -> dbc.Alert:
    return dbc.Alert([html.H5(modulo.etiqueta, className="alert-heading"),
                      html.P("Módulo en construcción.", className="mb-0")],
                     color="light", className="mt-3")


# ------------------------------------------------------------- inspección de layout
def recorrer_componentes(nodo: Any) -> Iterator[Any]:
    """Recorre un árbol de componentes Dash siguiendo ``children``."""
    if nodo is None or isinstance(nodo, (str, int, float, bool)):
        return
    if isinstance(nodo, (list, tuple)):
        for hijo in nodo:
            yield from recorrer_componentes(hijo)
        return
    yield nodo
    yield from recorrer_componentes(getattr(nodo, "children", None))


def ids_del_layout(layout: Any) -> list:
    return [getattr(c, "id") for c in recorrer_componentes(layout) if getattr(c, "id", None) is not None]


def verificar_ids_unicos(layout: Any) -> None:
    """Lanza ValueError si algún ID de componente se repite."""
    vistos, repetidos = set(), set()
    for i in map(str, ids_del_layout(layout)):
        (repetidos if i in vistos else vistos).add(i)
    if repetidos:
        raise ValueError(f"IDs de componentes repetidos: {sorted(repetidos)}")


# ----------------------------------------------------------------------- layout
def _marcas(meses_cal: pd.DatetimeIndex, observados: pd.DatetimeIndex) -> dict:
    vistos = set(observados)
    marcas = {}
    for k, m in enumerate(meses_cal):
        estilo = {"fontSize": "11px", "color": theme.TEXTO_SECUNDARIO}
        if m not in vistos:
            estilo = {"fontSize": "11px", "color": theme.COLOR_SIN_DATO_TEXTO, "fontStyle": "italic"}
        marcas[k] = {"label": theme.etiqueta_mes(m, corta=True), "style": estilo}
    return marcas


def _panel_filtros(opciones: Opciones, inicial: Filtros, meses_cal: pd.DatetimeIndex):
    n = len(meses_cal)
    if n:
        i = int(meses_cal.get_loc(inicial.mes_ini))
        j = int(meses_cal.get_loc(inicial.mes_fin))
    else:
        i = j = 0
    return dbc.Card(dbc.CardBody(dbc.Row([
        dbc.Col([
            html.Label("Rango de meses", htmlFor=ID_FILTRO_MESES, className="fw-semibold"),
            dcc.RangeSlider(id=ID_FILTRO_MESES, min=0, max=max(n - 1, 0), step=1, value=[i, j],
                            marks=_marcas(meses_cal, opciones.meses), allowCross=False,
                            disabled=(n == 0)),
            html.Div(id=ID_PERIODO_SELECCIONADO, className="small",
                     style={"color": theme.TEXTO_SECUNDARIO}),
            html.Div(id=ID_AVISO_HUECOS, className="small",
                     style={"color": theme.COLOR_SIN_DATO_TEXTO, "fontStyle": "italic"}),
        ], xs=12, lg=6, className="mb-3 mb-lg-0"),
        dbc.Col([
            html.Label("Tipo de visitante", className="fw-semibold"),
            dbc.RadioItems(id=ID_FILTRO_TIPO, inline=True, value=inicial.tipo,
                           options=[{"label": t.capitalize(), "value": t} for t in opciones.tipos]),
            html.Div("Nacionales y extranjeros nunca se suman.", className="small",
                     style={"color": theme.TEXTO_SECUNDARIO}),
        ], xs=12, md=6, lg=3, className="mb-3 mb-lg-0"),
        dbc.Col([
            html.Label("Subdestino", htmlFor=ID_FILTRO_SUBDESTINO, className="fw-semibold"),
            dcc.Dropdown(id=ID_FILTRO_SUBDESTINO, value=inicial.subdestino, clearable=False,
                         options=[{"label": s, "value": s} for s in opciones.subdestinos]),
            html.Div("Los subdestinos no se suman para formar un total.", className="small",
                     style={"color": theme.TEXTO_SECUNDARIO}),
        ], xs=12, md=6, lg=3),
    ])), className="mb-3 shadow-sm")


def _encabezado(opciones: Opciones):
    return html.Div(dbc.Container(dbc.Row([
        dbc.Col([
            html.H1(TITULO, className="h3 mb-1", style={"color": theme.TEXTO_SOBRE_ENCABEZADO}),
            html.Div(texto_cobertura(opciones), id=ID_PERIODO_CUBIERTO, className="small",
                     style={"color": theme.TEXTO_SOBRE_ENCABEZADO}),
        ], xs=12, lg=7),
        dbc.Col(
            # Indicador de cobertura por fuente (P3): lo llena app/indicador_cobertura.py.
            html.Div("Cargando cobertura por fuente…", id=ID_SLOT_COBERTURA,
                     className="small text-lg-end",
                     style={"color": theme.TEXTO_SOBRE_ENCABEZADO}),
            xs=12, lg=5, className="mt-2 mt-lg-0"),
    ], align="center"), fluid=True), className="py-3 mb-3",
        style={"backgroundColor": theme.ENCABEZADO})


def construir_layout(opciones: Opciones, inicial: Filtros, contenidos: Sequence) -> html.Div:
    """Arma el layout. ``contenidos`` es una lista de (Modulo, componente) en orden de pestañas."""
    meses_cal = calendario(opciones)
    aviso_datos = []
    if opciones.vacio:
        aviso_datos = [dbc.Alert("No se encontraron datos en data/processed/. "
                                 "Genere los datos con `python -m etl.run_all`.", color="warning")]
    return html.Div([
        dcc.Store(id=ID_STORE_FILTROS, data=inicial.a_dict()),
        _encabezado(opciones),
        dbc.Container([
            *aviso_datos,
            _panel_filtros(opciones, inicial, meses_cal),
            dbc.Tabs([dbc.Tab(contenido, label=m.etiqueta, tab_id=m.id) for m, contenido in contenidos],
                     id=ID_TABS, active_tab=contenidos[0][0].id),
            html.Hr(),
            html.P("Ausencia de dato no es cero: los períodos sin cobertura se muestran como «Sin dato». "
                   "Toda cifra estimada se rotula «Estimación».", className="small",
                   style={"color": theme.TEXTO_SECUNDARIO}),
        ], fluid=True),
    ], style={"backgroundColor": theme.FONDO_PAGINA, "minHeight": "100vh", "color": theme.TEXTO,
              "fontFamily": theme.FUENTE})


# ------------------------------------------------------------------------- app
def crear_app(opciones: Optional[Opciones] = None,
              implementaciones: Optional[Mapping[str, Any]] = None) -> Dash:
    """Construye la aplicación.

    ``opciones`` e ``implementaciones`` permiten inyectar datos sintéticos y módulos de
    prueba; por defecto se leen los parquet y se descubren app/modulo1..4.py.
    """
    opciones = opciones if opciones is not None else cargar_opciones()
    implementaciones = descubrir_implementaciones() if implementaciones is None else implementaciones
    inicial = valores_iniciales(opciones)
    meses_cal = calendario(opciones)

    contenidos = []
    for m in MODULOS:
        impl = implementaciones.get(m.id)
        contenidos.append((m, impl.layout() if impl is not None else en_construccion(m)))

    aplicacion = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title=TITULO,
                      update_title=None,
                      meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])
    aplicacion.layout = construir_layout(opciones, inicial, contenidos)
    verificar_ids_unicos(aplicacion.layout)

    @aplicacion.callback(
        Output(ID_STORE_FILTROS, "data"),
        Output(ID_PERIODO_SELECCIONADO, "children"),
        Output(ID_AVISO_HUECOS, "children"),
        Input(ID_FILTRO_MESES, "value"),
        Input(ID_FILTRO_TIPO, "value"),
        Input(ID_FILTRO_SUBDESTINO, "value"),
    )
    def _actualizar_filtros(rango, tipo, subdestino):
        return estado_desde_controles(rango, tipo, subdestino, meses_cal, opciones.meses)

    # Callbacks de cada módulo implementado (cada uno solo LEE el Store).
    for m in MODULOS:
        registrar = getattr(implementaciones.get(m.id), "registrar_callbacks", None)
        if callable(registrar):
            registrar(aplicacion)

    # Indicador de cobertura del encabezado (todas las pestañas): único escritor de slot-cobertura.
    indicador_cobertura.registrar_callbacks(aplicacion)

    return aplicacion


app = crear_app()
server = app.server

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
