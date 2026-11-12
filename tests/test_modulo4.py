"""Pruebas de los cálculos territoriales del Módulo 4."""
import pandas as pd

from app import modulo4 as m4
from app.utils.datos import Filtros


def _mensual():
    filas = []
    for sub, n in (("Coban", 100), ("Lanquin", 40), ("Cuevas De Candelaria", 20)):
        for seg, factor in (("mas_de_1_dia", .4), ("menos_de_1_dia", .6)):
            filas.append(dict(destino_clave="alta_verapaz", subdestino=sub, tipo="extranjero",
                              anio_mes=pd.Timestamp("2025-09-01"), segmento=seg, visitantes=n * factor))
    return pd.DataFrame(filas)


def test_perfil_no_suma_subdestinos_ni_meses():
    r = m4.perfil_territorial(_mensual())
    assert list(r["promedio_mensual"]) == [100, 40, 20]
    assert list(r["prop_mas_1"]) == [.4, .4, .4]


def test_presencia_fin_semana_agrega_paises_por_dia_sin_usar_mes():
    d = pd.DataFrame([x for sub in m4.SUBDESTINOS for x in [
        dict(destino_clave="alta_verapaz", subdestino=sub, tipo="extranjero", fecha="2025-09-01", presencia=10),
        dict(destino_clave="alta_verapaz", subdestino=sub, tipo="extranjero", fecha="2025-09-06", presencia=20),
    ]])
    d["fecha"] = pd.to_datetime(d["fecha"])
    r = m4.presencia_fin_semana(d, Filtros("2025-09", "2025-09", "extranjero", "Coban"))
    assert (r["ratio"] == 2).all()
