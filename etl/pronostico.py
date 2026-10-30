"""Estimación de ene-feb 2026 (meses sin cobertura de telefonía) para la base MENSUAL de movilidad.

MÉTODO (guía de uso de datos, sección 5.2)
  1. Driver: entradas migratorias mensuales de visitantes (Turista + Excursionista), que sí están observadas
     para ene-feb 2026 (la migración llega a junio de 2026).
  2. Factor de reparto por serie = visitantes del subdestino / entradas migratorias del mismo mes, calculado
     en los meses con AMBAS fuentes observadas: sep-dic 2025 y mar-jun 2026 (8 meses; jul-ago 2026 no tienen
     migración). Serie = (subdestino, tipo) con tipo en {extranjero, nacional}.
  3. Estimación = factor × entradas migratorias del mes a estimar.
  4. Validación obligatoria: leave-one-out sobre los meses observados (se oculta un mes, se calcula el factor
     con los demás, se predice y se compara). Se reportan MAPE, RMSE y MAE por serie y variante.
  5. Variantes con migración: razon_media, razon_agregada, razon_mediana y (solo extranjeros) por mercado
     emisor. Línea base sin migración: promedio de los meses observados. Se elige UNA variante por tipo (la
     de menor MAPE mediano entre series) para no sobreajustar por serie; la línea base se reporta aparte para
     mostrar si la migración aporta.
  6. Intervalo aproximado = estimación ± 1.96 × RMSE leave-one-out de la serie (con n=8 es solo orientativo).

LIMITACIONES: no existe total de destino, por lo que se estima por subdestino y NO se suman (doble conteo).
Los nacionales no dependen del ingreso internacional: el driver migratorio es solo un proxy estacional; si no
mejora a la línea base se declara. La base diaria no se proyecta; los feriados de ene-feb se declaran ausentes.
"""
import numpy as np
import pandas as pd

from etl import config
from etl.utils import guardar, log

OBJETIVO = pd.to_datetime(["2026-01-01", "2026-02-01"])
VARIANTES_MIG = ["razon_media", "razon_agregada", "razon_mediana", "mercado"]
BASE = "base_promedio"
Z = 1.96


def _serie_mes(sub_mes: pd.DataFrame) -> pd.DataFrame:
    """Visitantes por subdestino × tipo × mes (suma de segmentos dentro del mismo subdestino-mes; no suma meses
    ni subdestinos)."""
    s = sub_mes[sub_mes.tipo.isin(["extranjero", "nacional"])]
    return (s.groupby(["destino_clave", "destino_nombre", "subdestino", "tipo", "anio_mes"], as_index=False)
            .visitantes.sum())


def _mercado_mov(mensual: pd.DataFrame) -> pd.DataFrame:
    inv = {v: k for k, v in config.MERCADOS.items()}
    faltan = set(inv) - set(mensual.pais.dropna().unique())
    if faltan:
        raise ValueError(f"Mercados sin coincidencia en movilidad: {faltan}")
    e = mensual[mensual.tipo == "extranjero"].copy()
    e["mercado"] = e.pais.map(lambda p: inv.get(p, "Otros"))
    return (e.groupby(["subdestino", "anio_mes", "mercado"], as_index=False).visitantes.sum())


def _mercado_mig(mig_pais: pd.DataFrame) -> pd.DataFrame:
    m = mig_pais[mig_pais.anio >= config.MIG_ANIO_QUIEBRE].copy()
    faltan = set(config.MERCADOS) - set(m.pais.unique())
    if faltan:
        raise ValueError(f"Mercados sin coincidencia en migración: {faltan}")
    m["mercado"] = m.pais.where(m.pais.isin(config.MERCADOS), "Otros")
    return m.groupby(["anio_mes", "mercado"], as_index=False).viajeros.sum()


def _pred(v: str, tr_v: np.ndarray, tr_m: np.ndarray, m_t: float, mk: dict | None) -> float:
    """Predicción de una variante. tr_* = observaciones de entrenamiento (visitantes y migración)."""
    if v == BASE:
        return float(np.mean(tr_v))
    if v == "razon_media":
        return float(np.mean(tr_v / tr_m)) * m_t
    if v == "razon_agregada":
        return float(tr_v.sum() / tr_m.sum()) * m_t
    if v == "razon_mediana":
        return float(np.median(tr_v / tr_m)) * m_t
    if v == "mercado":  # mk = {'V': DataFrame meses×mercado, 'M': DataFrame meses×mercado, 'mes_t': Series}
        f = (mk["V"] / mk["M"]).mean(axis=0)
        return float((f * mk["Mt"]).sum())
    raise ValueError(v)


