"""Genera el dashboard estático para GitHub Pages a partir del CSV ficticio versionado.

No usa SQL Server ni credenciales: lee etl/n8n/ejemplos/cobros.csv, lo valida con las
mismas reglas que el workflow importar_cobros de n8n y calcula los totales con Decimal.

Uso desde la raíz del repo:
    python python/generar_pagina.py            # escribe _site/index.html y _site/plotly.min.js
    python python/generar_pagina.py --salida otra_carpeta
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import plotly
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

RAIZ = Path(__file__).resolve().parents[1]
CSV_ORIGEN = Path("etl/n8n/ejemplos/cobros.csv")
COLUMNAS = ["cobro_id", "inmueble", "fecha_cobro", "importe"]
RE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,19}$")
RE_IMPORTE = re.compile(r"^\d{1,10}(\.\d{1,2})?$")
ZONA = ZoneInfo("Europe/Madrid")
AZUL = "#2563eb"


def euros(valor: Decimal) -> str:
    """Decimal('13533.1') -> '13.533,10 €'."""
    s = f"{valor.quantize(Decimal('0.01')):,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".") + " €"


def leer_cobros(ruta: Path) -> list[dict]:
    """Lee y valida el CSV completo; cualquier error aborta la generación."""
    with ruta.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        if lector.fieldnames != COLUMNAS:
            raise ValueError(f"Cabecera inesperada {lector.fieldnames}; se esperaba {COLUMNAS}")
        filas, errores, vistos = [], [], set()
        for n, fila in enumerate(lector, start=2):
            v = {c: (fila.get(c) or "").strip() for c in COLUMNAS}
            if None in fila:
                errores.append(f"línea {n}: columnas de más")
            if not RE_ID.match(v["cobro_id"]):
                errores.append(f"línea {n}: cobro_id no válido")
            elif v["cobro_id"] in vistos:
                errores.append(f"línea {n}: cobro_id repetido {v['cobro_id']}")
            vistos.add(v["cobro_id"])
            if not v["inmueble"] or len(v["inmueble"]) > 100:
                errores.append(f"línea {n}: inmueble vacío o demasiado largo")
            try:
                fecha = date.fromisoformat(v["fecha_cobro"])
                if fecha.isoformat() != v["fecha_cobro"]:
                    raise ValueError
            except ValueError:
                errores.append(f"línea {n}: fecha_cobro debe ser AAAA-MM-DD")
                fecha = None
            if not RE_IMPORTE.match(v["importe"]) or Decimal(v["importe"]) <= 0:
                errores.append(f"línea {n}: importe positivo con punto decimal y hasta 2 decimales")
            else:
                filas.append({**v, "fecha": fecha, "importe": Decimal(v["importe"])})
    if not filas and not errores:
        errores.append("el CSV no tiene filas de datos")
    if errores:
        raise ValueError("CSV no válido: " + "; ".join(errores))
    return filas


def por_mes(filas: list[dict]) -> "OrderedDict[str, dict]":
    meses: dict[str, dict] = {}
    for f in filas:
        m = f["fecha"].strftime("%Y-%m")
        d = meses.setdefault(m, {"cobros": 0, "total": Decimal("0")})
        d["cobros"] += 1
        d["total"] += f["importe"]
    return OrderedDict(sorted(meses.items()))


def figura(meses: "OrderedDict[str, dict]") -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=list(meses),
            y=[float(d["total"]) for d in meses.values()],          # solo para dibujar la barra
            text=[euros(d["total"]) for d in meses.values()],        # etiquetas exactas
            customdata=[[d["cobros"], euros(d["total"])] for d in meses.values()],
            textposition="outside",
            textfont=dict(size=12),
            hovertemplate="%{x}<br>%{customdata[1]}<br>%{customdata[0]} cobros<extra></extra>",
            marker_color=AZUL,
            cliponaxis=False,
        )
    )
    fig.update_layout(
        autosize=True,
        height=340,
        margin=dict(l=8, r=8, t=28, b=8),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif", color="#1f2937", size=13),
        xaxis=dict(type="category", title=None, fixedrange=True),
        yaxis=dict(title=None, gridcolor="#e5e7eb", separatethousands=True, rangemode="tozero",
                   fixedrange=True, ticksuffix=" €"),
        separators=",.",
        showlegend=False,
        dragmode=False,
    )
    return fig


PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cobros de alquileres · datos ficticios</title>
<meta name="description" content="Dashboard de ejemplo con datos ficticios de cobros de alquileres.">
<style>
  :root {{ --tinta:#1f2937; --gris:#6b7280; --borde:#e5e7eb; --azul:{azul}; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color:var(--tinta); background:#fff; }}
  main {{ max-width: 900px; margin: 0 auto; padding: 20px 16px 32px; }}
  h1 {{ font-size: clamp(22px, 5vw, 28px); margin: 0 0 4px; }}
  h2 {{ font-size: 17px; margin: 24px 0 8px; }}
  .sub {{ color: var(--gris); margin: 0 0 16px; }}
  .aviso {{ background:#fffbeb; border:1px solid #fde68a; color:#92400e; border-radius:8px; padding:10px 14px; font-size:14px; margin-bottom:16px; }}
  .kpis {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:12px; }}
  .kpi {{ border:1px solid var(--borde); border-radius:8px; padding:14px 18px; }}
  .kpi .t {{ color:var(--gris); font-size:14px; }}
  .kpi .v {{ font-size: clamp(22px, 6.2vw, 32px); font-weight:600; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  #grafico {{ width:100%; min-height:340px; }}
  table {{ border-collapse: collapse; width:100%; max-width:420px; font-size:14px; }}
  th, td {{ padding:6px 10px; border-bottom:1px solid var(--borde); text-align:left; }}
  td.n, th.n {{ text-align:right; font-variant-numeric: tabular-nums; }}
  footer {{ color:var(--gris); font-size:13px; margin-top:24px; line-height:1.5; }}
  footer a {{ color: var(--azul); }}
</style>
<script src="plotly.min.js" charset="utf-8"></script>
</head>
<body>
<main>
  <h1>Cobros de alquileres</h1>
  <p class="sub">Gestion_Alquileres · vista estática publicada con GitHub Pages</p>
  <p class="aviso" role="note"><strong>Datos ficticios.</strong> Esta página usa solo el CSV de ejemplo
  <code>{csv}</code>; no contiene datos reales ni se conecta a ninguna base de datos.</p>

  <section class="kpis" aria-label="Resumen">
    <div class="kpi"><div class="t">Total cobrado</div><div class="v" id="total">{total}</div></div>
    <div class="kpi"><div class="t">Número de cobros</div><div class="v" id="num-cobros">{num}</div></div>
  </section>

  <h2>Total cobrado por mes</h2>
  <div id="grafico" role="img" aria-label="Gráfico de barras del total cobrado por mes"></div>

  <h2>Detalle mensual</h2>
  <table id="tabla">
    <thead><tr><th>Mes</th><th class="n">Cobros</th><th class="n">Total</th></tr></thead>
    <tbody>
{filas}
    </tbody>
  </table>

  <footer>
    Vista generada el <time id="generado" datetime="{generado_iso}">{generado}</time> (hora de Madrid){commit}.<br>
    Origen: <code>{csv}</code> · {n_filas} filas · total calculado con precisión decimal.{repo}
  </footer>
</main>
<script>
  var figura = {figura};
  Plotly.newPlot("grafico", figura.data, figura.layout, {{responsive: true, displayModeBar: false}});
</script>
</body>
</html>
"""


