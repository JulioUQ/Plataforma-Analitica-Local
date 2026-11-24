# Plan general (checklist)

| Fase        | Objetivo                                                          | Resultado verificable                                         |
| ----------- | ----------------------------------------------------------------- | ------------------------------------------------------------- |
| **1** | Instalar SQL Server Developer, driver ODBC 18, SSMS, VS Code, Git | Servicio SQL activo, `sqlcmd` responde, driver ODBC listado |
| **2** | Conectar y verificar el motor (TCP/IP, puerto 1433, logins)       | BD de prueba creada desde VS Code y SSMS                      |
| **3** | Entorno Python (venv, pandas/SQLAlchemy/pyodbc)                   | Script que escribe y lee una tabla en SQL Server              |
| **4** | ETL con n8n (Docker), única herramienta de ETL                    | Flujos de n8n que insertan y cargan datos en SQL Server       |
| **5** | Dash + HTML conectado a la BD                                     | Dashboard que refleja datos modificados en SQL                |
| **6** | Modelado de `Gestion_Alquileres`                                | Esquemas y tablas creados y versionados en Git                |

Un detalle de arquitectura que seguiremos: **una instancia de SQL Server con varias bases de datos independientes** (SIPE, Gestion_Alquileres, Finanzas_Personales). No necesitas una instalación por proyecto.

---

# FASE 1: Preparación del sistema y herramientas base

## 0. Requisitos previos

- Windows 10/11 de 64 bits, con **permisos de administrador**.
- Unos 15 GB libres en disco y 8 GB de RAM como mínimo recomendado.
- Una terminal **PowerShell** abierta como administrador (clic derecho → *Ejecutar como administrador*).

Comprueba que tienes `winget`, el gestor de paquetes de Windows, que nos ahorrará descargas manuales:

```powershell
winget --version
```

Si no existe, instala "App Installer" desde la Microsoft Store.

> **Nota:** las versiones cambian con frecuencia. Si algún ID de `winget` no se encuentra, usa `winget search <nombre>` para localizar el vigente, o la descarga manual indicada.

## 1. Instalar SQL Server Developer

**Versión:** usa **SQL Server 2025 Developer**, o **2022 Developer** si quieres máxima compatibilidad con tutoriales y herramientas antiguas. Ambas son gratuitas y tienen todas las funciones de Enterprise, pero **solo para desarrollo, nunca para producción**.

**Descarga oficial:** https://www.microsoft.com/sql-server/sql-server-downloads → sección *Developer* → "Download now".

**Pasos en el instalador:**

1. Elige el tipo **Custom**, no *Basic*. Así controlas qué se instala y la autenticación.
2. En el asistente de instalación, selecciona **New SQL Server stand-alone installation**.
3. **Edition:** *Developer*.
4. **Feature Selection:** marca solo **Database Engine Services**. No necesitas Analysis Services, Integration Services, R/Python ni PolyBase. Menos servicios significa menos RAM consumida.
5. **Instance Configuration:** deja **Default instance** (`MSSQLSERVER`).
   - *Por qué:* la instancia por defecto se conecta simplemente como `localhost` y usa el puerto estándar 1433. Una instancia con nombre (p. ej. `SQLEXPRESS`) usa puertos dinámicos y el servicio SQL Browser, lo que complica las conexiones desde n8n y Python.
6. **Server Configuration:** deja las cuentas de servicio por defecto. El tipo de inicio del Database Engine debe ser *Automatic*.
7. **Database Engine Configuration → Authentication Mode:** selecciona **Mixed Mode**.
   - Define una contraseña robusta para `sa` y **guárdala en un gestor de contraseñas**.
   - Pulsa **Add Current User** para que tu usuario de Windows sea administrador.
   - *Por qué Mixed Mode:* la **autenticación de Windows** es la más segura para uso interactivo (SSMS, VS Code) porque no hay contraseñas que gestionar. Pero **n8n y algunos conectores** funcionan mucho mejor con **autenticación SQL** (usuario y contraseña). Habilitar Mixed Mode ahora evita reinstalar o reconfigurar después. En la Fase 2 crearemos un login dedicado para no usar `sa` en el día a día.
8. En **Data Directories** puedes dejar los valores por defecto.
9. **Memory** (si aparece la pestaña): limita *Max server memory* a aproximadamente la mitad de tu RAM, para que SQL Server no se coma la memoria que necesitan Python, Power BI y Docker.
10. Finaliza la instalación. Puede tardar entre 10 y 20 minutos.

**Verificación 1.1: el servicio está activo**

```powershell
Get-Service MSSQLSERVER
```

Debe mostrar `Status: Running`. También puedes comprobarlo en `Win + R` → `services.msc` → "SQL Server (MSSQLSERVER)".

## 2. Instalar `sqlcmd` (cliente de línea de comandos)

Es nuestra herramienta de diagnóstico más rápida:

```powershell
winget install Microsoft.Sqlcmd
```

Cierra y vuelve a abrir PowerShell, y verifica:

```powershell
sqlcmd -S localhost -E -C -Q "SELECT @@VERSION"
```

- `-S localhost`: servidor.
- `-E`: autenticación de Windows.
- `-C`: confiar en el certificado del servidor. Esto es necesario porque el certificado es autofirmado (explicado en el punto 3).

**Resultado esperado:** una línea de texto con *Microsoft SQL Server 20xx ... Developer Edition (64-bit)*.

## 3. Instalar Microsoft ODBC Driver 18 para SQL Server

