"""Pruebas del Módulo 3 (figuras, interacción y reglas) con datos sintéticos; sin navegador."""
import numpy as np
import pandas as pd
import pytest

from app import main, modulo3 as m3, theme
from app.utils import cobertura as cb
from app.utils import oferta_ocupacion as oo
from app.utils.datos import Filtros

MAS, MENOS = "mas_de_1_dia", "menos_de_1_dia"
F = Filtros(mes_ini="2025-09", mes_fin="2026-08", tipo="extranjero", subdestino="Coban")
F_2026 = Filtros(mes_ini="2026-03", mes_fin="2026-08", tipo="extranjero", subdestino="Coban")
MESES_MOV = list(pd.date_range("2025-09-01", "2025-12-01", freq="MS")) + \
    list(pd.date_range("2026-03-01", "2026-08-01", freq="MS"))


@pytest.fixture
def mov():
    filas = []
    for i, m in enumerate(MESES_MOV):
        for sub, k in (("Coban", 10), ("Lanquin", 4), ("Cuevas De Candelaria", 3)):
            for tipo, f in (("extranjero", 1), ("nacional", 50)):
                for seg in (MAS, MENOS):
                    filas.append(dict(destino_clave="alta_verapaz", subdestino=sub, tipo=tipo, anio_mes=m,
                                      segmento=seg, visitantes=float(k * f * (10 + i))))
    return pd.DataFrame(filas)


@pytest.fixture
def ocup():
    meses = pd.date_range("2023-01-01", "2025-12-01", freq="MS")
    return pd.DataFrame([dict(departamento=d, anio_mes=m, indice_pct=40.0 + m.month + (5 if d == "Petén" else 0))
                         for m in meses for d in ("Alta Verapaz", "Petén")])


@pytest.fixture
def cob():
    filas = []
    for m in pd.date_range("2023-01-01", "2026-12-01", freq="MS"):
        filas.append(dict(fuente="movilidad_mensual", anio_mes=m, tiene_dato=m in MESES_MOV,
                          cobertura_completa=m in MESES_MOV))
        filas.append(dict(fuente="ocupacion", anio_mes=m, tiene_dato=m.year <= 2025,
                          cobertura_completa=m.year <= 2025))
    return cb.validar(pd.DataFrame(filas))


@pytest.fixture
def oferta():
    return pd.DataFrame([dict(anio=a, departamento="Alta Verapaz", tipo_alojamiento=t, establecimientos=10,
                              habitaciones=100 + a - 2022, plazas_cama=300, es_corte_parcial=a == 2026,
                              repite_valor_anio_previo=False)
                         for a in range(2022, 2027) for t in ("Hotel", "Hospedaje", "Pensión")])


def _anotaciones(fig):
    return [a.text for a in fig.layout.annotations]


def _es_sin_dato(fig):
    return not fig.data and any(theme.ETIQUETA_SIN_DATO in t for t in _anotaciones(fig))


# --------------------------------------------------------------------- A. capacidad
def test_capacidad_barras_por_anio_sin_lineas(oferta):
    fig = m3.fig_capacidad(oo.capacidad_por_anio(oferta), "habitaciones")
    assert {t.type for t in fig.data} == {"bar"} and fig.layout.barmode == "group"
    assert [t.name for t in fig.data] == ["2022", "2023", "2024", "2025"]
    assert any("Airbnb" in t for t in _anotaciones(fig))


def test_capacidad_2026_marcado_parcial_y_sin_color_de_estimacion(oferta):
    fig = m3.fig_capacidad(oo.capacidad_por_anio(oferta, incluir_parcial=True), "habitaciones")
    t2026 = fig.data[-1]
    assert "parcial" in t2026.name and t2026.marker.pattern.shape == "/"
    colores = {str(t.marker.color).lower() for t in fig.data}
    assert not colores & theme.COLORES_ESTIMACION


def test_capacidad_resalta_anio_seleccionado(oferta):
    fig = m3.fig_capacidad(oo.capacidad_por_anio(oferta), "habitaciones", anio_sel=2024)
    opac = {t.name: t.marker.opacity for t in fig.data}
    assert opac["2024"] == 1.0 and opac["2022"] < 1.0


# --------------------------------------------------------------------- B. ocupación
def test_ocupacion_completa_tiene_promedio_y_picos(ocup):
    fig = m3.construir_ocupacion(ocup, F, comparar=True, vista="completa", anio_sel=None)
    nombres = [t.name for t in fig.data]
    assert any("no es el índice nacional" in n for n in nombres)
    assert "Mes pico del año" in nombres and "Mes valle del año" in nombres
    assert not any("Estimación" in n for n in nombres)          # sin proyecciones


def test_ocupacion_vista_rango_sin_cobertura_es_sin_dato(ocup):
    fig = m3.construir_ocupacion(ocup, F_2026, comparar=False, vista="rango", anio_sel=None)
    assert _es_sin_dato(fig)


def test_ocupacion_vista_rango_recorta_a_meses_del_filtro(ocup):
    fig = m3.construir_ocupacion(ocup, F, comparar=False, vista="rango", anio_sel=None)
    serie = next(t for t in fig.data if t.name == "Alta Verapaz")
    assert len(serie.x) == 4      # solo sep–dic 2025 tienen ocupación dentro del filtro


# ------------------------------------------------------------------------ C. cruce
def test_cruce_solo_sep_dic_2025(mov, ocup, cob):
    fig, texto = m3.construir_cruce(mov, ocup, cob, F, "Coban")
    for t in fig.data:
        assert list(t.x) == ["sep 2025", "oct 2025", "nov 2025", "dic 2025"]
    assert {t.yaxis for t in fig.data} == {"y", "y2"}          # dos paneles, no doble eje superpuesto


