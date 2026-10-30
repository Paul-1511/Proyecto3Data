"""Checklist de aceptación de P1.   Uso:  python -m etl.checklist_p1
Verifica archivos, datos, reglas y (si hay repositorio git) commits, y escribe docs/checklist_p1.md.
Estados: [x] cumple · [ ] NO cumple (bloquea el traspaso) · [~] pendiente de tu parte / no evaluable aquí."""
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from etl import config
from etl.generar_contrato import DESC

R = config.ROOT
OK, NO, PEND = "[x]", "[ ]", "[~]"
filas: list[tuple[str, str, str]] = []


def chk(estado: bool, nombre: str, evidencia: str) -> None:
    filas.append((OK if estado else NO, nombre, evidencia))


def pend(nombre: str, evidencia: str) -> None:
    filas.append((PEND, nombre, evidencia))


def rd(n: str) -> pd.DataFrame:
    return pd.read_parquet(config.PROC / f"{n}.parquet")


def git(*a: str) -> str | None:
    try:
        r = subprocess.run(["git", *a], cwd=R, capture_output=True, text=True, check=True)
        return r.stdout.strip()
    except Exception:
        return None


def main() -> int:
    # 1. Tablas
    faltan = [n for n in DESC if not (config.PROC / f"{n}.parquet").exists()]
    chk(not faltan, "ETL reproducible: las 34 tablas existen", f"{len(DESC) - len(faltan)}/{len(DESC)} parquet en data/processed/"
        + (f"; faltan {faltan[:3]}" if faltan else ""))
    if faltan:
        _escribir()
        return 1
    chk(all(len(rd(n)) > 0 for n in DESC), "Ninguna tabla vacía", "todas con filas")

    # 2. Pruebas
    p = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=R, capture_output=True, text=True)
    ultima = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-200:]
    chk(p.returncode == 0, "pytest pasa", ultima)

    # 3. Ausencia de dato ≠ cero
    m = rd("movilidad_mensual")
    chk((m.visitantes > 0).all() and not m.anio_mes.isin(pd.to_datetime(["2026-01-01", "2026-02-01"])).any(),
        "Movilidad sin ceros ni filas inventadas en ene-feb 2026", f"{len(m):,} filas, todas con visitantes > 0")
    c = rd("cobertura")
    huecos = c[(c.fuente == "movilidad_mensual") & c.anio_mes.isin(pd.to_datetime(["2026-01-01", "2026-02-01"]))]
    chk(not huecos.tiene_dato.any(), "Cobertura declara ene-feb 2026 como sin dato", "movilidad_mensual: tiene_dato = False")
    t = rd("tikal_mensual")
    chk(t[t.cero_dudoso].total.isna().all(), "Cero dudoso de Tikal convertido a NaN", f"{int(t.cero_dudoso.sum())} mes(es)")

    # 4. Pronóstico y errores
    pr, rs, va = rd("pronostico_ene_feb_2026"), rd("pronostico_resumen_modelo"), rd("pronostico_validacion")
    chk(set(pr.anio_mes) == set(pd.to_datetime(["2026-01-01", "2026-02-01"])) and pr.es_estimacion.all(),
        "Pronóstico solo ene-feb 2026 y rotulado es_estimacion", f"{len(pr)} filas")
    chk(rs[["mape_mediano", "rmse_mediano", "mae_mediano"]].notna().all().all() and
        pr[["mape_loo", "rmse_loo", "mae_loo"]].notna().all().all(),
        "MAPE, RMSE y MAE reportados (leave-one-out)",
        "; ".join(f"{r.tipo}: MAPE mediano {r.mape_mediano:.1f} % (base {r.mape_mediano_base_sin_migracion:.1f} %)" for r in rs.itertuples()))
    chk("base_promedio" in set(va.variante), "Línea base sin migración incluida para comparar", "variante base_promedio")
    chk("total" not in " ".join(pr.subdestino.str.lower().unique()), "No se construye total de destino por suma de subdestinos",
        f"{pr.subdestino.nunique()} subdestinos estimados por separado")

    # 5. Documentación
    chk("## Índice" in (R / "docs/data_contract.md").read_text(encoding="utf-8") and
        all(f"## {n}" in (R / "docs/data_contract.md").read_text(encoding="utf-8") for n in DESC),
        "data_contract.md documenta las 34 tablas", "generado desde los parquet")
    sec = (R / "docs/seccion_arquitectura_y_pronostico.md").read_text(encoding="utf-8")
    fichas = len(re.findall(r"^### 5\.\d", sec, flags=re.M))
    campos = all(len(re.findall(rf"^\| {i}\. ", sec, flags=re.M)) == fichas for i in range(1, 9))
    chk(fichas >= 5 and campos, "Fichas técnicas con los 8 campos", f"{fichas} fichas × 8 campos")
    chk(all((R / f).exists() for f in ["HANDOFF_P1.md", "docs/inspeccion_datos.md", "docs/PROGRESO_P1.md", "README.md"]),
        "HANDOFF_P1, inspección, progreso y README presentes", "ok")

    # 6. Resguardo de datos
    gi = (R / ".gitignore").read_text(encoding="utf-8")
    chk(all(x in gi for x in ["data/raw/*", "data/processed/*", "*.xlsx", "*.csv", "*.parquet"]),
        ".gitignore bloquea datos originales y procesados", "data/raw, data/processed, xlsx, csv, parquet")
    texto_libre = [col for n in ("encuesta_antigua_gasto_declarado", "encuesta_peten_gasto_declarado",
                                 "encuesta_antigua_satisfaccion", "encuesta_peten_satisfaccion")
                   for col in rd(n).columns if "other" in col or "_otro" in col]
    chk(not texto_libre, "Tablas derivadas de encuestas sin textos libres", "solo variables codificadas")

    # 7. Git (solo se puede evaluar en el repo del equipo)
    if git("rev-parse", "--is-inside-work-tree") == "true":
        trk = (git("ls-files") or "").splitlines()
        datos = [f for f in trk if re.search(r"\.(xlsx|xls|csv|parquet|pdf|zip)$", f)]
        chk(not datos, "Ningún archivo de datos está versionado en git", f"{len(trk)} archivos versionados" + (f"; {datos[:3]}" if datos else ""))
        rama = git("rev-parse", "--abbrev-ref", "HEAD")
        yo = git("config", "user.name") or ""
        n = int(git("rev-list", "--count", "--author", yo, "HEAD") or 0) if yo else 0
        chk(n >= 8, f"≥ 8 commits tuyos (rama {rama})", f"{n} commits de '{yo}'")
        dias = sorted(set((git("log", "--author", yo, "--format=%ad", "--date=short") or "").splitlines()))
        chk(len(dias) >= 2, "Commits repartidos en más de un día", ", ".join(dias) or "ninguno")
        tag = git("tag", "--list", "handoff-p1")
        (chk if tag else lambda *a: pend("Tag handoff-p1", "aún no creado: hazlo tras el merge a main"))(
            bool(tag), "Tag handoff-p1 creado", tag or "")
    else:
        pend("Verificaciones de git (commits, tag, datos no versionados)", "ejecuta este checklist dentro del repositorio del equipo")
    return _escribir()


def _escribir() -> int:
    md = ["# Checklist de aceptación de P1\n", "| estado | criterio | evidencia |", "|:--:|---|---|"]
    md += [f"| {e} | {n} | {ev} |" for e, n, ev in filas]
    fallos = [f for f in filas if f[0] == NO]
    md.append(f"\n**Resultado:** {len(fallos)} criterio(s) sin cumplir; {sum(f[0] == PEND for f in filas)} pendiente(s).")
    (R / "docs/checklist_p1.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