def generar(salida: Path) -> dict:
    filas = leer_cobros(RAIZ / CSV_ORIGEN)
    meses = por_mes(filas)
    total = sum((f["importe"] for f in filas), Decimal("0"))
    ahora = datetime.now(ZONA)
    sha = os.environ.get("GITHUB_SHA", "")[:7]
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    servidor = os.environ.get("GITHUB_SERVER_URL", "https://github.com")

    filas_html = "\n".join(
        f'      <tr id="fila-{m}"><td>{m}</td><td class="n">{d["cobros"]}</td>'
        f'<td class="n">{html.escape(euros(d["total"]))}</td></tr>'
        for m, d in meses.items()
    )
    pagina = PLANTILLA.format(
        azul=AZUL,
        csv=html.escape(CSV_ORIGEN.as_posix()),
        total=html.escape(euros(total)),
        num=len(filas),
        filas=filas_html,
        generado_iso=ahora.isoformat(timespec="seconds"),
        generado=ahora.strftime("%d/%m/%Y a las %H:%M"),
        commit=f" desde el commit <code>{html.escape(sha)}</code>" if sha else "",
        n_filas=len(filas),
        repo=(f' · <a href="{html.escape(servidor)}/{html.escape(repo)}">Código en GitHub</a>' if repo else ""),
        # JSON dentro de <script>: se escapa "</" para que no pueda cerrar la etiqueta
        figura=figura(meses).to_json().replace("</", "<\\/"),
    )

    salida.mkdir(parents=True, exist_ok=True)
    (salida / "index.html").write_text(pagina, encoding="utf-8")
    (salida / "plotly.min.js").write_text(get_plotlyjs(), encoding="utf-8")
    return {"cobros": len(filas), "total": total, "meses": {m: d["total"] for m, d in meses.items()}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", default="_site", help="carpeta de salida (por defecto _site)")
    args = ap.parse_args()
    salida = Path(args.salida)
    if not salida.is_absolute():
        salida = RAIZ / salida
    r = generar(salida)
    print(f"Página generada en {salida} (plotly {plotly.__version__})")
    print(f"cobros={r['cobros']} total={r['total']}")
    for m, t in r["meses"].items():
        print(f"  {m} {t}")


if __name__ == "__main__":
    main()
