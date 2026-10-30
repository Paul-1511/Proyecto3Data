"""Pruebas de la parte 2 del ETL (ocupación, oferta, Tikal, AIMM, encuestas, pronóstico, contrato)."""
import numpy as np
import pandas as pd
import pytest

from etl import config
from etl.generar_contrato import DESC

faltan = [n for n in DESC if not (config.PROC / f"{n}.parquet").exists()]
pytestmark = pytest.mark.skipif(bool(faltan), reason=f"Corra `python -m etl.run_all` (faltan {faltan[:3]}...)")


def rd(n):
    return pd.read_parquet(config.PROC / f"{n}.parquet")


# ---------- ocupación y oferta ----------
def test_ocupacion_completa_y_en_fraccion():
    o = rd("ocupacion")
    assert len(o) == 22 * 36 and o.indice_ocupacion.between(0, 1).all()
    assert o.anio_mes.min() == pd.Timestamp("2023-01-01") and o.anio_mes.max() == pd.Timestamp("2025-12-01")


def test_ocupacion_sacatepequez_2024_coincide_con_boletin():
    # Contraste puntual con el boletín INGUAT 2024 (no se extrae a mano: es solo una prueba de sanidad)
    o = rd("ocupacion")
    x = o[(o.departamento == "Sacatepéquez") & (o.anio == 2024)].sort_values("mes")
    assert x.indice_pct.round().astype(int).tolist() == [90, 93, 95, 97, 71, 65, 76, 85, 83, 65, 82, 95]


def test_ocupacion_destino_seis_destinos_36_meses():
    d = rd("ocupacion_destino")
    assert d.groupby("destino_clave").size().eq(36).all() and d.destino_clave.nunique() == 6


def test_pacifico_esta_entre_escuintla_y_santa_rosa():
    o, d = rd("ocupacion"), rd("ocupacion_destino")
    p = d[d.destino_clave == "pacifico"].set_index("anio_mes").indice_ocupacion
    e = o[o.departamento == "Escuintla"].set_index("anio_mes").indice_ocupacion
    s = o[o.departamento == "Santa Rosa"].set_index("anio_mes").indice_ocupacion
    lo, hi = np.minimum(e, s).reindex(p.index), np.maximum(e, s).reindex(p.index)
    assert ((p >= lo - 1e-9) & (p <= hi + 1e-9)).all()
    assert set(d[d.destino_clave == "pacifico"].metodo) == {"ponderado_por_habitaciones"}


def test_oferta_cortes_anuales_y_2026_parcial():
    f = rd("oferta")
    assert len(f) == 330 and set(f.anio) == {2022, 2023, 2024, 2025, 2026}
    assert f[f.es_corte_parcial].anio.eq(2026).all()
    rep = f[f.anio == 2026].repite_valor_anio_previo.mean()
    assert 0.40 <= rep <= 0.55  # la guía: "cerca de la mitad" repite el valor previo


def test_oferta_destino_suma_pacifico():
    f, d = rd("oferta"), rd("oferta_destino")
    a = f[(f.anio == 2025) & f.departamento.isin(["Escuintla", "Santa Rosa"])].habitaciones.sum()
    b = d[(d.anio == 2025) & (d.destino_clave == "pacifico")].habitaciones.sum()
    assert a == b


# ---------- Tikal y AIMM ----------
def test_tikal_ceros_tratados_segun_regla():
    t = rd("tikal_mensual")
    assert len(t) == 116 and t.anio_mes.is_unique
    assert t.cero_dudoso.sum() == 1 and t[t.cero_dudoso].total.isna().all()
    assert t[t.cierre_pandemia].total.eq(0).all() and t.cierre_pandemia.sum() == 6
    ok = t.dropna(subset=["total"])
    assert (ok.nacionales + ok.extranjeros + ok.otros == ok.total).all()


def test_aimm_2023_reconstruido_desde_aerolineas_sin_segmento():
    t = rd("aimm_pasajeros_total")
    y = t.groupby("anio").pasajeros_total.sum()
    assert y[2022] == 186_324 and y[2023] == 284_365 and y[2024] == 365_422 and y[2025] == 390_584
    assert not t[t.anio == 2023].tiene_segmento.any()
    assert t[t.anio.isin([2022, 2024, 2025])].tiene_segmento.all()
    assert t.anio_mes.max() == pd.Timestamp("2026-04-01")


def test_aimm_operaciones_separa_cruces_y_poptun():
    o, a = rd("aimm_operaciones"), rd("aimm_operaciones_aux")
    assert o.groupby("anio").operaciones.sum().loc[2025] == 8_272
    assert set(a.categoria) == {"Cruces", "Aeródromo Poptún"}
    assert not o.operador.str.contains("Cruce|Popt", case=False).any()


def test_aimm_aerolineas_no_trae_total_duplicado():
    assert "Total Mes Aerolínea" not in rd("aimm_pasajeros_aerolinea").columns


# ---------- encuestas ----------
def test_encuestas_casos_y_escala():
    assert len(rd("encuesta_antigua_datos")) == 510 and len(rd("encuesta_peten_datos")) == 500
    for n in ("antigua", "peten"):
        s = rd(f"encuesta_{n}_satisfaccion")
        assert s.valor.between(1, 5).all() and s.id.nunique() == (510 if n == "antigua" else 500)


