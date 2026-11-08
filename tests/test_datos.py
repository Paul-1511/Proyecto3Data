"""Pruebas de app/utils/datos.py con datos sintéticos (no usan archivos institucionales)."""
import numpy as np
import pandas as pd
import pytest

from app.utils import datos
from app.utils.datos import Filtros


@pytest.fixture(autouse=True)
def _cache_limpia():
    datos.limpiar_cache()
    yield
    datos.limpiar_cache()


@pytest.fixture
def mensual():
    return pd.DataFrame({
        "subdestino": ["Coban", "Coban", "Coban", "Lanquin", "Lanquin", "Coban"],
        "tipo": ["extranjero", "extranjero", "nacional", "extranjero", "nacional", "extranjero"],
        "anio_mes": pd.to_datetime(["2025-09-01", "2025-10-01", "2025-10-01",
                                    "2025-10-01", "2025-11-01", "2025-12-01"]),
        "visitantes": [10.0, 20.0, 30.0, 40.0, np.nan, 60.0],
    })


@pytest.fixture
def diaria():
    return pd.DataFrame({
        "subdestino": ["Coban"] * 5,
        "tipo": ["extranjero"] * 5,
        "fecha": pd.to_datetime(["2025-09-30 00:00:00", "2025-10-01 00:00:00",
                                 "2025-10-31 00:00:00", "2025-10-31 23:30:00",
                                 "2025-11-01 00:00:00"]),
        "presencia": [1.0, 2.0, np.nan, 4.0, 5.0],
    })


# ------------------------------------------------------------------------- cargar
def test_cargar_lee_tabla_permitida(tmp_path):
    df = pd.DataFrame({"a": [1, 2]})
    df.to_parquet(tmp_path / "cobertura.parquet")
    pd.testing.assert_frame_equal(datos.cargar("cobertura", directorio=tmp_path), df)


@pytest.mark.parametrize("nombre", ["no_existe", "../secreto", "cobertura.parquet",
                                    "C:/Windows/x", "", "data/processed/cobertura"])
def test_cargar_rechaza_nombres_no_permitidos(tmp_path, nombre):
    with pytest.raises(ValueError):
        datos.cargar(nombre, directorio=tmp_path)


def test_cargar_rechaza_tipos_no_texto(tmp_path):
    with pytest.raises(TypeError):
        datos.cargar(None, directorio=tmp_path)


def test_cargar_archivo_faltante(tmp_path):
    with pytest.raises(FileNotFoundError):
        datos.cargar("cobertura", directorio=tmp_path)


def test_cache_protegida_frente_a_modificaciones(tmp_path):
    pd.DataFrame({"a": [1, 2]}).to_parquet(tmp_path / "cobertura.parquet")
    primero = datos.cargar("cobertura", directorio=tmp_path)
    primero.loc[0, "a"] = 999
    primero["nueva"] = 1
    segundo = datos.cargar("cobertura", directorio=tmp_path)
    assert segundo["a"].tolist() == [1, 2]
    assert "nueva" not in segundo.columns
    assert primero is not segundo


# ------------------------------------------------------------------------ Filtros
def test_filtros_desde_dict_y_a_dict():
    f = Filtros.desde_dict({"mes_ini": "2025-09", "mes_fin": "2025-12-15",
                            "tipo": "nacional", "subdestino": "", "otra": 1})
    assert f.mes_ini == pd.Timestamp("2025-09-01")
    assert f.mes_fin == pd.Timestamp("2025-12-01")
    assert f.subdestino is None
    assert f.a_dict() == {"mes_ini": "2025-09", "mes_fin": "2025-12",
                          "tipo": "nacional", "subdestino": None}


def test_filtros_vacios():
    assert Filtros.desde_dict(None) == Filtros()
    assert Filtros.desde_dict({}) == Filtros()


def test_filtros_rango_invalido():
    with pytest.raises(ValueError):
        Filtros(mes_ini="2025-12", mes_fin="2025-09")


def test_filtros_fecha_invalida():
    with pytest.raises(ValueError):
        Filtros(mes_ini="no-es-fecha")


# ------------------------------------------------------------------- filtrar mensual
def test_filtrar_mensual_por_rango(mensual):
    out = datos.filtrar_mensual(mensual, Filtros(mes_ini="2025-10", mes_fin="2025-11"))
    assert set(out["anio_mes"]) == {pd.Timestamp("2025-10-01"), pd.Timestamp("2025-11-01")}
    assert len(out) == 4


def test_filtrar_mensual_por_tipo_y_subdestino(mensual):
    f = Filtros(mes_ini="2025-09", mes_fin="2025-12", tipo="extranjero", subdestino="Coban")
    out = datos.filtrar_mensual(mensual, f)
    assert out["visitantes"].tolist() == [10.0, 20.0, 60.0]
    assert (out["tipo"] == "extranjero").all() and (out["subdestino"] == "Coban").all()


def test_filtrar_mensual_sin_filtros_devuelve_todo_como_copia(mensual):
    out = datos.filtrar_mensual(mensual, Filtros())
    pd.testing.assert_frame_equal(out, mensual)
    out.loc[out.index[0], "visitantes"] = -1
    assert mensual.loc[0, "visitantes"] == 10.0


def test_filtrar_mensual_solo_extremo_inferior_o_superior(mensual):
    assert len(datos.filtrar_mensual(mensual, Filtros(mes_ini="2025-12"))) == 1
    assert len(datos.filtrar_mensual(mensual, Filtros(mes_fin="2025-09"))) == 1


