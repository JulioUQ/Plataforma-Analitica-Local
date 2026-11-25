"""Genera el dashboard estático de GitHub Pages a partir de los agregados exportados.

Solo lee publicacion/agregados_alquileres.json (creado en local con exportar_agregados.py):
ni Excel, ni SQL Server, ni credenciales. Los importes se tratan como Decimal y solo se
redondean a céntimos al mostrarlos.

Uso desde la raíz del repo:
    python python/generar_pagina.py                 # escribe _site/index.html y _site/plotly.min.js
    python python/generar_pagina.py --salida carpeta
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import plotly
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

RAIZ = Path(__file__).resolve().parents[1]
ORIGEN = Path("publicacion/agregados_alquileres.json")
ZONA = ZoneInfo("Europe/Madrid")
COLORES = {"airbnb": "#e11d48", "booking": "#1d4ed8"}
IMPORTES = ("importe_bruto", "comisiones", "gastos_pago", "neto", "importe_cobrado")
ENTEROS = ("reservas", "reservas_excluidas", "noches", "pagos")
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
            "octubre", "noviembre", "diciembre"]
CERO = Decimal("0")


def euros(valor: Decimal | None) -> str:
    if valor is None:
        return "n/d"
    s = f"{valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".") + " €"


def mes_largo(m: str) -> str:
    a, n = m.split("-")
    return f"{MESES_ES[int(n) - 1]} {a}"


def leer(ruta: Path) -> dict:
    """Carga y valida el JSON exportado; cualquier incoherencia hace fallar el build."""
    d = json.loads(ruta.read_text(encoding="utf-8"))
    if d.get("esquema") != 1 or d.get("moneda") != "EUR":
        raise ValueError("Esquema o moneda no admitidos en el archivo de agregados")
    plataformas = {p["id"]: p for p in d["plataformas"]}
    meses = []
    for f in d["meses"]:
        if f["plataforma"] not in plataformas or not re.fullmatch(r"\d{4}-\d{2}", f["mes"]):
            raise ValueError(f"Fila de agregados no válida: {f.get('plataforma')} {f.get('mes')}")
        g = dict(f)
        for k in IMPORTES:
            g[k] = None if f[k] is None else Decimal(f[k])
        for k in ENTEROS:
            g[k] = None if f[k] is None else int(f[k])
        meses.append(g)
    if not meses:
        raise ValueError("El archivo de agregados no tiene filas")
    todos = sorted({f["mes"] for f in meses})
    if d["periodo"] != {"desde": todos[0], "hasta": todos[-1]}:
        raise ValueError("El periodo declarado no coincide con los meses del archivo")
    d["meses"], d["_plataformas"] = meses, plataformas
    return d


def resumen(filas: list[dict]) -> dict:
    cobrados = [f["importe_cobrado"] for f in filas if f["importe_cobrado"] is not None]
    excl = sum(f["reservas_excluidas"] for f in filas)
    return {
        "reservas": str(sum(f["reservas"] for f in filas)) + (f" ({excl} excluidas)" if excl else ""),
        "noches": str(sum(f["noches"] for f in filas)),
        "importe_bruto": euros(sum((f["importe_bruto"] for f in filas), CERO)),
        "comisiones": euros(sum((f["comisiones"] for f in filas), CERO)),
        "gastos_pago": euros(sum((f["gastos_pago"] for f in filas), CERO)),
        "neto": euros(sum((f["neto"] for f in filas), CERO)),
        "importe_cobrado": euros(sum(cobrados, CERO)) if cobrados else "n/d",
    }


def figura(d: dict) -> go.Figure:
    meses = sorted({f["mes"] for f in d["meses"]})
    fig = go.Figure()
    for pid, p in sorted(d["_plataformas"].items()):
        por_mes = {f["mes"]: f for f in d["meses"] if f["plataforma"] == pid}
        fig.add_bar(
            name=p["nombre"], x=meses, marker_color=COLORES.get(pid),
            y=[float(por_mes[m]["neto"]) if m in por_mes else 0 for m in meses],      # solo para dibujar
            customdata=[[euros(por_mes[m]["neto"]), euros(por_mes[m]["importe_bruto"]), por_mes[m]["reservas"]]
                        if m in por_mes else ["0,00 €", "0,00 €", 0] for m in meses],
            hovertemplate=p["nombre"] + " · %{x}<br>Neto: %{customdata[0]}<br>Bruto: %{customdata[1]}"
                          "<br>%{customdata[2]} reservas<extra></extra>",
        )
    fig.update_layout(
        barmode="stack", autosize=True, height=340, margin=dict(l=8, r=8, t=8, b=8),
        plot_bgcolor="white", paper_bgcolor="white", separators=",.", showlegend=True, dragmode=False,
        font=dict(family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif", color="#1f2937", size=12),
        xaxis=dict(type="category", title=None, fixedrange=True),
        yaxis=dict(title=None, gridcolor="#e5e7eb", ticksuffix=" €", fixedrange=True, rangemode="tozero"),
        legend=dict(orientation="h", y=1.1, x=0),
    )
    return fig


KPIS = [("reservas", "Reservas"), ("noches", "Noches"), ("importe_bruto", "Importe bruto"),
        ("comisiones", "Comisiones"), ("gastos_pago", "Gastos de pago"), ("neto", "Neto de reservas"),
        ("importe_cobrado", "Cobrado (liquidado)")]

PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Alquileres · indicadores mensuales</title>
<meta name="description" content="Indicadores mensuales agregados de alquiler vacacional (Airbnb y Booking).">
<style>
  :root {{ --tinta:#1f2937; --gris:#6b7280; --borde:#e5e7eb; --azul:#2563eb; color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color:var(--tinta); background:#fff; }}
  main {{ max-width: 1000px; margin: 0 auto; padding: 20px 16px 32px; }}
  h1 {{ font-size: clamp(22px, 5vw, 28px); margin: 0 0 4px; }}
  h2 {{ font-size: 17px; margin: 24px 0 8px; }}
  .sub {{ color: var(--gris); margin: 0 0 14px; }}
  .aviso {{ background:#eff6ff; border:1px solid #bfdbfe; color:#1e3a8a; border-radius:8px; padding:10px 14px; font-size:14px; margin-bottom:14px; line-height:1.45; }}
  .filtro {{ display:flex; gap:8px; flex-wrap:wrap; margin: 0 0 14px; }}
  .filtro button {{ border:1px solid var(--borde); background:#fff; color:var(--tinta); border-radius:999px; padding:7px 14px; font-size:14px; cursor:pointer; }}
  .filtro button[aria-pressed="true"] {{ background:var(--azul); border-color:var(--azul); color:#fff; }}
  .kpis {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:10px; }}
  .kpi {{ border:1px solid var(--borde); border-radius:8px; padding:12px 14px; }}
  .kpi .t {{ color:var(--gris); font-size:13px; }}
  .kpi .v {{ font-size: clamp(19px, 5vw, 24px); font-weight:600; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  #grafico {{ width:100%; min-height:340px; }}
  .tabla {{ overflow-x:auto; }}
  table {{ border-collapse: collapse; width:100%; font-size:13px; }}
  th, td {{ padding:6px 8px; border-bottom:1px solid var(--borde); text-align:right; white-space:nowrap; font-variant-numeric: tabular-nums; }}
  th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align:left; }}
  dl {{ font-size:13px; line-height:1.45; margin:0; }}
  dt {{ font-weight:600; margin-top:8px; }} dd {{ margin:0; color:#374151; }}
  footer {{ color:var(--gris); font-size:13px; margin-top:24px; line-height:1.5; }}
  footer a {{ color: var(--azul); }}
</style>
<script src="plotly.min.js" charset="utf-8"></script>
</head>
<body>
<main>
  <h1>Alquileres: indicadores mensuales</h1>
  <p class="sub">Airbnb y Booking · periodo cubierto: <strong id="periodo">{periodo}</strong></p>
  <p class="aviso" role="note"><strong>Datos reales agregados por mes.</strong> Esta página solo contiene totales
  mensuales por plataforma exportados del SQL Server local; no incluye reservas individuales, huéspedes ni referencias.
  Exportación de los datos: <time id="exportado" datetime="{exportado_iso}">{exportado}</time>.</p>

  <div class="filtro" role="group" aria-label="Plataforma">
{botones}
  </div>

  <section class="kpis" aria-label="Indicadores">
{kpis}
  </section>

  <h2>Neto de reservas por mes de llegada</h2>
  <div id="grafico" role="img" aria-label="Gráfico de barras apiladas del neto mensual por plataforma"></div>

  <h2>Agregados mensuales</h2>
  <div class="tabla">
  <table id="tabla">
    <thead><tr><th>Plataforma</th><th>Mes</th><th>Reservas</th><th>Noches</th><th>Importe bruto</th><th>Comisiones</th>
    <th>Gastos de pago</th><th>Neto</th><th>Cobrado</th></tr></thead>
    <tbody>
{filas}
    </tbody>
  </table>
  </div>

  <h2>Qué mide cada indicador</h2>
  <dl>
{definiciones}
    <dt>Base del mes</dt><dd>Reservas, noches e importes de reserva: mes de llegada. Cobrado: mes del pago liquidado.
    El neto y el cobrado describen la misma actividad desde dos momentos distintos: no se suman.</dd>
  </dl>

  <footer>
    Vista generada el <time id="generado" datetime="{generado_iso}">{generado}</time> (hora de Madrid){commit}
    a partir de <code>{origen}</code>.{repo}
  </footer>
</main>
<script>
  var VISTAS = {vistas};
  var TRAZAS = {trazas};
  var figura = {figura};
  Plotly.newPlot("grafico", figura.data, figura.layout, {{responsive: true, displayModeBar: false}});
  function elegir(p) {{
    document.querySelectorAll(".filtro button").forEach(function (b) {{
      b.setAttribute("aria-pressed", String(b.dataset.p === p)); }});
    Object.keys(VISTAS[p]).forEach(function (k) {{ document.getElementById("k-" + k).textContent = VISTAS[p][k]; }});
    Plotly.restyle("grafico", {{visible: TRAZAS.map(function (t) {{ return p === "todas" || t === p; }})}});
    document.querySelectorAll("#tabla tbody tr").forEach(function (tr) {{
      tr.hidden = !(p === "todas" || tr.dataset.p === p); }});
  }}
  document.querySelectorAll(".filtro button").forEach(function (b) {{
    b.addEventListener("click", function () {{ elegir(b.dataset.p); }}); }});
</script>
</body>
</html>
"""


