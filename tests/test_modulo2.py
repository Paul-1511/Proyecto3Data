"""Pruebas del Módulo 2 (Dinámica, eventos y pronóstico) con datos sintéticos; sin Parquet ni navegador."""
from dataclasses import replace

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import pytest

from app import main, modulo1, modulo2, theme
from app.utils import metricas
from app.utils.datos import Filtros

AV = "alta_verapaz"
F = Filtros(mes_ini="2025-09", mes_fin="2025-11", tipo="extranjero", subdestino="Coban")
F_NAC = replace(F, tipo="nacional")
F_SIN_RANGO = Filtros(tipo="extranjero", subdestino="Coban")


# --------------------------------------------------------------------- constructores
def _d(filas, sub="Coban", tipo="extranjero", destino=AV):
    """Diaria: filas = (fecha, evento, presencia_total), repartida en dos países (40/60)."""
    out = []
    for fecha, evento, total in filas:
        f = pd.Timestamp(fecha)
        for pais, frac in (("Estados Unidos", 0.4), ("Mexico", 0.6)):
            out.append(dict(destino_clave=destino, subdestino=sub, tipo=tipo, fecha=f,
                            anio_mes=f.to_period("M").to_timestamp(), pais=pais, evento=evento,
                            es_regular=(evento == "Regular"), presencia=total * frac))
    return pd.DataFrame(out)


# 2025-09-01 lunes | 09-02 martes | 09-06 sábado | 09-07 domingo | 09-15 lunes | 09-17 miércoles | 10-06 y 10-20 lunes
REGULARES = [("2025-09-01", "Regular", 10), ("2025-09-08", "Regular", 20), ("2025-09-02", "Regular", 100),
             ("2025-09-09", "Regular", 100), ("2025-09-06", "Regular", 40), ("2025-09-07", "Regular", 50),
             ("2025-10-06", "Regular", 12)]
EVENTOS = [("2025-09-15", "15 de Septiembre", 30), ("2025-09-16", "15 de Septiembre", 150),
           ("2025-10-20", "20 de Octubre", 24), ("2025-09-17", "Fiestas Agostinas", 50)]


@pytest.fixture
def diaria():
    ruido = pd.concat([
        _d([("2025-09-01", "Regular", 777)], tipo="nacional"),        # otro tipo
        _d([("2025-09-01", "Regular", 888)], sub="Lanquin"),          # otro subdestino
        _d([("2025-09-01", "Regular", 9999)], destino="antigua"),     # otro destino
        _d([("2025-09-01", "Regular", 5555)], tipo="sin_dato"),       # tipo inválido
        _d([("2025-12-01", "Regular", 1)]),                           # fuera del rango de meses
    ])
    return pd.concat([_d(REGULARES + EVENTOS), ruido], ignore_index=True)


@pytest.fixture
def dia_f(diaria):
    return modulo2.preparar_diaria(diaria, F)


def _textos(componente):
    """Todos los textos hijos de un componente Dash."""
    for c in main.recorrer_componentes(componente):
        h = getattr(c, "children", None)
        for x in (h if isinstance(h, list) else [h]):
            if isinstance(x, str):
                yield x


def _sin_dato(fig):
    return [a for a in fig.layout.annotations if a.text == "Sin dato"]


def _formas(fig, color):
    return [s for s in fig.layout.shapes if s.fillcolor == color]


# ------------------------------------------------- Alta Verapaz y filtros globales
def test_excluye_destinos_tipos_ajenos_y_fuera_de_rango(dia_f):
    assert set(dia_f["destino_clave"]) == {AV}
    assert set(dia_f["subdestino"]) == {"Coban"} and set(dia_f["tipo"]) == {"extranjero"}
    assert not {9999, 5555, 777, 888, 1} & set(np.round(dia_f.groupby("fecha")["presencia"].sum()))
    assert dia_f["fecha"].max() < pd.Timestamp("2025-12-01")