```powershell
winget install Microsoft.msodbcsql.18
```

Descarga manual alternativa: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server

**Por qué el Driver 18 y no el "SQL Server" que viene con Windows:**

- El driver antiguo llamado simplemente `SQL Server` es obsoleto y no soporta TLS moderno ni funciones nuevas.
- **pyodbc, SQLAlchemy y Power BI** deben apuntar a `ODBC Driver 18 for SQL Server`.
- **Cambio importante del Driver 18:** el cifrado está activado por defecto (`Encrypt=yes`). Como tu SQL Server local usa un certificado autofirmado, tendrás que añadir **`TrustServerCertificate=yes`** en tus cadenas de conexión locales. Es aceptable en tu máquina, pero **nunca en un servidor remoto o productivo**. Verás este error muy a menudo si lo olvidas: *"certificate verify failed"* o *"SSL Provider: The certificate chain was issued by an authority that is not trusted"*.

**Verificación 1.2: el driver está registrado**

```powershell
Get-OdbcDriver -Name "*SQL Server*" | Select-Object Name, Platform
```

Debe aparecer **`ODBC Driver 18 for SQL Server`** con plataforma `64-bit`.

## 4. Instalar SQL Server Management Studio (SSMS)

```powershell
winget install Microsoft.SQLServerManagementStudio.22
```

Descarga manual: https://aka.ms/ssms/22/release/vs_SSMS.exe (o la página oficial: https://learn.microsoft.com/sql/ssms/download-sql-server-management-studio-ssms).

SSMS es el mejor apoyo para administración: planes de ejecución, seguridad, SQL Server Agent y exploración visual. VS Code será tu entorno de escritura diaria.

**Verificación 1.3:** abre SSMS y, en el cuadro *Connect to Server*, rellena:

- **Server name:** `localhost`
- **Authentication:** *Windows Authentication*
- **Encryption:** *Optional* (o *Mandatory* marcando **Trust server certificate**)

Pulsa **Connect**. Debes ver en el *Object Explorer* tu servidor con las carpetas *Databases*, *Security*, etc.

## 5. Instalar Git

```powershell
winget install Git.Git
```

Cierra y reabre la terminal, y configura tu identidad:

```powershell
git --version
git config --global user.name "Tu Nombre"
git config --global user.email "tu@correo.com"
git config --global init.defaultBranch main
```

## 6. Instalar Visual Studio Code y extensiones

```powershell
winget install Microsoft.VisualStudioCode
```

Descarga manual: https://code.visualstudio.com/

Cierra y reabre PowerShell, y luego instala las extensiones esenciales desde la terminal:

```powershell
code --install-extension ms-mssql.mssql
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension ms-toolsai.jupyter
code --install-extension eamodio.gitlens
code --install-extension mechatroner.rainbow-csv
```

| Extensión                   | Para qué sirve                                                            |
| ---------------------------- | -------------------------------------------------------------------------- |
| **SQL Server (mssql)** | Conectar a SQL Server, ejecutar consultas y explorar objetos desde VS Code |
| **Python + Pylance**   | Intérprete, autocompletado, selección de entorno virtual                 |
| **Jupyter**            | Notebooks para exploración de datos                                       |
| **GitLens**            | Historial y control de versiones mejorado                                  |
| **Rainbow CSV**        | Leer cómodamente CSV de origen (por ejemplo, los de SIPE)                 |

**Verificación 1.4:**

```powershell
code --list-extensions
```

Deben aparecer las seis extensiones. Después abre VS Code y comprueba que en la barra lateral izquierda existe el icono de **SQL Server**.

## 7. Crear la estructura de carpetas del proyecto

Una carpeta raíz con un repositorio Git, separando cada proyecto analítico:

```powershell
mkdir C:\Analytics
cd C:\Analytics
git init
mkdir sql, python, etl, docs
code .
```

Esta estructura la iremos llenando en las siguientes fases (`sql/` para scripts DDL, `python/` para el entorno y los scripts, `etl/` para los flujos de n8n).

---

## Checklist de salida de la Fase 1

Confírmame que has comprobado **todo** lo siguiente:

- [X] `Get-Service MSSQLSERVER` muestra **Running**.
- [X] `sqlcmd -S localhost -E -C -Q "SELECT @@VERSION"` devuelve la versión *Developer Edition*.
- [X] `Get-OdbcDriver` lista **ODBC Driver 18 for SQL Server**.
- [X] SSMS conecta a `localhost` y muestra el Object Explorer.
- [X] `git --version` responde y `code --list-extensions` muestra las extensiones.
- [X] Guardaste de forma segura la contraseña de `sa`.

**Aviso para más adelante:** Python se instalará en la Fase 3 y Docker Desktop (para n8n) en la Fase 4, así que no los instales ahora.

Cuando lo hayas completado, escríbeme "Fase 1 completada". Si algún paso falla, pégame el mensaje de error exacto y lo resolvemos antes de avanzar a la Fase 2.

Fase 1 completada. Se ve en tu salida:

- El reinicio funcionó (PowerShell ya era de administrador) y `IsIntegratedSecurityOnly` devuelve `0`, es decir, **Mixed Mode activo**.
- `sa` responde con la contraseña que definiste.

---

# FASE 2: Conexión y verificación del motor

**Objetivo:** confirmar que SQL Server acepta conexiones por TCP/IP en el puerto 1433, crear la primera base de datos desde VS Code, verla en SSMS y crear un login propio con permisos limitados.

## Por qué importa esta fase

