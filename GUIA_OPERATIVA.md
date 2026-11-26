# Guía operativa

Plataforma local en Windows para los alquileres de Airbnb y Booking: **n8n** importa los Excel
exportados de cada plataforma a **SQL Server**, **Python** los consulta, un **Dash** local los
muestra en vivo y **GitHub Pages** publica la última exportación de los agregados mensuales.
Todos los comandos se ejecutan en PowerShell desde la raíz del repo.

| Vista | Dirección | Datos |
| --- | --- | --- |
| Dashboard público (GitHub Pages) | https://juliouq.github.io/plataforma-analitica-local/ | Agregados mensuales reales de la última exportación publicada |
| Dash de alquileres (local) | http://127.0.0.1:8060 | SQL Server en vivo (`Gestion_Alquileres.alq`) |
| Dash de la demo ficticia (local) | http://127.0.0.1:8050 | `dbo.cobros`, cargada desde un CSV inventado |
| Editor de n8n (local) | http://localhost:5678 | Workflows `importar_alquileres`, `importar_cobros`, `ping_n8n` |

**Arquitectura:** una instancia de SQL Server con bases independientes por proyecto; **n8n es la
única herramienta de ETL**; Python (`python/db.py`) para el acceso a datos; Dash para la
visualización local. Los Excel, las filas individuales, los datos de huéspedes, las referencias
de reserva y las credenciales **solo existen en este equipo**; al repositorio y a Pages solo llegan
totales mensuales por plataforma.

## Las dos rutinas

1. **Importación programada (n8n → SQL Server).** Cada día a las **09:00 (Europe/Madrid)** n8n
   lee todos los `.xlsx` de `data/`, los valida y carga en SQL Server lo que haya cambiado. También
   puedes lanzarla cuando quieras: `.\etl\n8n\importar_alquileres.ps1`.
2. **Actualizar la vista pública (tú, a mano).** Cuando quieras publicar los datos nuevos:

   ```powershell
   .\.venv\Scripts\python.exe python\exportar_agregados.py
   git add publicacion/agregados_alquileres.json
   git commit -m "Actualiza los agregados publicados"
   git push
   ```

   GitHub Actions reconstruye Pages solo con ese archivo (uno o dos minutos).

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

Después, siempre (los dos se pueden repetir):

```powershell
sqlcmd -S "tcp:localhost,1433" -E -C -b -i sql\03_gestion_alquileres_cobros.sql   # base y demo dbo.cobros
sqlcmd -S "tcp:localhost,1433" -E -C -b -i sql\05_alquileres_mvp.sql              # MVP real: esquema alq
```

`sql/05` crea en `Gestion_Alquileres` el esquema `alq` (separado de `dbo.cobros`): tablas
`reservas`, `pagos`, `fuentes`, `ejecuciones` y `ejecuciones_fuentes`, la vista
`v_agregados_mensuales` y los procedimientos `registrar_fuente` y `cerrar_ejecucion`. El login
`analytics_etl` **solo puede ejecutar esos dos procedimientos y leer la vista y el registro**: no
puede leer ni modificar las tablas directamente.

## 2. Levantar n8n y cargar credenciales

```powershell
docker compose -f etl\n8n\compose.yml up -d
do { Start-Sleep 3 } until ((docker logs n8n 2>&1) -match 'Editor is now accessible')
.\etl\n8n\cargar_credencial.ps1
```

La espera es necesaria al arrancar con un volumen nuevo: n8n responde en `/healthz` antes de
terminar las migraciones de su base interna, y un comando de la CLI lanzado en ese momento falla
con `SQLITE_ERROR ... already exists`. Los scripts usan el contenedor `n8n` y el proyecto de
Compose toma el nombre de la carpeta (`n8n`): levanta n8n desde un solo checkout a la vez.
`cargar_credencial.ps1` crea las credenciales de n8n desde `.env` (repetir tras rotar la
contraseña).

Compose monta en solo lectura `etl/n8n/ejemplos/` (CSV ficticio) en `/data/ejemplos` y la carpeta
`data/` del repo en `/data/alquileres`; los nodos de ficheros de n8n no pueden leer nada más.

## 3. Importar los Excel de Airbnb y Booking (workflow `importar_alquileres`)

### Dónde dejar los archivos y cómo añadir los próximos

Deja los `.xlsx` **en cualquier subcarpeta de `data/`** (por ejemplo
`data/Resumen de ActividadAlquileres-2026/Airbnb/`). El workflow busca `/data/alquileres/**/*.xlsx`
y reconoce la plataforma por los encabezados, no por el nombre del archivo. Para incorporar un
archivo nuevo basta con copiarlo ahí: lo cargará la siguiente ejecución programada o
`.\etl\n8n\importar_alquileres.ps1`.

