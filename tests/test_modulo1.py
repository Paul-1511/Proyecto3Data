"""Pruebas del Módulo 1 (Demanda y mercados) con datos sintéticos; sin Parquet ni navegador."""
import numpy as np
import pandas as pd
import pytest

from app import main, modulo1
from app.utils import metricas
from app.utils.datos import Filtros

F = Filtros(mes_ini="2025-09", mes_fin="2025-10", tipo="extranjero", subdestino="Coban")
F_NAC = Filtros(mes_ini="2025-09", mes_fin="2025-10", tipo="nacional", subdestino="Coban")
F_NOV = Filtros(mes_ini="2025-09", mes_fin="2025-11", tipo="extranjero", subdestino="Coban")  # nov sin dato


def _s(destino, sub, tipo, mes, seg, vis, dias):
    return dict(destino_clave=destino, subdestino=sub, tipo=tipo, anio_mes=pd.Timestamp(f"{mes}-01"),
                segmento=seg, visitantes=vis, dias_persona=dias)


def _p(pais, mes, seg, vis, dias=0.0, sub="Coban", tipo="extranjero", destino="alta_verapaz"):
    return dict(destino_clave=destino, subdestino=sub, tipo=tipo, anio_mes=pd.Timestamp(f"{mes}-01"),
                pais=pais, segmento=seg, visitantes=vis, dias_persona=dias)


MAS, MENOS = "mas_de_1_dia", "menos_de_1_dia"


@pytest.fixture
def df_sub():
    av = "alta_verapaz"
    filas = [
        # Coban extranjero: visitantes/mes 40 y 90 -> 65; días-persona 100 y 300 -> 200; estadía 370/100 = 3.7
        _s(av, "Coban", "extranjero", "2025-09", MAS, 30, 90), _s(av, "Coban", "extranjero", "2025-09", MENOS, 10, 10),
        _s(av, "Coban", "extranjero", "2025-10", MAS, 70, 280), _s(av, "Coban", "extranjero", "2025-10", MENOS, 20, 20),
        # Coban nacional: 150 y 200 -> 175
        _s(av, "Coban", "nacional", "2025-09", MAS, 100, 200), _s(av, "Coban", "nacional", "2025-09", MENOS, 50, 50),
        _s(av, "Coban", "nacional", "2025-10", MAS, 120, 240), _s(av, "Coban", "nacional", "2025-10", MENOS, 80, 80),
        # Otro subdestino de Alta Verapaz
        _s(av, "Lanquin", "extranjero", "2025-09", MAS, 5, 10), _s(av, "Lanquin", "extranjero", "2025-09", MENOS, 5, 5),
        # Ruido que NO debe aparecer
        _s(av, "Coban", "sin_dato", "2025-09", MAS, 1000, 1000),
        _s("antigua", "Antigua Guatemala", "extranjero", "2025-09", MAS, 9999, 9999),
        _s("antigua", "Coban", "extranjero", "2025-09", MAS, 5000, 5000),   # mismo nombre, otro destino
    ]
    return pd.DataFrame(filas)


@pytest.fixture
def df_pais():
    filas = [
        _p("Estados Unidos", "2025-09", MAS, 20, 40), _p("Estados Unidos", "2025-09", MENOS, 20, 20),
        _p("Estados Unidos", "2025-10", MAS, 60, 180),              # promedio mensual (40 + 60) / 2 = 50
        _p("Mexico", "2025-09", MAS, 80, 240),                      # solo 1 mes con dato
        _p("sin_dato", "2025-09", MAS, 500), _p("Sin_dato", "2025-09", MAS, 600), _p(None, "2025-09", MAS, 700),
        _p("Canada", "2025-09", MAS, np.nan),                       # nulo: no entra al ranking
        _p("Guatemala", "2025-09", MAS, 1000, tipo="nacional"),     # nacional: nunca en el ranking extranjero
        _p("Estados Unidos", "2025-09", MAS, 9999, sub="Lanquin"),  # otro subdestino
        _p("Francia", "2025-09", MAS, 7777, destino="antigua"),     # otro destino
    ]
    return pd.DataFrame(filas)


def _textos_sin_dato(fig):
    return [a.text for a in fig.layout.annotations if a.text == "Sin dato"]


