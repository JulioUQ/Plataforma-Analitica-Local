"""Agregados mensuales reales de Airbnb y Booking (Gestion_Alquileres.alq).

Consulta compartida por el Dash local (dashboard_alquileres.py) y la exportación pública
(exportar_agregados.py). Los importes llegan como Decimal desde DECIMAL(16,3) y no pasan por
float: los totales son exactos y solo se redondean al mostrarlos (2 decimales, medio hacia arriba).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from sqlalchemy.engine import Engine

from db import get_engine

BASE_DATOS = "Gestion_Alquileres"
CERO = Decimal("0")

# Qué mide cada indicador (se reutiliza en Dash, en el JSON exportado y en GitHub Pages)
DEFINICIONES: dict[str, dict[str, str]] = {
    "reservas": {"etiqueta": "Reservas",
                 "descripcion": "Reservas confirmadas (sin canceladas ni no presentadas), por mes de llegada."},
    "noches": {"etiqueta": "Noches", "descripcion": "Noches de las reservas confirmadas, por mes de llegada."},
    "importe_bruto": {"etiqueta": "Importe bruto de reservas",
                      "descripcion": "Precio de la estancia antes de las comisiones de la plataforma "
                                     "(Airbnb: Ingresos brutos; Booking: Final amount), por mes de llegada."},
    "comisiones": {"etiqueta": "Comisiones de la plataforma",
                   "descripcion": "Airbnb: Comisión de servicio; Booking: Commission amount. Por mes de llegada."},
    "gastos_pago": {"etiqueta": "Gastos de pago",
                    "descripcion": "Airbnb: Comisión por Pago rápido; Booking: Payment fee. Por mes de llegada."},
    "neto": {"etiqueta": "Neto de reservas",
             "descripcion": "Importe bruto − comisiones − gastos de pago, por mes de llegada. "
                            "En Booking es un cálculo: su export no incluye pagos liquidados."},
    "importe_cobrado": {"etiqueta": "Cobrado (pagos liquidados)",
                        "descripcion": "Solo Airbnb: importe de los pagos (Payout) por mes de la fecha de pago. "
                                       "No se suma al neto: es la misma actividad vista desde la liquidación."},
}

_SQL = text(
    """
    SELECT plataforma, plataforma_nombre, mes, reservas, reservas_excluidas, noches,
           importe_bruto, comisiones, gastos_pago, neto, pagos, importe_cobrado
    FROM alq.v_agregados_mensuales
    ORDER BY mes, plataforma;
    """
)


@dataclass(frozen=True)
class AgregadoMes:
    plataforma: str              # 'airbnb' | 'booking'
    plataforma_nombre: str
    mes: str                     # 'AAAA-MM'
    reservas: int
    reservas_excluidas: int
    noches: int
    importe_bruto: Decimal
    comisiones: Decimal
    gastos_pago: Decimal
    neto: Decimal
    pagos: int | None            # None: la plataforma no informa pagos liquidados
    importe_cobrado: Decimal | None

    def a_texto(self) -> dict:
        """Diccionario serializable: los Decimal como texto exacto."""
        return {k: (format(v, "f") if isinstance(v, Decimal) else v) for k, v in asdict(self).items()}

    @classmethod
    def desde_texto(cls, d: dict) -> "AgregadoMes":
        dec = lambda v: None if v is None else Decimal(v)
        return cls(d["plataforma"], d["plataforma_nombre"], d["mes"], int(d["reservas"]),
                   int(d["reservas_excluidas"]), int(d["noches"]), dec(d["importe_bruto"]), dec(d["comisiones"]),
                   dec(d["gastos_pago"]), dec(d["neto"]), None if d["pagos"] is None else int(d["pagos"]),
                   dec(d["importe_cobrado"]))


_engine: Engine | None = None


def engine_gestion() -> Engine:
    global _engine
    if _engine is None:
        _engine = get_engine(database=BASE_DATOS)
    return _engine


def reiniciar_conexion() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def agregados_mensuales(engine: Engine | None = None) -> list[AgregadoMes]:
    """Todos los agregados mensuales por plataforma, ordenados por mes y plataforma."""
    engine = engine or engine_gestion()
    with engine.connect() as conn:
        filas = conn.execute(_SQL).all()
    return [
        AgregadoMes(f.plataforma, f.plataforma_nombre, f.mes, int(f.reservas), int(f.reservas_excluidas),
                    int(f.noches), Decimal(f.importe_bruto), Decimal(f.comisiones), Decimal(f.gastos_pago),
                    Decimal(f.neto), None if f.pagos is None else int(f.pagos),
                    None if f.importe_cobrado is None else Decimal(f.importe_cobrado))
        for f in filas
    ]


def filtrar(filas: list[AgregadoMes], plataforma: str | None = None,
            desde: str | None = None, hasta: str | None = None) -> list[AgregadoMes]:
    return [f for f in filas
            if (not plataforma or plataforma == "todas" or f.plataforma == plataforma)
            and (not desde or f.mes >= desde) and (not hasta or f.mes <= hasta)]


def totales(filas: list[AgregadoMes]) -> dict:
    """Totales exactos. El cobrado solo suma plataformas que lo informan (None si ninguna)."""
    cobrados = [f.importe_cobrado for f in filas if f.importe_cobrado is not None]
    return {
        "reservas": sum(f.reservas for f in filas),
        "reservas_excluidas": sum(f.reservas_excluidas for f in filas),
        "noches": sum(f.noches for f in filas),
        "importe_bruto": sum((f.importe_bruto for f in filas), CERO),
        "comisiones": sum((f.comisiones for f in filas), CERO),
        "gastos_pago": sum((f.gastos_pago for f in filas), CERO),
        "neto": sum((f.neto for f in filas), CERO),
        "pagos": sum(f.pagos for f in filas if f.pagos is not None) if cobrados else None,
        "importe_cobrado": sum(cobrados, CERO) if cobrados else None,
    }


def euros(valor: Decimal | None) -> str:
    """Decimal('2441.975') -> '2.441,98 €' (redondeo a céntimos medio hacia arriba)."""
    if valor is None:
        return "—"
    s = f"{valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".") + " €"


if __name__ == "__main__":
    datos = agregados_mensuales()
    for f in datos:
        print(f"{f.mes} {f.plataforma:<8} res={f.reservas:>2} noches={f.noches:>2} bruto={f.importe_bruto:>9} "
              f"com={f.comisiones:>8} gastos={f.gastos_pago:>6} neto={f.neto:>9} cobrado={f.importe_cobrado}")
    for p in ("airbnb", "booking", "todas"):
        t = totales(filtrar(datos, p))
        print(p, {k: (format(v, "f") if isinstance(v, Decimal) else v) for k, v in t.items()})