def test_cruce_fuera_de_ventana_es_sin_dato(mov, ocup, cob):
    fig, _ = m3.construir_cruce(mov, ocup, cob, F_2026, "Coban")
    assert _es_sin_dato(fig)


def test_cruce_advierte_n4_sin_correlacion(mov, ocup, cob):
    _, texto = m3.construir_cruce(mov, ocup, cob, F, "Coban")
    plano = str(texto)
    assert "n = 4" in plano and "correlación" in plano


def test_cruce_respeta_cobertura(mov, ocup, cob):
    cob2 = cob.copy()
    cob2.loc[(cob2["fuente"] == "ocupacion") & (cob2["anio_mes"] == "2025-11-01"), "tiene_dato"] = False
    fig, _ = m3.construir_cruce(mov, ocup, cob2, F, "Coban")
    linea = next(t for t in fig.data if t.type == "scatter")
    assert np.isnan(linea.y[2])                                   # nov: hueco, no 0
    assert theme.ETIQUETA_SIN_DATO in _anotaciones(fig)


# ------------------------------------------------------------------- D. subdestinos
def test_subdestinos_sin_barra_total(mov, cob):
    fig = m3.construir_subdestinos(mov, cob, F, oo.PROMEDIO, None)
    assert list(fig.data[0].x) == ["Cobán", "Lanquín", "Cuevas de Candelaria"]
    assert "Total" not in " ".join(fig.data[0].x)


def test_subdestinos_rechaza_total_construido():
    af = pd.DataFrame(dict(subdestino=["Coban", "Total"], nombre=["Cobán", "Total"], tipo="extranjero",
                           visitantes=[1.0, 2.0], n_meses=[1, 1], relativo_pct=[50.0, 100.0]))
    with pytest.raises(ValueError):
        m3.fig_subdestinos(af, "extranjero", "Período")


def test_subdestinos_mes_seleccionado(mov, cob):
    fig = m3.construir_subdestinos(mov, cob, F, "2025-09", None)
    assert fig.data[0].y[0] == 2 * 10 * 10           # Cobán, sep 2025: 2 segmentos × 100


def test_subdestinos_resalta_seleccion(mov, cob):
    fig = m3.construir_subdestinos(mov, cob, F, oo.PROMEDIO, "Lanquin")
    colores = list(fig.data[0].marker.color)
    assert colores[1] == m3.COLOR_RESALTE and colores[0] == m3.COLOR_ATENUADO


# --------------------------------------------------------------- E. estacionalidad
def test_estacionalidad_dos_paneles_y_ene_feb_sin_dato(mov, ocup, cob):
    fig = m3.construir_estacionalidad(mov, ocup, cob, F, "Coban", None)
    vis = next(t for t in fig.data if t.name.startswith("Visitantes"))
    assert np.isnan(vis.y[0]) and np.isnan(vis.y[1])
    assert sum(1 for t in fig.data if t.name.startswith("Ocupación")) == 3


# ------------------------------------------------------------------- interacción
def test_mes_desde_click():
    assert m3.mes_desde_click({"points": [{"x": "nov 2025", "customdata": "2025-11"}]}) == "2025-11"
    assert m3.mes_desde_click(None) is None


def test_alternar_y_valor_click():
    assert m3.valor_desde_click({"points": [{"customdata": 2024}]}) == 2024
    assert m3.alternar(2024, 2024) is None and m3.alternar(None, 2023) == 2023


def test_subdestino_efectivo():
    assert m3.subdestino_efectivo("Lanquin", F) == "Lanquin"
    assert m3.subdestino_efectivo(None, F) == "Coban"
    assert m3.subdestino_efectivo("Total", F) == "Coban"


def test_opciones_mes_solo_meses_con_cobertura(cob):
    opciones = m3.opciones_mes(m3.meses_movilidad(cob, Filtros(mes_ini="2025-12", mes_fin="2026-03")))
    assert [o["value"] for o in opciones] == [oo.PROMEDIO, "2025-12", "2026-03"]


# --------------------------------------------------------------------- integración
def test_ids_con_prefijo_y_app_sin_repetidos():
    ids = main.ids_del_layout(m3.layout())
    assert ids and all(str(i).startswith("m3-") for i in ids)
    opciones = main.Opciones(pd.DatetimeIndex(MESES_MOV), ("extranjero", "nacional"), oo.SUBDESTINOS)
    app = main.crear_app(opciones=opciones, implementaciones={"oferta": m3})
    assert any("m3-grafico-cruce" in str(k) for k in app.callback_map)


def test_al_menos_dos_graficos_reaccionan_a_clics():
    opciones = main.Opciones(pd.DatetimeIndex(MESES_MOV), ("extranjero",), oo.SUBDESTINOS)
    app = main.crear_app(opciones=opciones, implementaciones={"oferta": m3})
    graficos_con_clic = {m3.ID_G_CAPACIDAD, m3.ID_G_CRUCE, m3.ID_G_SUBDESTINOS, m3.ID_G_OCUPACION}
    disparados = set()
    for salida, cb_ in app.callback_map.items():
        entradas = {i["id"] for i in cb_["inputs"]}
        if entradas & {m3.ID_ANIO_SEL, m3.ID_SUB_SEL, m3.ID_MES_SUB} and "grafico" in salida:
            disparados.add(salida)
        assert not (entradas & graficos_con_clic and salida.split(".")[0] in graficos_con_clic)
    assert len(disparados) >= 2
