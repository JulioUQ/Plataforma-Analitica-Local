# n8n local

n8n `2.49.5` en Docker (`compose.yml`): interfaz en `127.0.0.1:5678`, volumen `n8n_data`,
zona `Europe/Madrid` y `ejemplos/` montado en `/data/ejemplos` en solo lectura (único
directorio que pueden leer los nodos de ficheros).

| Workflow | Origen | Destino |
| --- | --- | --- |
| `ping_n8n` | — | `Test_Analytics.dbo.ping` (inserta «Hola desde n8n») |
| `importar_cobros` | `ejemplos/cobros.csv` | `Gestion_Alquileres.dbo.cobros` (upsert por `cobro_id`) |

## Repetir la carga de cobros (desde la raíz del repo)

```powershell
sqlcmd -S "tcp:localhost,1433" -E -C -b -i sql\03_gestion_alquileres_cobros.sql   # base, tabla y permisos (repetible)
docker compose -f etl\n8n\compose.yml up -d
do { Start-Sleep 3 } until ((docker logs n8n 2>&1) -match 'Editor is now accessible')   # migraciones terminadas
.\etl\n8n\cargar_credencial.ps1      # credenciales SQL desde .env (repetir tras rotar la contraseña)
.\etl\n8n\cargar_cobros.ps1          # importa el workflow, lo ejecuta y muestra totales
sqlcmd -S "tcp:localhost,1433" -E -C -W -i sql\04_verificar_cobros.sql             # comprobación independiente
```

`importar_cobros` lee el CSV, valida todo el fichero (columnas exactas, `cobro_id` único,
fecha ISO `AAAA-MM-DD`, importe positivo con punto decimal y hasta 2 decimales) y, si no
hay errores, hace un único `MERGE` transaccional. El lote viaja como parámetro (`@p1`) y se
desempaqueta con `OPENJSON`; los valores del CSV nunca se concatenan en el SQL. Repetir la
carga con el mismo CSV no inserta ni actualiza nada; un importe corregido para un
`cobro_id` existente actualiza esa fila y fija `actualizado_en`.

## Totales esperados de `ejemplos/cobros.csv`

20 cobros ficticios de cuatro inmuebles.

| Mes | Cobros | Total |
| --- | ---: | ---: |
| 2026-08 | 5 | 3446.50 |
| 2026-09 | 5 | 3326.65 |
| 2026-10 | 5 | 3361.55 |
| 2026-11 | 5 | 3398.40 |
| **Total** | **20** | **13533.10** |
