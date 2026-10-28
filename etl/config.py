"""Configuración central del ETL: rutas, nombres de archivos y catálogo de destinos."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"

# Archivos de entrada (nombres exactos entregados por el curso)
F_MIGRACION = "Base_Migracion_2009-2026jun.xlsx"
F_MOV_MENSUAL = "BD_moviidad_mensual.xlsx"
F_MOV_DIARIO = "BD_moviidad_diario.xlsx"
F_OCUPACION = "indice_ocupacion_mensual_2023_2025_1.csv"
F_OFERTA = "oferta_hotelera_2022_2026.csv"

# Hoja de movilidad -> (clave interna, nombre del destino, departamento(s) base)
DESTINOS = {
    "Antigua": ("antigua", "La Antigua Guatemala", ["Sacatepéquez"]),
    "Peten": ("peten", "Tikal y Flores (Petén)", ["Petén"]),
    "Atitlan": ("atitlan", "Lago de Atitlán", ["Sololá"]),
    "Alta Verapaz": ("alta_verapaz", "Cobán y Alta Verapaz", ["Alta Verapaz"]),
    "Izabal": ("izabal", "Río Dulce y Livingston", ["Izabal"]),
    "Playas Pacifico": ("pacifico", "Costa del Pacífico", ["Escuintla", "Santa Rosa"]),
}

# Valores válidos de la columna es_consecutivo (segmento de estadía)
SEGMENTOS = {
    "mayor a 1 dia": "mas_de_1_dia",
    "menor a 1 dia": "menos_de_1_dia",
}

# Rango de la tabla de fechas común
FECHA_INI = "2009-01-01"
FECHA_FIN = "2026-12-31"

# Rango de meses para la tabla de cobertura
COBERTURA_INI = "2022-01"
COBERTURA_FIN = "2026-12"

# Ruptura metodológica de migración (la serie 2023+ no es comparable en niveles con <=2022)
MIG_ANIO_QUIEBRE = 2023
# Tipos de viajero que SÍ son visitantes (Viajero y Cruceristas no cuentan)
MIG_TIPOS_VISITANTE = ["Turista", "Excursionista"]