# ------------------------------------------------------- Alta Verapaz y filtros globales
def test_excluye_destinos_ajenos_y_tipos_invalidos(df_sub, df_pais):
    out = modulo1.solo_alta_verapaz(df_sub)
    assert set(out["destino_clave"]) == {"alta_verapaz"}
    assert set(out["subdestino"]) <= set(modulo1.SUBDESTINOS_AV)
    assert set(out["tipo"]) == {"extranjero", "nacional"}
    assert not {9999, 5000, 1000} & set(out["visitantes"])
    assert set(modulo1.solo_alta_verapaz(df_pais)["destino_clave"]) == {"alta_verapaz"}


def test_solo_alta_verapaz_exige_destino_clave(df_sub):
    with pytest.raises(KeyError):
        modulo1.solo_alta_verapaz(df_sub.drop(columns="destino_clave"))


def test_filtros_globales_actualizan_los_datos(df_sub):
    todo = modulo1.preparar(df_sub, F)
    assert set(todo["subdestino"]) == {"Coban"} and set(todo["tipo"]) == {"extranjero"}
    assert len(todo) == 4
    solo_sep = modulo1.preparar(df_sub, Filtros(mes_ini="2025-09", mes_fin="2025-09", tipo="extranjero",
                                                subdestino="Coban"))
    assert set(solo_sep["anio_mes"]) == {pd.Timestamp("2025-09-01")}
    assert set(modulo1.preparar(df_sub, F_NAC)["tipo"]) == {"nacional"}
    lanquin = modulo1.preparar(df_sub, Filtros(tipo="extranjero", subdestino="Lanquin"))
    assert set(lanquin["subdestino"]) == {"Lanquin"}


# ---------------------------------------------------------------------------- KPI
def test_kpis_coherentes_con_metricas(df_sub):
    df = modulo1.preparar(df_sub, F)
    vis, dias, estadia = modulo1.tarjetas_kpi(df, F)
    assert metricas.promedio_mensual_visitantes(df).promedio == pytest.approx(65)
    assert metricas.estadia_ponderada(df) == pytest.approx(3.7)
    assert vis.valor == "65" and dias.valor == "200" and estadia.valor == "3.70 días"
    assert "2 meses observados" in vis.detalle and "Período: sep 2025 – oct 2025" in vis.detalle
    assert "2 meses observados" in estadia.detalle


def test_kpis_nacionales_se_calculan_aparte(df_sub):
    vis_nac = modulo1.tarjetas_kpi(modulo1.preparar(df_sub, F_NAC), F_NAC)[0]
    assert vis_nac.valor == "175"   # (150 + 200) / 2; no mezcla extranjeros


def test_kpis_sin_datos_o_filtro_incompleto(df_sub):
    vacio = modulo1.preparar(df_sub.iloc[0:0], F)
    assert [k.valor for k in modulo1.tarjetas_kpi(vacio, F)] == ["Sin dato"] * 3
    sin_tipo = Filtros(mes_ini="2025-09", mes_fin="2025-10", subdestino="Coban")
    assert [k.valor for k in modulo1.tarjetas_kpi(modulo1.preparar(df_sub, F), sin_tipo)] == ["Sin dato"] * 3


def test_archivo_faltante_da_tablas_vacias(monkeypatch):
    def falla(nombre):
        raise FileNotFoundError(nombre)
    monkeypatch.setattr(modulo1.datos, "cargar", falla)
    sub = modulo1._leer_sub()
    assert sub.empty
    assert [k.valor for k in modulo1.tarjetas_kpi(modulo1.preparar(sub, F), F)] == ["Sin dato"] * 3
    assert modulo1.ranking_extranjeros(modulo1._leer_pais(), F).empty


# --------------------------------------------------------------------------- ranking
def test_ranking_promedia_meses_con_dato_sin_sumar_ni_paises_desconocidos(df_pais):
    rank = modulo1.ranking_extranjeros(df_pais, F)
    assert rank["pais"].tolist() == ["Mexico", "Estados Unidos"]
    assert rank["promedio_mensual"].tolist() == pytest.approx([80.0, 50.0])   # EE. UU.: no 100 ni 9999
    assert rank["n_meses"].tolist() == [1, 2]
    for ajeno in ("sin_dato", "Sin_dato", "Canada", "Guatemala", "Francia", None):
        assert ajeno not in rank["pais"].tolist()


def test_ranking_extranjero_ignora_el_tipo_global_y_no_incluye_nacionales(df_pais):
    rank = modulo1.ranking_extranjeros(df_pais, F_NAC)
    assert "Guatemala" not in rank["pais"].tolist()
    assert rank["pais"].tolist() == ["Mexico", "Estados Unidos"]