- **Memoria compartida vs TCP/IP:** cuando ejecutas `sqlcmd -S localhost`, la conexión suele ir por *Shared Memory*, un canal interno solo local. **n8n, Python y Power BI conectan por TCP/IP.** Si TCP/IP estuviera deshabilitado, SSMS funcionaría pero las demás herramientas fallarían. Por eso lo verificamos explícitamente.
- **Puerto 1433:** es el puerto estándar de la instancia por defecto. Lo usaremos en todas las cadenas de conexión.
- **Windows vs SQL Authentication:** tú usarás autenticación de Windows en SSMS y VS Code. Las herramientas de ETL usarán un **login SQL dedicado** con permisos mínimos, para no exponer `sa` ni depender de la sesión de Windows.

## 2.1 Verificar TCP/IP y el puerto 1433

Fuerza una conexión TCP con el prefijo `tcp:` y el puerto tras una coma:

```powershell
sqlcmd -S "tcp:localhost,1433" -E -C -Q "SELECT net_transport, local_tcp_port, auth_scheme FROM sys.dm_exec_connections WHERE session_id = @@SPID"
```

**Resultado esperado:** `net_transport = TCP`, `local_tcp_port = 1433`, `auth_scheme = NTLM` o `KERBEROS` (ambos valen en local).

Comprueba también que el puerto está escuchando:

```powershell
Test-NetConnection localhost -Port 1433
```

Debe mostrar `TcpTestSucceeded : True`.

**Si falla**, habilita TCP/IP:

1. Abre **SQL Server Configuration Manager** (búscalo en el menú Inicio, o ejecuta `SQLServerManager17.msc` con `Win + R`).
2. *SQL Server Network Configuration* → *Protocols for MSSQLSERVER* → clic derecho en **TCP/IP** → **Enable**.
3. Doble clic en TCP/IP → pestaña **IP Addresses** → baja a **IPAll**: deja *TCP Dynamic Ports* **vacío** y *TCP Port* = `1433`.
4. Reinicia el servicio (PowerShell como administrador): `Restart-Service MSSQLSERVER -Force`.

No necesitas abrir el firewall de Windows: las conexiones son locales.

## 2.2 Conectar VS Code y crear la primera base de datos

1. Abre VS Code en tu carpeta de proyecto:

```powershell
cd C:\Analytics
code .
```

2. Haz clic en el icono de **SQL Server** de la barra lateral → **Add Connection**.
3. Rellena los parámetros (la interfaz puede variar ligeramente según la versión de la extensión):
   - **Server name:** `localhost`
   - **Database:** vacío (o `master`)
   - **Authentication type:** *Integrated* (autenticación de Windows)
   - **Profile name:** `Local - Windows`
   - **Encrypt:** *Optional*, o *Mandatory* con **Trust server certificate = Yes**. Es el mismo motivo del certificado autofirmado que vimos con el Driver 18.
4. Conecta. En el panel debes ver el servidor con sus bases de datos.
5. Crea el archivo `C:\Analytics\sql\00_crear_bd_prueba.sql` con este contenido:

```sql
-- Base de datos de prueba para validar el entorno
IF DB_ID('Test_Analytics') IS NULL
    CREATE DATABASE Test_Analytics;
GO

SELECT name, collation_name, state_desc
FROM sys.databases
WHERE name = 'Test_Analytics';
```

6. Con el archivo abierto, pulsa **Ctrl+Shift+E** (o clic derecho → *Execute Query*). Si te pregunta por la conexión, elige `Local - Windows`.

**Resultado esperado:** una fila con `Test_Analytics`, su *collation* (en tu equipo probablemente `Modern_Spanish_CI_AS`) y `state_desc = ONLINE`.

## 2.3 Verificar en SSMS

En SSMS, en el Explorador de objetos, clic derecho en **Bases de datos** → **Actualizar**. Debe aparecer `Test_Analytics`.

## 2.4 Crear un login dedicado con permisos limitados

En SSMS abre una **consulta nueva** y ejecuta lo siguiente. Elige una contraseña distinta a la de `sa` (12+ caracteres, **sin** `;`, `{`, `}` ni `=`) y guárdala en tu gestor de contraseñas. **No guardes este script en el repositorio**: déjalo como consulta sin guardar, para que la contraseña no acabe en Git.

```sql
USE master;
GO
CREATE LOGIN analytics_etl
    WITH PASSWORD = 'CambiaEstaContraseña_2026!',
         CHECK_POLICY = ON,
         DEFAULT_DATABASE = Test_Analytics;
GO

USE Test_Analytics;
GO
CREATE USER analytics_etl FOR LOGIN analytics_etl;
ALTER ROLE db_datareader ADD MEMBER analytics_etl;
ALTER ROLE db_datawriter ADD MEMBER analytics_etl;
ALTER ROLE db_ddladmin   ADD MEMBER analytics_etl;
GO
```

**Qué hace cada rol:**

- `db_datareader`: puede leer todas las tablas.
- `db_datawriter`: puede insertar, actualizar y borrar datos.
- `db_ddladmin`: puede crear y modificar tablas (necesario para cargas y para que Pandas cree tablas).

No tiene permisos de administración del servidor ni acceso a otras bases de datos. Cuando creemos SIPE o Gestion_Alquileres, daremos acceso a cada una por separado.

## 2.5 Probar el login SQL por TCP

```powershell
sqlcmd -S "tcp:localhost,1433" -U analytics_etl -d Test_Analytics -C -Q "SELECT SUSER_NAME() AS Login, DB_NAME() AS BaseDatos"
```

