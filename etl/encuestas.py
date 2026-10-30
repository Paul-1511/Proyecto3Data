"""Encuestas de satisfacción del visitante 2025 (Antigua, Petén) y tabulados de residentes.

REGLAS (nota metodológica de las fuentes y guía de uso de datos):
  * Corte transversal de una sola ola, por cuotas, SIN factor de expansión: se reportan porcentajes dentro de
    segmento. Nunca totales de visitantes, nunca el 'total del destino', nunca como serie de tiempo,
    y Antigua (marzo) no se compara con Petén (mayo).
  * Un % alto de no respuesta suele ser un filtro del cuestionario (p. ej. hospedaje solo si usó hospedaje).
  * Las etiquetas de pregunta de Antigua se derivaron del cuestionario de Petén: verificar antes de publicar.
  * Se eliminaron nombre del encuestador y geolocalización. Los textos libres (*_other) quedan solo en la tabla
    ancha (que no se versiona); las tablas derivadas no los incluyen.
  * Gasto: es gasto DECLARADO por el encuestado, no gasto del destino. Las categorías P70a_01..06 de Antigua y
    T_p70a_1..6 de Petén no tienen etiqueta en el diccionario: se conservan como categoria_1..6.
  * Centinelas: -1 en P71/P11A de Antigua = sin respuesta; se convierte a NaN.
"""
import numpy as np
import pandas as pd

from etl import config
from etl.utils import guardar, leer_excel, log

ITEM_ESCALA = "escala 1 a 5"
MIN_N = 30  # por debajo de este tamaño de segmento el resultado se marca como n_bajo

CONF = {
    "antigua": dict(archivo=config.F_ENC_ANTIGUA, id="id", genero="p05", edad="p06",
                    gasto=dict(moneda="p70", personas="p71", noches="p11a", total="p70a_07q",
                               cats=[f"p70a_0{i}q" for i in range(1, 7)])),
    "peten": dict(archivo=config.F_ENC_PETEN, id="sbjnum", genero="p05", edad="p06",
                  gasto=dict(moneda="p70", personas="p71", noches="p_11res", total="p70totalq",
                             pp="p_70vidp_71", cats=[f"t_p70a_{i}_q" for i in range(1, 7)])),
}


def _cargar(destino: str):
    xl = leer_excel(CONF[destino]["archivo"])
    datos, dic = xl.parse("datos"), xl.parse("diccionario")
    originales = dict(zip(datos.columns.str.lower(), datos.columns))
    datos.columns = datos.columns.str.lower()
    if datos.columns.duplicated().any():
        raise ValueError(f"{destino}: columnas duplicadas al pasar a minúsculas")
    dic["columna_norm"] = dic.columna.str.lower()
    if len(datos) != (510 if destino == "antigua" else 500):
        log.warning("%s: %s casos (esperados 510/500)", destino, len(datos))
    return datos, dic, originales


def _segmentos(destino: str, d: pd.DataFrame) -> pd.DataFrame:
    c = CONF[destino]
    s = pd.DataFrame({"id": d[c["id"]].astype("int64"), "destino": destino,
                      "genero": d[c["genero"]], "edad": d[c["edad"]]})
    if destino == "antigua":
        s["procedencia"] = np.where(d.p08.eq("Guatemala"), "nacional", "extranjero")
        s["es_pernocta"] = d.p11.eq("Una o más noches")
        s["lugar"], s["segmento_cuota"] = None, None
    else:
        s["procedencia"] = d.tipo_visitante.map({"Emisor": "nacional", "Receptor": "extranjero"})
        s["es_pernocta"] = d.v_isitante.eq("Turista")
        s["lugar"], s["segmento_cuota"] = d.lugar_turistico, d.turista
    if s.procedencia.isna().any():
        raise ValueError(f"{destino}: procedencia sin clasificar")
    return s


