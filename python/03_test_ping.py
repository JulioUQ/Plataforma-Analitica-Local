"""Prueba de la Fase 3: conexión, lectura y escritura en SQL Server."""
from datetime import datetime

import pandas as pd
import polars as pl
from sqlalchemy import text

from db import get_engine

engine = get_engine()

# 1) Conexión
with engine.connect() as conn:
    login, base, servidor = conn.execute(
        text("SELECT SUSER_NAME(), DB_NAME(), @@SERVERNAME")
    ).one()
print(f"[1] Conectado como '{login}' a la BD '{base}' en '{servidor}'")

# 2) Lectura con pandas
antes = pd.read_sql("SELECT * FROM dbo.ping ORDER BY id", engine)
print(f"[2] pandas leyó {len(antes)} fila(s) de dbo.ping")

# 3) Escritura con pandas
nueva = pd.DataFrame({"mensaje": [f"Hola desde Python {datetime.now():%H:%M:%S}"]})
nueva.to_sql("ping", engine, schema="dbo", if_exists="append", index=False)
despues = pd.read_sql("SELECT * FROM dbo.ping ORDER BY id", engine)
assert len(despues) == len(antes) + 1, "La fila no se insertó"
print(f"[3] Insertada 1 fila. Ahora hay {len(despues)}")

# 4) Crear una tabla nueva desde pandas
prueba = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
prueba.to_sql("ping_pandas", engine, schema="dbo", if_exists="replace", index=False)
leida = pd.read_sql("SELECT * FROM dbo.ping_pandas", engine)
assert leida.equals(prueba), "La tabla creada no coincide con el original"
print("[4] Tabla dbo.ping_pandas creada y leída correctamente")

# 5) Lectura con polars
df_pl = pl.read_database("SELECT TOP 5 * FROM dbo.ping ORDER BY id DESC", connection=engine)
print("[5] polars leyó:")
print(df_pl)

# 6) Limpieza de la tabla temporal
with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS dbo.ping_pandas"))
print("[6] Tabla temporal eliminada. TODO OK")