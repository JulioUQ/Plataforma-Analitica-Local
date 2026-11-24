"""Conexión reutilizable a SQL Server (instancia local)."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL

# Carga el .env de la raíz del repositorio, se ejecute desde donde se ejecute
load_dotenv(
    Path(__file__).resolve().parents[1] / ".env",
    override=True,
)


def get_engine(database: str | None = None) -> Engine:
    """Devuelve un engine de SQLAlchemy.

    Si no se indica `database`, usa DB_NAME del .env.
    """
    url = URL.create(
        drivername="mssql+pyodbc",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "1433")),
        database=database or os.environ["DB_NAME"],
        query={
            "driver": "ODBC Driver 18 for SQL Server",
            "Encrypt": "yes",
            "TrustServerCertificate": "yes",  # solo válido en local (certificado autofirmado)
        },
    )
    return create_engine(url, fast_executemany=True)