def generar(origen: Path, salida: Path) -> dict:
    d = leer(origen)
    plats = d["_plataformas"]
    vistas = {"todas": resumen(d["meses"])}
    for pid in plats:
        vistas[pid] = resumen([f for f in d["meses"] if f["plataforma"] == pid])
    exportado = datetime.fromisoformat(d["exportado_en"]).astimezone(ZONA)
    ahora = datetime.now(ZONA)
    sha = os.environ.get("GITHUB_SHA", "")[:7]
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    servidor = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    esc = html.escape

    botones = "\n".join(
        f'    <button type="button" data-p="{esc(pid)}" aria-pressed="{str(pid == "todas").lower()}">{esc(nombre)}</button>'
        for pid, nombre in [("todas", "Todas")] + [(p["id"], p["nombre"]) for p in sorted(plats.values(), key=lambda p: p["id"])])
    kpis = "\n".join(
        f'    <div class="kpi" title="{esc(d["definiciones"][k]["descripcion"])}"><div class="t">{esc(t)}</div>'
        f'<div class="v" id="k-{k}">{esc(vistas["todas"][k])}</div></div>' for k, t in KPIS)
    filas = "\n".join(
        f'      <tr data-p="{esc(f["plataforma"])}"><td>{esc(plats[f["plataforma"]]["nombre"])}</td><td>{f["mes"]}</td>'
        f'<td>{f["reservas"]}</td><td>{f["noches"]}</td><td>{esc(euros(f["importe_bruto"]))}</td>'
        f'<td>{esc(euros(f["comisiones"]))}</td><td>{esc(euros(f["gastos_pago"]))}</td><td>{esc(euros(f["neto"]))}</td>'
        f'<td>{esc(euros(f["importe_cobrado"]))}</td></tr>'
        for f in sorted(d["meses"], key=lambda f: (f["mes"], f["plataforma"])))
    definiciones = "\n".join(f'    <dt>{esc(v["etiqueta"])}</dt><dd>{esc(v["descripcion"])}</dd>'
                             for v in d["definiciones"].values())
    json_script = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")

    pagina = PLANTILLA.format(
        periodo=esc(f'{mes_largo(d["periodo"]["desde"])} – {mes_largo(d["periodo"]["hasta"])}'),
        exportado_iso=exportado.isoformat(timespec="seconds"),
        exportado=exportado.strftime("%d/%m/%Y a las %H:%M") + " (hora de Madrid)",
        botones=botones, kpis=kpis, filas=filas, definiciones=definiciones,
        generado_iso=ahora.isoformat(timespec="seconds"), generado=ahora.strftime("%d/%m/%Y a las %H:%M"),
        commit=f" desde el commit <code>{esc(sha)}</code>" if sha else "",
        origen=esc(ORIGEN.as_posix()),
        repo=f' · <a href="{esc(servidor)}/{esc(repo)}">Código en GitHub</a>' if repo else "",
        vistas=json_script(vistas), trazas=json_script(sorted(plats)),
        figura=figura(d).to_json().replace("</", "<\\/"),
    )
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "index.html").write_text(pagina, encoding="utf-8")
    (salida / "plotly.min.js").write_text(get_plotlyjs(), encoding="utf-8")
    return {"periodo": d["periodo"], "vistas": vistas}


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera el dashboard estático de GitHub Pages")
    ap.add_argument("--origen", default=str(ORIGEN))
    ap.add_argument("--salida", default="_site")
    args = ap.parse_args()
    origen, salida = Path(args.origen), Path(args.salida)
    origen = origen if origen.is_absolute() else RAIZ / origen
    salida = salida if salida.is_absolute() else RAIZ / salida
    r = generar(origen, salida)
    print(f"Página generada en {salida} (plotly {plotly.__version__}) · periodo {r['periodo']['desde']} a {r['periodo']['hasta']}")
    for p, v in r["vistas"].items():
        print(f"  {p:<8} " + " · ".join(f"{k}={v[k]}" for k, _ in KPIS))


if __name__ == "__main__":
    main()