def _metricas(obs: np.ndarray, est: np.ndarray) -> tuple[float, float, float]:
    e = est - obs
    ok = obs != 0
    mape = float(np.mean(np.abs(e[ok] / obs[ok])) * 100) if ok.any() else np.nan
    return mape, float(np.sqrt(np.mean(e ** 2))), float(np.mean(np.abs(e)))


def run_con(sub_mes, mensual, mig_total, mig_pais, diaria) -> dict[str, pd.DataFrame]:
    ser = _serie_mes(sub_mes)
    mt = mig_total.set_index("anio_mes").visitantes
    mmov, mmig = _mercado_mov(mensual), _mercado_mig(mig_pais)
    Mg = mmig.pivot(index="anio_mes", columns="mercado", values="viajeros")

    meses_obs = sorted(set(ser.anio_mes) & set(mt.index))
    log.info("pronóstico: %s meses con movilidad y migración: %s", len(meses_obs),
             [m.strftime("%Y-%m") for m in meses_obs])
    if len(meses_obs) < 6 or not set(OBJETIVO) <= set(mt.index):
        raise ValueError("Cobertura insuficiente para estimar ene-feb 2026")

    val_rows, det_rows, series_info = [], [], {}
    for (dk, dn, sd, tp), g in ser.groupby(["destino_clave", "destino_nombre", "subdestino", "tipo"]):
        g = g.set_index("anio_mes").visitantes.reindex(meses_obs)  # NaN = mes sin dato de la serie (no es cero)
        obs_m = g.dropna().index.tolist()
        if len(obs_m) < 6:
            log.warning("serie %s/%s/%s con %s meses: no estimable", dk, sd, tp, len(obs_m))
            continue
        Vm = None
        if tp == "extranjero":
            Vm = (mmov[mmov.subdestino == sd].pivot(index="anio_mes", columns="mercado", values="visitantes")
                  .reindex(index=obs_m, columns=Mg.columns).fillna(0.0))  # mes observado: ausencia = 0 visitantes
        series_info[(dk, dn, sd, tp)] = (g.dropna(), obs_m, Vm)
        variantes = [BASE] + [v for v in VARIANTES_MIG if not (v == "mercado" and tp != "extranjero")]
        for v in variantes:
            obs, est, mes = [], [], []
            for h in obs_m:
                tr = [m for m in obs_m if m != h]
                tr_v, tr_m = g.loc[tr].to_numpy(float), mt.loc[tr].to_numpy(float)
                mk = None
                if v == "mercado":
                    Vt, Mt_ = Vm.loc[tr], Mg.loc[tr]
                    mk = {"V": Vt.loc[:, Mt_.columns], "M": Mt_, "Mt": Mg.loc[h]}
                    mk["V"] = mk["V"].where(mk["M"] > 0)
                est.append(_pred(v, tr_v, tr_m, float(mt.loc[h]), mk))
                obs.append(float(g.loc[h]))
                mes.append(h)
            mape, rmse, mae = _metricas(np.array(obs), np.array(est))
            val_rows.append(dict(destino_clave=dk, destino_nombre=dn, subdestino=sd, tipo=tp, variante=v,
                                 n_loo=len(obs_m), mape=mape, rmse=rmse, mae=mae))
            for h, o, e in zip(mes, obs, est):
                det_rows.append(dict(destino_clave=dk, subdestino=sd, tipo=tp, variante=v, anio_mes=h,
                                     observado=o, predicho=e, error_pct=(100 * (e - o) / o) if o else np.nan))
    val = pd.DataFrame(val_rows)
    det = pd.DataFrame(det_rows)

    # Variante elegida por tipo: menor MAPE mediano entre las variantes con migración
    med = (val[val.variante != BASE].groupby(["tipo", "variante"]).mape.median().reset_index())
    elegida = med.loc[med.groupby("tipo").mape.idxmin()].set_index("tipo").variante.to_dict()
    val["es_elegida"] = val.apply(lambda r: elegida.get(r.tipo) == r.variante, axis=1)

    resumen = []
    for tp, v in elegida.items():
        a = val[(val.tipo == tp) & (val.variante == v)]
        b = val[(val.tipo == tp) & (val.variante == BASE)]
        resumen.append(dict(tipo=tp, variante_elegida=v, series=len(a), mape_mediano=a.mape.median(),
                            mape_medio=a.mape.mean(), rmse_mediano=a.rmse.median(), mae_mediano=a.mae.median(),
                            mape_mediano_base_sin_migracion=b.mape.median(),
                            migracion_mejora_a_la_base=bool(a.mape.median() < b.mape.median())))
    resumen = pd.DataFrame(resumen)

    # Estimación final ene-feb 2026
    out = []
    for (dk, dn, sd, tp), (g, obs_m, Vm) in series_info.items():
        v = elegida[tp]
        met = val[(val.subdestino == sd) & (val.tipo == tp) & (val.variante == v)].iloc[0]
        met_b = val[(val.subdestino == sd) & (val.tipo == tp) & (val.variante == BASE)].iloc[0]
        est_base = float(g.mean())
        for t in OBJETIVO:
            mk = None
            if v == "mercado":
                M_ = Mg.loc[obs_m]
                mk = {"V": Vm.where(M_ > 0), "M": M_, "Mt": Mg.loc[t]}
            est = _pred(v, g.to_numpy(float), mt.loc[obs_m].to_numpy(float), float(mt.loc[t]), mk)
            out.append(dict(destino_clave=dk, destino_nombre=dn, subdestino=sd, tipo=tp, anio_mes=t,
                            estimacion=est, lim_inf=max(est - Z * met.rmse, 0.0), lim_sup=est + Z * met.rmse,
                            metodo=v, mape_loo=met.mape, rmse_loo=met.rmse, mae_loo=met.mae, n_loo=int(met.n_loo),
                            driver_migracion_visitantes=float(mt.loc[t]), es_estimacion=True,
                            estimacion_base_sin_migracion=est_base, mape_loo_base=met_b.mape,
                            migracion_mejora_a_la_base=bool(met.mape < met_b.mape)))
    pron = pd.DataFrame(out)
    pron["nota"] = "Estimación (no observada). Intervalo ≈ ±1.96×RMSE leave-one-out con n≈8: orientativo."

    # Chequeo con la base diaria: ¿la presencia diaria promedio acompaña al volumen mensual?
    comp = (diaria.groupby(["subdestino", "tipo", "anio_mes"]).fecha.nunique().rename("dias").reset_index())
    d = (diaria.groupby(["subdestino", "tipo", "anio_mes", "fecha"], as_index=False).presencia.sum()
         .groupby(["subdestino", "tipo", "anio_mes"], as_index=False).presencia.mean()
         .rename(columns={"presencia": "presencia_diaria_media"})
         .merge(comp, on=["subdestino", "tipo", "anio_mes"]))
    d = d[d.dias == d.anio_mes.dt.days_in_month]  # solo meses con cobertura diaria completa
    chk = []
    for (sd, tp), x in d.groupby(["subdestino", "tipo"]):
        m = ser[(ser.subdestino == sd) & (ser.tipo == tp)].merge(x, on=["subdestino", "tipo", "anio_mes"])
        if len(m) >= 6:
            chk.append(dict(subdestino=sd, tipo=tp, meses=len(m),
                            correlacion_mensual_vs_presencia_diaria=float(np.corrcoef(m.visitantes,
                                                                                   m.presencia_diaria_media)[0, 1])))
    chk = pd.DataFrame(chk)
    return {"pronostico_ene_feb_2026": pron, "pronostico_validacion": val, "pronostico_loo_detalle": det,
            "pronostico_resumen_modelo": resumen, "pronostico_chequeo_diario": chk}


def run() -> dict[str, pd.DataFrame]:
    P = config.PROC
    rd = lambda n: pd.read_parquet(P / f"{n}.parquet")
    out = run_con(rd("movilidad_subdestino_mes"), rd("movilidad_mensual"), rd("migracion_total_mensual"),
                  rd("migracion_mensual_pais"), rd("movilidad_diaria"))
    for k, v in out.items():
        guardar(v, k)
    return out
