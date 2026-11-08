"""Capa de acceso a datos del tablero.

Responsabilidad ÚNICA: cargar los Parquet de ``data/processed/``, validar y filtrar.
No calcula KPI (estadía, lift, proporciones...): eso pertenece a ``app/utils/metricas.py``.

Reglas que esta capa respeta:
* Ausencia de dato != cero: nunca se rellena, interpola ni sustituye por 0.
* Nunca se modifica un DataFrame de entrada ni el almacenado en caché.
* Un filtro ``None`` significa "sin restricción", NO "sumar". Quien consuma
  los datos sin filtrar ``tipo``/``subdestino`` no debe agregarlos entre sí.
* No depende de Dash.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

import pandas as pd

# Raíz del repo: app/utils/datos.py -> parents[2]. Relativa al archivo, por lo que
# funciona igual en Windows y dentro de Docker (/app/data/processed).
RAIZ = Path(__file__).resolve().parents[2]
DIR_PROCESADOS = RAIZ / "data" / "processed"

# Las 17 tablas del contrato de datos vigente (docs/data_contract.md).
TABLAS_PERMITIDAS = frozenset({
    "dim_fecha",
    "migracion_total_mensual",
    "migracion_mensual",
    "migracion_mensual_pais",
    "movilidad_mensual",
    "movilidad_subdestino_mes",
    "movilidad_diaria",
    "ocupacion",
    "ocupacion_destino",
    "oferta",
    "oferta_destino",
    "pronostico_ene_feb_2026",
    "pronostico_validacion",
    "pronostico_loo_detalle",
    "pronostico_resumen_modelo",
    "pronostico_chequeo_diario",
    "cobertura",
})


# --------------------------------------------------------------------------- carga
@lru_cache(maxsize=None)
def _leer(ruta: str) -> pd.DataFrame:
    """Lee un parquet una sola vez por ruta. Uso interno: el objeto NO debe salir."""
    return pd.read_parquet(ruta)


def limpiar_cache() -> None:
    """Vacía la caché de lectura (útil en pruebas o tras regenerar el ETL)."""
    _leer.cache_clear()


def cargar(nombre: str, directorio: Optional[Path] = None) -> pd.DataFrame:
    """Devuelve una COPIA del parquet ``<nombre>.parquet`` de ``data/processed/``.

    ``nombre`` debe estar en ``TABLAS_PERMITIDAS`` (sin extensión ni rutas), lo que
    impide leer rutas arbitrarias. ``directorio`` existe solo para pruebas.
    La caché guarda el original; el llamador recibe una copia profunda, por lo que
    modificarla no altera lecturas posteriores.
    """
    if not isinstance(nombre, str):
        raise TypeError(f"El nombre de tabla debe ser str, no {type(nombre).__name__}.")
    if nombre not in TABLAS_PERMITIDAS:
        raise ValueError(f"Tabla no permitida: {nombre!r}. Permitidas: {sorted(TABLAS_PERMITIDAS)}")
    base = Path(directorio) if directorio is not None else DIR_PROCESADOS
    ruta = base / f"{nombre}.parquet"
    if not ruta.is_file():
        raise FileNotFoundError(
            f"No existe {ruta}. Genere los datos con `python -m etl.run_all`.")
    return _leer(str(ruta)).copy(deep=True)


# -------------------------------------------------------------------------- filtros
def _a_mes(valor: Any) -> Optional[pd.Timestamp]:
    """Convierte 'YYYY-MM', 'YYYY-MM-DD' o fecha al primer día de su mes. None/'' -> None."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    try:
        ts = pd.Timestamp(valor)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Fecha de filtro inválida: {valor!r}") from exc
    if pd.isna(ts):
        raise ValueError(f"Fecha de filtro inválida: {valor!r}")
    return ts.to_period("M").to_timestamp()