def satisfaccion_larga(destino: str, d: pd.DataFrame, dic: pd.DataFrame) -> pd.DataFrame:
    items = dic[dic.tipo.astype(str).str.strip().str.lower() == ITEM_ESCALA]
    seg = _segmentos(destino, d)
    filas = []
    for _, it in items.iterrows():
        col = it.columna_norm
        v = pd.to_numeric(d[col], errors="coerce")
        fuera = v.notna() & ~v.isin([1, 2, 3, 4, 5])
        if fuera.any():
            log.warning("%s %s: %s valores fuera de 1-5 -> NaN", destino, col, int(fuera.sum()))
        v = v.where(v.isin([1, 2, 3, 4, 5]))
        codigo = col[2:] if col.startswith("t_") else col
        x = seg.assign(item=codigo, pregunta=str(it.pregunta).strip(), valor=v)
        filas.append(x[x.valor.notna()])  # NaN = no aplica por filtro del cuestionario
    out = pd.concat(filas, ignore_index=True)
    out["valor"] = out.valor.astype(int)
    log.info("%s: %s items de escala 1-5, %s respuestas válidas", destino, len(items), f"{len(out):,}")
    return out


def resumen_satisfaccion(larga: pd.DataFrame) -> pd.DataFrame:
    """Por ítem y por segmento. NO hay fila de total del destino (es un artefacto del diseño muestral)."""
    dims = ["procedencia", "es_pernocta", "lugar", "segmento_cuota"]
    filas = []
    for dim in dims:
        if larga[dim].isna().all():
            continue
        g = larga.dropna(subset=[dim]).assign(segmento=lambda x: x[dim].astype(str)).groupby(
            ["destino", "item", "pregunta", "segmento"], as_index=False).agg(
            n_validos=("valor", "size"), media=("valor", "mean"),
            pct_insatisfecho=("valor", lambda v: 100 * (v <= 2).mean()),
            pct_neutral=("valor", lambda v: 100 * (v == 3).mean()),
            pct_satisfecho=("valor", lambda v: 100 * (v >= 4).mean()))
        g.insert(3, "dimension", dim)
        filas.append(g)
    r = pd.concat(filas, ignore_index=True)
    r["n_bajo"] = r.n_validos < MIN_N
    return r


def gasto_declarado(destino: str, d: pd.DataFrame) -> pd.DataFrame:
    g = CONF[destino]["gasto"]
    s = _segmentos(destino, d)[["id", "destino", "procedencia", "es_pernocta"]]
    personas = pd.to_numeric(d[g["personas"]], errors="coerce").where(lambda x: x > 0)
    noches = pd.to_numeric(d[g["noches"]], errors="coerce").where(lambda x: x > 0)
    total = pd.to_numeric(d[g["total"]], errors="coerce")
    s["moneda_declarada"] = d[g["moneda"]]
    s["personas_gasto"] = personas
    s["noches"] = noches.where(s.es_pernocta)  # solo tiene sentido en quien pernocta
    s["gasto_declarado_total_q"] = total
    pp = pd.to_numeric(d[g["pp"]], errors="coerce") if "pp" in g else total / personas
    s["gasto_declarado_por_persona_q"] = pp
    s["gasto_declarado_por_persona_noche_q"] = s.gasto_declarado_por_persona_q / s.noches
    for i, c in enumerate(g["cats"], start=1):
        s[f"categoria_{i}_q"] = pd.to_numeric(d[c], errors="coerce")
    s["declaro_gasto"] = s.gasto_declarado_total_q.notna()
    return s


def residentes() -> pd.DataFrame:
    t = leer_excel(config.F_ENC_RESIDENTES).parse("tabulados")
    cols = ["destino", "variable", "pregunta", "respuesta", "casos", "base", "porcentaje"]
    if list(t.columns) != cols:
        raise ValueError(f"Residentes: columnas inesperadas {list(t.columns)}")
    calc = 100 * t.casos / t.base
    if ((calc - t.porcentaje).abs() > 0.11).any():
        raise ValueError("Residentes: porcentaje != casos/base")
    return t


def run() -> dict[str, pd.DataFrame]:
    out = {}
    for destino in CONF:
        d, dic, orig = _cargar(destino)
        larga = satisfaccion_larga(destino, d, dic)
        out[f"encuesta_{destino}_datos"] = d
        out[f"encuesta_{destino}_diccionario"] = dic.drop(columns="columna_norm")
        out[f"encuesta_{destino}_satisfaccion"] = larga
        out[f"encuesta_{destino}_satisfaccion_resumen"] = resumen_satisfaccion(larga)
        out[f"encuesta_{destino}_gasto_declarado"] = gasto_declarado(destino, d)
    out["encuesta_residentes_tabulados"] = residentes()
    for k, v in out.items():
        guardar(v, k)
    return out