def test_filtros_globales_actualizan_la_serie(diaria):
    nac = modulo2.preparar_diaria(diaria, F_NAC)
    assert set(nac["tipo"]) == {"nacional"} and nac["presencia"].sum() == pytest.approx(777)
    lanquin = modulo2.preparar_diaria(diaria, replace(F, subdestino="Lanquin"))
    assert lanquin["presencia"].sum() == pytest.approx(888)
    sin_tipo = Filtros(mes_ini="2025-09", mes_fin="2025-11", subdestino="Coban")
    assert modulo2.preparar_diaria(diaria, sin_tipo).empty   # no se mezclan tipos


def test_el_mes_final_se_incluye_completo():
    df = _d([("2025-09-30 18:00:00", "Regular", 5), ("2025-10-01", "Regular", 7)])
    out = modulo2.preparar_diaria(df, Filtros(mes_ini="2025-09", mes_fin="2025-09", tipo="extranjero",
                                              subdestino="Coban"))
    assert out["presencia"].sum() == pytest.approx(5)


# ------------------------------------------------------------------ serie diaria
def test_serie_diaria_suma_paises_sin_duplicar_fechas(dia_f):
    dias = modulo2.serie_diaria(dia_f)
    assert len(dias) == dia_f["fecha"].nunique() == 11
    assert dias.loc[pd.Timestamp("2025-09-15"), "presencia"] == pytest.approx(30.0)   # 12 + 18, no 12 ni 18
    fig = modulo2.fig_serie(dia_f, F)
    y = np.asarray(fig.data[0].y, dtype=float)
    assert y[14] == pytest.approx(30.0)            # 15 de septiembre
    assert np.isfinite(y).sum() == 11


def test_serie_diaria_rechaza_mezcla_de_series(diaria):
    with pytest.raises(ValueError):
        modulo2.serie_diaria(diaria[diaria["destino_clave"] == AV])   # varios subdestinos y tipos


def test_dias_sin_dato_son_huecos_no_ceros(dia_f):
    fig = modulo2.fig_serie(dia_f, F)
    y = np.asarray(fig.data[0].y, dtype=float)
    assert np.isnan(y[3]) and not (y == 0).any()           # 4 de septiembre: sin fila
    assert fig.data[0].connectgaps is False
    assert _formas(fig, modulo2.COLOR_SOMBREADO_SIN_DATO)    # tramos grises
    assert len(_sin_dato(fig)) >= 1                          # tramo largo (oct 21 – nov 30) rotulado


def test_seleccion_y_sombreado_de_eventos(dia_f):
    fig = modulo2.fig_serie(dia_f, F, ["15 de Septiembre"])
    assert len(_formas(fig, modulo2.COLOR_SOMBREADO_EVENTO)) == 1      # 15 y 16 son un tramo consecutivo
    assert any(a.text == "15 de Septiembre" for a in fig.layout.annotations)
    marcas = [t for t in fig.data if t.name == "Día de evento"][0]
    assert len(marcas.x) == 2 and set(marcas.text) == {"15 de Septiembre"}

    dos = modulo2.fig_serie(dia_f, F, ["Fiestas Agostinas", "20 de Octubre"])
    assert len(_formas(dos, modulo2.COLOR_SOMBREADO_EVENTO)) == 2

    ninguno = modulo2.fig_serie(dia_f, F, [])
    assert _formas(ninguno, modulo2.COLOR_SOMBREADO_EVENTO) == []
    todos = [t for t in ninguno.data if t.name == "Día de evento"][0]
    assert len(todos.x) == 4    # sin selección se marcan todos los días de evento


