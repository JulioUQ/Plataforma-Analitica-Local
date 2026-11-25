"""Exporta desde SQL Server los agregados mensuales reales a un JSON versionable.

Es lo único que se publica en GitHub Pages: totales por plataforma y mes, sin filas
individuales, huéspedes, referencias de reserva ni nombre del alojamiento.

Uso desde la raíz del repo (SQL Server en marcha y .env configurado):
    .\\.venv\\Scripts\\python.exe python\\exportar_agregados.py
    git add publicacion/agregados_alquileres.json ; git commit -m "..." ; git push
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from alquileres import DEFINICIONES, agregados_mensuales

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = Path("publicacion/agregados_alquileres.json")


def construir() -> dict:
    filas = agregados_mensuales()
    if not filas:
        raise SystemExit("No hay agregados en alq.v_agregados_mensuales: ejecuta antes la importación de n8n.")
    meses = sorted({f.mes for f in filas})
    plataformas = {}
    for f in filas:
        p = plataformas.setdefault(f.plataforma, {"id": f.plataforma, "nombre": f.plataforma_nombre,
                                                  "informa_pagos": f.importe_cobrado is not None})
        p["informa_pagos"] = p["informa_pagos"] or f.importe_cobrado is not None
    return {
        "esquema": 1,
        "titulo": "Indicadores mensuales de alquiler (Airbnb y Booking)",
        "exportado_en": datetime.now(ZoneInfo("Europe/Madrid")).isoformat(timespec="seconds"),
        "origen": "SQL Server local · Gestion_Alquileres.alq.v_agregados_mensuales (cargado con n8n desde los Excel)",
        "moneda": "EUR",
        "periodo": {"desde": meses[0], "hasta": meses[-1]},
        "base_del_mes": {
            "reservas": "mes de la fecha de llegada (check-in)",
            "importe_cobrado": "mes de la fecha del pago liquidado",
        },
        "definiciones": DEFINICIONES,
        "plataformas": sorted(plataformas.values(), key=lambda p: p["id"]),
        "meses": [f.a_texto() for f in filas],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Exporta los agregados mensuales a JSON")
    ap.add_argument("--salida", default=str(SALIDA))
    args = ap.parse_args()
    salida = Path(args.salida)
    if not salida.is_absolute():
        salida = RAIZ / salida
    datos = construir()
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Exportado {salida.relative_to(RAIZ) if salida.is_relative_to(RAIZ) else salida}: "
          f"{len(datos['meses'])} filas mes×plataforma, periodo {datos['periodo']['desde']} a {datos['periodo']['hasta']}")


if __name__ == "__main__":
    main()
