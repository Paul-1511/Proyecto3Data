"""Pruebas del indicador de cobertura del encabezado (sin navegador ni Parquet reales)."""
import pandas as pd
import pytest
from dash import html

from app import indicador_cobertura as ic
from app import main, theme
from app.utils import cobertura as cb


@pytest.fixture
def cob():
    filas = []
    for m in pd.date_range("2025-09-01", "2026-08-01", freq="MS"):
        sin_mov = m.month in (1, 2)
        filas += [
            dict(fuente="movilidad_mensual", anio_mes=m, tiene_dato=not sin_mov, cobertura_completa=not sin_mov),
            dict(fuente="ocupacion", anio_mes=m, tiene_dato=m.year == 2025, cobertura_completa=m.year == 2025),
        ]
    return cb.validar(pd.DataFrame(filas))


def _spans(componente):
    return [c for c in main.recorrer_componentes(componente)
            if isinstance(c, html.Span) and str(getattr(c, "id", "")).startswith(ic.PREFIJO_CHIP)]


def test_un_chip_por_fuente_con_estado(cob):
    comp = ic.contenido({"mes_ini": "2026-03", "mes_fin": "2026-08"}, cob)
    estados = {s.id: s.to_plotly_json()["props"]["data-estado"] for s in _spans(comp)}
    assert estados == {"cob-chip-movilidad_mensual": cb.COMPLETA, "cob-chip-ocupacion": cb.SIN_DATO}


def test_chip_sin_dato_es_gris_y_con_dato_verde(cob):
    comp = ic.contenido({"mes_ini": "2026-03", "mes_fin": "2026-08"}, cob)
    por_id = {s.id: s for s in _spans(comp)}
    assert por_id["cob-chip-ocupacion"].style["backgroundColor"] == theme.COBERTURA_SIN_DATO_FONDO
    assert por_id["cob-chip-movilidad_mensual"].style["backgroundColor"] == theme.COBERTURA_FONDO
    assert por_id["cob-chip-ocupacion"].children.startswith("—")   # el estado no depende solo del color


def test_rango_con_hueco_es_parcial(cob):
    comp = ic.contenido({"mes_ini": "2025-12", "mes_fin": "2026-03"}, cob)
    por_id = {s.id: s.to_plotly_json()["props"]["data-estado"] for s in _spans(comp)}
    assert por_id["cob-chip-movilidad_mensual"] == cb.PARCIAL


def test_tabla_vacia_muestra_aviso():
    vacia = cb.validar(pd.DataFrame(columns=list(cb.COLUMNAS)))
    comp = ic.contenido({"mes_ini": "2025-09", "mes_fin": "2025-12"}, vacia)
    assert "ETL" in comp.children


def test_contraste_aa_de_los_chips():
    assert theme.cumple_aa(theme.COBERTURA_TEXTO, theme.COBERTURA_FONDO)
    assert theme.cumple_aa(theme.COBERTURA_TEXTO, theme.COBERTURA_PARCIAL_FONDO)
    assert theme.cumple_aa(theme.COLOR_SIN_DATO_TEXTO, theme.COBERTURA_SIN_DATO_FONDO)


def test_main_registra_indicador_en_el_slot():
    app = main.crear_app(opciones=main.Opciones(pd.DatetimeIndex([]), (), ()), implementaciones={})
    salidas = [str(k) for k in app.callback_map]
    assert any(theme.ID_SLOT_COBERTURA in s for s in salidas)