def test_serie_sin_datos_o_filtro_incompleto(diaria):
    vacia = modulo2.preparar_diaria(diaria.iloc[0:0], F)
    fig = modulo2.fig_serie(vacia, F)
    assert len(fig.data) == 0 and len(_sin_dato(fig)) == 1
    assert "Período: sep 2025 – nov 2025" in fig.layout.title.text
    sin_sub = Filtros(mes_ini="2025-09", mes_fin="2025-11", tipo="extranjero")
    assert len(modulo2.fig_serie(modulo2.preparar_diaria(diaria, sin_sub), sin_sub).data) == 0


def test_titulo_declara_periodo_fuente_subdestino_y_tipo_de_medida(dia_f):
    titulo = modulo2.fig_serie(dia_f, F).layout.title.text
    for texto in ("Período: sep 2025 – nov 2025", "movilidad_diaria", "Coban", "no visitantes únicos mensuales"):
        assert texto in titulo


# ----------------------------------------------------------------------------- lift
def test_eventos_disponibles_y_poda(dia_f):
    disp = modulo2.eventos_disponibles(dia_f)
    assert disp == ["15 de Septiembre", "Fiestas Agostinas", "20 de Octubre"]   # orden de aparición, sin «Regular»
    assert modulo2.podar_eventos(["20 de Octubre", "Semana Santa"], disp) == ["20 de Octubre"]
    assert modulo2.podar_eventos(None, disp) == []
    assert modulo2.eventos_disponibles(dia_f.iloc[0:0]) == []


def test_lift_con_dias_regulares_comparables(dia_f):
    disp = modulo2.eventos_disponibles(dia_f)
    tabla = modulo2.tabla_lift(dia_f, disp, [])
    assert tabla["evento"].tolist() == ["20 de Octubre", "15 de Septiembre", "Fiestas Agostinas"]   # NaN al final
    por_evento = tabla.set_index("evento")
    # lunes regulares: 10, 20, 12 -> 14 ; martes regulares: 100, 100 -> 100
    assert por_evento.loc["20 de Octubre", "lift_pct"] == pytest.approx((24 / 14 - 1) * 100)
    assert por_evento.loc["15 de Septiembre", "lift_pct"] == pytest.approx((90 / 57 - 1) * 100)
    assert por_evento.loc["15 de Septiembre", "media_evento"] == pytest.approx(90.0)
    assert por_evento.loc["15 de Septiembre", "media_regular"] == pytest.approx(57.0)
    assert (por_evento.loc["15 de Septiembre", "n_dias_evento"], por_evento.loc["15 de Septiembre", "n_dias_regular"]) \
        == (2, 5)
    assert por_evento.loc["15 de Septiembre", "lift_pct"] == pytest.approx(
        metricas.lift_evento(dia_f, "15 de Septiembre").lift_pct)   # reutiliza metricas


def test_lift_sin_dias_comparables_es_sin_dato_no_cero(dia_f):
    tabla = modulo2.tabla_lift(dia_f, modulo2.eventos_disponibles(dia_f), [])
    fila = tabla[tabla["evento"] == "Fiestas Agostinas"].iloc[0]    # miércoles sin días regulares
    assert pd.isna(fila["lift_pct"]) and fila["n_dias_evento"] == 0
    textos = list(_textos(modulo2.render_lift(tabla, F, mostrando_todos=True)))
    assert "Sin dato" in textos
    assert "+0.0 %" not in textos and "0.0 %" not in textos
    assert "+71.4 %" in textos and "+57.9 %" in textos


def test_seleccion_de_eventos_actualiza_el_lift(dia_f):
    disp = modulo2.eventos_disponibles(dia_f)
    uno = modulo2.tabla_lift(dia_f, disp, ["20 de Octubre"])
    assert uno["evento"].tolist() == ["20 de Octubre"]
    vacia = modulo2.render_lift(modulo2.tabla_lift(dia_f.iloc[0:0], [], []), F, True)
    assert any("Sin dato" in t for t in _textos(vacia))