Te pedirá la contraseña. Debe devolver `analytics_etl` y `Test_Analytics`.

## 2.6 Prueba de ida y vuelta entre VS Code y SSMS

En VS Code, añade una **segunda conexión** con *Authentication type:* **SQL Login**, usuario `analytics_etl`, base de datos `Test_Analytics`, *Trust server certificate = Yes* y perfil `Local - analytics_etl`. Marca la opción de guardar la contraseña si te la ofrece. Luego crea `C:\Analytics\sql\01_tabla_ping.sql`:

```sql
CREATE TABLE dbo.ping (
    id      INT IDENTITY(1,1) PRIMARY KEY,
    mensaje NVARCHAR(100) NOT NULL,
    creado  DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

INSERT INTO dbo.ping (mensaje) VALUES (N'Hola desde VS Code');
GO

SELECT * FROM dbo.ping;
```

Ejecútalo con la conexión `Local - analytics_etl`. Después, en SSMS, ejecuta:

```sql
USE Test_Analytics;
SELECT * FROM dbo.ping;
```

**Resultado esperado:** ves la fila "Hola desde VS Code" en SSMS. Con esto queda probado que el login SQL puede crear y escribir, y que ambas herramientas ven los mismos datos.

## 2.7 Guardar en Git

```powershell
cd C:\Analytics
git add sql
git commit -m "Fase 2: scripts de BD de prueba"
```

Si Git pide configurar algo, o lista archivos que no esperabas, dímelo.

## Checklist de salida de la Fase 2

- [X] La consulta de `sys.dm_exec_connections` muestra `TCP` y puerto `1433`, y `Test-NetConnection` da `True`.
- [X] VS Code conecta con autenticación de Windows y creó `Test_Analytics`.
- [X] SSMS muestra `Test_Analytics`.
- [X] El login `analytics_etl` funciona por `sqlcmd` y su contraseña está guardada en tu gestor.
- [X] La fila de `dbo.ping` insertada desde VS Code se ve en SSMS.
- [X] Commit hecho en `C:\Analytics`.

---

# FASE 3: Entorno de analítica con Python

**Objetivo:** un entorno virtual aislado con las librerías clave y un script que escribe y lee en SQL Server usando el login `analytics_etl`, sin contraseñas en el código.

## Por qué importan estas decisiones

- **Python 3.12 y no el más reciente:** las librerías con código nativo (`pyodbc`, `polars`, `pyarrow`) tardan semanas o meses en publicar versiones compatibles con cada Python nuevo. 3.12 es estable y todas funcionan sin compilar nada.
- **Entorno virtual (`.venv`):** cada proyecto tiene sus propias versiones de librerías, y no ensucias el Python del sistema. Ya está en tu `.gitignore`, así que no se subirá a Git.
- **Pandas y Polars:** pandas es el estándar y lo usaremos para escribir con SQLAlchemy. Polars es más rápido con volúmenes grandes (útil para datos de SIPE). Instalamos ambos para que elijas según el caso.
- **SQLAlchemy sobre pyodbc:** `pyodbc` habla con el driver ODBC 18 que instalaste en la Fase 1, y SQLAlchemy lo envuelve en un "engine" que pandas y polars entienden.
- **`fast_executemany=True`:** sin esto, pyodbc inserta fila a fila y es muy lento. Con esto envía lotes. Es casi obligatorio con SQL Server.
- **`.env` para credenciales:** el código lee las credenciales de un archivo local que Git ignora. Así puedes publicar el repo sin filtrar contraseñas.

## 3.1 Instalar Python 3.12

En PowerShell:

```powershell
winget install Python.Python.3.12
```

**Cierra y vuelve a abrir** la terminal (o VS Code entero) para que se actualice el PATH. Verifica:

```powershell
py -3.12 --version
```

**Resultado esperado:** `Python 3.12.x`.

> `py` es el _Python Launcher_ de Windows y selecciona la versión exacta, así que no se confunde con el alias de la Store. Si más adelante `python` sin venv sigue sin responder, desactívalo en _Configuración → Aplicaciones → Configuración avanzada de aplicaciones → Alias de ejecución de aplicaciones_ (desmarca los de `python.exe` y `python3.exe`). Dentro del venv no hará falta.

## 3.2 Crear y activar el entorno virtual

Desde la raíz de tu repositorio (ajusta la ruta si renombraste la carpeta):

