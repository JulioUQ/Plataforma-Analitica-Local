# Plataforma local de analítica: CSV → n8n → SQL Server → Python → Dash

Demo reproducible en Windows: un CSV ficticio de cobros se carga con n8n en
`Gestion_Alquileres.dbo.cobros` (SQL Server local) y un dashboard Dash lo consulta
con Python. Todos los comandos se ejecutan en PowerShell desde la raíz del repo.

**Arquitectura:** una instancia de SQL Server con bases independientes por proyecto; **n8n es
la única herramienta de ETL** (no se usa Spoon/PDI ni Java); Python para acceso y análisis;
Dash para visualización.

**Dashboard público (datos ficticios):** https://juliouq.github.io/plataforma-analitica-local/
— versión estática generada desde `etl/n8n/ejemplos/cobros.csv` con GitHub Actions; ver
[Dashboard público en GitHub Pages](#dashboard-público-en-github-pages).

## Requisitos

- SQL Server Developer (`MSSQLSERVER`, TCP 1433, autenticación mixta), ODBC Driver 18 y `sqlcmd`,
  con tu cuenta de Windows como administradora.
- Docker Desktop con el motor en marcha (requiere WSL actualizado: `wsl --update` como administrador).
- Python 3.13 (`py -3.13 --version`).

## 0. Configuración local (`.env`)

```powershell
Copy-Item .env.example .env
notepad .env
```

Sustituye el marcador de `DB_PASSWORD` por la contraseña de `analytics_etl` (guárdala en tu
gestor de contraseñas; `.env` lo ignora Git). La contraseña no puede contener `;`, `{`, `}` ni `=`.

## 1. Preparar SQL Server

Solo en una instancia nueva, crea antes el login `analytics_etl` y la base de pruebas
(`sql/01` lleva un marcador `<CONTRASEÑA_EN_GESTOR>`: ejecútalo por bloques desde SSMS con la
contraseña real, sin guardarla en el archivo, y deja fuera el `ALTER LOGIN` final):

```powershell
sqlcmd -S "tcp:localhost,1433" -E -C -b -i sql\00_crear_bd_prueba.sql
# sql\01_crear_usuario_roles_prueba.sql desde SSMS, como se indica arriba
sqlcmd -S "tcp:localhost,1433" -E -C -b -i sql\02_tabla_ping_desdeVSC.sql   # solo para el workflow ping_n8n
```

Después, siempre:

```powershell
sqlcmd -S "tcp:localhost,1433" -E -C -b -i sql\03_gestion_alquileres_cobros.sql
```

Crea, si faltan, la base `Gestion_Alquileres`, la tabla `dbo.cobros` (`cobro_id` como clave,
`importe DECIMAL(12,2)`) y el usuario de `analytics_etl` con `SELECT, INSERT, UPDATE` sobre ella.
Se puede repetir.

## 2. Cargar el CSV con n8n

```powershell
docker compose -f etl\n8n\compose.yml up -d
do { Start-Sleep 3 } until ((docker logs n8n 2>&1) -match 'Editor is now accessible')
.\etl\n8n\cargar_credencial.ps1
.\etl\n8n\cargar_cobros.ps1
sqlcmd -S "tcp:localhost,1433" -E -C -W -i sql\04_verificar_cobros.sql
```

La espera es necesaria al arrancar con un volumen nuevo: n8n responde en `/healthz` antes de
terminar las migraciones de su base interna, y un comando de la CLI lanzado en ese momento falla
con `SQLITE_ERROR ... already exists`. Los scripts usan el contenedor `n8n` y el proyecto de
Compose toma el nombre de la carpeta (`n8n`): levanta n8n desde un solo checkout a la vez.
`cargar_credencial.ps1` crea las credenciales de n8n desde `.env` (repetir tras rotar la
contraseña). `cargar_cobros.ps1` importa y ejecuta `importar_cobros` sobre
`etl/n8n/ejemplos/cobros.csv` y muestra los totales. Repetir la carga no duplica filas; un
importe corregido para un `cobro_id` existente actualiza esa fila. Detalle en `etl/n8n/README.md`.

## 3. Iniciar Dash

Primera vez (o tras clonar):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Arranque:

```powershell
.\.venv\Scripts\python.exe python\dashboard_cobros.py
```

Abrir **http://127.0.0.1:8050**. Muestra el total cobrado, el número de cobros, un gráfico de
barras mensual y una tabla por mes. «Actualizar datos» vuelve a consultar SQL Server. La app
lee la conexión de `.env` mediante `python/db.py` y, si la consulta falla, muestra un aviso
breve sin datos de conexión.

## Valores esperados con el CSV de ejemplo

| Mes | Cobros | Total |
| --- | ---: | ---: |
| 2026-08 | 5 | 3.446,50 € |
| 2026-09 | 5 | 3.326,65 € |
| 2026-10 | 5 | 3.361,55 € |
| 2026-11 | 5 | 3.398,40 € |
| **Total** | **20** | **13.533,10 €** |

Prueba de extremo a extremo: cambiar `COB-2026-0012` de `720.50` a `745.50` en el CSV,
ejecutar `.\etl\n8n\cargar_cobros.ps1` y pulsar «Actualizar datos»: siguen 20 cobros,
octubre pasa a 3.386,55 € y el total a 13.558,10 €. Restaurar `720.50` y volver a cargar.

**Reproducibilidad comprobada** (24-11-2026) desde un checkout limpio en una carpeta aparte, en
el mismo equipo y **con SQL Server ya instalado**: se reutilizaron la instancia, el login
`analytics_etl` y `Test_Analytics` (los pasos `sql/00`–`02` no se ejecutaron desde cero) y se
repitió `sql/03`. Desde cero se hicieron el `.venv` con Python 3.13 y `pip check`, la validación de
Compose, una instancia de n8n aislada (proyecto, puerto y volumen propios) con carga de
credenciales e importación y ejecución de `importar_cobros`, y Dash en otro puerto con
20 cobros y 13.533,10 €. La instalación en otro ordenador no se ha probado.

## Dashboard público en GitHub Pages

https://juliouq.github.io/plataforma-analitica-local/ muestra el total cobrado, el número de
cobros, un gráfico mensual interactivo (Plotly) y el detalle por mes. Es una **página estática con
datos ficticios**: se genera solo a partir del CSV versionado `etl/n8n/ejemplos/cobros.csv`, sin
SQL Server ni credenciales, y no sustituye al Dash local (que consulta la base en vivo).

- El workflow `.github/workflows/pages.yml` la regenera y publica con cada push a `main` y
  también a mano (*Actions → Publicar dashboard en GitHub Pages → Run workflow*).
- Para actualizarla tras cambiar el CSV: `git add etl/n8n/ejemplos/cobros.csv`, `git commit`,
  `git push`; en uno o dos minutos la página muestra los nuevos totales y la hora de generación.
  El build falla, y la página anterior se mantiene, si el CSV no supera la validación.
- Vista previa local (escribe en `_site/`, ignorada por Git):

  ```powershell
  .\.venv\Scripts\python.exe python\generar_pagina.py
  .\.venv\Scripts\python.exe -m http.server 8090 -d _site
  ```

  y abrir http://127.0.0.1:8090.

## Estructura

| Ruta | Contenido |
| --- | --- |
| `sql/` | Scripts de Test_Analytics (00–02), Gestion_Alquileres (03) y verificación (04) |
| `etl/n8n/` | Compose, workflows exportados, CSV de ejemplo y scripts de carga |
| `python/db.py` | Engine SQLAlchemy reutilizable que lee `.env` |
| `python/cobros.py` | Consulta de cobros por mes (importes como `Decimal`) |
| `python/dashboard_cobros.py` | Dashboard Dash |
| `python/generar_pagina.py` | Genera el dashboard estático de GitHub Pages desde el CSV |
| `requirements-pages.txt` | Dependencias mínimas del build de Pages |
| `.github/workflows/pages.yml` | Build y despliegue en GitHub Pages |
| `Plan General (checklist).md` | Guía por fases y comprobaciones realizadas |

`.claude/launch.json` permite arrancar el mismo dashboard desde el panel de vista previa de Claude.

Siguiente: modelado completo de Gestion_Alquileres (fase 6).