# ------------------------------------------------------------------- patrón semanal
def test_patron_semanal_por_modo(dia_f):
    reg = modulo2.patron_modo(dia_f, "regulares", [])
    assert reg["presencia_media"].iloc[:2].tolist() == pytest.approx([14.0, 100.0])
    assert reg["n_dias"].iloc[:2].tolist() == [3, 2]
    todos = modulo2.patron_modo(dia_f, "todos", [])
    assert todos["presencia_media"].iloc[0] == pytest.approx((10 + 20 + 12 + 30 + 24) / 5)
    assert todos["n_dias"].iloc[0] == 5
    ev = modulo2.patron_modo(dia_f, "eventos", ["15 de Septiembre"])
    assert ev["presencia_media"].iloc[:2].tolist() == pytest.approx([30.0, 150.0])
    assert modulo2.patron_modo(dia_f, "eventos", []) is None
    assert reg["dia_semana"].tolist() == list(metricas.DIAS_SEMANA)


def test_grafico_semanal_resalta_fin_de_semana_y_no_inventa_ceros(dia_f):
    fig = modulo2.fig_semanal(dia_f, F, "regulares", [])
    entre, finde = fig.data[0], fig.data[1]
    assert list(entre.x) == modulo2.DIAS_ETIQUETA
    y_entre = np.asarray(entre.y, dtype=float)
    y_finde = np.asarray(finde.y, dtype=float)
    assert y_entre[0] == pytest.approx(14.0) and np.isnan(y_entre[5]) and np.isnan(y_entre[6])
    assert y_finde[5] == pytest.approx(40.0) and y_finde[6] == pytest.approx(50.0) and np.isnan(y_finde[0])
    assert entre.marker.color != finde.marker.color
    assert len(_sin_dato(fig)) == 3                      # miércoles, jueves y viernes sin días regulares
    assert list(entre.customdata)[:2] == [3, 2]          # días observados disponibles en el hover
    assert "Período: sep 2025 – nov 2025" in fig.layout.title.text


def test_semanal_respeta_filtros_globales_y_modo_eventos(diaria):
    nac = modulo2.preparar_diaria(diaria, F_NAC)
    fig = modulo2.fig_semanal(nac, F_NAC, "regulares", [])
    assert np.asarray(fig.data[0].y, dtype=float)[0] == pytest.approx(777.0)
    sin_sel = modulo2.fig_semanal(modulo2.preparar_diaria(diaria, F), F, "eventos", [])
    assert len(sin_sel.data) == 0 and sin_sel.layout.annotations[0].text == "Seleccione al menos un evento"


def test_el_evento_seleccionado_actualiza_el_patron_semanal(dia_f):
    fig = modulo2.fig_semanal(dia_f, F, "eventos", ["15 de Septiembre"])
    y = np.asarray(fig.data[0].y, dtype=float)
    assert y[0] == pytest.approx(30.0) and y[1] == pytest.approx(150.0)


# ------------------------------------------------------------------- mapa de calor
def test_matriz_dia_mes_usa_solo_diaria_y_no_convierte_ausencias_en_cero(dia_f):
    meses = pd.date_range("2025-09-01", "2025-11-01", freq="MS")
    z, n = modulo2.matriz_dia_mes(dia_f, meses, "regulares", [])
    assert z.shape == (7, 3)
    assert z[0, 0] == pytest.approx(15.0) and n[0, 0] == 2     # lunes de sep: 10 y 20
    assert z[0, 1] == pytest.approx(12.0) and n[0, 1] == 1     # lunes de oct
    assert z[5, 0] == pytest.approx(40.0) and z[6, 0] == pytest.approx(50.0)
    assert np.isnan(z[:, 2]).all() and (n[:, 2] == 0).all()    # noviembre sin cobertura
    z_todos, _ = modulo2.matriz_dia_mes(dia_f, meses, "todos", [])
    assert z_todos[0, 0] == pytest.approx(20.0)                # (10 + 20 + 30) / 3
    assert modulo2.matriz_dia_mes(dia_f, meses, "eventos", []) is None