def test_filtrar_mensual_sin_observaciones_es_vacio_con_columnas(mensual):
    out = datos.filtrar_mensual(mensual, Filtros(tipo="no_existe"))
    assert out.empty
    assert list(out.columns) == list(mensual.columns)
    out2 = datos.filtrar_mensual(mensual, Filtros(mes_ini="2030-01", mes_fin="2030-02"))
    assert out2.empty


def test_filtrar_preserva_nan(mensual):
    out = datos.filtrar_mensual(mensual, Filtros(subdestino="Lanquin", tipo="nacional"))
    assert len(out) == 1
    assert np.isnan(out["visitantes"].iloc[0])  # no se convierte en 0


def test_filtrar_no_modifica_original(mensual, diaria):
    m0, d0 = mensual.copy(), diaria.copy()
    datos.filtrar_mensual(mensual, Filtros(mes_ini="2025-10", tipo="nacional"))
    datos.filtrar_diaria(diaria, Filtros(mes_ini="2025-10", mes_fin="2025-10"))
    pd.testing.assert_frame_equal(mensual, m0)
    pd.testing.assert_frame_equal(diaria, d0)


def test_filtrar_ignora_tipo_si_la_tabla_no_lo_tiene():
    ocup = pd.DataFrame({"departamento": ["Alta Verapaz"],
                         "anio_mes": pd.to_datetime(["2025-09-01"]), "indice_pct": [50.0]})
    out = datos.filtrar_mensual(ocup, Filtros(tipo="nacional", subdestino="Coban"))
    assert len(out) == 1


def test_filtrar_sin_columna_de_fecha_falla(mensual):
    with pytest.raises(KeyError):
        datos.filtrar_diaria(mensual, Filtros())


# -------------------------------------------------------------------- filtrar diaria
def test_filtrar_diaria_incluye_ultimo_dia_del_mes_final(diaria):
    out = datos.filtrar_diaria(diaria, Filtros(mes_ini="2025-10", mes_fin="2025-10"))
    fechas = out["fecha"].tolist()
    assert pd.Timestamp("2025-10-01") in fechas
    assert pd.Timestamp("2025-10-31") in fechas
    assert pd.Timestamp("2025-10-31 23:30:00") in fechas  # con hora
    assert pd.Timestamp("2025-09-30") not in fechas
    assert pd.Timestamp("2025-11-01") not in fechas
    assert len(out) == 3


def test_filtrar_diaria_preserva_nan(diaria):
    out = datos.filtrar_diaria(diaria, Filtros(mes_ini="2025-10", mes_fin="2025-10"))
    assert out["presencia"].isna().sum() == 1


# ----------------------------------------------------------------------- disponibles
def test_meses_observados(mensual, diaria):
    meses = datos.meses_observados(mensual)
    assert meses.tolist() == [pd.Timestamp(f"2025-{m:02d}-01") for m in (9, 10, 11, 12)]
    meses_d = datos.meses_observados(diaria, "fecha")
    assert meses_d.tolist() == [pd.Timestamp("2025-09-01"), pd.Timestamp("2025-10-01"),
                                pd.Timestamp("2025-11-01")]


def test_tipos_y_subdestinos_disponibles(mensual):
    assert datos.tipos_disponibles(mensual) == ["extranjero", "nacional"]
    assert datos.subdestinos_disponibles(mensual) == ["Coban", "Lanquin"]
    assert datos.valores_disponibles(mensual, "no_existe") == []


def test_disponibles_en_tabla_vacia(mensual):
    vacia = mensual.iloc[0:0]
    assert datos.tipos_disponibles(vacia) == []
    assert len(datos.meses_observados(vacia)) == 0


# --------------------------------------------------------------------------- huecos
def test_rango_meses():
    assert datos.rango_meses("2025-11", "2026-02").tolist() == [
        pd.Timestamp("2025-11-01"), pd.Timestamp("2025-12-01"),
        pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01")]
    with pytest.raises(ValueError):
        datos.rango_meses("2026-02", "2025-11")


def test_reindexar_meses_marca_huecos_con_nan_no_cero(mensual):
    serie = datos.filtrar_mensual(mensual, Filtros(tipo="extranjero", subdestino="Coban"))
    serie = serie[serie["anio_mes"] != pd.Timestamp("2025-10-01")]  # quedan sep y dic
    out = datos.reindexar_meses(serie, datos.rango_meses("2025-09", "2025-12"))
    assert out["anio_mes"].tolist() == datos.rango_meses("2025-09", "2025-12").tolist()
    assert out["visitantes"].iloc[0] == 10.0
    assert np.isnan(out["visitantes"].iloc[1]) and np.isnan(out["visitantes"].iloc[2])
    assert out["visitantes"].iloc[3] == 60.0
    assert (out["visitantes"].fillna(-1) != 0).all()  # ningún cero inventado


def test_reindexar_meses_conserva_nan_existentes_y_no_modifica_original():
    serie = pd.DataFrame({"anio_mes": pd.to_datetime(["2025-09-01", "2025-10-01"]),
                          "visitantes": [np.nan, 5.0]})
    original = serie.copy()
    out = datos.reindexar_meses(serie, datos.rango_meses("2025-09", "2025-11"))
    assert np.isnan(out["visitantes"].iloc[0])
    assert out["visitantes"].iloc[1] == 5.0
    assert np.isnan(out["visitantes"].iloc[2])
    pd.testing.assert_frame_equal(serie, original)


def test_reindexar_meses_rechaza_mas_de_una_serie(mensual):
    with pytest.raises(ValueError):
        datos.reindexar_meses(mensual, datos.rango_meses("2025-09", "2025-12"))
