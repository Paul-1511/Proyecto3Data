"""Pruebas de app/utils/cobertura.py con una tabla de cobertura sintética (sin Parquet reales)."""
import pandas as pd
import pytest

from app.utils import cobertura as cb


def _fila(fuente, mes, tiene, completa=None):
    return dict(fuente=fuente, anio_mes=pd.Timestamp(f"{mes}-01"), tiene_dato=tiene,
                cobertura_completa=tiene if completa is None else completa)


@pytest.fixture
def cob():
    meses = [f"2025-{m:02d}" for m in range(9, 13)] + [f"2026-{m:02d}" for m in range(1, 9)]
    filas = []
    for m in meses:
        ene_feb = m in ("2026-01", "2026-02")
        filas.append(_fila("movilidad_mensual", m, not ene_feb))
        filas.append(_fila("ocupacion", m, m.startswith("2025")))
        filas.append(_fila("oferta_corte_anual", m, True, completa=m.startswith("2025")))  # 2026 parcial
        filas.append(_fila("migracion", m, m <= "2026-06"))
        filas.append(_fila("movilidad_diaria", m, not ene_feb, completa=(m != "2025-09") and not ene_feb))
        filas.append(_fila("tikal", m, True))   # fuente extra de otro grupo
    return cb.validar(pd.DataFrame(filas))


def _estado(df, fuente):
    return df.set_index("fuente").loc[fuente, "estado"]


def test_validar_exige_columnas():
    with pytest.raises(KeyError):
        cb.validar(pd.DataFrame({"fuente": ["x"]}))


def test_validar_rechaza_duplicados():
    df = pd.DataFrame([_fila("ocupacion", "2025-09", True), _fila("ocupacion", "2025-09", True)])
    with pytest.raises(ValueError):
        cb.validar(df)


def test_validar_sin_dato_nunca_es_completa():
    df = cb.validar(pd.DataFrame([_fila("ocupacion", "2025-09", False, completa=True)]))
    assert not df["cobertura_completa"].iloc[0]


def test_orden_fuentes_catalogo_y_extras(cob):
    assert cb.fuentes_presentes(cob) == ["movilidad_mensual", "movilidad_diaria", "ocupacion",
                                         "oferta_corte_anual", "migracion", "tikal"]


def test_estado_ventana_coincidente(cob):
    est = cb.estado_fuentes(cob, "2025-09", "2025-12")
    assert _estado(est, "movilidad_mensual") == cb.COMPLETA
    assert _estado(est, "ocupacion") == cb.COMPLETA
    assert _estado(est, "movilidad_diaria") == cb.PARCIAL      # sep 2025 incompleto
    assert set(est["meses_en_rango"]) == {4}


def test_ocupacion_sin_dato_en_2026(cob):
    est = cb.estado_fuentes(cob, "2026-03", "2026-08")
    fila = est.set_index("fuente").loc["ocupacion"]
    assert fila["estado"] == cb.SIN_DATO
    assert fila["meses_con_dato"] == 0
    assert fila["sin_dato_en_rango"] == "mar 2026 – ago 2026"


def test_oferta_2026_parcial(cob):
    assert _estado(cb.estado_fuentes(cob, "2026-03", "2026-04"), "oferta_corte_anual") == cb.PARCIAL


def test_huecos_ene_feb_parcial(cob):
    est = cb.estado_fuentes(cob, "2025-12", "2026-03")
    fila = est.set_index("fuente").loc["movilidad_mensual"]
    assert fila["estado"] == cb.PARCIAL
    assert fila["meses_con_dato"] == 2
    assert fila["sin_dato_en_rango"] == "ene 2026 – feb 2026"


