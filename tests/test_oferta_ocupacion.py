"""Pruebas de los cálculos del Módulo 3 (app/utils/oferta_ocupacion.py) con datos sintéticos."""
import numpy as np
import pandas as pd
import pytest

from app.utils import oferta_ocupacion as oo

MAS, MENOS = "mas_de_1_dia", "menos_de_1_dia"
AV = "Alta Verapaz"


# ----------------------------------------------------------------------- fixtures
@pytest.fixture
def oferta():
    filas = []
    for anio, hab in ((2022, 100), (2023, 110), (2024, 120), (2025, 130), (2026, 130)):
        for tipo, factor in (("Hotel", 1), ("Hospedaje", 2)):
            filas.append(dict(anio=anio, departamento=AV, tipo_alojamiento=tipo, establecimientos=10 * factor,
                              habitaciones=hab * factor, plazas_cama=3 * hab * factor,
                              es_corte_parcial=anio == 2026, repite_valor_anio_previo=anio == 2026))
    filas.append(dict(anio=2025, departamento="Petén", tipo_alojamiento="Hotel", establecimientos=999,
                      habitaciones=999, plazas_cama=999, es_corte_parcial=False, repite_valor_anio_previo=False))
    return pd.DataFrame(filas)


@pytest.fixture
def ocup():
    meses = pd.date_range("2023-01-01", "2025-12-01", freq="MS")
    filas = []
    for i, m in enumerate(meses):
        filas.append(dict(departamento=AV, anio_mes=m, indice_pct=30 + (m.month == 6) * 20 - (m.month == 11) * 10
                          + (m.year - 2023) * 10))
        filas.append(dict(departamento="Petén", anio_mes=m, indice_pct=60.0))
    return pd.DataFrame(filas)


def _mov(sub, tipo, mes, mas, menos, destino="alta_verapaz"):
    m = pd.Timestamp(f"{mes}-01")
    return [dict(destino_clave=destino, subdestino=sub, tipo=tipo, anio_mes=m, segmento=MAS, visitantes=mas),
            dict(destino_clave=destino, subdestino=sub, tipo=tipo, anio_mes=m, segmento=MENOS, visitantes=menos)]


@pytest.fixture
def mov():
    filas = []
    for mes, base in (("2025-09", 100), ("2025-10", 120), ("2025-11", 110), ("2025-12", 150),
                      ("2026-03", 130), ("2026-04", 140)):
        filas += _mov("Coban", "extranjero", mes, base, base)          # visitantes = 2 × base
        filas += _mov("Lanquin", "extranjero", mes, base / 2, base / 2)
        filas += _mov("Coban", "nacional", mes, 1000, 1000)
    filas += _mov("Antigua Guatemala", "extranjero", "2025-09", 9999, 9999, destino="antigua")
    filas += _mov("Coban", "sin_dato", "2025-09", 5000, 5000)
    # Candelaria: solo un segmento en sep -> el mes no está completo
    filas.append(dict(destino_clave="alta_verapaz", subdestino="Cuevas De Candelaria", tipo="extranjero",
                      anio_mes=pd.Timestamp("2025-09-01"), segmento=MAS, visitantes=50))
    filas += _mov("Cuevas De Candelaria", "extranjero", "2025-10", 40, 40)
    return pd.DataFrame(filas)


# -------------------------------------------------------------------- A. capacidad
def test_capacidad_excluye_2026_y_otros_departamentos(oferta):
    cap = oo.capacidad_por_anio(oferta)
    assert sorted(cap["anio"].unique()) == [2022, 2023, 2024, 2025]
    assert (cap["establecimientos"] < 999).all()


def test_capacidad_incluye_2026_marcado_como_parcial(oferta):
    cap = oo.capacidad_por_anio(oferta, incluir_parcial=True)
    assert cap.loc[cap["anio"] == 2026, "es_corte_parcial"].all()
    assert not cap.loc[cap["anio"] < 2026, "es_corte_parcial"].any()


def test_capacidad_rechaza_cortes_duplicados(oferta):
    with pytest.raises(ValueError):
        oo.capacidad_por_anio(pd.concat([oferta, oferta]))


def test_variacion_capacidad_suma_tipos_del_mismo_anio(oferta):
    var = oo.variacion_capacidad(oo.capacidad_por_anio(oferta), "habitaciones").set_index("tipo_alojamiento")
    assert var.loc["Total departamento", "inicial"] == 300      # 100 + 200 (2022)
    assert var.loc["Total departamento", "final"] == 390        # 130 + 260 (2025)
    assert var.loc["Hotel", "variacion_pct"] == pytest.approx(30.0)


def test_variacion_pct_sin_base():
    assert np.isnan(oo.variacion_pct(0, 10)) and np.isnan(oo.variacion_pct(np.nan, 10))


# --------------------------------------------------------------------- B. ocupación
def test_serie_ocupacion_reindexa_sin_rellenar(ocup):
    s = oo.serie_ocupacion(ocup[ocup["anio_mes"] != "2024-05-01"])
    assert len(s) == 36 and s["indice_pct"].isna().sum() == 1


def test_promedio_departamental_es_media_simple(ocup):
    prom = oo.promedio_departamental(ocup).set_index("anio_mes")
    av_ene23 = 30.0
    assert prom.loc["2023-01-01", "indice_pct"] == pytest.approx((av_ene23 + 60) / 2)
    assert prom["n_departamentos"].eq(2).all()


def test_promedio_departamental_mes_incompleto_es_nan(ocup):
    incompleto = ocup.drop(ocup[(ocup["departamento"] == "Petén") & (ocup["anio_mes"] == "2025-01-01")].index)
    prom = oo.promedio_departamental(incompleto).set_index("anio_mes")
    assert np.isnan(prom.loc["2025-01-01", "indice_pct"])


