"""Pruebas de app/utils/metricas.py con datos sintéticos (sin archivos institucionales)."""
import numpy as np
import pandas as pd
import pytest

from app.utils import metricas
from app.utils.metricas import DIAS_SEMANA, Lift, PromedioMensual


# ---------------------------------------------------------------------- constructores
def _m(filas, sub="Coban", tipo="extranjero"):
    """Mensual: filas = (YYYY-MM, segmento, visitantes, dias_persona, permanencia_prom)."""
    return pd.DataFrame([
        dict(subdestino=sub, tipo=tipo, anio_mes=pd.Timestamp(f"{mes}-01"), segmento=seg,
             visitantes=vis, dias_persona=dias, permanencia_prom=perm)
        for mes, seg, vis, dias, perm in filas])


def _d(filas, sub="Coban", tipo="extranjero"):
    """Diaria: filas = (fecha, evento, presencia_total). El total se reparte en dos países (40/60)."""
    out = []
    for fecha, evento, total in filas:
        for pais, frac in (("Estados Unidos", 0.4), ("Mexico", 0.6)):
            out.append(dict(subdestino=sub, tipo=tipo, fecha=pd.Timestamp(fecha), pais=pais,
                            evento=evento, es_regular=(evento == "Regular"),
                            presencia=np.nan if total is None else total * frac))
    return pd.DataFrame(out)


def _vacio_m():
    return pd.DataFrame(columns=["subdestino", "tipo", "anio_mes", "segmento", "visitantes",
                                 "dias_persona", "permanencia_prom"])


def _vacio_d():
    return pd.DataFrame(columns=["subdestino", "tipo", "fecha", "pais", "evento", "es_regular", "presencia"])


# 2025-09-01 lunes | 09-02 martes | 09-03 miércoles | 09-08 lunes | 09-09 martes | 09-15 lunes | 09-17 miércoles
REGULARES = [("2025-09-01", "Regular", 10), ("2025-09-08", "Regular", 20),
             ("2025-09-02", "Regular", 100), ("2025-09-09", "Regular", 100)]


# ------------------------------------------------------------------ estadia_ponderada
def test_estadia_ponderada_difiere_del_promedio_simple():
    df = _m([("2025-09", "mas_de_1_dia", 10, 20, 2.0),
             ("2025-10", "mas_de_1_dia", 90, 450, 5.0),
             ("2025-10", "menos_de_1_dia", 1000, 9999, 9.0)])   # otro segmento: se ignora
    assert metricas.estadia_ponderada(df) == pytest.approx(470 / 100)   # 4.7
    assert df.loc[df["segmento"] == "mas_de_1_dia", "permanencia_prom"].mean() == pytest.approx(3.5)
    assert metricas.estadia_ponderada(df) != pytest.approx(3.5)


def test_estadia_ponderada_denominador_cero_o_sin_filas_es_nan():
    assert pd.isna(metricas.estadia_ponderada(_m([("2025-09", "mas_de_1_dia", 0, 0, 0.0)])))
    assert pd.isna(metricas.estadia_ponderada(_m([("2025-09", "menos_de_1_dia", 5, 5, 1.0)])))
    assert pd.isna(metricas.estadia_ponderada(_vacio_m()))


def test_estadia_ponderada_excluye_nulos_de_ambas_sumas():
    df = _m([("2025-09", "mas_de_1_dia", 10, 20, 2.0),
             ("2025-10", "mas_de_1_dia", 100, np.nan, np.nan),    # sin días-persona
             ("2025-11", "mas_de_1_dia", np.nan, 5, 5.0)])         # sin visitantes
    assert metricas.estadia_ponderada(df) == pytest.approx(2.0)   # no 20/110 ni 25/10


def test_estadia_ponderada_rechaza_negativos():
    with pytest.raises(ValueError):
        metricas.estadia_ponderada(_m([("2025-09", "mas_de_1_dia", -1, 5, 5.0)]))


