"""Consultas de cobros sobre Gestion_Alquileres (SQL Server local)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Engine

from db import get_engine

BASE_DATOS = "Gestion_Alquileres"

_SQL_COBROS_POR_MES = text(
    """
    SELECT CONVERT(char(7), fecha_cobro, 126) AS mes,
           COUNT(*)                           AS cobros,
           SUM(importe)                       AS total
    FROM dbo.cobros
    GROUP BY CONVERT(char(7), fecha_cobro, 126)
    ORDER BY mes;
    """
)


@dataclass(frozen=True)
class CobrosMes:
    mes: str          # 'AAAA-MM'
    cobros: int
    total: Decimal    # DECIMAL(12,2) tal cual llega de SQL Server, sin pasar por float


_engine: Engine | None = None


def engine_gestion() -> Engine:
    """Engine de Gestion_Alquileres, creado una vez con la configuración del .env."""
    global _engine
    if _engine is None:
        _engine = get_engine(database=BASE_DATOS)
    return _engine


def reiniciar_conexion() -> None:
    """Descarta el pool tras un fallo para que el siguiente intento abra conexiones nuevas."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def cobros_por_mes(engine: Engine | None = None) -> list[CobrosMes]:
    """Número de cobros e importe total por mes, ordenados cronológicamente."""
    engine = engine or engine_gestion()
    with engine.connect() as conn:
        filas = conn.execute(_SQL_COBROS_POR_MES).all()
    return [CobrosMes(mes=f.mes, cobros=int(f.cobros), total=Decimal(f.total)) for f in filas]


if __name__ == "__main__":
    datos = cobros_por_mes()
    for d in datos:
        print(f"{d.mes}  {d.cobros:>3}  {d.total:>10}")
    print(f"TOTAL    {sum(d.cobros for d in datos):>3}  {sum((d.total for d in datos), Decimal('0')):>10}")