def test_picos_y_valles_por_anio(ocup):
    pv = oo.picos_valles(oo.serie_ocupacion(ocup))
    picos = pv[pv["tipo"] == "pico"]
    valles = pv[pv["tipo"] == "valle"]
    assert list(picos["anio_mes"].dt.month) == [6, 6, 6]
    assert list(valles["anio_mes"].dt.month) == [11, 11, 11]


def test_resumen_anual_y_brecha(ocup):
    r = oo.resumen_anual_ocupacion(oo.serie_ocupacion(ocup), oo.promedio_departamental(ocup)).set_index("anio")
    esperado_2023 = (30 * 10 + 50 + 20) / 12
    assert r.loc[2023, "departamento"] == pytest.approx(esperado_2023)
    assert r.loc[2023, "brecha_pp"] == pytest.approx(esperado_2023 - (esperado_2023 + 60) / 2)


# ------------------------------------------------------------------- movilidad
def test_visitantes_mes_suma_segmentos_y_filtra(mov):
    s = oo.visitantes_mes(mov, "Coban", "extranjero")
    assert s.loc["2025-09-01"] == 200      # 100 + 100; ignora 'sin_dato' y otros destinos


def test_visitantes_mes_incompleto_es_nan(mov):
    s = oo.visitantes_mes(mov, "Cuevas De Candelaria", "extranjero", oo.VENTANA_CRUCE)
    assert np.isnan(s.loc["2025-09-01"]) and s.loc["2025-10-01"] == 80
    assert np.isnan(s.loc["2025-12-01"])   # sin filas: NaN, no 0


# ----------------------------------------------------------------- C. cruce
def test_meses_cruce_limita_a_sep_dic_2025():
    assert list(oo.meses_cruce("2025-10", "2026-08").month) == [10, 11, 12]
    assert len(oo.meses_cruce("2026-03", "2026-08")) == 0
    assert len(oo.meses_cruce()) == 4


def test_datos_cruce_rechaza_meses_fuera_de_ventana(mov, ocup):
    with pytest.raises(ValueError):
        oo.datos_cruce(mov, ocup, "Coban", "extranjero", pd.to_datetime(["2026-03-01"]))


def test_datos_cruce_y_descripcion(mov, ocup):
    cruce = oo.datos_cruce(mov, ocup, "Coban", "extranjero", oo.VENTANA_CRUCE)
    assert list(cruce["visitantes"]) == [200, 240, 220, 300]
    rel = oo.describir_relacion(cruce)
    assert rel["n_meses"] == 4 and rel["comparables"] == 3
    # oct: vis sube, ocup igual; nov: vis baja, ocup baja; dic: vis sube, ocup sube
    assert [c["visitantes"] for c in rel["cambios"]] == ["sube", "baja", "sube"]
    assert rel["coinciden"] == 2
    assert rel["mes_max_visitantes"] == pd.Timestamp("2025-12-01")
    assert "correlacion" not in rel     # con n = 4 no se calcula correlación


# ------------------------------------------------------------------ D. subdestinos
def test_afluencia_promedio_sin_total(mov):
    af = oo.afluencia_subdestinos(mov, "extranjero", pd.date_range("2025-09-01", "2026-04-01", freq="MS"))
    assert "Total" not in set(af["subdestino"]) and len(af) == 3
    coban = af.set_index("subdestino").loc["Coban"]
    assert coban["visitantes"] == pytest.approx(2 * np.mean([100, 120, 110, 150, 130, 140]))
    assert coban["n_meses"] == 6 and coban["relativo_pct"] == pytest.approx(100)
    assert af.set_index("subdestino").loc["Lanquin", "relativo_pct"] == pytest.approx(50)


def test_afluencia_mes_seleccionado(mov):
    af = oo.afluencia_subdestinos(mov, "extranjero", oo.VENTANA_CRUCE, mes="2025-09").set_index("subdestino")
    assert af.loc["Coban", "visitantes"] == 200
    assert np.isnan(af.loc["Cuevas De Candelaria", "visitantes"])   # mes incompleto: sin dato


def test_afluencia_no_mezcla_tipos(mov):
    af = oo.afluencia_subdestinos(mov, "nacional", oo.VENTANA_CRUCE).set_index("subdestino")
    assert af.loc["Coban", "visitantes"] == 2000
    assert np.isnan(af.loc["Lanquin", "visitantes"])


# -------------------------------------------------------------- E. estacionalidad
def test_indice_estacional_ocupacion(ocup):
    ie = oo.indice_estacional_ocupacion(oo.serie_ocupacion(ocup))
    assert ie.groupby("anio")["indice_estacional"].mean().round(6).eq(100).all()


def test_indice_estacional_visitantes_compuesto(mov):
    meses = pd.date_range("2025-09-01", "2026-04-01", freq="MS")
    ie = oo.indice_estacional_visitantes(mov, "Coban", "extranjero", meses).set_index("mes")
    assert len(ie) == 12 and np.isnan(ie.loc[1, "indice_estacional"])   # enero sin dato
    assert ie["indice_estacional"].mean() == pytest.approx(100)


def test_indice_estacional_rechaza_mes_repetido(mov):
    extra = pd.DataFrame(_mov("Coban", "extranjero", "2026-09", 1, 1))
    meses = pd.date_range("2025-09-01", "2026-09-01", freq="MS")
    with pytest.raises(ValueError):
        oo.indice_estacional_visitantes(pd.concat([mov, extra]), "Coban", "extranjero", meses)