def test_estadia_ponderada_ignora_permanencia_prom():
    a = _m([("2025-09", "mas_de_1_dia", 10, 20, 99.0)])
    b = _m([("2025-09", "mas_de_1_dia", 10, 20, 1.0)])
    assert metricas.estadia_ponderada(a) == metricas.estadia_ponderada(b) == pytest.approx(2.0)


# ------------------------------------------------- validaciones comunes (mezclas, estimación)
@pytest.mark.parametrize("funcion", [metricas.estadia_ponderada,
                                     metricas.proporcion_turista_excursionista,
                                     metricas.promedio_mensual_visitantes])
def test_mensuales_rechazan_mezcla_de_subdestinos_y_tipos(funcion):
    base = [("2025-09", "mas_de_1_dia", 10, 20, 2.0), ("2025-09", "menos_de_1_dia", 5, 5, 1.0)]
    with pytest.raises(ValueError):
        funcion(pd.concat([_m(base, sub="Coban"), _m(base, sub="Lanquin")]))
    with pytest.raises(ValueError):
        funcion(pd.concat([_m(base, tipo="nacional"), _m(base, tipo="extranjero")]))


@pytest.mark.parametrize("funcion", [metricas.estadia_ponderada,
                                     metricas.proporcion_turista_excursionista,
                                     metricas.promedio_mensual_visitantes])
def test_mensuales_rechazan_estimaciones(funcion):
    df = _m([("2025-09", "mas_de_1_dia", 10, 20, 2.0)]).assign(es_estimacion=True)
    with pytest.raises(ValueError):
        funcion(df)


def test_columnas_faltantes():
    with pytest.raises(KeyError):
        metricas.estadia_ponderada(_m([("2025-09", "mas_de_1_dia", 1, 1, 1.0)]).drop(columns="tipo"))


# --------------------------------------------------- proporcion_turista_excursionista
def test_proporcion_por_mes_sin_total_del_periodo():
    df = _m([("2025-10", "mas_de_1_dia", 5, 0, 0), ("2025-10", "menos_de_1_dia", 15, 0, 0),
             ("2025-09", "mas_de_1_dia", 30, 0, 0), ("2025-09", "menos_de_1_dia", 10, 0, 0)])
    out = metricas.proporcion_turista_excursionista(df)
    assert list(out.columns) == ["anio_mes", "prop_mas_de_1_dia", "prop_menos_de_1_dia"]
    assert out["anio_mes"].tolist() == [pd.Timestamp("2025-09-01"), pd.Timestamp("2025-10-01")]
    assert out["prop_mas_de_1_dia"].tolist() == pytest.approx([0.75, 0.25])
    assert out["prop_menos_de_1_dia"].tolist() == pytest.approx([0.25, 0.75])
    assert "visitantes" not in out.columns   # no se construye un total del período


def test_proporcion_suma_filas_del_mismo_mes_y_segmento():
    df = _m([("2025-09", "mas_de_1_dia", 20, 0, 0), ("2025-09", "mas_de_1_dia", 10, 0, 0),   # dos países
             ("2025-09", "menos_de_1_dia", 10, 0, 0)])
    assert metricas.proporcion_turista_excursionista(df)["prop_mas_de_1_dia"].iloc[0] == pytest.approx(0.75)


def test_proporcion_segmento_faltante_nulo_o_total_cero_es_nan_no_cero():
    df = _m([("2025-09", "mas_de_1_dia", 8, 0, 0),                                   # falta menos_de_1_dia
             ("2025-10", "mas_de_1_dia", np.nan, 0, 0), ("2025-10", "menos_de_1_dia", 4, 0, 0),
             ("2025-11", "mas_de_1_dia", 0, 0, 0), ("2025-11", "menos_de_1_dia", 0, 0, 0)])
    out = metricas.proporcion_turista_excursionista(df)
    assert out[["prop_mas_de_1_dia", "prop_menos_de_1_dia"]].isna().all().all()
    assert len(out) == 3


def test_proporcion_segmento_desconocido_y_vacio():
    with pytest.raises(ValueError):
        metricas.proporcion_turista_excursionista(_m([("2025-09", "otro", 1, 0, 0)]))
    assert metricas.proporcion_turista_excursionista(_vacio_m()).empty