- Formatos admitidos: export **Pagos** de Airbnb (columnas `Fecha`, `Tipo`, `Código de
  confirmación`, `Ingresos brutos`, `Cobrado`…) y export **Reservas** de Booking (`Reservation
  number`, `Arrival`, `Final amount`, `Commission amount`, `Payment fee`, `Status`…). Otro formato
  se rechaza con un motivo claro.
- Un archivo con el mismo contenido (SHA-256) que otro ya cargado se **omite** (`sin_cambios`).
- Si dos archivos contienen la misma reserva (exports que se solapan), no se duplica: la clave es
  el código de reserva/pago y la versión más reciente la actualiza.
- Los archivos `~$…xlsx` (Excel abierto) se ignoran. No hace falta mover ni renombrar los originales;
  n8n nunca los modifica.

### Qué hace el workflow

```
Ejecutar manualmente ─┐
                      ├─► Buscar Excel ─► Huella SHA-256 ─► Preparar fuentes ─► Recorrer fuentes (1 archivo por vuelta)
Programación 09:00 ───┘                                                          │  ├─► Extraer filas ─► Validar y normalizar
                                                                                 │  │      ─► Registrar fuente (SQL) ─┐
                                                                                 │  └──────────────◄─────────────────┘
                                                                                 └─► Cerrar ejecución (SQL) ─► Resumen
```

1. **Validar y normalizar** (n8n, sin escribir nada): encabezados, divisa EUR, fechas, importes con
   punto decimal, noches = salida − llegada, neto = bruto − comisiones, códigos únicos y, en Airbnb,
   que cada pago cuadre con la suma de sus reservas. Con un solo error el archivo se rechaza entero.
2. **Registrar fuente** llama a `alq.registrar_fuente` con el lote como parámetro JSON. SQL Server
   vuelve a validar y carga el archivo en **una transacción** (`MERGE` por clave): o entra todo o
   nada. Un bloqueo de aplicación (`sp_getapplock`) impide que dos ejecuciones simultáneas carguen
   a la vez; la segunda ve el archivo ya registrado y lo omite.
3. **Resumen** termina con un mensaje claro: *Carga correcta*, *Sin cambios* (no escribe nada) o
   *Importación con errores* (la ejecución queda en rojo en n8n).

Cada ejecución queda registrada, sin datos personales, en `alq.ejecuciones` (modo, estado,
archivos cargados/omitidos/rechazados y filas aceptadas/excluidas/rechazadas) y
`alq.ejecuciones_fuentes` (una fila por archivo con su motivo).

### Importar a mano

```powershell
.\etl\n8n\importar_alquileres.ps1
```

Muestra solo el resumen (rutas, recuentos, motivos). `-Importar` vuelve a cargar el workflow desde
`etl/n8n/workflows/importar_alquileres.json` (lo deja desactivado: ver «Activar o pausar»).

### Programación en n8n: guía rápida

- **Abrir el workflow.** Entra en http://localhost:5678. La primera vez n8n pide crear la cuenta de
  propietario (es local; guarda la contraseña en tu gestor). Abre **importar_alquileres**.
- **Cambiar el horario.** Doble clic en el nodo **Programación diaria 09:00** → *Trigger
  Interval* `Days`, *Days Between Triggers* `1`, *Trigger at Hour* `9am`, *Trigger at Minute* `0`.
  Cambia lo que quieras, cierra el nodo, **Save** y **Publish** para que la versión activa use el
  nuevo horario. La zona horaria está en *Workflow settings → Timezone* (`Europe/Madrid`).
- **Activar o pausar.** En el editor, **Publish** activa el workflow y **Unpublish** lo pausa (la
  ejecución manual sigue disponible). Desde PowerShell:

  ```powershell
  docker exec n8n n8n publish:workflow --id=impAlquileresMVP ; docker restart n8n     # activar
  docker exec n8n n8n unpublish:workflow --id=impAlquileresMVP ; docker restart n8n   # pausar
  ```

- **Ver una ejecución.** Pestaña **Executions** del workflow (o *Overview → Executions*): cada
  ejecución muestra su estado, su hora y si la lanzó el horario (modo `trigger`) o una persona.
  Abre una para ver la salida de cada nodo; el nodo **Resumen** tiene el balance. Desde SQL, la
  columna `modo` distingue `programada`, `manual_editor` y `manual_cli`:

  ```sql
  SELECT TOP 10 * FROM Gestion_Alquileres.alq.ejecuciones ORDER BY inicio DESC;
  SELECT TOP 20 ejecucion_n8n, ruta, estado, filas_aceptadas, filas_rechazadas, motivo
  FROM Gestion_Alquileres.alq.ejecuciones_fuentes ORDER BY id DESC;
  ```

