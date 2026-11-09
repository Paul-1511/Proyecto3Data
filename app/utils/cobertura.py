"""Cobertura por fuente: qué fuentes tienen dato en un rango de meses.

Lee ``data/processed/cobertura.parquet`` (grano fuente × mes, generado por ``etl/cobertura.py``) y
responde, para el rango de meses del filtro global, qué fuentes respaldan ese período.

Reglas que respeta este módulo:
* Ausencia de dato != cero. Un mes sin cobertura se informa como «Sin dato»; nunca se rellena.
* La cobertura es por fuente (no por destino): la tabla la construye P1 para todo el paquete.
* La oferta es un corte ANUAL (inventario): un mes «con dato» significa que el año tiene corte.
  El corte de 2026 es parcial (primer trimestre) y la tabla lo marca con ``cobertura_completa = False``.
* No depende de Dash (la parte visual vive en ``app/indicador_cobertura.py``).

Estados por fuente en el rango:
* ``completa``: todos los meses del rango tienen dato completo.
* ``parcial``: algunos meses tienen dato, o tienen dato incompleto (p. ej. pocos días en la base
  diaria, corte parcial de 2026 en la oferta).
* ``sin_dato``: ningún mes del rango tiene dato.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd

from app.utils import datos

TABLA = "cobertura"
COLUMNAS = ("fuente", "anio_mes", "tiene_dato", "cobertura_completa")

COMPLETA, PARCIAL, SIN_DATO = "completa", "parcial", "sin_dato"

_MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


@dataclass(frozen=True)
class Fuente:
    """Fuente de la tabla ``cobertura`` y cómo se presenta en el tablero."""
    clave: str          # valor de la columna ``fuente``
    etiqueta: str       # texto del chip
    descripcion: str    # qué mide (va en el tooltip)
    granularidad: str   # mensual / diaria / anual


# Fuentes del Grupo 4, en el orden en que se muestran. Si la tabla trae otras fuentes (Tikal, AIMM en
# otros grupos), se agregan al final con su nombre: son las «extra del destino».
FUENTES = (
    Fuente("movilidad_mensual", "Movilidad", "Visitantes únicos del mes (telefonía móvil)", "mensual"),
    Fuente("movilidad_diaria", "Movilidad diaria", "Presencia por día (telefonía móvil)", "diaria"),
    Fuente("ocupacion", "Ocupación", "Índice de ocupación hotelera departamental", "mensual"),
    Fuente("oferta_corte_anual", "Oferta", "Inventario de alojamiento: un corte por año", "anual"),
    Fuente("migracion", "Migración", "Ingresos de visitantes al país", "mensual"),
)
_POR_CLAVE = {f.clave: f for f in FUENTES}


def fuente(clave: str) -> Fuente:
    """Metadatos de una fuente; si no está en el catálogo se crea una genérica (fuente extra)."""
    return _POR_CLAVE.get(clave, Fuente(clave, clave.replace("_", " ").capitalize(),
                                        "Fuente adicional del destino", "mensual"))


# ----------------------------------------------------------------------- carga
def cargar(directorio: Optional[Path] = None) -> pd.DataFrame:
    """Tabla de cobertura validada. Si el parquet no existe devuelve una tabla vacía."""
    try:
        df = datos.cargar(TABLA, directorio)
    except FileNotFoundError:
        return pd.DataFrame({"fuente": pd.Series(dtype=object),
                             "anio_mes": pd.Series(dtype="datetime64[ns]"),
                             "tiene_dato": pd.Series(dtype=bool),
                             "cobertura_completa": pd.Series(dtype=bool)})
    return validar(df)


def validar(df: pd.DataFrame) -> pd.DataFrame:
    """Exige las columnas mínimas y normaliza ``anio_mes`` al primer día del mes (copia)."""
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise KeyError(f"La tabla de cobertura no tiene las columnas {faltan}.")
    out = df.copy()
    out["anio_mes"] = pd.to_datetime(out["anio_mes"]).dt.to_period("M").dt.to_timestamp()
    out["tiene_dato"] = out["tiene_dato"].fillna(False).astype(bool)
    # Si no hay dato, la cobertura no puede ser completa.
    out["cobertura_completa"] = out["cobertura_completa"].fillna(False).astype(bool) & out["tiene_dato"]
    if out.duplicated(["fuente", "anio_mes"]).any():
        raise ValueError("La tabla de cobertura tiene filas repetidas por (fuente, anio_mes).")
    return out


def fuentes_presentes(cob: pd.DataFrame) -> list:
    """Fuentes de la tabla en orden de presentación (catálogo primero, extras después)."""
    presentes = list(pd.unique(cob["fuente"])) if len(cob) else []
    orden = [f.clave for f in FUENTES if f.clave in presentes]
    return orden + sorted(c for c in presentes if c not in orden)


# ---------------------------------------------------------------------- períodos
def etiqueta_mes(m: pd.Timestamp) -> str:
    return f"{_MESES[m.month - 1]} {m.year}"


def tramos(meses: Iterable) -> list:
    """Agrupa meses en tramos contiguos: [(ini, fin), ...]. Sirve para describir huecos."""
    ms = sorted(pd.DatetimeIndex(pd.to_datetime(list(meses))).to_period("M").unique())
    salida = []
    for p in ms:
        if salida and p == salida[-1][1] + 1:
            salida[-1][1] = p
        else:
            salida.append([p, p])
    return [(a.to_timestamp(), b.to_timestamp()) for a, b in salida]


def texto_tramos(meses: Iterable, granularidad: str = "mensual") -> str:
    """'sep 2025 – dic 2025, mar 2026 – ago 2026' (o '2022 – 2026' si es anual). Vacío -> 'ninguno'."""
    tr = tramos(meses)
    if not tr:
        return "ninguno"
    if granularidad == "anual":
        anios = sorted({m.year for a, b in tr for m in pd.date_range(a, b, freq="MS")})
        return f"{anios[0]} – {anios[-1]}" if len(anios) > 1 else str(anios[0])
    partes = [etiqueta_mes(a) if a == b else f"{etiqueta_mes(a)} – {etiqueta_mes(b)}" for a, b in tr]
    return ", ".join(partes)


def _rango(cob: pd.DataFrame, mes_ini: Any, mes_fin: Any) -> pd.DatetimeIndex:
    """Meses del rango. Sin límites -> todos los meses de la tabla."""
    if mes_ini is None and mes_fin is None:
        if cob.empty:
            return pd.DatetimeIndex([], name="anio_mes")
        mes_ini, mes_fin = cob["anio_mes"].min(), cob["anio_mes"].max()
    mes_ini = mes_ini if mes_ini is not None else mes_fin
    mes_fin = mes_fin if mes_fin is not None else mes_ini
    return datos.rango_meses(mes_ini, mes_fin)


def meses_con_dato(cob: pd.DataFrame, clave: str, mes_ini: Any = None, mes_fin: Any = None) -> pd.DatetimeIndex:
    """Meses del rango en que ``clave`` tiene dato (aunque sea parcial)."""
    rango = _rango(cob, mes_ini, mes_fin)
    sub = cob[(cob["fuente"] == clave) & cob["tiene_dato"] & cob["anio_mes"].isin(rango)]
    return pd.DatetimeIndex(sorted(sub["anio_mes"].unique()), name="anio_mes")


def meses_sin_dato(cob: pd.DataFrame, clave: str, mes_ini: Any = None, mes_fin: Any = None) -> pd.DatetimeIndex:
    """Meses del rango SIN dato de ``clave``: se rotulan «Sin dato» (nunca 0)."""
    rango = _rango(cob, mes_ini, mes_fin)
    return rango.difference(meses_con_dato(cob, clave, mes_ini, mes_fin))


def tiene_dato(cob: pd.DataFrame, clave: str, mes_ini: Any = None, mes_fin: Any = None) -> bool:
    """True si ``clave`` tiene dato en al menos un mes del rango."""
    return len(meses_con_dato(cob, clave, mes_ini, mes_fin)) > 0


def periodo_total(cob: pd.DataFrame, clave: str) -> pd.DatetimeIndex:
    """Todos los meses con dato de la fuente (para el tooltip: «período cubierto»)."""
    sub = cob[(cob["fuente"] == clave) & cob["tiene_dato"]]
    return pd.DatetimeIndex(sorted(sub["anio_mes"].unique()), name="anio_mes")


# ---------------------------------------------------------------------- estado
def estado_fuentes(cob: pd.DataFrame, mes_ini: Any = None, mes_fin: Any = None) -> pd.DataFrame:
    """Una fila por fuente con su estado en el rango [mes_ini, mes_fin].

    Columnas: ``fuente, etiqueta, descripcion, granularidad, meses_en_rango, meses_con_dato,
    meses_completos, estado, periodo_cubierto, periodo_en_rango, sin_dato_en_rango``.
    """
    columnas = ["fuente", "etiqueta", "descripcion", "granularidad", "meses_en_rango", "meses_con_dato",
                "meses_completos", "estado", "periodo_cubierto", "periodo_en_rango", "sin_dato_en_rango"]
    if cob.empty:
        return pd.DataFrame(columns=columnas)
    rango = _rango(cob, mes_ini, mes_fin)
    filas = []
    for clave in fuentes_presentes(cob):
        meta = fuente(clave)
        sub = cob[(cob["fuente"] == clave) & cob["anio_mes"].isin(rango)]
        con = pd.DatetimeIndex(sub.loc[sub["tiene_dato"], "anio_mes"])
        completos = int(sub["cobertura_completa"].sum())
        n_rango, n_con = len(rango), len(con)
        if n_con == 0:
            estado = SIN_DATO
        elif completos == n_rango:
            estado = COMPLETA
        else:
            estado = PARCIAL
        filas.append(dict(
            fuente=clave, etiqueta=meta.etiqueta, descripcion=meta.descripcion, granularidad=meta.granularidad,
            meses_en_rango=n_rango, meses_con_dato=n_con, meses_completos=completos, estado=estado,
            periodo_cubierto=texto_tramos(periodo_total(cob, clave), meta.granularidad),
            periodo_en_rango=texto_tramos(con, meta.granularidad),
            sin_dato_en_rango=texto_tramos(rango.difference(con)),
        ))
    return pd.DataFrame(filas, columns=columnas)


def texto_tooltip(fila: Any) -> str:
    """Texto del tooltip de un chip (una fila de ``estado_fuentes``)."""
    estado = {COMPLETA: "Con dato en todo el rango", PARCIAL: "Dato parcial en el rango",
              SIN_DATO: "Sin dato en el rango (no es cero)"}[fila["estado"]]
    partes = [f"{fila['etiqueta']}: {fila['descripcion']}.",
              f"{estado} ({fila['meses_con_dato']} de {fila['meses_en_rango']} meses).",
              f"Período cubierto por la fuente: {fila['periodo_cubierto']}."]
    if fila["estado"] != COMPLETA and fila["sin_dato_en_rango"] != "ninguno":
        partes.append(f"Sin dato en: {fila['sin_dato_en_rango']}.")
    if fila["fuente"] == "oferta_corte_anual":
        partes.append("Corte anual de inventario (no serie mensual); 2026 es un corte parcial.")
    if fila["fuente"] == "movilidad_diaria" and fila["estado"] == PARCIAL:
        partes.append("Algún mes tiene solo parte de sus días.")
    return " ".join(partes)
