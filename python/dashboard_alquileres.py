"""Dashboard local de alquileres reales (Airbnb y Booking) sobre SQL Server.

Arranque desde la raíz del repo:
    .\\.venv\\Scripts\\python.exe python\\dashboard_alquileres.py
y abrir http://127.0.0.1:8060  (la demo ficticia sigue en dashboard_cobros.py, puerto 8050)
"""
from __future__ import annotations

import logging
from datetime import datetime

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dash_table, dcc, html

from alquileres import (DEFINICIONES, AgregadoMes, agregados_mensuales, euros, filtrar,
                        reiniciar_conexion, totales)

HOST, PUERTO = "127.0.0.1", 8060
log = logging.getLogger("dashboard_alquileres")

TINTA, GRIS, BORDE = "#1f2937", "#6b7280", "#e5e7eb"
COLORES = {"airbnb": "#e11d48", "booking": "#1d4ed8"}
FUENTE = "system-ui, -apple-system, Segoe UI, sans-serif"


def tarjeta(clave: str, id_valor: str, nota: str | None = None) -> html.Div:
    d = DEFINICIONES[clave]
    return html.Div(
        [html.Div(d["etiqueta"], style={"color": GRIS, "fontSize": "13px"}),
         html.Div("—", id=id_valor, style={"fontSize": "24px", "fontWeight": 600, "whiteSpace": "nowrap",
                                            "fontVariantNumeric": "tabular-nums"}),
         html.Div(nota or "", style={"color": GRIS, "fontSize": "12px"})],
        title=d["descripcion"],
        style={"border": f"1px solid {BORDE}", "borderRadius": "8px", "padding": "12px 16px", "flex": "1",
               "minWidth": "170px"},
    )


def figura(filas: list[AgregadoMes]) -> go.Figure:
    meses = sorted({f.mes for f in filas})
    fig = go.Figure()
    for p in sorted({f.plataforma for f in filas}):
        por_mes = {f.mes: f for f in filas if f.plataforma == p}
        nombre = next(f.plataforma_nombre for f in filas if f.plataforma == p)
        fig.add_bar(
            name=nombre, x=meses, marker_color=COLORES.get(p),
            y=[float(por_mes[m].neto) if m in por_mes else 0 for m in meses],   # solo para dibujar
            customdata=[[euros(por_mes[m].neto), euros(por_mes[m].importe_bruto), por_mes[m].reservas]
                        if m in por_mes else ["—", "—", 0] for m in meses],
            hovertemplate=f"{nombre} · %{{x}}<br>Neto: %{{customdata[0]}}<br>Bruto: %{{customdata[1]}}"
                          "<br>%{customdata[2]} reservas<extra></extra>",
        )
    fig.update_layout(
        barmode="stack", height=360, margin=dict(l=8, r=8, t=8, b=8), plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family=FUENTE, color=TINTA, size=13), separators=",.",
        xaxis=dict(type="category", title=None), yaxis=dict(title=None, gridcolor=BORDE, ticksuffix=" €"),
        legend=dict(orientation="h", y=1.08, x=0),
    )
    return fig


COLUMNAS_TABLA = [
    ("plataforma_nombre", "Plataforma"), ("mes", "Mes"), ("reservas", "Reservas"), ("noches", "Noches"),
    ("importe_bruto", "Importe bruto"), ("comisiones", "Comisiones"), ("gastos_pago", "Gastos de pago"),
    ("neto", "Neto de reservas"), ("importe_cobrado", "Cobrado (pagos liquidados)"),
    ("reservas_excluidas", "Excluidas"),
]


def filas_tabla(filas: list[AgregadoMes]) -> list[dict]:
    out = []
    for f in sorted(filas, key=lambda f: (f.mes, f.plataforma)):
        d = {k: getattr(f, k) for k, _ in COLUMNAS_TABLA}
        for k in ("importe_bruto", "comisiones", "gastos_pago", "neto", "importe_cobrado"):
            d[k] = euros(d[k]) if d[k] is not None else "n/d"
        out.append(d)
    return out


estilo_select = {"minWidth": "160px"}
app = Dash(__name__, title="Alquileres · Airbnb y Booking")
# Esquema claro fijo: con el sistema en modo oscuro, el texto oscuro quedaría sobre fondo oscuro
app.index_string = app.index_string.replace(
    "{%css%}", "{%css%}<style>:root{color-scheme:light} body{background:#fff;margin:0}</style>")