def test_ranking_limita_a_diez_y_ordena():
    filas = [_p(f"P{i:02d}", "2025-09", MAS, i) for i in range(1, 13)] + [_p("Zeta", "2025-09", MAS, 12)]
    rank = modulo1.ranking_mercados(pd.DataFrame(filas))
    assert len(rank) == modulo1.N_TOP == 10
    assert rank["pais"].iloc[:2].tolist() == ["P12", "Zeta"]     # empate: orden alfabético
    assert rank["promedio_mensual"].is_monotonic_decreasing


def test_ranking_rechaza_mezcla_de_subdestinos_y_tipos(df_pais):
    con_lanquin = df_pais[df_pais["destino_clave"] == "alta_verapaz"]
    with pytest.raises(ValueError):
        modulo1.ranking_mercados(con_lanquin)   # incluye Coban y Lanquin / extranjero y nacional


def test_ranking_sin_filas_validas():
    assert modulo1.ranking_mercados(pd.DataFrame([_p("sin_dato", "2025-09", MAS, 5)])).empty
    assert modulo1.ranking_extranjeros(pd.DataFrame([_p("Mexico", "2025-09", MAS, 5)]),
                                       Filtros(tipo="extranjero")).empty   # sin subdestino


# ------------------------------------------------------------------------ interacción
def test_interaccion_del_ranking():
    click = {"points": [{"y": "Mexico", "customdata": ["Mexico", 1]}]}
    assert modulo1.mercado_desde_click(click) == "Mexico"
    assert modulo1.mercado_desde_click({"points": [{"y": "Francia"}]}) == "Francia"
    assert modulo1.mercado_desde_click(None) is None
    assert modulo1.mercado_desde_click({"points": []}) is None
    assert modulo1.seleccion_desde_evento(modulo1.ID_G_RANKING, click) == "Mexico"
    assert modulo1.seleccion_desde_evento(modulo1.ID_LIMPIAR, click) is None
    assert modulo1.seleccion_desde_evento("store-filtros", click) is None   # cambio de filtro: se borra


def test_seleccion_compatible_con_filtros_globales(df_sub, df_pais):
    assert modulo1.mercado_efectivo("Estados Unidos", F) == "Estados Unidos"
    assert modulo1.mercado_efectivo("Estados Unidos", F_NAC) is None
    assert modulo1.mercado_efectivo(None, F) is None
    assert "no se aplica" in modulo1.texto_seleccion("Estados Unidos", F_NAC)


def test_seleccion_actualiza_segmentos_y_estadia(df_sub, df_pais):
    general = modulo1.serie_para_graficos(df_sub, df_pais, F)
    mercado = modulo1.serie_para_graficos(df_sub, df_pais, F, "Estados Unidos")
    assert set(mercado["pais"]) == {"Estados Unidos"} and "pais" not in general.columns
    assert set(mercado["subdestino"]) == {"Coban"}     # sigue respetando subdestino (9999 de Lanquin fuera)

    seg_gen = modulo1.fig_segmentos(general, F)
    seg_mer = modulo1.fig_segmentos(mercado, F, "Estados Unidos")
    assert seg_gen.data[0].y[0] == pytest.approx(75.0)
    assert seg_mer.data[0].y[0] == pytest.approx(50.0)
    assert "Mercado: Estados Unidos" in seg_mer.layout.title.text

    est_gen = modulo1.fig_estadia(general, F)
    est_mer = modulo1.fig_estadia(mercado, F, "Estados Unidos")
    assert list(est_gen.data[0].y) == pytest.approx([3.0, 4.0])
    assert list(est_mer.data[0].y) == pytest.approx([2.0, 3.0])


def test_ranking_resalta_la_barra_seleccionada(df_pais):
    rank = modulo1.ranking_extranjeros(df_pais, F)
    sin_sel = modulo1.fig_ranking(rank, F)
    con_sel = modulo1.fig_ranking(rank, F, "Mexico")
    assert sin_sel.data[0].marker.color == modulo1.theme.COLOR_OBSERVADO
    colores = list(con_sel.data[0].marker.color)
    assert colores[0] == modulo1.theme.COLOR_OBSERVADO and colores[1] != colores[0]
    assert con_sel.data[0].customdata[0][0] == "Mexico"
    assert list(con_sel.data[0].x) == pytest.approx([80.0, 50.0])


