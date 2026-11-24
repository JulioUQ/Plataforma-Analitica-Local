"""Dashboard local de cobros de Gestion_Alquileres.

Arranque desde la raíz del repo:
    .\\.venv\\Scripts\\python.exe python\\dashboard_cobros.py
y abrir http://127.0.0.1:8050
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

from cobros import CobrosMes, cobros_por_mes, reiniciar_conexion

HOST, PUERTO = "127.0.0.1", 8050
log = logging.getLogger("dashboard_cobros")

AZUL = "#2563eb"
TINTA = "#1f2937"
GRIS = "#6b7280"
BORDE = "#e5e7eb"
FONDO_ERROR = "#fef2f2"
TINTA_ERROR = "#991b1b"


def euros(valor: Decimal) -> str:
    """13533.1 -> '13.533,10 €' (formato español, exacto con Decimal)."""
    s = f"{valor.quantize(Decimal('0.01')):,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".") + " €"


def figura(datos: list[CobrosMes]) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=[d.mes for d in datos],
            y=[float(d.total) for d in datos],
            text=[euros(d.total) for d in datos],
            textposition="outside",
            customdata=[[d.cobros, euros(d.total)] for d in datos],
            hovertemplate="%{x}<br>%{customdata[1]}<br>%{customdata[0]} cobros<extra></extra>",
            marker_color=AZUL,
            cliponaxis=False,
        )
    )
    fig.update_layout(
        margin=dict(l=8, r=8, t=24, b=8),
        height=360,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=TINTA, size=13),
        xaxis=dict(type="category", title=None),
        yaxis=dict(title="Euros", gridcolor=BORDE, separatethousands=True, rangemode="tozero"),
        separators=",.",
        showlegend=False,
    )
    return fig


def figura_vacia() -> go.Figure:
    fig = go.Figure()
    fig.update_layout(height=360, plot_bgcolor="white", paper_bgcolor="white",
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def tarjeta(titulo: str, id_valor: str) -> html.Div:
    return html.Div(
        [html.Div(titulo, style={"color": GRIS, "fontSize": "14px"}),
         html.Div("—", id=id_valor, style={"fontSize": "32px", "fontWeight": 600,
                                            "fontVariantNumeric": "tabular-nums"})],
        style={"border": f"1px solid {BORDE}", "borderRadius": "8px", "padding": "16px 20px",
               "flex": "1", "minWidth": "200px"},
    )


def tabla(datos: list[CobrosMes]) -> html.Table:
    celda = {"padding": "6px 12px", "borderBottom": f"1px solid {BORDE}"}
    num = {**celda, "textAlign": "right", "fontVariantNumeric": "tabular-nums"}
    return html.Table(
        [html.Thead(html.Tr([html.Th("Mes", style=celda), html.Th("Cobros", style=num),
                             html.Th("Total", style=num)])),
         html.Tbody([html.Tr([html.Td(d.mes, style=celda), html.Td(d.cobros, style=num),
                              html.Td(euros(d.total), style=num)], id=f"fila-{d.mes}")
                     for d in datos])],
        style={"borderCollapse": "collapse", "fontSize": "14px"},
    )


app = Dash(__name__, title="Cobros · Gestion_Alquileres")
app.layout = html.Main(
    [
        html.H1("Cobros de alquileres", style={"fontSize": "26px", "margin": "0 0 4px"}),
        html.P("Gestion_Alquileres · SQL Server local · carga desde CSV con n8n",
               style={"color": GRIS, "margin": "0 0 20px"}),
        html.Div(
            [html.Button("Actualizar datos", id="actualizar", n_clicks=0,
                         style={"background": AZUL, "color": "white", "border": "none",
                                "borderRadius": "6px", "padding": "8px 16px", "fontSize": "14px",
                                "cursor": "pointer"}),
             html.Span(id="consultado", style={"color": GRIS, "fontSize": "13px"})],
            style={"display": "flex", "gap": "12px", "alignItems": "center", "marginBottom": "16px"},
        ),
        html.Div(id="error", role="alert"),
        dcc.Loading(
            html.Div(
                [
                    html.Div([tarjeta("Total cobrado", "total"), tarjeta("Número de cobros", "num-cobros")],
                             style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "marginBottom": "16px"}),
                    html.H2("Total cobrado por mes", style={"fontSize": "17px", "margin": "8px 0"}),
                    dcc.Graph(id="grafico", config={"displayModeBar": False}),
                    html.Div(id="tabla", style={"marginTop": "8px"}),
                ]
            ),
            type="circle",
        ),
    ],
    style={"maxWidth": "900px", "margin": "32px auto", "padding": "0 16px",
           "fontFamily": "system-ui, -apple-system, Segoe UI, sans-serif", "color": TINTA},
)


@app.callback(
    Output("total", "children"),
    Output("num-cobros", "children"),
    Output("grafico", "figure"),
    Output("tabla", "children"),
    Output("consultado", "children"),
    Output("error", "children"),
    Input("actualizar", "n_clicks"),
)
def actualizar(_n_clicks: int):
    """Se ejecuta al cargar la página y con cada pulsación de «Actualizar datos»."""
    try:
        datos = cobros_por_mes()
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de conexión o consulta
        # Solo el tipo de error en el log del servidor; nada de cadenas de conexión ni mensajes del driver.
        log.error("Fallo al consultar cobros: %s", type(exc).__name__)
        reiniciar_conexion()
        aviso = html.Div(
            "No se pudieron cargar los datos de SQL Server. Comprueba que el servicio está en marcha "
            "y vuelve a pulsar «Actualizar datos».",
            style={"background": FONDO_ERROR, "color": TINTA_ERROR, "border": "1px solid #fecaca",
                   "borderRadius": "6px", "padding": "10px 14px", "marginBottom": "16px"},
        )
        return "—", "—", figura_vacia(), None, "", aviso

    total = sum((d.total for d in datos), Decimal("0"))
    num = sum(d.cobros for d in datos)
    hora = datetime.now().strftime("%H:%M:%S")
    return euros(total), f"{num}", figura(datos), tabla(datos), f"Datos consultados a las {hora}", None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app.run(host=HOST, port=PUERTO, debug=False)