- **Recuperar una carga fallida.** Una ejecución con errores **no deja cargas parciales**: el
  archivo rechazado no ha escrito nada y los demás archivos se procesan igualmente. Lee el motivo
  (línea y columna) en el nodo **Resumen** o en `alq.ejecuciones_fuentes`, corrige o vuelve a
  exportar el Excel en `data/` y lanza `.\etl\n8n\importar_alquileres.ps1` (o *Execute workflow*
  en el editor). Si el fallo fue de conexión (SQL Server parado), basta con relanzar: la carga es
  idempotente y lo ya cargado se omite.

**Importante:** la ejecución programada solo ocurre si a las 09:00 están en marcha **Docker Desktop
con el contenedor `n8n`** y **SQL Server**. Si el ordenador está apagado o suspendido, esa ejecución
se pierde: n8n no la recupera al encenderlo. Lánzala a mano o espera a la del día siguiente. En este
MVP la programación procesa los Excel que tú dejes en `data/`; no descarga nada de Airbnb ni de Booking.
Para que el contenedor arranque solo, activa *Docker Desktop → Settings → General → Start Docker
Desktop when you sign in* (el contenedor tiene `restart: unless-stopped`).

### Qué mide cada indicador

| Indicador | Airbnb (export Pagos) | Booking (export Reservas) | Mes |
| --- | --- | --- | --- |
| Reservas / Noches | filas `Reserva` / `Noches` | filas con `Status` OK / `Room nights` | llegada |
| Importe bruto de reservas | `Ingresos brutos` | `Final amount` | llegada |
| Comisiones de la plataforma | `Comisión de servicio` | `Commission amount` | llegada |
| Gastos de pago | `Comisión por Pago rápido` | `Payment fee` | llegada |
| Neto de reservas | `Importe` (= bruto − comisiones) | bruto − comisión − gastos (calculado) | llegada |
| Cobrado (pagos liquidados) | filas `Payout`, columna `Cobrado` | no disponible en este export | fecha del pago |

El **neto** y el **cobrado** describen la misma actividad desde dos momentos distintos (estancia y
liquidación): no se suman entre sí. Las reservas de Booking canceladas o no presentadas se
cuentan como **excluidas** y no suman en ningún importe. Solo se admite EUR.

## 4. Dash local