def test_meses_con_y_sin_dato(cob):
    assert list(cb.meses_sin_dato(cob, "migracion", "2026-05", "2026-08").strftime("%Y-%m")) == \
        ["2026-07", "2026-08"]
    assert cb.tiene_dato(cob, "migracion", "2026-05", "2026-08")
    assert not cb.tiene_dato(cob, "ocupacion", "2026-01", "2026-02")
    assert not cb.tiene_dato(cob, "fuente_inexistente", "2025-09", "2025-12")


def test_texto_tramos():
    meses = pd.to_datetime(["2025-09-01", "2025-10-01", "2026-03-01"])
    assert cb.texto_tramos(meses) == "sep 2025 – oct 2025, mar 2026"
    assert cb.texto_tramos([]) == "ninguno"
    assert cb.texto_tramos(pd.date_range("2022-01-01", "2026-12-01", freq="MS"), "anual") == "2022 – 2026"


def test_periodo_cubierto_en_tooltip(cob):
    fila = cb.estado_fuentes(cob, "2026-03", "2026-08").set_index("fuente").loc["ocupacion"].copy()
    fila["fuente"] = "ocupacion"
    texto = cb.texto_tooltip(fila)
    assert "sep 2025 – dic 2025" in texto and "no es cero" in texto


def test_tabla_vacia():
    vacia = cb.validar(pd.DataFrame(columns=list(cb.COLUMNAS)))
    assert cb.estado_fuentes(vacia, "2025-09", "2025-12").empty


def test_fuente_desconocida_es_generica():
    assert cb.fuente("aimm_pasajeros").etiqueta == "Aimm pasajeros"


# ------------------------------------------- aplicación a los módulos 1 y 2 (P3, PR separado)
def test_solo_con_cobertura_quita_meses_sin_dato(cob):
    df = pd.DataFrame({"anio_mes": pd.to_datetime(["2025-12-01", "2026-01-01", "2026-03-01"]), "visitantes": [1, 2, 3]})
    out = cb.solo_con_cobertura(df, "movilidad_mensual", cob)
    assert list(out["visitantes"]) == [1, 3]          # ene 2026 sin cobertura: fuera (quedará «Sin dato»)


def test_solo_con_cobertura_diaria_por_fecha(cob):
    df = pd.DataFrame({"fecha": pd.to_datetime(["2026-02-10", "2026-03-05"]), "presencia": [5.0, 6.0]})
    assert list(cb.solo_con_cobertura(df, "movilidad_diaria", cob, columna="fecha")["presencia"]) == [6.0]


def test_solo_con_cobertura_sin_tabla_no_cambia_nada():
    df = pd.DataFrame({"anio_mes": pd.to_datetime(["2026-01-01"]), "visitantes": [1]})
    vacia = cb.validar(pd.DataFrame(columns=list(cb.COLUMNAS)))
    assert len(cb.solo_con_cobertura(df, "movilidad_mensual", vacia)) == 1
    assert len(cb.solo_con_cobertura(df, "fuente_ausente", vacia)) == 1


def test_modulos_1_y_2_usan_la_cobertura(monkeypatch, cob):
    from app import modulo1, modulo2
    llamadas = []
    original = cb.solo_con_cobertura
    monkeypatch.setattr(cb, "solo_con_cobertura",
                        lambda df, clave, c=None, columna="anio_mes": llamadas.append(clave) or original(df, clave, cob, columna))
    monkeypatch.setattr(modulo1, "_leer", lambda nombre, cols: pd.DataFrame(
        {"anio_mes": pd.to_datetime(["2026-01-01", "2026-03-01"]), **{c: ["x", "y"] for c in cols if c != "anio_mes"}}))
    assert len(modulo1._leer_sub()) == 1 and len(modulo1._leer_pais()) == 1
    monkeypatch.setattr(modulo2, "_leer", modulo1._leer)
    assert len(modulo2._leer_diaria()) == 1 and len(modulo2._leer_sub()) == 1
    assert llamadas == ["movilidad_mensual", "movilidad_mensual", "movilidad_diaria", "movilidad_mensual"]
