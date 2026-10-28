"""Ejecuta el ETL completo:  python -m etl.run_all"""
import time

from etl import cobertura, dim_fecha, migracion, movilidad
from etl.utils import log


def main() -> None:
    t0 = time.time()
    log.info("== dim_fecha ==")
    dim_fecha.run()
    log.info("== migración ==")
    mig = migracion.run()
    log.info("== movilidad ==")
    mov = movilidad.run()
    log.info("== cobertura ==")
    cobertura.run(mov["mensual"], mov["diaria"], mig["total"])
    # PARTE 2 (pendiente): ocupación, oferta, tablas extra del Módulo 4, pronóstico ene-feb 2026
    log.info("ETL parte 1 terminado en %.1f s", time.time() - t0)


if __name__ == "__main__":
    main()
