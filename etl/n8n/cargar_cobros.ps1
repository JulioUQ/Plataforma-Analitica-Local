# Importa (o actualiza) el workflow importar_cobros en n8n y lo ejecuta una vez
# sobre etl/n8n/ejemplos/cobros.csv (montado en /data/ejemplos, solo lectura).
# Uso (desde la raiz del repo, con n8n en marcha y las credenciales cargadas):
#   .\etl\n8n\cargar_cobros.ps1
$ErrorActionPreference = 'Stop'
$wf = Join-Path $PSScriptRoot 'workflows\importar_cobros.json'

docker cp $wf n8n:/tmp/importar_cobros.json
docker exec n8n n8n import:workflow --input=/tmp/importar_cobros.json | Out-Null
$rc = $LASTEXITCODE
docker exec -u root n8n rm -f /tmp/importar_cobros.json
if ($rc -ne 0) { throw "import:workflow fallo ($rc)" }

# El proceso principal ya usa el Task Broker en 5679; la ejecucion CLI usa otro puerto
$salida = docker exec -e N8N_RUNNERS_BROKER_PORT=5680 n8n n8n execute --id=importarCobrosGA --rawOutput 2>&1 | ForEach-Object { "$_" }
$rc = $LASTEXITCODE
$texto = $salida -join "`n"
$ini = $texto.IndexOf("`n{")
if ($rc -ne 0 -or $ini -lt 0) {
    # Solo el mensaje de error y el nodo donde se detuvo (sin trazas ni datos de conexion)
    $msg = $salida | Where-Object { $_ -match '^(Error: |CSV no valido)' } | Select-Object -First 1
    $nodo = $salida | Where-Object { $_ -match '"lastNodeExecuted"' } | Select-Object -First 1
    if ($msg) { "Error: " + ($msg -replace '^Error: ', '' -replace ' \[line \d+\]$', '') }
    if ($nodo) { "Detenido en: " + ($nodo -replace '.*"lastNodeExecuted":\s*"([^"]+)".*', '$1') }
    throw "La ejecucion de importar_cobros fallo ($rc)"
}

$run = ($texto.Substring($ini + 1) | ConvertFrom-Json)
$datos = $run.data.resultData.runData
"Ejecucion: $($run.status)  inicio: $($run.startedAt)"
"Validacion: " + ($datos.'Validar cobros'[0].data.main[0] | ForEach-Object { "filas=$($_.json.filas) total_csv=$($_.json.total_csv)" })
"Carga:      " + ($datos.'Cargar cobros'[0].data.main[0] | ForEach-Object { "filas_csv=$($_.json.filas_csv) insertadas=$($_.json.insertadas) actualizadas=$($_.json.actualizadas)" })
"Totales en Gestion_Alquileres.dbo.cobros:"
$datos.'Totales por mes'[0].data.main[0] | ForEach-Object { $_.json } | Format-Table mes, cobros, total -AutoSize | Out-String -Width 120
