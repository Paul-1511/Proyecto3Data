"""Pruebas sobre los parquet generados. Se omiten si aún no se corrió el ETL (data/processed vacío)."""
import numpy as np
import pandas as pd
import pytest

from etl import config

NECESARIOS = ["movilidad_mensual", "movilidad_subdestino_mes", "movilidad_diaria",
              "migracion_total_mensual", "cobertura", "dim_fecha"]
faltan = [n for n in NECESARIOS if not (config.PROC / f"{n}.parquet").exists()]
pytestmark = pytest.mark.skipif(bool(faltan), reason=f"Corra `python -m etl.run_all` (faltan {faltan})")


def leer(n):
    return pd.read_parquet(config.PROC / f"{n}.parquet")


def test_movilidad_mensual_cobertura_segun_guia():
    m = leer("movilidad_mensual")
    meses = sorted(m.anio_mes.dt.strftime("%Y-%m").unique())
    assert meses == ["2025-09", "2025-10", "2025-11", "2025-12",
                     "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]
    # ene-feb 2026 NO existen: ausencia de dato, no ceros
    assert not m.anio_mes.isin(pd.to_datetime(["2026-01-01", "2026-02-01"])).any()


def test_no_hay_filas_en_cero_ni_negativas():
    m = leer("movilidad_mensual")
    assert (m.visitantes > 0).all()


def test_segmentos_y_tipos_validos():
    m = leer("movilidad_mensual")
    assert set(m.segmento) == {"mas_de_1_dia", "menos_de_1_dia"}
    assert set(m.tipo) <= {"nacional", "extranjero", "sin_dato"}


def test_menos_de_1_dia_tiene_permanencia_uno():
    m = leer("movilidad_mensual")
    x = m[m.segmento == "menos_de_1_dia"]
    assert np.allclose(x.dias_persona, x.visitantes)


def test_las_seis_hojas_se_cargaron():
    m = leer("movilidad_mensual")
    assert set(m.destino_clave) == {"antigua", "peten", "atitlan", "alta_verapaz", "izabal", "pacifico"}


def test_estadia_ponderada_atitlan_coincide_con_guia():
    # La guía de datos reporta estadía 5.55 para Panajachel (Σ días-persona / Σ visitantes, >1 día)
    s = leer("movilidad_subdestino_mes")
    p = s[(s.subdestino == "Panajachel") & (s.segmento == "mas_de_1_dia")]
    assert round(p.dias_persona.sum() / p.visitantes.sum(), 2) == 5.55


def test_no_existe_total_destino_construido_por_suma():
    # Ninguna tabla debe traer una fila de total de destino (regla 4)
    for n in ("movilidad_mensual", "movilidad_subdestino_mes", "movilidad_diaria"):
        assert "total" not in " ".join(leer(n).subdestino.str.lower().unique())


def test_diario_dia_semana_consistente_y_paises_unificados():
    d = leer("movilidad_diaria")
    assert (d.fecha.dt.dayofweek == d.dia_semana_num).all()
    assert d[(d.tipo != "sin_dato")].pais.notna().all()
    assert "ESPAAA" not in set(d.pais.dropna())


def test_diario_no_tiene_ene_feb_2026():
    d = leer("movilidad_diaria")
    assert not ((d.fecha >= "2026-01-01") & (d.fecha < "2026-03-01")).any()


def test_migracion_cubre_hasta_junio_2026_y_marca_quiebre():
    g = leer("migracion_total_mensual")
    assert g.anio_mes.max() == pd.Timestamp("2026-06-01")
    assert g.anio_mes.is_unique
    assert set(g.periodo_metodologico) == {"<=2022", ">=2023"}
    # visitantes = turistas + excursionistas (no incluye 'Viajero')
    assert np.allclose(g.visitantes, g.turistas.fillna(0) + g.excursionistas.fillna(0))


def test_cobertura_marca_huecos_como_sin_dato():
    c = leer("cobertura")
    mm = c[(c.fuente == "movilidad_mensual")].set_index("anio_mes").tiene_dato
    assert not mm[pd.Timestamp("2026-01-01")] and not mm[pd.Timestamp("2026-02-01")]
    assert mm[pd.Timestamp("2025-12-01")] and mm[pd.Timestamp("2026-03-01")]