def test_fig_heatmap_orden_cobertura_y_filtros(dia_f, diaria):
    fig = modulo2.fig_heatmap(dia_f, F, "regulares", [])
    assert list(fig.data[0].y) == modulo2.DIAS_ETIQUETA and fig.data[0].y[0] == "Lunes"
    assert list(fig.data[0].x) == ["sep 2025", "oct 2025", "nov 2025"]
    z = np.asarray(fig.data[0].z, dtype=float)
    assert np.isnan(z[:, 2]).all() and not (z == 0).any()
    assert len(_sin_dato(fig)) == 1                            # noviembre
    assert "Período: sep 2025 – nov 2025" in fig.layout.title.text
    assert modulo2.fig_heatmap(dia_f, F, "eventos", []).layout.annotations[0].text == "Seleccione al menos un evento"
    nac = modulo2.preparar_diaria(diaria, F_NAC)
    assert np.asarray(modulo2.fig_heatmap(nac, F_NAC, "regulares", []).data[0].z, dtype=float)[0, 0] == pytest.approx(777)
    vacio = modulo2.fig_heatmap(dia_f.iloc[0:0], F)
    assert len(vacio.data) == 0 and len(_sin_dato(vacio)) == 1


# ------------------------------------------------------------------------ pronóstico
def _mensual_sub():
    filas = []
    meses = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-03", "2026-04", "2026-05", "2026-06",
             "2026-07", "2026-08"]
    for i, mes in enumerate(meses):   # Coban extranjero: totales 100, 110, ..., 190
        for seg, vis in (("mas_de_1_dia", 60 + 6 * i), ("menos_de_1_dia", 40 + 4 * i)):
            filas.append(dict(destino_clave=AV, subdestino="Coban", tipo="extranjero",
                              anio_mes=pd.Timestamp(f"{mes}-01"), segmento=seg, visitantes=vis, dias_persona=1.0))
    filas.append(dict(destino_clave="antigua", subdestino="Coban", tipo="extranjero",
                      anio_mes=pd.Timestamp("2026-01-01"), segmento="mas_de_1_dia", visitantes=9999, dias_persona=1.0))
    return pd.DataFrame(filas)


def _pron_fila(sub, tipo, mes, est, inf, sup, mape=12.5, mape_base=14.0, mejora=True, es_est=True, destino=AV):
    return dict(destino_clave=destino, subdestino=sub, tipo=tipo, anio_mes=pd.Timestamp(mes), estimacion=est,
                lim_inf=inf, lim_sup=sup, metodo="razon_media", mape_loo=mape, rmse_loo=1234.0, mae_loo=987.0,
                n_loo=8, es_estimacion=es_est, migracion_mejora_a_la_base=mejora, mape_loo_base=mape_base,
                nota="Intervalo orientativo.")


@pytest.fixture
def pron():
    return pd.DataFrame([
        _pron_fila("Coban", "extranjero", "2026-01-01", 110, 90, 130),
        _pron_fila("Coban", "extranjero", "2026-02-01", 120, 100, 140),
        _pron_fila("Coban", "extranjero", "2026-03-01", 999, 0, 999),                  # fuera de ene–feb
        _pron_fila("Coban", "nacional", "2026-01-01", 200, 150, 250, mape=15.0, mape_base=10.0, mejora=False),
        _pron_fila("Coban", "nacional", "2026-02-01", 210, 160, 260, mape=15.0, mape_base=10.0, mejora=False),
        _pron_fila("Lanquin", "extranjero", "2026-01-01", 5, 1, 9),
        _pron_fila("Lanquin", "extranjero", "2026-02-01", 6, 2, 10),
        _pron_fila("Coban", "extranjero", "2026-01-01", 7777, 1, 9999, destino="antigua"),
    ])


