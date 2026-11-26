# Plataforma local de analítica

Trabaja desde la raíz del repositorio en Windows con PowerShell y usa rutas relativas al checkout. Algunas rutas absolutas del checklist corresponden a una ubicación anterior.

## Arquitectura

- Una instancia de SQL Server (`MSSQLSERVER`, TCP 1433) con bases independientes por proyecto: `Test_Analytics` (pruebas) y `Gestion_Alquileres`.
- **n8n es la única herramienta de ETL** (Docker, `etl/n8n/compose.yml`, versión fijada). Spoon/PDI y Java están retirados: no los propongas ni los instales.
- Python 3.13 en `.venv` (`requirements.txt`), con `python/db.py` como única forma de conectar.
- MVP real: Excel de Airbnb y Booking en `data/` (ignorada por Git, montada en n8n en solo lectura) → workflow `importar_alquileres` (`impAlquileresMVP`, manual y diario 09:00, activo) → esquema `Gestion_Alquileres.alq` (`sql/05_alquileres_mvp.sql`).
- Dash local: alquileres reales en `python/dashboard_alquileres.py` (http://127.0.0.1:8060) y demo ficticia en `python/dashboard_cobros.py` (http://127.0.0.1:8050).
- Dashboard público estático en GitHub Pages (https://juliouq.github.io/Plataforma-Analitica-Local/), generado por `.github/workflows/pages.yml` con `python/generar_pagina.py` **solo** desde `publicacion/agregados_alquileres.json` (agregados mensuales exportados con `python/exportar_agregados.py`). Nunca publiques Excel, filas individuales, datos de huéspedes, referencias de reserva ni credenciales, ni des acceso a SQL Server al build.

## Repositorio

- Público en GitHub (`JulioUQ/Plataforma-Analitica-Local`); `main` sigue a `origin/main`. Trabaja con `git pull` y `git push origin main`; no uses `push --all`, `--mirror`, `--force` ni subas etiquetas.
- El historial publicado empieza en un commit nuevo sin la contraseña antigua. El historial anterior queda solo en local en `refs/respaldo/main-original`: no lo subas ni lo fusiones con `main`.
- Los commits de este repo usan el correo `noreply` de GitHub (configuración local del repo).
- `INFORME_TRASPASO.md` es un informe histórico local: no lo versiones.

## Estado

La primera demo CSV → n8n → SQL Server → Python → Dash está cerrada, verificada y publicada: carga idempotente por `cobro_id`, corrección de importes, rechazo de CSV inválido sin escrituras, actualización en el navegador y reproducción desde un checkout limpio en este equipo (con SQL Server ya instalado). Los pasos están en `README.md`; lo comprobado, en `Plan General (checklist).md`.

El MVP con datos reales (fase 6) está en `README.md` (secciones 3–5) y en la fase 6 del checklist.

## Reglas de trabajo

- Credenciales solo en `.env` (ignorado) y en el volumen `n8n_data`. No muestres valores de contraseña en comandos, logs ni respuestas; `.env.example` lleva un marcador. Tras rotar la contraseña de `analytics_etl`, ejecuta `.\etl\n8n\cargar_credencial.ps1`.
- No leas ni imprimas `.env` ni `01_Contraseñas`.
- Conserva el volumen `n8n_data` y el historial de Git. Exporta los workflows a `etl/n8n/workflows/` y comprueba que no llevan secretos antes de versionarlos.
- Si una prueba modifica `etl/n8n/ejemplos/cobros.csv`, restáuralo y comprueba su hash; deja `Gestion_Alquileres.dbo.cobros` con 20 cobros y 13533.10 (`sql/04_verificar_cobros.sql`).
- `sql/03_gestion_alquileres_cobros.sql` es repetible; los scripts `00`–`02` de `Test_Analytics` presuponen que los objetos faltan: no los relances sobre una instalación existente.
- `python/03_test_ping.py` reemplaza y elimina `dbo.ping_pandas`: confirma la base de destino antes de ejecutarlo.
- Datos reales: no imprimas filas de los Excel ni la salida completa de `n8n execute` (incluye nombres); usa `.\etl\n8n\importar_alquileres.ps1`, que solo muestra el resumen. Pruebas con archivos inválidos: copia temporal en `data/` y bórrala al terminar; no modifiques los originales.
- `importar_alquileres.ps1 -Importar` deja el workflow desactivado: vuelve a publicarlo (`publish:workflow` + `docker restart n8n`) para mantener la programación diaria.
