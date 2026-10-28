"""Pruebas unitarias que no requieren datos."""
import numpy as np
import pandas as pd

from etl.utils import clave, clave_corregida, tipo_procedencia
from etl.dim_fecha import construir
from etl.movilidad import construir_subdestino_mes


def test_clave_ignora_acentos_y_mayusculas():
    assert clave("  PANAJACHEL ") == "panajachel"
    assert clave("España") == "espana"
    assert clave("Quetzaltenango") == clave("QUETZALTENANGO")


def test_nombre_danado_en_diario_se_corrige():
    assert clave_corregida("ESPAAA") == clave_corregida("España")


def test_tipo_procedencia():
    assert tipo_procedencia("Guatemala") == "nacional"
    assert tipo_procedencia("GUATEMALA") == "nacional"
    assert tipo_procedencia("Alemania") == "extranjero"
    assert tipo_procedencia(None) == "sin_dato"
    assert tipo_procedencia(float("nan")) == "sin_dato"
    assert tipo_procedencia("Null") == "sin_dato"


def test_dim_fecha_continua_y_sin_duplicados():
    f = construir()
    assert f.fecha.is_unique
    assert (f.fecha.diff().dropna() == pd.Timedelta(days=1)).all()
    assert f.loc[f.fecha == "2026-02-01", "dias_en_mes"].iloc[0] == 28
    assert f.loc[f.fecha == "2026-10-28", "nombre_dia"].iloc[0] == "Miércoles"


def test_estadia_ponderada_no_es_promedio_simple():
    # Dos países en el mismo subdestino-mes: el promedio simple de permanencia daría 2.0,
    # el ponderado (Σ días-persona / Σ visitantes) debe dar (10*1.5 + 90*3.0)/100 = 2.85.
    m = pd.DataFrame({
        "destino_clave": "x", "destino_nombre": "X", "subdestino": "S", "anio": 2025, "mes": 9,
        "anio_mes": pd.Timestamp("2025-09-01"), "tipo": "extranjero", "segmento": "mas_de_1_dia",
        "pais": ["A", "B"], "visitantes": [10.0, 90.0], "dias_persona": [15.0, 270.0],
        "permanencia_prom": [1.5, 3.0],
    })
    g = construir_subdestino_mes(m)
    assert len(g) == 1
    assert np.isclose(g.estadia_ponderada.iloc[0], 2.85)
    assert not np.isclose(m.permanencia_prom.mean(), 2.85)


def test_estadia_vacia_para_menos_de_1_dia():
    m = pd.DataFrame({
        "destino_clave": "x", "destino_nombre": "X", "subdestino": "S", "anio": 2025, "mes": 9,
        "anio_mes": pd.Timestamp("2025-09-01"), "tipo": "nacional", "segmento": "menos_de_1_dia",
        "pais": ["Guatemala"], "visitantes": [10.0], "dias_persona": [10.0], "permanencia_prom": [1.0],
    })
    g = construir_subdestino_mes(m)
    assert g.estadia_ponderada.isna().all()