# ------------------------------------------------------ promedio_mensual_visitantes
def test_promedio_mensual_no_suma_meses():
    df = _m([("2025-09", "mas_de_1_dia", 30, 0, 0), ("2025-09", "menos_de_1_dia", 10, 0, 0),
             ("2025-10", "mas_de_1_dia", 5, 0, 0), ("2025-10", "menos_de_1_dia", 15, 0, 0)])
    res = metricas.promedio_mensual_visitantes(df)
    assert isinstance(res, PromedioMensual)
    assert res.promedio == pytest.approx(30.0)   # (40 + 20) / 2, no 60
    assert res.n_meses == 2


def test_promedio_mensual_excluye_meses_incompletos_o_con_nulos():
    df = _m([("2025-09", "mas_de_1_dia", 30, 0, 0), ("2025-09", "menos_de_1_dia", 10, 0, 0),
             ("2025-10", "mas_de_1_dia", 8, 0, 0),                                       # falta un segmento
             ("2025-11", "mas_de_1_dia", np.nan, 0, 0), ("2025-11", "menos_de_1_dia", 5, 0, 0)])
    res = metricas.promedio_mensual_visitantes(df)
    assert res == PromedioMensual(pytest.approx(40.0), 1)


def test_promedio_mensual_vacio_es_nan_con_cero_meses():
    res = metricas.promedio_mensual_visitantes(_vacio_m())
    assert pd.isna(res.promedio) and res.n_meses == 0


# ------------------------------------------------------------------------ lift_evento
def test_lift_compara_con_el_mismo_dia_de_semana():
    df = _d(REGULARES + [("2025-09-15", "Fiesta", 30)])   # lunes de evento
    res = metricas.lift_evento(df, "Fiesta")
    assert isinstance(res, Lift)
    assert res.media_regular == pytest.approx(15.0)       # media de lunes regulares (10, 20)
    assert res.media_evento == pytest.approx(30.0)        # 30 sumando países, no 12 ni 18
    assert res.lift_pct == pytest.approx(100.0)
    assert (res.n_dias_evento, res.n_dias_regular) == (1, 2)
    # Con la media regular de TODOS los días el resultado sería otro (57.5 -> -47.8 %): no se usa.
    assert res.lift_pct != pytest.approx((30 / 57.5 - 1) * 100)


def test_lift_excluye_dias_de_evento_sin_dia_regular_equivalente():
    df = _d(REGULARES + [("2025-09-15", "Fiesta", 30), ("2025-09-17", "Fiesta", 50)])  # miércoles sin regulares
    res = metricas.lift_evento(df, "Fiesta")
    assert res.lift_pct == pytest.approx(100.0)
    assert res.n_dias_evento == 1


def test_lift_sin_dias_comparables_o_evento_inexistente_es_nan():
    solo_miercoles = _d(REGULARES + [("2025-09-17", "Feria", 50)])
    res = metricas.lift_evento(solo_miercoles, "Feria")
    assert pd.isna(res.lift_pct) and res.n_dias_evento == 0
    assert pd.isna(metricas.lift_evento(_d(REGULARES), "Fiesta").lift_pct)
    assert pd.isna(metricas.lift_evento(_vacio_d(), "Fiesta").lift_pct)


def test_lift_media_regular_cero_es_nan():
    df = _d([("2025-09-01", "Regular", 0), ("2025-09-15", "Fiesta", 30)])
    res = metricas.lift_evento(df, "Fiesta")
    assert pd.isna(res.lift_pct)
    assert res.media_evento == pytest.approx(30.0)


def test_lift_ignora_dias_sin_dato_en_lugar_de_contarlos_como_cero():
    df = _d(REGULARES + [("2025-09-15", "Fiesta", 30), ("2025-09-22", "Fiesta", None)])
    res = metricas.lift_evento(df, "Fiesta")
    assert res.n_dias_evento == 1
    assert res.media_evento == pytest.approx(30.0)


