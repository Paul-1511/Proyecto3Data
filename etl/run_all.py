"""Ejecuta el ETL completo:  python -m etl.run_all

Las fuentes opcionales (Tikal/AIMM y encuestas) solo las reciben algunos grupos: si faltan sus archivos en
data/raw/, ese bloque se omite con un aviso y el resto del ETL corre normal."""
import time

from etl import (cobertura, dim_fecha, encuestas, migracion, movilidad, ocupacion_oferta, pronostico,
                 tikal_aimm)
from etl.utils import bloque_disponible, config, faltantes, log


def _opcional(nombre: str, funcion):
    if bloque_disponible(nombre):
        return funcion()
    log.warning("bloque opcional '%s' OMITIDO: faltan %s", nombre, faltantes(config.FUENTES_OPCIONALES[nombre]["archivos"]))
    return None


def main() -> None:
    t0 = time.time()
    log.info("== dim_fecha ==")
    dim_fecha.run()
    log.info("== migración ==")
    mig = migracion.run()
    log.info("== movilidad ==")
    mov = movilidad.run()
    log.info("== ocupación y oferta ==")
    oo = ocupacion_oferta.run()
    log.info("== Tikal y aeropuerto (AIMM) [opcional] ==")
    ta = _opcional("tikal_aimm", tikal_aimm.run)
    log.info("== encuestas [opcional] ==")
    _opcional("encuestas", encuestas.run)
    log.info("== cobertura ==")
    extras = {"ocupacion": oo["ocupacion"].anio_mes}
    if ta is not None:
        extras.update({
            "tikal": ta["tikal_mensual"].dropna(subset=["total"]).anio_mes,
            "aimm_pasajeros": ta["aimm_pasajeros_total"].anio_mes,
            "aimm_operaciones": ta["aimm_operaciones"].anio_mes,
        })
    anios_oferta = {int(a): True for a in oo["oferta"].anio.unique()}
    cobertura.run(mov["mensual"], mov["diaria"], mig["total"], extras, anios_oferta)
    log.info("== pronóstico ene-feb 2026 ==")
    pronostico.run()
    log.info("ETL completo en %.1f s", time.time() - t0)


if __name__ == "__main__":
    main()