@pytest.fixture
def resumen():
    return pd.DataFrame({"tipo": ["extranjero", "nacional"], "mape_mediano": [21.2, 15.2],
                         "mape_mediano_base_sin_migracion": [34.8, 10.6]})


def _obs(f=F_SIN_RANGO, sub=None):
    return modulo2.visitantes_mensuales(modulo1.preparar(_mensual_sub() if sub is None else sub, f))


def test_pronostico_limitado_a_ene_feb_2026_y_a_una_serie(pron):
    est = modulo2.datos_pronostico(pron, F)
    assert est["anio_mes"].tolist() == [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01")]
    assert est["estimacion"].tolist() == [110, 120]            # sin Lanquin, sin nacionales, sin antigua
    assert est["lim_inf"].tolist() == [90, 100] and est["lim_sup"].tolist() == [130, 140]
    assert modulo2.datos_pronostico(pron, F_NAC)["estimacion"].tolist() == [200, 210]
    assert modulo2.datos_pronostico(pron, replace(F, subdestino="Lanquin"))["estimacion"].tolist() == [5, 6]
    assert modulo2.datos_pronostico(pron, replace(F, tipo=None)).empty     # no se mezclan tipos
    assert modulo2.datos_pronostico(pron.assign(es_estimacion=False), F).empty


def test_el_rango_global_no_oculta_la_estimacion(pron):
    corto = replace(F, mes_ini="2025-09", mes_fin="2025-10")
    assert len(modulo2.datos_pronostico(pron, corto)) == 2


def test_observado_y_estimacion_separados_con_estilo_exclusivo(pron):
    est = modulo2.datos_pronostico(pron, F)
    fig = modulo2.fig_pronostico(_obs(), est, F)
    por_nombre = {t.name: t for t in fig.data if t.name}
    obs, estim = por_nombre["Observado"], por_nombre["Estimación"]
    y_obs = np.asarray(obs.y, dtype=float)
    y_est = np.asarray(estim.y, dtype=float)
    assert len(obs.x) == 12 and obs.x[4] == "ene 2026" and obs.x[5] == "feb 2026"
    assert np.isnan(y_obs[4]) and np.isnan(y_obs[5])               # lo estimado no se pinta como observado
    assert y_obs[0] == pytest.approx(100.0) and y_obs[3] == pytest.approx(130.0) and y_obs[6] == pytest.approx(140.0)
    assert y_est[4] == pytest.approx(110.0) and y_est[5] == pytest.approx(120.0)
    assert np.isnan(np.delete(y_est, [4, 5])).all()
    assert estim.line.color == theme.COLOR_ESTIMACION and estim.line.dash == "dash"
    assert obs.line.color == theme.COLOR_OBSERVADO != theme.COLOR_ESTIMACION
    assert "Estimación" in list(estim.text)
    assert "Estimación: ene 2026 y feb 2026" in fig.layout.title.text
    assert "Período: sep 2025 – ago 2026" in fig.layout.title.text
    assert _sin_dato(fig) == []     # cada mes está observado o estimado


def test_banda_de_error_usa_lim_inf_y_lim_sup(pron):
    fig = modulo2.fig_pronostico(_obs(), modulo2.datos_pronostico(pron, F), F)
    inferior = [t for t in fig.data if t.fill == "tonexty"][0]
    superior = fig.data[list(fig.data).index(inferior) - 1]
    assert inferior.fillcolor == theme.COLOR_ESTIMACION_BANDA
    assert np.asarray(inferior.y, dtype=float)[4:6].tolist() == [90, 100]
    assert np.asarray(superior.y, dtype=float)[4:6].tolist() == [130, 140]
    assert superior.showlegend is False


def test_no_se_suman_subdestinos_en_el_pronostico(pron):
    est = modulo2.datos_pronostico(pron, F)
    fig = modulo2.fig_pronostico(_obs(), est, F)
    y_est = np.asarray([t for t in fig.data if t.name == "Estimación"][0].y, dtype=float)
    assert y_est[4] == 110 and y_est[4] != 110 + 5     # no se agrega Lanquin
    assert 9999 not in np.asarray(fig.data[0].y, dtype=float)    # el otro destino no entra al observado


def test_meses_sin_observacion_ni_estimacion_quedan_como_hueco(pron):
    sub = _mensual_sub()
    sub = sub[sub["anio_mes"] != pd.Timestamp("2026-05-01")]
    fig = modulo2.fig_pronostico(_obs(sub=sub), modulo2.datos_pronostico(pron, F), F)
    y_obs = np.asarray(fig.data[0].y, dtype=float)
    assert np.isnan(y_obs[8]) and fig.data[0].connectgaps is False      # mayo 2026 (sep=0 ... may=8)
    assert len(_sin_dato(fig)) == 1
    assert y_obs[7] == pytest.approx(150.0) and y_obs[9] == pytest.approx(170.0)   # abr y jun siguen observados


def test_serie_sin_estimacion_muestra_solo_observado(pron):
    fig = modulo2.fig_pronostico(_obs(), modulo2.datos_pronostico(pron, replace(F, subdestino="Cuevas De Candelaria")), F)
    assert [t.name for t in fig.data] == ["Observado"] or len(fig.data) == 1
    sin_nada = modulo2.fig_pronostico(pd.Series(dtype=float), modulo2.datos_pronostico(pron.iloc[0:0], F), F)
    assert len(sin_nada.data) == 0 and len(_sin_dato(sin_nada)) == 1


def test_tarjetas_mape_rmse_mae_y_metodo(pron):
    textos = list(_textos(modulo2.tarjetas_error(modulo2.datos_pronostico(pron, F))))
    assert "12.5 %" in textos and "1,234 visitantes" in textos and "987 visitantes" in textos
    assert any("razon_media" in t and "8 meses" in t for t in textos)
    sin = list(_textos(modulo2.tarjetas_error(modulo2.datos_pronostico(pron.iloc[0:0], F))))
    assert sin.count("Sin dato") == 3


def test_aviso_nacionales_compara_con_la_linea_base(pron, resumen):
    est = modulo2.datos_pronostico(pron, F_NAC)
    avisos = modulo2.aviso_pronostico(est, resumen, F_NAC)
    alertas = [a for a in avisos if a.color == "warning"]
    assert len(alertas) == 1
    texto = " ".join(_textos(alertas[0]))
    assert "15.2 %" in texto and "10.6 %" in texto and "línea base" in texto
    sin_resumen = modulo2.aviso_pronostico(est, resumen.iloc[0:0], F_NAC)
    assert "15.0 %" in " ".join(_textos([a for a in sin_resumen if a.color == "warning"][0]))


def test_aviso_extranjeros_sin_advertencia_salvo_error_alto(pron, resumen):
    est = modulo2.datos_pronostico(pron, F)
    avisos = modulo2.aviso_pronostico(est, resumen, F)
    assert all(a.color == "light" for a in avisos)
    assert "Estimación" in " ".join(_textos(avisos[0])) and "razon_media" in " ".join(_textos(avisos[0]))
    alto = modulo2.aviso_pronostico(est.assign(mape_loo=45.0), resumen, F)
    assert any(a.color == "warning" and "45.0 %" in " ".join(_textos(a)) for a in alto)
    vacio = modulo2.aviso_pronostico(est.iloc[0:0], resumen, F)
    assert "Sin dato" in " ".join(_textos(vacio[0]))


# ------------------------------------------------------------------ archivos faltantes
def test_sin_archivos_todo_queda_en_sin_dato(monkeypatch):
    def falla(nombre):
        raise FileNotFoundError(nombre)
    monkeypatch.setattr(modulo2.datos, "cargar", falla)
    df = modulo2.preparar_diaria(modulo2._leer_diaria(), F)
    assert df.empty and modulo2.eventos_disponibles(df) == []
    assert len(modulo2.fig_serie(df, F).data) == 0
    assert len(modulo2.fig_semanal(df, F).data) == 0 and len(modulo2.fig_heatmap(df, F).data) == 0
    est = modulo2.datos_pronostico(modulo2._leer_pron(), F)
    obs = modulo2.visitantes_mensuales(modulo1.preparar(modulo2._leer_sub(), F_SIN_RANGO))
    assert est.empty and len(obs) == 0
    assert len(modulo2.fig_pronostico(obs, est, F).data) == 0


# ------------------------------------------------------------- integración con Dash
def test_layout_ids_unicos_con_prefijo_y_sin_descargas():
    layout = modulo2.layout()
    main.verificar_ids_unicos(layout)
    ids = [str(i) for i in main.ids_del_layout(layout)]
    assert ids and all(i.startswith("m2-") for i in ids)
    for requerido in (modulo2.ID_EVENTOS, modulo2.ID_MODO, modulo2.ID_G_SERIE, modulo2.ID_LIFT,
                      modulo2.ID_G_SEMANAL, modulo2.ID_G_HEATMAP, modulo2.ID_G_PRON,
                      modulo2.ID_PRON_METRICAS, modulo2.ID_PRON_AVISO):
        assert requerido in ids
    clases = {type(c).__name__ for c in main.recorrer_componentes(layout)}
    assert not clases & {"Download", "DataTable"}
    graficos = [c for c in main.recorrer_componentes(layout) if type(c).__name__ == "Graph"]
    assert len(graficos) == 4 and all(g.config == {"displayModeBar": False} for g in graficos)
    textos = " ".join(_textos(layout))
    assert "Observado" in textos or any("Observado" in t for t in _textos(layout))


def _entrada(app, salida):
    clave = next(k for k in app.callback_map if salida in k)
    return app.callback_map[clave]


def _tiene(lista, id_, propiedad):
    return any(str(e.get("id")) == id_ and e.get("property") == propiedad for e in lista)


def test_integracion_con_main_y_visualizaciones_vinculadas():
    sub = _mensual_sub()
    opciones = main.cargar_opciones(sub)
    app = main.crear_app(opciones, implementaciones={"demanda": modulo1, "dinamica": modulo2})   # IDs/Outputs únicos
    ids = [str(i) for i in main.ids_del_layout(app.layout)]
    assert len(ids) == len(set(ids))
    # el selector de eventos alimenta serie+lift, patrón semanal y mapa de calor (≥ 3 visuales vinculadas)
    for salida in ("m2-grafico-serie.figure", "m2-lift.children", "m2-grafico-semanal.figure",
                   "m2-grafico-heatmap.figure"):
        entrada = _entrada(app, salida)
        assert _tiene(entrada["inputs"], modulo2.ID_EVENTOS, "value"), salida
        assert _tiene(entrada["inputs"], "store-filtros", "data"), salida
    assert _tiene(_entrada(app, "m2-grafico-heatmap.figure")["inputs"], modulo2.ID_MODO, "value")
    assert _tiene(_entrada(app, "m2-grafico-pronostico.figure")["inputs"], "store-filtros", "data")
    # sin ciclos: el callback que escribe las opciones solo LEE el valor como State
    opciones_cb = _entrada(app, "m2-eventos.options")
    assert not _tiene(opciones_cb["inputs"], modulo2.ID_EVENTOS, "value")
    assert _tiene(opciones_cb["state"], modulo2.ID_EVENTOS, "value")
    # el Módulo 2 no comparte salidas con el Módulo 1
    claves = " ".join(app.callback_map)
    for salida in ("m1-grafico-ranking.figure", "m2-grafico-pronostico.figure", "m2-pron-aviso.children"):
        assert salida in claves