def test_lift_rechazos():
    base = _d(REGULARES + [("2025-09-15", "Fiesta", 30)])
    with pytest.raises(ValueError):
        metricas.lift_evento(base, "Regular")
    with pytest.raises(ValueError):
        metricas.lift_evento(pd.concat([base, _d(REGULARES, sub="Lanquin")]), "Fiesta")
    with pytest.raises(ValueError):
        metricas.lift_evento(pd.concat([base, _d(REGULARES, tipo="nacional")]), "Fiesta")
    conflicto = base.copy()
    conflicto.loc[(conflicto["fecha"] == "2025-09-15") & (conflicto["pais"] == "Mexico"), "evento"] = "Otro"
    with pytest.raises(ValueError):
        metricas.lift_evento(conflicto, "Fiesta")
    with pytest.raises(ValueError):
        metricas.lift_evento(base.assign(es_estimacion=True), "Fiesta")


# --------------------------------------------------------------------- patron_semanal
def test_patron_semanal_no_duplica_por_pais_y_conserva_el_orden():
    df = _d([("2025-09-01", "Regular", 10), ("2025-09-08", "Regular", 20), ("2025-09-02", "Regular", 100)])
    out = metricas.patron_semanal(df)
    assert out["dia_semana"].tolist() == list(DIAS_SEMANA)
    assert out["dia_semana_num"].tolist() == list(range(7))
    lunes, martes, miercoles = out.iloc[0], out.iloc[1], out.iloc[2]
    assert lunes["presencia_media"] == pytest.approx(15.0)    # media de fechas; las filas por país darían 7.5
    assert lunes["n_dias"] == 2
    assert martes["presencia_media"] == pytest.approx(100.0) and martes["n_dias"] == 1
    assert pd.isna(miercoles["presencia_media"]) and miercoles["n_dias"] == 0   # sin dato, no 0


def test_patron_semanal_solo_regulares_excluye_eventos():
    df = _d([("2025-09-01", "Regular", 10), ("2025-09-08", "Regular", 20), ("2025-09-15", "Fiesta", 60)])
    todos = metricas.patron_semanal(df).iloc[0]
    regulares = metricas.patron_semanal(df, solo_regulares=True).iloc[0]
    assert todos["presencia_media"] == pytest.approx(30.0) and todos["n_dias"] == 3
    assert regulares["presencia_media"] == pytest.approx(15.0) and regulares["n_dias"] == 2


def test_patron_semanal_dias_sin_dato_no_cuentan_como_cero():
    df = _d([("2025-09-02", "Regular", 100), ("2025-09-09", "Regular", None)])
    martes = metricas.patron_semanal(df).iloc[1]
    assert martes["presencia_media"] == pytest.approx(100.0)
    assert martes["n_dias"] == 1


def test_patron_semanal_vacio_y_rechazos():
    out = metricas.patron_semanal(_vacio_d())
    assert len(out) == 7 and out["presencia_media"].isna().all() and (out["n_dias"] == 0).all()
    with pytest.raises(ValueError):
        metricas.patron_semanal(pd.concat([_d(REGULARES), _d(REGULARES, sub="Lanquin")]))
    with pytest.raises(ValueError):
        metricas.patron_semanal(pd.concat([_d(REGULARES), _d(REGULARES, tipo="nacional")]))


# ------------------------------------------------------- no modificación de originales
def test_las_funciones_no_modifican_los_datos_de_entrada():
    mensual = _m([("2025-09", "mas_de_1_dia", 30, 90, 3.0), ("2025-09", "menos_de_1_dia", 10, 10, 1.0)])
    diaria = _d(REGULARES + [("2025-09-15", "Fiesta", 30)])
    m0, d0 = mensual.copy(), diaria.copy()
    metricas.estadia_ponderada(mensual)
    metricas.proporcion_turista_excursionista(mensual)
    metricas.promedio_mensual_visitantes(mensual)
    metricas.lift_evento(diaria, "Fiesta")
    metricas.patron_semanal(diaria)
    metricas.patron_semanal(diaria, solo_regulares=True)
    pd.testing.assert_frame_equal(mensual, m0)
    pd.testing.assert_frame_equal(diaria, d0)