```powershell
cd "C:\Users\usuario\Documents\GitHub\End-to-End Local Analytics Platform SQL Server, Python, ETL & Dash"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

El prompt debe empezar con `(.venv)`. Si PowerShell bloquea el script con un error de _ejecución de scripts deshabilitada_, ejecuta una vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

y repite la activación.

**Selecciona el intérprete en VS Code:** `Ctrl+Shift+P` → **Python: Select Interpreter** → elige el que termina en `.venv\Scripts\python.exe`. A partir de ahí, cada terminal nueva de VS Code activará el venv sola.

**Verificación 3.2:**

```powershell
python -c "import sys; print(sys.executable)"
```

La ruta debe apuntar a `...\.venv\Scripts\python.exe`.

## 3.3 Instalar las librerías

```powershell
python -m pip install --upgrade pip
python -m pip install pandas polars pyarrow sqlalchemy pyodbc python-dotenv plotly ipykernel
python -m pip freeze > requirements.txt
```

Notas:

- `pyarrow` lo necesita polars para intercambiar datos con pandas.
- `ipykernel` permite usar notebooks de Jupyter con este venv.
- **Dash** lo instalaremos en la Fase 5. Streamlit lo dejamos fuera porque elegiste Dash; se puede añadir cuando quieras.
- `requirements.txt` fija las versiones, así que reconstruir el entorno en otro equipo será `pip install -r requirements.txt`.

**Verificación 3.3a: las librerías cargan**

```powershell
python -c "import pandas, polars, sqlalchemy, pyodbc, plotly, dotenv; print('pandas', pandas.__version__); print('polars', polars.__version__); print('sqlalchemy', sqlalchemy.__version__); print('pyodbc', pyodbc.version)"
```

**Verificación 3.3b: pyodbc ve el driver 18**

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

La lista debe incluir `'ODBC Driver 18 for SQL Server'`. Si no aparece, el driver de la Fase 1 no está registrado para 64 bits: avísame.

## 3.4 Configurar las credenciales

Crea el archivo **`.env.example`** en la raíz del repo (este **sí** se sube a Git, está permitido en tu `.gitignore` con `!.env.example`):

```ini
DB_HOST=localhost
DB_PORT=1433
DB_NAME=Test_Analytics
DB_USER=analytics_etl
DB_PASSWORD=pon_aqui_tu_contraseña
```

Cópialo a `.env` y edita la contraseña real del login `analytics_etl`:

```powershell
Copy-Item .env.example .env
code .env
```

Recuerda: la contraseña **no debe contener** `;`, `{`, `}` ni `=` (por eso lo indicamos en la Fase 2).

**Verificación 3.4: Git ignora `.env` pero no `.env.example`**

```powershell
git check-ignore -v .env
git check-ignore -v .env.example
```

El primero debe mostrar la regla de `.gitignore` que lo ignora. El segundo no debe mostrar nada.

## 3.5 Módulo de conexión reutilizable

Todos tus proyectos (SIPE, Gestion_Alquileres...) usarán la misma función y solo cambiará el nombre de la base de datos. Crea **`python/db.py`**:

```python
"""Conexión reutilizable a SQL Server (instancia local)."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL

# Carga el .env de la raíz del repositorio, se ejecute desde donde se ejecute
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


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
```

`URL.create` escapa la contraseña correctamente, así que nunca montamos la cadena de conexión a mano.

## 3.6 Script de prueba: escribir y leer

Crea **`python/03_test_ping.py`**:

```python
"""Prueba de la Fase 3: conexión, lectura y escritura en SQL Server."""
from datetime import datetime

import pandas as pd
import polars as pl
from sqlalchemy import text

from db import get_engine

engine = get_engine()

# 1) Conexión: ¿quién soy y dónde estoy?
with engine.connect() as conn:
    login, base, servidor = conn.execute(
        text("SELECT SUSER_NAME(), DB_NAME(), @@SERVERNAME")
    ).one()
print(f"[1] Conectado como '{login}' a la BD '{base}' en '{servidor}'")

# 2) Lectura con pandas
antes = pd.read_sql("SELECT * FROM dbo.ping ORDER BY id", engine)
print(f"[2] pandas leyó {len(antes)} fila(s) de dbo.ping")

# 3) Escritura con pandas en la tabla existente (id y creado los rellena SQL Server)
nueva = pd.DataFrame({"mensaje": [f"Hola desde Python {datetime.now():%H:%M:%S}"]})
nueva.to_sql("ping", engine, schema="dbo", if_exists="append", index=False)
despues = pd.read_sql("SELECT * FROM dbo.ping ORDER BY id", engine)
assert len(despues) == len(antes) + 1, "La fila no se insertó"
print(f"[3] Insertada 1 fila. Ahora hay {len(despues)}")

# 4) Crear una tabla nueva desde pandas (comprueba el permiso db_ddladmin)
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
```

Ejecútalo desde la raíz del repo con el venv activo:

```powershell
python python\03_test_ping.py
```

**Resultado esperado:** los seis mensajes `[1]` a `[6]`, terminando en `TODO OK`, y un cuadro de polars con tus filas de `dbo.ping`.

**Errores típicos:**

| Error                                     | Causa                              | Solución                                  |
| ----------------------------------------- | ---------------------------------- | ------------------------------------------ |
| `Login failed for user 'analytics_etl'` | Contraseña incorrecta en `.env` | Revisa `.env` (sin espacios ni comillas) |
| `certificate verify failed`             | Falta `TrustServerCertificate`   | Revisa `db.py`                           |
| `Data source name not found`            | Driver 18 no visible               | Repite la verificación 3.3b               |
| `CREATE TABLE permission denied`        | Falta el rol `db_ddladmin`       | Pégame el error y lo ajustamos            |
| `KeyError: 'DB_USER'`                   | `.env` no encontrado o vacío    | Debe estar en la raíz del repo            |

## 3.7 Verificar desde SSMS

En SSMS ejecuta:

```sql
USE Test_Analytics;
SELECT * FROM dbo.ping ORDER BY id;
```

Debes ver tu fila original "Hola desde VS Code" y una nueva "Hola desde Python hh:mm:ss". Con eso queda confirmado que Python escribe en la misma BD que ves desde SSMS.

## 3.8 Guardar en Git

```powershell
git add requirements.txt .env.example python
git status
```

**Antes de confirmar, mira `git status`:** `.env` y `.venv` **no** deben aparecer. Después:

```powershell
git commit -m "Fase 3: entorno Python, modulo de conexion y test ping"
```

Tu `git status` de la captura también muestra:

- `Plan General (checklist).md` modificado: puedes incluirlo en este commit si son tus avances del plan (`git add "Plan General (checklist).md"`).
- Un archivo o carpeta sin seguimiento llamado **`dsd`**: parece un residuo accidental. Revísalo y bórralo o añádelo a `.gitignore` según lo que sea.

Por último, tienes `01_Contraseñas.md` dentro del repo. Está bien que `.gitignore` lo excluya, pero contiene secretos en texto plano en disco. Cuando puedas, muévelo a un gestor de contraseñas y quédate solo con `.env`.

## Checklist de salida de la Fase 3

- [X] `py -3.12 --version` responde y el venv `.venv` se activa.
- [X] VS Code usa el intérprete del `.venv`.
- [X] `pyodbc.drivers()` incluye `ODBC Driver 18 for SQL Server`.
- [X] `git check-ignore` confirma que `.env` está ignorado y `.env.example` no.
- [X] `python python\03_test_ping.py` termina en `TODO OK`.
- [X] SSMS muestra la fila "Hola desde Python".
- [X] Commit hecho sin `.env` ni `.venv`.

Cuando lo hayas verificado, escríbeme **"Fase 3 completada"**. Si algo falla, pégame el mensaje de error exacto (sin la contraseña) y lo resolvemos antes de pasar a la Fase 4 (n8n).

---

# FASE 4: Herramientas de ingesta (ETL)

**Objetivo:** flujos de n8n que escriben en SQL Server con el login `analytics_etl`: primero una fila de prueba en `Test_Analytics.dbo.ping` y después la carga de cobros en `Gestion_Alquileres`. n8n es la única herramienta de ETL del proyecto.

## Por qué importan estas decisiones

- **n8n corre dentro de un contenedor.** Allí, `localhost` es el propio contenedor, no tu PC. Para llegar a tu SQL Server usaremos el nombre especial **`host.docker.internal`**, que apunta a Windows.
- **Autenticación SQL obligatoria para n8n.** El contenedor es Linux y no puede usar tu sesión de Windows. Por eso creamos `analytics_etl` en la Fase 2.
- **Firewall.** Hasta ahora todo era local y no hizo falta abrirlo. Una conexión desde Docker puede ser bloqueada por Windows. Lo probamos antes y solo creamos una regla si falla.
- **Credenciales fuera de los exports.** n8n guarda las credenciales cifradas en su volumen; los workflows exportados solo las referencian por nombre e id, así que se pueden versionar sin riesgo.

---

# n8n con Docker

## 4.1 Instalar Docker Desktop

Comprueba que la virtualización está activa: `Ctrl+Shift+Esc` → *Rendimiento* → *CPU* → **Virtualización: Habilitado**. Si no lo está, hay que activarla en la BIOS.

En PowerShell como administrador:

```powershell
winget install Docker.DockerDesktop
```

Reinicia el equipo si lo pide, abre **Docker Desktop**, acepta los términos (es gratuito para uso personal y pequeñas empresas; revisa su licencia si es tu caso) y espera a que indique *Engine running*.

**Verificación 4.1:**

```powershell
docker --version
docker compose version
docker run --rm hello-world
```

Debe aparecer el mensaje *Hello from Docker!*.

> Docker usa WSL2 y puede acaparar RAM. Si notas lentitud, crea `C:\Users\usuario\.wslconfig` con `[wsl2]` y `memory=4GB` en la línea siguiente, y ejecuta `wsl --shutdown`.

## 4.2 Crear el contenedor de n8n

Crea la carpeta `etl\n8n` en tu repo (ya existe `etl`) y dentro el archivo **`compose.yml`**:

```yaml
services:
  n8n:
    image: docker.n8n.io/n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    ports:
      - "127.0.0.1:5678:5678"
    environment:
      - GENERIC_TIMEZONE=Europe/Madrid
      - TZ=Europe/Madrid
    volumes:
      - n8n_data:/home/node/.n8n

volumes:
  n8n_data:
```

- `127.0.0.1:5678:5678`: solo accesible desde tu propio PC, no desde la red.
- `n8n_data`: volumen persistente con tus flujos y credenciales. Sin él, perderías todo al recrear el contenedor.

Arranca desde esa carpeta:

```powershell
cd etl\n8n
docker compose up -d
docker compose ps
docker logs n8n --tail 15
```

**Resultado esperado:** estado `running` y, en el log, un mensaje indicando que el editor es accesible en `http://localhost:5678`.

Cuando funcione, **fija la versión** para que no cambie sola: obtén la versión con `docker exec n8n n8n --version` y sustituye `:latest` por ese número en el compose.

## 4.3 Probar la ruta hacia SQL Server (antes de usar n8n)

```powershell
docker run --rm busybox sh -c "nc -w 3 host.docker.internal 1433 </dev/null && echo CONECTADO || echo FALLO"
```

- **`CONECTADO`**: sigue al 4.4.
- **`FALLO`**: casi seguro es el firewall. En PowerShell **como administrador**:

```powershell
New-NetFirewallRule -DisplayName "SQL Server 1433 - Docker local" -Direction Inbound -Protocol TCP -LocalPort 1433 -Action Allow -RemoteAddress 172.16.0.0/12 -Profile Any
```

Solo permite entradas desde el rango de redes internas de Docker/WSL, no desde Internet. Repite la prueba. Si sigue fallando, pégame el resultado.

## 4.4 Primer acceso y credencial

1. Abre `http://localhost:5678` y crea la cuenta de propietario (es local; guarda la contraseña en tu gestor).
2. **Credentials → Create credential → Microsoft SQL** y rellena:
   - **Server:** `host.docker.internal`
   - **Database:** `Test_Analytics`
   - **User:** `analytics_etl`
   - **Password:** la de ese login
   - **Port:** `1433`
   - Si da error de certificado, activa **Ignore SSL Issues** (equivale a `TrustServerCertificate`; el nombre exacto puede variar según versión).
3. Guarda. Debe mostrar *Connection tested successfully*.

## 4.5 Primer flujo

1. **Create workflow** → añade **Manual Trigger**.
2. Añade el nodo **Microsoft SQL** → operación **Execute Query**, con tu credencial:

```sql
INSERT INTO dbo.ping (mensaje) VALUES (N'Hola desde n8n');
```

3. Pulsa **Execute workflow**. El nodo debe quedar en verde.
4. Añade un segundo nodo Microsoft SQL con `SELECT TOP 5 * FROM dbo.ping ORDER BY id DESC;` y ejecútalo: verás tu fila nueva arriba.
5. Nombra el flujo `ping_n8n`.

**Verificación 4.5 en SSMS:** `SELECT * FROM Test_Analytics.dbo.ping ORDER BY id;` debe mostrar "Hola desde n8n".

---

## 4.6 Decisión de arquitectura: n8n es la única herramienta de ETL

Todas las cargas se hacen con n8n. La antigua parte B (Spoon / Pentaho Data Integration, con Java 21 y el driver JDBC de SQL Server) queda retirada: no hay que instalar Java, PDI ni JDBC, ni versionar transformaciones `.ktr`.

## 4.7 Guardar en Git

Exporta cada workflow desde n8n a `etl\n8n\workflows\` (los exports llevan el nombre y el id de la credencial, nunca su contraseña) y compruébalo antes de confirmar:

```powershell
Select-String -Path etl\n8n\workflows\*.json -Pattern "password"
git add etl
git status
```

La búsqueda no debe devolver nada. `.env`, `.venv` y el volumen `n8n_data` nunca se versionan.

## Errores típicos

| Síntoma                              | Causa probable                                      | Solución                                             |
| ------------------------------------- | --------------------------------------------------- | ----------------------------------------------------- |
| `docker` no se reconoce             | Terminal abierta antes de instalar                  | Reabre PowerShell                                     |
| Docker no arranca                     | Virtualización/WSL2 desactivados                   | Activar en BIOS; ejecutar `wsl --update`            |
| n8n: `ETIMEDOUT` o `ECONNREFUSED` | Firewall o host incorrecto                          | Repite 4.3; el host debe ser `host.docker.internal` |
| n8n: error de certificado             | Falta ignorar SSL                                   | Activar *Ignore SSL Issues*                         |
| n8n: `Login failed for user`        | Contraseña errónea                                | Revisa la credencial; sin `;{}=`                    |

## Checklist de salida de la Fase 4

- [X] `docker run --rm hello-world` funciona y `docker compose ps` muestra n8n en ejecución.
- [X] La prueba `busybox` devuelve `CONECTADO`.
- [X] El flujo `ping_n8n` inserta "Hola desde n8n".
- [X] Exports de n8n versionados sin contraseñas (commit local de la primera demo).

> **Verificado el 24-11-2026.** n8n `2.49.5` fijado en `etl/n8n/compose.yml`. Docker Desktop 4.96 no arrancaba (*WSL update required*); se resolvió con `wsl --update` como administrador (WSL 3.0.1). La credencial se carga con `etl/n8n/cargar_credencial.ps1` desde `.env` y el flujo se importa y ejecuta con `etl/n8n/probar_ping.ps1`. Fila comprobada con `sqlcmd` independiente: `id 3 | Hola desde n8n | 2026-11-24 18:30:25.0201146`. Spoon/PDI quedó retirado del proyecto (ver 4.6).

## 4.8 Primer flujo de negocio: CSV de cobros → n8n → `Gestion_Alquileres`

Detalle e instrucciones para repetirlo en `etl/n8n/README.md`.

- [X] Contraseña de `analytics_etl` rotada (la anterior figuraba en Git): la nueva funciona, la anterior es rechazada, `.env` actualizado, credenciales de n8n recargadas y `ping_n8n` sigue insertando en `Test_Analytics`.
- [X] `.env.example` solo contiene un marcador en `DB_PASSWORD`.
- [X] `sql/03_gestion_alquileres_cobros.sql` crea `Gestion_Alquileres`, `dbo.cobros` (`cobro_id` PK, `importe DECIMAL(12,2)`) y concede `SELECT, INSERT, UPDATE` a `analytics_etl`; ejecutado dos veces sin errores.
- [X] `etl/n8n/ejemplos/` montado en `/data/ejemplos` en solo lectura; los nodos de ficheros solo pueden leer ahí.
- [X] Credencial `SQL Server Gestion_Alquileres (analytics_etl)` creada; `ping_n8n` conserva la de `Test_Analytics`.
- [X] `importar_cobros` (disparador manual → leer CSV → validar → `MERGE` parametrizado → totales) exportado en `etl/n8n/workflows/importar_cobros.json` y reimportado sin errores.
- [X] Dos ejecuciones con el mismo CSV: 20 filas (20 IDs distintos) tras cada una; la segunda, 0 insertadas y 0 actualizadas. Totales por SQL independiente iguales al CSV: 2026-08 3446.50 · 2026-09 3326.65 · 2026-10 3361.55 · 2026-11 3398.40 · total 13533.10.
- [X] Corrección: `COB-2026-0012` de 720.50 a 745.50 → 1 actualizada, 0 insertadas, 20 filas, octubre 3386.55 y total 13558.10. CSV original restaurado (hash idéntico), recargado y `actualizado_en` devuelto a `NULL`; estado final igual al de la primera carga.
- [X] CSV inválido rechazado sin escrituras: `COB-2026-0001` corregido a 900.00 (fila válida al principio) y `COB-2026-0015` con importe `-95.30` (línea 16). El flujo se detiene en «Validar cobros» antes de tocar la base; por SQL, `COB-2026-0001` sigue en 850.00 sin `actualizado_en`, 20 cobros y 13533.10. CSV original restaurado y hash comprobado.
- [X] Commit local de la entrega (primera demo).

---

# FASE 5: Dash conectado a SQL Server (primera demo de extremo a extremo)

**Recorrido:** `etl/n8n/ejemplos/cobros.csv` → n8n `importar_cobros` → `Gestion_Alquileres.dbo.cobros` → `python/cobros.py` → `python/dashboard_cobros.py` en http://127.0.0.1:8050. Instrucciones en el `README.md` de la raíz.

## Checklist de la demo (verificado el 24-11-2026)

- [X] Entorno Python recuperado: el `.venv` anterior dependía del Python 3.12 incluido en otra aplicación (`MapasInteractivos`); se conservó como `.venv_old_py312` (ignorado) y se creó un `.venv` nuevo con Python 3.13.7. Mismas versiones fijadas más `dash==4.5.1`; `requirements.txt` pasa a UTF-8 y `pip check` no muestra problemas.
- [X] `python/cobros.py` reutiliza `get_engine(database="Gestion_Alquileres")`, agrupa por mes con número de cobros y devuelve los importes como `Decimal` (sin pasar por `float`).
- [X] El dashboard muestra total cobrado en euros, número de cobros, barras mensuales, tabla por mes y botón «Actualizar datos». Un fallo de consulta muestra un aviso breve; probado con un error simulado: ni la pantalla ni el log incluyen datos de conexión.
- [X] Navegador, estado inicial: 20 cobros y 13.533,10 €; barras 2026-08 3446.50 · 2026-09 3326.65 · 2026-10 3361.55 · 2026-11 3398.40.
- [X] Corrección de extremo a extremo: `COB-2026-0012` 720.50 → 745.50 en el CSV, `importar_cobros` (1 actualizada, 0 insertadas) y «Actualizar datos»: 20 cobros, octubre 3386.55, total 13.558,10 €.
- [X] Restauración: CSV original (hash idéntico), nueva carga, `actualizado_en` devuelto a `NULL` y «Actualizar datos»: 20 cobros y 13.533,10 €. SQL independiente (`sql/04_verificar_cobros.sql`) coincide.

## Cierre de la primera demo

- [X] README de la raíz revisado frente a los pasos reales: preparar SQL Server, levantar n8n, cargar credenciales, cargar el CSV, crear el entorno con Python 3.13 y arrancar Dash. Todos los archivos que usa están en el commit.
- [X] Contenido versionado revisado: sin la contraseña actual ni la anterior, sin `.env`, `.venv`, `.venv_old_py312`, `01_Contraseñas`, `Programas/` ni `__pycache__`; `.env.example` con marcador; exports de n8n sin datos fijados (`pinData` vacío) ni secretos.
- [X] `.claude/launch.json` incluido: usa rutas relativas al checkout (`.venv\Scripts\python.exe python\dashboard_cobros.py`, puerto 8050) y arranca el dashboard desde el panel de vista previa de Claude.
- [X] Base en el estado original al cerrar: 20 cobros, 13533.10, ninguna fila con `actualizado_en`.
- [X] Commit local de la primera demo.

## Reproducibilidad y publicación (24-11-2026)

- [X] Reproducida desde un checkout limpio en carpeta aparte, en el mismo equipo y con SQL Server ya instalado (instancia, login y `Test_Analytics` reutilizados; `sql/03` repetido). Desde cero: `.venv` con Python 3.13 y `pip check`, Compose validado, n8n aislado (proyecto, puerto y volumen propios) con credenciales e `importar_cobros`, y Dash en otro puerto con 20 cobros y 13.533,10 €.
- [X] README corregido: creación de `.env`, espera a que n8n termine sus migraciones antes de usar la CLI y aviso de no levantar Compose desde dos checkouts.
- [X] Dashboard estático (`python/generar_pagina.py`) desde el CSV ficticio versionado, con importes en `Decimal`: 20 cobros, 13.533,10 € y los cuatro meses verificados; cabe en 375 px sin desplazamiento horizontal. Build probado en un entorno limpio solo con `requirements-pages.txt`.
- [X] Workflow `.github/workflows/pages.yml` (push a `main` y ejecución manual) sin credenciales ni acceso a SQL Server.
- [X] Historial publicable nuevo sin el commit con la contraseña antigua; historial original conservado en una referencia local de respaldo.
- [X] Repositorio público, GitHub Pages con GitHub Actions y rama `main` local siguiendo a `origin/main`.

Siguiente: modelado completo de `Gestion_Alquileres` (fase 6).

Sources:

- [n8n 3.0 breaking changes](https://docs.n8n.io/changelog/v30-breaking-changes)
- [n8n one-line setup](https://docs.n8n.io/deploy/host-n8n/install-options/one-line-setup)
