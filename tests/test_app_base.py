"""Pruebas de la base de la app (tema, layout, filtros). Sin navegador, servidor ni Parquet reales."""
import json
from types import SimpleNamespace

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.io as pio
import pytest
from dash import dcc, html

from app import main, theme
from app.utils.datos import Filtros

MESES_OBS = ["2025-09", "2025-10", "2025-11", "2025-12",
             "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]


@pytest.fixture
def df_sintetico():
    """Alta Verapaz (10 meses) + ruido que NO debe aparecer: otro destino, otros meses y 'sin_dato'."""
    filas = [("alta_verapaz", sub, tipo, pd.Timestamp(f"{m}-01"))
             for m in MESES_OBS
             for sub in ("Lanquin", "Coban", "Cuevas De Candelaria")
             for tipo in ("nacional", "extranjero")]
    ruido = [
        ("antigua", "Antigua Guatemala", "extranjero", pd.Timestamp("2025-01-01")),  # destino ajeno, mes ajeno
        ("antigua", "Antigua Guatemala", "nacional", pd.Timestamp("2025-10-01")),
        ("peten", "Flores", "extranjero", pd.Timestamp("2026-10-01")),
        ("alta_verapaz", "Coban", "sin_dato", pd.Timestamp("2025-02-01")),            # tipo inválido, mes ajeno
        ("alta_verapaz", "Lanquin", "sin_dato", pd.Timestamp("2025-09-01")),
    ]
    return pd.DataFrame(filas + ruido, columns=["destino_clave", "subdestino", "tipo", "anio_mes"]
                        ).assign(visitantes=1.0)


@pytest.fixture
def opciones(df_sintetico):
    return main.cargar_opciones(df_sintetico)


@pytest.fixture
def app_base(opciones):
    """App sin módulos implementados (todo en construcción), con opciones sintéticas."""
    return main.crear_app(opciones, implementaciones={})


def _buscar(layout, id_):
    return next(c for c in main.recorrer_componentes(layout) if getattr(c, "id", None) == id_)


# ------------------------------------------------------------------- pestañas y Store
def test_cuatro_pestanas(app_base):
    tabs = next(c for c in main.recorrer_componentes(app_base.layout) if isinstance(c, dbc.Tabs))
    etiquetas = [t.label for t in tabs.children]
    assert etiquetas == ["1 Demanda y mercados", "2 Dinámica y pronóstico",
                         "3 Oferta y territorio", "4 Reto de Cobán y Alta Verapaz"]
    assert [t.tab_id for t in tabs.children] == [m.id for m in main.MODULOS]


def test_modulos_sin_implementar_muestran_en_construccion(app_base):
    textos = []
    for c in main.recorrer_componentes(app_base.layout):
        hijos = getattr(c, "children", None)
        textos += [h for h in (hijos if isinstance(hijos, list) else [hijos]) if isinstance(h, str)]
    assert textos.count("Módulo en construcción.") == 4


def test_existe_store_con_filtros_iniciales(app_base):
    store = _buscar(app_base.layout, theme.ID_STORE_FILTROS)
    assert isinstance(store, dcc.Store)
    assert store.data == {"mes_ini": "2025-09", "mes_fin": "2026-08",
                          "tipo": "extranjero", "subdestino": "Coban"}


def test_valores_iniciales_no_suman_tipos_ni_subdestinos(opciones):
    f = main.valores_iniciales(opciones)
    assert f.tipo in opciones.tipos and f.subdestino in opciones.subdestinos
    assert f.tipo is not None and f.subdestino is not None


def test_opciones_salen_de_los_datos_sin_opcion_todos(app_base, opciones):
    assert opciones.tipos == ("extranjero", "nacional")
    assert opciones.subdestinos == ("Coban", "Cuevas De Candelaria", "Lanquin")
    tipo = _buscar(app_base.layout, main.ID_FILTRO_TIPO)
    sub = _buscar(app_base.layout, main.ID_FILTRO_SUBDESTINO)
    assert {o["value"] for o in tipo.options} == {"extranjero", "nacional"}
    assert {o["value"] for o in sub.options} == set(opciones.subdestinos)
    assert sub.clearable is False


def test_opciones_solo_alta_verapaz_y_tipos_validos(app_base, opciones):
    """Regresión: no mostrar destinos ajenos ni 'sin_dato' en los selectores."""
    assert opciones.subdestinos == ("Coban", "Cuevas De Candelaria", "Lanquin")
    assert opciones.tipos == ("extranjero", "nacional")
    assert opciones.meses.min() == pd.Timestamp("2025-09-01")   # ignora ene-2025 de otro destino
    assert opciones.meses.max() == pd.Timestamp("2026-08-01")   # ignora oct-2026 de otro destino
    assert len(opciones.meses) == 10
    tipo = _buscar(app_base.layout, main.ID_FILTRO_TIPO)
    sub = _buscar(app_base.layout, main.ID_FILTRO_SUBDESTINO)
    valores = {o["value"] for o in tipo.options} | {o["value"] for o in sub.options}
    assert valores.isdisjoint({"sin_dato", "Sin_dato", "Antigua Guatemala", "Flores"})
    assert not any("antigua" in str(o).lower() or "sin_dato" in str(o).lower()
                   for o in (*tipo.options, *sub.options))


def test_valores_iniciales_pertenecen_a_las_opciones(app_base, opciones):
    inicial = main.valores_iniciales(opciones)
    assert inicial.tipo in opciones.tipos
    assert inicial.subdestino in opciones.subdestinos
    assert inicial.mes_ini in set(opciones.meses) and inicial.mes_fin in set(opciones.meses)
    assert _buscar(app_base.layout, main.ID_FILTRO_TIPO).value in opciones.tipos
    assert _buscar(app_base.layout, main.ID_FILTRO_SUBDESTINO).value in opciones.subdestinos


def test_opciones_exigen_destino_clave():
    with pytest.raises(KeyError):
        main.cargar_opciones(pd.DataFrame({"subdestino": ["Coban"], "tipo": ["nacional"],
                                           "anio_mes": [pd.Timestamp("2025-09-01")]}))


def test_slider_cubre_calendario_con_huecos(app_base):
    slider = _buscar(app_base.layout, main.ID_FILTRO_MESES)
    assert slider.max == 11  # sep-2025 .. ago-2026 = 12 meses calendario (incluye ene-feb sin dato)
    assert slider.value == [0, 11]


def test_serializacion_del_estado_ida_y_vuelta(opciones):
    f = main.valores_iniciales(opciones)
    texto = json.dumps(f.a_dict())
    assert Filtros.desde_dict(json.loads(texto)) == f


# ---------------------------------------------------------------- lógica de filtros
def test_estado_desde_controles_rango_con_huecos(opciones):
    cal = main.calendario(opciones)
    estado, periodo, aviso = main.estado_desde_controles([2, 6], "nacional", "Lanquin", cal, opciones.meses)
    assert estado == {"mes_ini": "2025-11", "mes_fin": "2026-03", "tipo": "nacional", "subdestino": "Lanquin"}
    assert periodo == "Período: nov 2025 – mar 2026"
    assert "ene 2026" in aviso and "feb 2026" in aviso and "interpretan como cero" in aviso


def test_estado_desde_controles_sin_huecos(opciones):
    cal = main.calendario(opciones)
    _, _, aviso = main.estado_desde_controles([0, 3], "extranjero", "Coban", cal, opciones.meses)
    assert aviso == ""


def test_estado_desde_controles_valores_invalidos_usan_todo_el_rango(opciones):
    cal = main.calendario(opciones)
    estado, _, _ = main.estado_desde_controles(None, "extranjero", "Coban", cal, opciones.meses)
    assert (estado["mes_ini"], estado["mes_fin"]) == ("2025-09", "2026-08")
    estado, _, _ = main.estado_desde_controles([9, 0], "extranjero", "Coban", cal, opciones.meses)  # invertido
    assert (estado["mes_ini"], estado["mes_fin"]) == ("2025-09", "2026-06")


def test_meses_sin_cobertura(opciones):
    huecos = main.meses_sin_cobertura("2025-12", "2026-03", opciones.meses)
    assert huecos == [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01")]


def test_sin_datos_la_app_se_construye_y_avisa():
    vacio = main.cargar_opciones(pd.DataFrame(columns=["destino_clave", "subdestino", "tipo", "anio_mes"]))
    assert vacio.vacio
    app = main.crear_app(vacio, implementaciones={})
    assert any(isinstance(c, dbc.Alert) and "No se encontraron datos" in str(c.children)
               for c in main.recorrer_componentes(app.layout))
    assert main.valores_iniciales(vacio) == Filtros()


# ----------------------------------------------------------- módulos y callbacks
def test_modulo_inyectado_registra_layout_y_callbacks(opciones):
    llamadas = []
    impl = SimpleNamespace(layout=lambda: html.Div(id="m1-raiz"),
                           registrar_callbacks=lambda app: llamadas.append(app))
    app = main.crear_app(opciones, implementaciones={"demanda": impl})
    assert "m1-raiz" in main.ids_del_layout(app.layout)
    assert llamadas == [app]


def test_ids_repetidos_se_detectan(opciones):
    impl = SimpleNamespace(layout=lambda: html.Div(id=main.ID_FILTRO_TIPO))
    with pytest.raises(ValueError):
        main.crear_app(opciones, implementaciones={"demanda": impl})


def test_layout_base_sin_ids_duplicados(app_base):
    ids = [str(i) for i in main.ids_del_layout(app_base.layout)]
    assert len(ids) == len(set(ids))
    assert theme.ID_SLOT_COBERTURA in ids  # espacio para P3


def test_server_expuesto():
    assert main.server is main.app.server


def test_descubrimiento_ignora_modulos_inexistentes():
    assert main.importar_modulo("app.modulo_que_no_existe") is None


# ------------------------------------------------------------------------- tema
def test_plantilla_plotly_disponible():
    assert theme.NOMBRE_PLANTILLA in pio.templates
    assert list(theme.PLANTILLA.layout.colorway) == list(theme.CATEGORICOS)
    fig = theme.aplicar_plantilla(theme.figura_sin_dato("x"))
    assert fig.layout.template.layout.font.family == theme.FUENTE


def test_color_estimacion_es_exclusivo():
    observados = {c.lower() for c in (*theme.CATEGORICOS, *theme.SECUENCIAL, theme.COLOR_OBSERVADO,
                                      theme.COLOR_SIN_DATO, theme.COLOR_SIN_DATO_TEXTO, theme.TEXTO,
                                      theme.TEXTO_SECUNDARIO, theme.FONDO, theme.FONDO_PAGINA,
                                      theme.ENCABEZADO, theme.COLOR_GRILLA, theme.COLOR_EJE)}
    assert observados.isdisjoint(theme.COLORES_ESTIMACION)
    colores_plantilla = {c.lower() for c in theme.PLANTILLA.layout.colorway}
    assert colores_plantilla.isdisjoint(theme.COLORES_ESTIMACION)
    assert theme.COLOR_OBSERVADO != theme.COLOR_ESTIMACION


@pytest.mark.parametrize("nombre,texto,fondo", theme.PARES_TEXTO_AA)
def test_contraste_aa_de_textos(nombre, texto, fondo):
    assert theme.razon_contraste(texto, fondo) >= 4.5, nombre
    assert theme.cumple_aa(texto, fondo)


def test_razon_contraste_referencias():
    assert theme.razon_contraste("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert theme.razon_contraste("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)
    assert not theme.cumple_aa("#9AA0A6", "#FFFFFF")  # el gris de relleno NO sirve para texto


def test_subtitulo_periodo():
    assert theme.subtitulo_periodo("2025-09", "2025-12") == "Período: sep 2025 – dic 2025"
    assert theme.subtitulo_periodo("2025-09", "2025-09-30") == "Período: sep 2025"
    assert theme.subtitulo_periodo("2025-09", "2025-12", "movilidad_mensual").endswith(
        "· Fuente: movilidad_mensual")
    assert theme.subtitulo_periodo() == "Período: sin definir"


def test_rotulo_y_estilo_de_estimacion():
    assert theme.rotulo_estimacion() == "Estimación"
    assert theme.rotulo_estimacion("ene 2026") == "ene 2026 · Estimación"
    estilo = theme.estilo_estimacion()
    assert estilo["line"]["color"] == theme.COLOR_ESTIMACION
    assert estilo["line"]["dash"] == "dash"


def test_figura_sin_dato_no_tiene_trazos_ni_ceros():
    fig = theme.figura_sin_dato("Ocupación", "Período: ene 2026")
    assert len(fig.data) == 0
    assert fig.layout.annotations[0].text == "Sin dato"
    assert "Período: ene 2026" in fig.layout.title.text
    assert fig.layout.xaxis.visible is False and fig.layout.yaxis.visible is False