Primera vez (o tras clonar):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Alquileres reales (**http://127.0.0.1:8060**):

```powershell
.\.venv\Scripts\python.exe python\dashboard_alquileres.py
```

Filtros por plataforma y por periodo (desde/hasta), indicadores etiquetados, gráfico mensual del
neto por plataforma, tabla de agregados y «Actualizar datos», que vuelve a consultar SQL Server.
`python/alquileres.py` es la consulta compartida con la exportación pública: importes como
`Decimal`, redondeados a céntimos solo al mostrarlos. Si la consulta falla, la app muestra un aviso
breve sin datos de conexión.

Demo ficticia (**http://127.0.0.1:8050**): `.\.venv\Scripts\python.exe python\dashboard_cobros.py`.

## 5. Dashboard público en GitHub Pages

https://juliouq.github.io/plataforma-analitica-local/ muestra los **indicadores reales agregados
por mes** de la última exportación publicada: periodo cubierto, fecha de exportación, indicadores
con filtro por plataforma, gráfico mensual interactivo (Plotly) y tabla. Funciona en móvil y en
escritorio.

- `python/exportar_agregados.py` consulta SQL Server en local y escribe
  `publicacion/agregados_alquileres.json` (solo totales por plataforma y mes).
- `.github/workflows/pages.yml` construye la página **solo con ese archivo**
  (`python/generar_pagina.py`), sin Excel, credenciales ni acceso a este equipo, con cada push a
  `main` y también a mano (*Actions → Publicar dashboard en GitHub Pages → Run workflow*).
- Vista previa local (escribe en `_site/`, ignorada por Git):

  ```powershell
  .\.venv\Scripts\python.exe python\generar_pagina.py
  .\.venv\Scripts\python.exe -m http.server 8090 -d _site
  ```

## Limitaciones observadas en los Excel

- **Fechas de Airbnb:** el export usa `MM/DD/AAAA` en texto. Cuando día y mes son ≤ 12, Excel las
  convirtió en fechas **con día y mes intercambiados** (p. ej. 1-nov aparece como 11-ene). El
  workflow deshace el intercambio y lo valida con las noches y con el cuadre de cada pago; si
  Airbnb cambia el formato, el archivo se rechaza en lugar de cargar fechas erróneas.
- **Airbnb es un informe de pagos:** solo incluye reservas ya liquidadas (octubre–diciembre de
  2025 en este archivo); las reservas futuras o pendientes no aparecen hasta que se pagan. Los
  importes llegan como texto y `Comisión por Pago rápido`, `Gastos de limpieza` e impuestos están
  vacíos o a cero.
- **Booking es un informe de reservas:** no trae pagos liquidados, así que su neto es un cálculo
  (bruto − comisión − gastos de pago). Alguna comisión tiene tres decimales (p. ej. 49,875 €): se
  guarda exacta (`DECIMAL(14,3)`) y se redondea a céntimos solo al mostrarla.
- Los archivos actuales no contienen cancelaciones, ajustes ni otras divisas: la regla de
  exclusión de cancelaciones de Booking está implementada pero no se ha probado con datos reales;
  los tipos de fila de Airbnb distintos de `Payout`/`Reserva` se rechazan.
- La carga es por clave y **nunca borra**: si una reserva desaparece de un export posterior, sigue
  en SQL Server (las cancelaciones de Booking sí se reflejan al cambiar su `Status`).
- Los códigos de reserva y de pago se guardan como SHA-256 sin sal. El historial de ejecuciones de
  n8n guarda las filas leídas (incluidos datos de huéspedes) en su volumen local durante 14 días.

## Demo ficticia (ejemplo de aprendizaje)

El workflow `importar_cobros` carga `etl/n8n/ejemplos/cobros.csv` en `dbo.cobros` y
`dashboard_cobros.py` lo muestra (http://127.0.0.1:8050). Se conserva como ejemplo:

```powershell
.\etl\n8n\cargar_cobros.ps1
sqlcmd -S "tcp:localhost,1433" -E -C -W -i sql\04_verificar_cobros.sql
```

Valores esperados: 2026-08 3.446,50 € · 2026-09 3.326,65 € · 2026-10 3.361,55 € ·
2026-11 3.398,40 € · total **20 cobros y 13.533,10 €**. Repetir la carga no duplica filas y un
importe corregido para un `cobro_id` existente actualiza esa fila.

**Reproducibilidad comprobada** (24-11-2026) desde un checkout limpio en una carpeta aparte, en
el mismo equipo y **con SQL Server ya instalado**: se reutilizaron la instancia, el login
`analytics_etl` y `Test_Analytics` (los pasos `sql/00`–`02` no se ejecutaron desde cero) y se
repitió `sql/03`. Desde cero se hicieron el `.venv` con Python 3.13 y `pip check`, la validación de
Compose, una instancia de n8n aislada (proyecto, puerto y volumen propios) y Dash en otro puerto.
La instalación en otro ordenador no se ha probado.

## Estructura

| Ruta | Contenido |
| --- | --- |
| `sql/` | Test_Analytics (00–02), demo `dbo.cobros` (03), verificación de la demo (04) y MVP `alq` (05) |
| `etl/n8n/compose.yml` | n8n 2.49.5 con los montajes de solo lectura |
| `etl/n8n/workflows/` | Workflows exportados sin secretos: `importar_alquileres`, `importar_cobros`, `ping_n8n` |
| `etl/n8n/*.ps1` | Credenciales y ejecución manual de los workflows |
| `python/db.py` | Engine SQLAlchemy reutilizable que lee `.env` |
| `python/alquileres.py` | Consulta compartida de agregados mensuales (Dash y exportación) |
| `python/dashboard_alquileres.py` | Dash de alquileres reales (puerto 8060) |
| `python/exportar_agregados.py` | Exporta los agregados a `publicacion/agregados_alquileres.json` |
| `python/generar_pagina.py` | Genera el dashboard de GitHub Pages desde ese JSON |
| `python/cobros.py`, `python/dashboard_cobros.py` | Demo ficticia (puerto 8050) |
| `publicacion/agregados_alquileres.json` | Único dato real versionado: totales mensuales por plataforma |
| `.github/workflows/pages.yml` | Build y despliegue en GitHub Pages |
| `Plan General (checklist).md` | Guía por fases y comprobaciones realizadas |

`.claude/launch.json` permite arrancar los dos Dash desde el panel de vista previa de Claude.
`data/` (Excel reales) está ignorada por Git.