def _texto_o_none(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise TypeError(f"El filtro debe ser texto o None, no {type(valor).__name__}.")
    valor = valor.strip()
    return valor or None


@dataclass(frozen=True)
class Filtros:
    """Filtros globales del tablero. ``None`` = sin restricción en ese campo.

    ``mes_ini``/``mes_fin`` se normalizan al primer día del mes e incluyen ambos
    extremos (mes completo). Valida ``mes_ini <= mes_fin``.
    """
    mes_ini: Optional[pd.Timestamp] = None
    mes_fin: Optional[pd.Timestamp] = None
    tipo: Optional[str] = None
    subdestino: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mes_ini", _a_mes(self.mes_ini))
        object.__setattr__(self, "mes_fin", _a_mes(self.mes_fin))
        object.__setattr__(self, "tipo", _texto_o_none(self.tipo))
        object.__setattr__(self, "subdestino", _texto_o_none(self.subdestino))
        if self.mes_ini is not None and self.mes_fin is not None and self.mes_ini > self.mes_fin:
            raise ValueError(
                f"Rango inválido: mes_ini ({self.mes_ini:%Y-%m}) > mes_fin ({self.mes_fin:%Y-%m}).")

    @classmethod
    def desde_dict(cls, datos: Optional[Mapping[str, Any]]) -> "Filtros":
        """Construye desde el diccionario de ``dcc.Store``. ``None``/``{}`` -> sin filtros.

        Las claves desconocidas se ignoran.
        """
        datos = datos or {}
        return cls(mes_ini=datos.get("mes_ini"), mes_fin=datos.get("mes_fin"),
                   tipo=datos.get("tipo"), subdestino=datos.get("subdestino"))

    def a_dict(self) -> dict:
        """Representación serializable a JSON (meses como 'YYYY-MM') para ``dcc.Store``."""
        return {
            "mes_ini": None if self.mes_ini is None else f"{self.mes_ini:%Y-%m}",
            "mes_fin": None if self.mes_fin is None else f"{self.mes_fin:%Y-%m}",
            "tipo": self.tipo,
            "subdestino": self.subdestino,
        }


def _filtrar(df: pd.DataFrame, col_fecha: str, filtros: Filtros) -> pd.DataFrame:
    """Aplica rango [mes_ini, fin del mes_fin) + tipo + subdestino sobre una copia.

    ``tipo``/``subdestino`` solo se aplican si la tabla tiene esa columna (p. ej.
    ``ocupacion`` no tiene ``tipo``). La columna de fecha es obligatoria.
    """
    if col_fecha not in df.columns:
        raise KeyError(f"La tabla no tiene la columna de fecha {col_fecha!r}.")
    mascara = pd.Series(True, index=df.index)
    if filtros.mes_ini is not None:
        mascara &= df[col_fecha] >= filtros.mes_ini
    if filtros.mes_fin is not None:
        # Límite superior exclusivo = primer día del mes siguiente: incluye todo el mes final.
        mascara &= df[col_fecha] < filtros.mes_fin + pd.DateOffset(months=1)
    if filtros.tipo is not None and "tipo" in df.columns:
        mascara &= df["tipo"] == filtros.tipo
    if filtros.subdestino is not None and "subdestino" in df.columns:
        mascara &= df["subdestino"] == filtros.subdestino
    return df.loc[mascara].copy()


def filtrar_mensual(df: pd.DataFrame, filtros: Filtros) -> pd.DataFrame:
    """Filtra una tabla mensual (columna ``anio_mes``). Devuelve una copia; sin filas -> vacío."""
    return _filtrar(df, "anio_mes", filtros)


def filtrar_diaria(df: pd.DataFrame, filtros: Filtros) -> pd.DataFrame:
    """Filtra una tabla diaria (columna ``fecha``) incluyendo TODOS los días del mes final."""
    return _filtrar(df, "fecha", filtros)


# ------------------------------------------------------------------ disponibilidad
def meses_observados(df: pd.DataFrame, columna: str = "anio_mes") -> pd.DatetimeIndex:
    """Meses (primer día) que tienen al menos una fila en ``df``, ordenados.

    Sirve para ``anio_mes`` o ``fecha``. Es presencia de filas, no garantía de
    cobertura completa: para eso está la tabla ``cobertura``.
    """
    serie = pd.Series(pd.to_datetime(df[columna])).dropna()
    meses = serie.dt.to_period("M").drop_duplicates().sort_values().dt.to_timestamp()
    return pd.DatetimeIndex(meses.values, name="anio_mes")


def valores_disponibles(df: pd.DataFrame, columna: str) -> list[str]:
    """Valores únicos no nulos de ``columna``, ordenados. Si no existe la columna -> []."""
    if columna not in df.columns:
        return []
    return sorted(df[columna].dropna().unique().tolist())


def tipos_disponibles(df: pd.DataFrame) -> list[str]:
    """Valores de ``tipo`` presentes en los datos."""
    return valores_disponibles(df, "tipo")


def subdestinos_disponibles(df: pd.DataFrame) -> list[str]:
    """Valores de ``subdestino`` presentes en los datos."""
    return valores_disponibles(df, "subdestino")


# ----------------------------------------------------------------------- huecos
def rango_meses(mes_ini: Any, mes_fin: Any) -> pd.DatetimeIndex:
    """Todos los meses (primer día) entre ``mes_ini`` y ``mes_fin``, ambos incluidos."""
    ini, fin = _a_mes(mes_ini), _a_mes(mes_fin)
    if ini is None or fin is None:
        raise ValueError("rango_meses requiere mes_ini y mes_fin.")
    if ini > fin:
        raise ValueError(f"Rango inválido: {ini:%Y-%m} > {fin:%Y-%m}.")
    return pd.date_range(ini, fin, freq="MS", name="anio_mes")


def reindexar_meses(df: pd.DataFrame, meses: Iterable, columna: str = "anio_mes") -> pd.DataFrame:
    """Hace explícitos los meses sin cobertura de UNA serie: aparecen con ``NaN``.

    ``df`` debe tener a lo sumo una fila por mes (una sola serie: llámese por
    subdestino/tipo). No interpola ni rellena con 0; los ``NaN`` ya existentes se
    conservan. Los enteros pasan a float por la presencia de ``NaN``.
    Los meses de ``df`` fuera de ``meses`` se descartan.
    """
    base = df.copy()
    base[columna] = pd.to_datetime(base[columna]).dt.to_period("M").dt.to_timestamp()
    if base[columna].duplicated().any():
        raise ValueError("reindexar_meses requiere una fila por mes; filtre una sola serie.")
    destino = pd.DatetimeIndex([_a_mes(m) for m in meses], name=columna)
    return base.set_index(columna).reindex(destino).reset_index()