app.layout = html.Main(
    [
        dcc.Store(id="datos"),
        html.H1("Alquileres: Airbnb y Booking", style={"fontSize": "26px", "margin": "0 0 4px"}),
        html.P("Datos reales en SQL Server local (Gestion_Alquileres.alq), cargados por n8n desde los Excel.",
               style={"color": GRIS, "margin": "0 0 16px"}),
        html.Div(
            [html.Label(["Plataforma", dcc.Dropdown(id="plataforma", clearable=False, value="todas",
                                                    options=[{"label": "Todas", "value": "todas"},
                                                             {"label": "Airbnb", "value": "airbnb"},
                                                             {"label": "Booking", "value": "booking"}],
                                                    style=estilo_select)]),
             html.Label(["Desde", dcc.Dropdown(id="desde", clearable=False, style=estilo_select)]),
             html.Label(["Hasta", dcc.Dropdown(id="hasta", clearable=False, style=estilo_select)]),
             html.Button("Actualizar datos", id="actualizar", n_clicks=0,
                         style={"background": "#2563eb", "color": "white", "border": "none", "borderRadius": "6px",
                                "padding": "9px 16px", "fontSize": "14px", "cursor": "pointer", "alignSelf": "end"}),
             html.Span(id="consultado", style={"color": GRIS, "fontSize": "13px", "alignSelf": "end"})],
            style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginBottom": "16px", "fontSize": "13px"},
        ),
        html.Div(id="error", role="alert"),
        html.Div([tarjeta("reservas", "k-reservas"), tarjeta("noches", "k-noches"),
                  tarjeta("importe_bruto", "k-bruto"), tarjeta("comisiones", "k-comisiones"),
                  tarjeta("gastos_pago", "k-gastos"), tarjeta("neto", "k-neto", "bruto − comisiones − gastos"),
                  tarjeta("importe_cobrado", "k-cobrado", "solo Airbnb · por mes de pago")],
                 style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginBottom": "16px"}),
        html.H2("Neto de reservas por mes de llegada", style={"fontSize": "17px", "margin": "8px 0"}),
        dcc.Graph(id="grafico", config={"displayModeBar": False}),
        html.H2("Agregados mensuales", style={"fontSize": "17px", "margin": "16px 0 8px"}),
        dash_table.DataTable(
            id="tabla", columns=[{"name": n, "id": k} for k, n in COLUMNAS_TABLA], page_size=24,
            style_cell={"fontFamily": FUENTE, "fontSize": "13px", "padding": "6px 8px", "textAlign": "right"},
            style_cell_conditional=[{"if": {"column_id": c}, "textAlign": "left"} for c in ("plataforma_nombre", "mes")],
            style_header={"fontWeight": 600, "backgroundColor": "#f9fafb"}, style_table={"overflowX": "auto"},
        ),
        html.Details([html.Summary("Qué mide cada importe"),
                      html.Ul([html.Li([html.Strong(d["etiqueta"] + ": "), d["descripcion"]])
                               for d in DEFINICIONES.values()] +
                              [html.Li("Excluidas: reservas canceladas o no presentadas; no suman en ningún importe.")],
                              style={"fontSize": "13px", "color": TINTA})],
                     style={"marginTop": "16px"}),
    ],
    style={"maxWidth": "1100px", "margin": "24px auto", "padding": "0 16px", "fontFamily": FUENTE, "color": TINTA},
)


@app.callback(
    Output("datos", "data"), Output("desde", "options"), Output("hasta", "options"),
    Output("desde", "value"), Output("hasta", "value"), Output("consultado", "children"), Output("error", "children"),
    Input("actualizar", "n_clicks"), State("desde", "value"), State("hasta", "value"),
)
def actualizar(_n, desde, hasta):
    """Consulta SQL Server al cargar la página y con cada pulsación de «Actualizar datos»."""
    try:
        filas = agregados_mensuales()
    except Exception as exc:  # noqa: BLE001
        log.error("Fallo al consultar agregados: %s", type(exc).__name__)   # sin mensajes del driver
        reiniciar_conexion()
        aviso = html.Div("No se pudieron cargar los datos de SQL Server. Comprueba que el servicio está en marcha "
                         "y vuelve a pulsar «Actualizar datos».",
                         style={"background": "#fef2f2", "color": "#991b1b", "border": "1px solid #fecaca",
                                "borderRadius": "6px", "padding": "10px 14px", "marginBottom": "16px"})
        return [], [], [], None, None, "", aviso
    meses = sorted({f.mes for f in filas})
    opciones = [{"label": m, "value": m} for m in meses]
    desde = desde if desde in meses else (meses[0] if meses else None)
    hasta = hasta if hasta in meses else (meses[-1] if meses else None)
    return ([f.a_texto() for f in filas], opciones, opciones, desde, hasta,
            f"Datos consultados a las {datetime.now():%H:%M:%S}", None)


@app.callback(
    Output("k-reservas", "children"), Output("k-noches", "children"), Output("k-bruto", "children"),
    Output("k-comisiones", "children"), Output("k-gastos", "children"), Output("k-neto", "children"),
    Output("k-cobrado", "children"), Output("grafico", "figure"), Output("tabla", "data"),
    Input("datos", "data"), Input("plataforma", "value"), Input("desde", "value"), Input("hasta", "value"),
)
def pintar(datos, plataforma, desde, hasta):
    filas = filtrar([AgregadoMes.desde_texto(d) for d in (datos or [])], plataforma, desde, hasta)
    t = totales(filas)
    excl = f" ({t['reservas_excluidas']} excluidas)" if t["reservas_excluidas"] else ""
    return (f"{t['reservas']}{excl}", f"{t['noches']}", euros(t["importe_bruto"]), euros(t["comisiones"]),
            euros(t["gastos_pago"]), euros(t["neto"]),
            euros(t["importe_cobrado"]) if t["importe_cobrado"] is not None else "n/d",
            figura(filas), filas_tabla(filas))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app.run(host=HOST, port=PUERTO, debug=False)