def test_encuestas_resumen_solo_por_segmento_nunca_total_destino():
    for n in ("antigua", "peten"):
        r = rd(f"encuesta_{n}_satisfaccion_resumen")
        assert set(r.dimension) <= {"procedencia", "es_pernocta", "lugar", "segmento_cuota"}
        assert not r.segmento.str.lower().isin(["total", "todos"]).any()
        assert np.allclose(r.pct_insatisfecho + r.pct_neutral + r.pct_satisfecho, 100)


def test_encuestas_gasto_es_declarado_y_sin_negativos():
    for n in ("antigua", "peten"):
        g = rd(f"encuesta_{n}_gasto_declarado")
        assert (g.gasto_declarado_total_q.dropna() >= 0).all()
        assert g.personas_gasto.dropna().gt(0).all()  # el centinela -1 pasa a NaN
        assert g.noches.dropna().gt(0).all()


def test_residentes_porcentaje_coincide_con_casos_sobre_base():
    t = rd("encuesta_residentes_tabulados")
    assert ((100 * t.casos / t.base - t.porcentaje).abs() <= 0.11).all()


# ---------- pronóstico ----------
def test_pronostico_solo_ene_feb_2026_y_es_estimacion():
    p = rd("pronostico_ene_feb_2026")
    assert set(p.anio_mes) == {pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01")}
    assert p.es_estimacion.all()
    assert len(p) == 25 * 2 * 2  # 25 subdestinos × 2 tipos × 2 meses


def test_pronostico_intervalos_y_errores_presentes():
    p = rd("pronostico_ene_feb_2026")
    assert (p.lim_inf >= 0).all() and (p.lim_inf <= p.estimacion).all() and (p.estimacion <= p.lim_sup).all()
    assert p[["mape_loo", "rmse_loo", "mae_loo"]].notna().all().all()
    assert p.n_loo.eq(8).all() or p.n_loo.between(6, 8).all()


def test_pronostico_usa_la_migracion_observada_de_ene_feb_2026():
    p = rd("pronostico_ene_feb_2026")
    m = rd("migracion_total_mensual").set_index("anio_mes").visitantes
    for t in p.anio_mes.unique():
        assert np.isclose(p[p.anio_mes == t].driver_migracion_visitantes.iloc[0], m[t])


def test_pronostico_entrenado_solo_con_meses_con_ambas_fuentes():
    d = rd("pronostico_loo_detalle")
    meses = sorted(d.anio_mes.unique())
    assert [m.strftime("%Y-%m") for m in meses] == ["2025-09", "2025-10", "2025-11", "2025-12",
                                                    "2026-03", "2026-04", "2026-05", "2026-06"]


def test_pronostico_no_se_estima_a_nivel_destino_ni_suma_subdestinos():
    p = rd("pronostico_ene_feb_2026")
    assert "total" not in " ".join(p.subdestino.str.lower().unique())
    assert set(p.tipo) == {"extranjero", "nacional"}


def test_pronostico_incluye_linea_base_y_variante_elegida():
    v, r = rd("pronostico_validacion"), rd("pronostico_resumen_modelo")
    assert "base_promedio" in set(v.variante)
    assert v.groupby(["subdestino", "tipo"]).es_elegida.sum().eq(1).all()
    assert set(r.tipo) == {"extranjero", "nacional"} and r.mape_mediano.notna().all()


def test_pronostico_plausible_frente_a_lo_observado():
    p = rd("pronostico_ene_feb_2026")
    s = rd("movilidad_subdestino_mes").groupby(["subdestino", "tipo", "anio_mes"]).visitantes.sum().reset_index()
    prom = s.groupby(["subdestino", "tipo"]).visitantes.mean()
    q = p.merge(prom.rename("prom").reset_index(), on=["subdestino", "tipo"])
    r = q.estimacion / q.prom
    assert r.between(0.2, 5).all()


def test_pronostico_chequeo_diario_coherente():
    c = rd("pronostico_chequeo_diario")
    assert c.correlacion_mensual_vs_presencia_diaria.median() > 0.7


def test_la_base_observada_no_tiene_ene_feb_2026_y_cobertura_lo_dice():
    c = rd("cobertura")
    for f in ("movilidad_mensual", "movilidad_diaria"):
        x = c[(c.fuente == f) & c.anio_mes.isin(pd.to_datetime(["2026-01-01", "2026-02-01"]))]
        assert not x.tiene_dato.any()
    oc = c[(c.fuente == "ocupacion")].set_index("anio_mes").tiene_dato
    assert oc["2023-01-01":"2025-12-01"].all() and not oc["2026-01-01":].any()


def test_cobertura_diaria_distingue_parcial_de_completa():
    c = rd("cobertura")
    d = c[(c.fuente == "movilidad_diaria")].set_index("anio_mes")
    assert d.loc["2025-04-01", "tiene_dato"] and not d.loc["2025-04-01", "cobertura_completa"]
    assert d.loc["2025-10-01", "cobertura_completa"]


# ---------- contrato ----------
def test_todo_parquet_esta_documentado_en_el_contrato():
    en_disco = {p.stem for p in config.PROC.glob("*.parquet")}
    assert en_disco == set(DESC), f"sin documentar: {en_disco - set(DESC)}; documentadas sin archivo: {set(DESC) - en_disco}"
    txt = (config.ROOT / "docs" / "data_contract.md").read_text(encoding="utf-8")
    assert all(f"## {n}" in txt for n in DESC)