# ------------------------------------------------------------------ nacionales aparte
def test_nacionales_separados_de_extranjeros(df_sub):
    fig = modulo1.fig_nacionales(modulo1.preparar(df_sub, F_NAC, tipo="nacional"), F_NAC)
    assert list(fig.data[0].y) == pytest.approx([150.0, 200.0])   # solo nacionales
    assert "nacional" in fig.layout.title.text
    fig2 = modulo1.fig_nacionales(modulo1.preparar(df_sub, F, tipo="nacional"), F)   # tipo global extranjero
    assert list(fig2.data[0].y) == pytest.approx([150.0, 200.0])


# --------------------------------------------------------------- ausencia de datos
def test_estados_sin_datos_no_dibujan_ceros(df_sub, df_pais):
    vacio = modulo1.preparar(df_sub.iloc[0:0], F)
    figuras = [modulo1.fig_segmentos(vacio, F), modulo1.fig_estadia(vacio, F),
               modulo1.fig_ranking(modulo1.ranking_extranjeros(df_pais.iloc[0:0], F), F),
               modulo1.fig_nacionales(vacio, F)]
    for fig in figuras:
        assert len(fig.data) == 0
        assert _textos_sin_dato(fig) == ["Sin dato"]
        assert "Período: sep 2025 – oct 2025" in fig.layout.title.text
    sin_sub = Filtros(mes_ini="2025-09", mes_fin="2025-10", tipo="extranjero")
    assert len(modulo1.fig_segmentos(modulo1.preparar(df_sub, F), sin_sub).data) == 0


def test_meses_sin_cobertura_quedan_como_hueco_no_como_cero(df_sub):
    df = modulo1.preparar(df_sub, F_NOV)   # sep y oct con dato; nov sin dato
    seg = modulo1.fig_segmentos(df, F_NOV)
    est = modulo1.fig_estadia(df, F_NOV)
    assert np.isnan(seg.data[0].y[2]) and np.isnan(seg.data[1].y[2])
    assert np.isnan(est.data[0].y[2]) and est.data[0].connectgaps is False
    assert _textos_sin_dato(seg) == ["Sin dato"] and _textos_sin_dato(est) == ["Sin dato"]
    nac_f = Filtros(mes_ini="2025-09", mes_fin="2025-11", tipo="nacional", subdestino="Coban")
    nac = modulo1.fig_nacionales(modulo1.preparar(df_sub, nac_f, tipo="nacional"), nac_f)
    assert np.isnan(nac.data[0].y[2]) and _textos_sin_dato(nac) == ["Sin dato"]


# ---------------------------------------------------- integración con main.py
def test_layout_ids_unicos_con_prefijo_y_sin_descargas():
    layout = modulo1.layout()
    main.verificar_ids_unicos(layout)
    ids = [str(i) for i in main.ids_del_layout(layout)]
    assert ids and all(i.startswith("m1-") for i in ids)
    for requerido in (modulo1.ID_G_RANKING, modulo1.ID_G_SEGMENTOS, modulo1.ID_G_ESTADIA,
                      modulo1.ID_G_NACIONALES, modulo1.ID_SELECCION, modulo1.ID_LIMPIAR,
                      modulo1.ID_SELECCION_TEXTO):
        assert requerido in ids
    for base in modulo1.IDS_KPI:
        assert f"{base}-valor" in ids and f"{base}-detalle" in ids and f"{base}-info" in ids
    clases = {type(c).__name__ for c in main.recorrer_componentes(layout)}
    assert not clases & {"Download", "DataTable"}
    graficos = [c for c in main.recorrer_componentes(layout) if type(c).__name__ == "Graph"]
    assert len(graficos) == 4 and all(g.config == {"displayModeBar": False} for g in graficos)


def test_registro_de_callbacks_sin_ids_duplicados(df_sub):
    opciones = main.cargar_opciones(df_sub)
    assert opciones.subdestinos == ("Coban", "Lanquin")   # el ruido de otros destinos no llega a los filtros
    app = main.crear_app(opciones, implementaciones={"demanda": modulo1})   # falla si hay IDs/Outputs repetidos
    claves = " ".join(app.callback_map)
    for salida in ("m1-seleccion.data", "m1-grafico-segmentos.figure", "m1-grafico-estadia.figure",
                   "m1-grafico-ranking.figure", "m1-seleccion-texto.children",
                   "m1-grafico-nacionales.figure", "m1-kpi-visitantes-valor.children",
                   "m1-kpi-estadia-detalle.children"):
        assert salida in claves, salida
    ids = [str(i) for i in main.ids_del_layout(app.layout)]
    assert len(ids) == len(set(ids))
