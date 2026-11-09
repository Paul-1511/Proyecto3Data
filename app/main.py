"""Tablero Dash básico para los datos de Cobán y Alta Verapaz."""
from pathlib import Path
import os

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html


DESTINO = "alta_verapaz"
TIPOS = ("extranjero", "nacional")
TIPOS_LABEL = {"extranjero": "Extranjeros", "nacional": "Nacionales"}
MESES_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
DATA_DIR = Path(
    os.getenv(
        "DATA_DIR",
        str(Path(__file__).resolve().parents[1] / "data" / "processed"),
    )
)


def _read_parquet(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.parquet"
    if not path.is_file():
        raise FileNotFoundError(
            f"No se encontró {path}. Ejecute primero `python -m etl.run_all` "
            "o inicie los servicios con `docker compose up --build`."
        )
    return pd.read_parquet(path)


def load_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Carga las tablas publicadas por el ETL y limita las series al destino del grupo."""
    mobility = _read_parquet("movilidad_subdestino_mes")
    occupancy = _read_parquet("ocupacion_destino")
    forecast = _read_parquet("pronostico_ene_feb_2026")

    mobility = mobility.loc[
        (mobility["destino_clave"] == DESTINO) & mobility["tipo"].isin(TIPOS)
    ].copy()
    occupancy = occupancy.loc[occupancy["destino_clave"] == DESTINO].copy()
    forecast = forecast.loc[
        (forecast["destino_clave"] == DESTINO) & forecast["tipo"].isin(TIPOS)
    ].copy()

    if mobility.empty:
        raise ValueError(
            f"La tabla de movilidad no contiene datos para {DESTINO!r}."
        )
    if occupancy.empty:
        raise ValueError(
            f"La tabla de ocupación no contiene datos para {DESTINO!r}."
        )
    if forecast.empty:
        raise ValueError(
            f"La tabla de pronóstico no contiene datos para {DESTINO!r}."
        )
    return mobility, occupancy, forecast


mobility_data, occupancy_data, forecast_data = load_dashboard_data()
subdestinos = sorted(mobility_data["subdestino"].dropna().unique().tolist())


def _format_visitors(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "Sin dato"
    return f"{value:,.0f}"


def _visitor_figure(subdestino: str):
    data = mobility_data.loc[mobility_data["subdestino"] == subdestino]
    monthly = (
        data.groupby(["anio_mes", "tipo"], as_index=False, observed=True)["visitantes"]
        .sum()
        .sort_values("anio_mes")
    )
    monthly["tipo_label"] = monthly["tipo"].map(TIPOS_LABEL)
    figure = px.bar(
        monthly,
        x="anio_mes",
        y="visitantes",
        color="tipo_label",
        barmode="group",
        labels={
            "anio_mes": "Mes",
            "visitantes": "Visitantes",
            "tipo_label": "Tipo",
        },
        title="Visitantes observados por mes",
        color_discrete_map={"Extranjeros": "#2878b5", "Nacionales": "#ef8a24"},
    )
    figure.update_layout(legend_title_text="", margin=dict(l=20, r=20, t=55, b=20))
    return figure


def _forecast_figure(subdestino: str):
    data = forecast_data.loc[forecast_data["subdestino"] == subdestino].copy()
    data["tipo_label"] = data["tipo"].map(TIPOS_LABEL)
    data["error_sup"] = (data["lim_sup"] - data["estimacion"]).clip(lower=0)
    data["error_inf"] = (data["estimacion"] - data["lim_inf"]).clip(lower=0)
    figure = px.bar(
        data,
        x="anio_mes",
        y="estimacion",
        color="tipo_label",
        barmode="group",
        error_y="error_sup",
        error_y_minus="error_inf",
        labels={
            "anio_mes": "Mes",
            "estimacion": "Visitantes estimados",
            "tipo_label": "Tipo",
        },
        title="Pronóstico para enero y febrero de 2026",
        color_discrete_map={"Extranjeros": "#2878b5", "Nacionales": "#ef8a24"},
    )
    figure.update_layout(legend_title_text="", margin=dict(l=20, r=20, t=55, b=20))
    return figure


def _occupancy_figure():
    data = occupancy_data.sort_values("anio_mes")
    figure = px.line(
        data,
        x="anio_mes",
        y="indice_pct",
        markers=True,
        labels={"anio_mes": "Mes", "indice_pct": "Ocupación (%)"},
        title="Índice de ocupación hotelera",
        color_discrete_sequence=["#29866b"],
    )
    figure.update_yaxes(ticksuffix="%")
    figure.update_layout(margin=dict(l=20, r=20, t=55, b=20))
    return figure


def _kpis(subdestino: str):
    data = mobility_data.loc[
        (mobility_data["subdestino"] == subdestino)
        & mobility_data["tipo"].isin(TIPOS)
    ]
    latest_month = data["anio_mes"].max()
    latest = (
        data.loc[data["anio_mes"] == latest_month]
        .groupby("tipo", observed=True)["visitantes"]
        .sum()
    )
    month_label = f"{MESES_ES[latest_month.month - 1].capitalize()} {latest_month.year}"
    return [
        html.Div(
            [
                html.Div(TIPOS_LABEL[tipo], className="kpi-label"),
                html.Div(_format_visitors(latest.get(tipo)), className="kpi-value"),
                html.Div(f"Último dato observado: {month_label}", className="kpi-note"),
            ],
            className="kpi-card",
        )
        for tipo in TIPOS
    ]


app = Dash(__name__, title="Observatorio turístico | Alta Verapaz")
server = app.server

app.layout = html.Main(
    [
        html.Header(
            [
                html.P("Observatorio de Inteligencia Turística · INGUAT"),
                html.H1("Cobán y Alta Verapaz"),
                html.P(
                    "Indicadores de movilidad turística y ocupación hotelera. "
                    "Los datos se muestran por subdestino; no representan un total "
                    "del destino."
                ),
            ],
            className="page-header",
        ),
        html.Section(
            [
                html.Label("Subdestino", htmlFor="subdestino-selector"),
                dcc.Dropdown(
                    id="subdestino-selector",
                    options=[{"label": item, "value": item} for item in subdestinos],
                    value=subdestinos[0],
                    clearable=False,
                ),
            ],
            className="filter-section",
        ),
        html.Section(id="kpi-cards", className="kpi-grid"),
        html.Section(
            [
                dcc.Graph(id="visitors-chart"),
                dcc.Graph(id="forecast-chart"),
            ],
            className="chart-grid",
        ),
        html.Section(
            [
                dcc.Graph(figure=_occupancy_figure()),
                html.P(
                    "El índice de ocupación es un indicador departamental y no se "
                    "usa como denominador de visitantes. Los pronósticos son "
                    "estimaciones; para nacionales, la migración no mejora la "
                    "línea base del modelo.",
                    className="data-note",
                ),
            ],
            className="occupancy-section",
        ),
    ],
    className="page",
)

app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body { margin: 0; background: #f3f6f9; color: #172b3a; font-family: Arial, sans-serif; }
            .page { max-width: 1280px; margin: 0 auto; padding: 28px; }
            .page-header { padding: 26px 30px; color: white; background: #164b63; border-radius: 12px; }
            .page-header h1 { margin: 8px 0; }
            .page-header p { margin: 6px 0; }
            .filter-section, .occupancy-section { margin: 20px 0; padding: 20px; background: white; border-radius: 10px; }
            .filter-section label { display: block; margin-bottom: 8px; font-weight: 700; }
            .kpi-grid, .chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin: 20px 0; }
            .kpi-card { padding: 20px; background: white; border-radius: 10px; }
            .kpi-label { color: #526675; }
            .kpi-value { margin: 8px 0; font-size: 30px; font-weight: 700; }
            .kpi-note, .data-note { color: #526675; font-size: 14px; }
            @media (max-width: 760px) {
                .page { padding: 14px; }
                .kpi-grid, .chart-grid { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""


@app.callback(
    Output("visitors-chart", "figure"),
    Output("forecast-chart", "figure"),
    Output("kpi-cards", "children"),
    Input("subdestino-selector", "value"),
)
def update_subdestino(subdestino: str):
    return (
        _visitor_figure(subdestino),
        _forecast_figure(subdestino),
        _kpis(subdestino),
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
