# Ejecuta ahora el workflow importar_alquileres (Excel de data/ -> SQL Server) y muestra
# solo el resumen final: rutas, recuentos y motivos, nunca datos de huéspedes.
# Uso desde la raíz del repo, con n8n y SQL Server en marcha:
#   .\etl\n8n\importar_alquileres.ps1             # ejecutar ahora
#   .\etl\n8n\importar_alquileres.ps1 -Importar   # antes, (re)importar el workflow desde etl/n8n/workflows/
# -Importar deja el workflow desactivado: vuelve a activarlo con
#   docker exec n8n n8n publish:workflow --id=impAlquileresMVP ; docker restart n8n
param([switch]$Importar)
$ErrorActionPreference = 'Stop'
$id = 'impAlquileresMVP'

if ($Importar) {
    docker cp (Join-Path $PSScriptRoot 'workflows\importar_alquileres.json') n8n:/tmp/importar_alquileres.json
    docker exec n8n n8n import:workflow --input=/tmp/importar_alquileres.json | Out-Null
    $rc = $LASTEXITCODE
    docker exec -u root n8n rm -f /tmp/importar_alquileres.json
    if ($rc -ne 0) { throw "import:workflow fallo ($rc)" }
    Write-Host "Workflow importado (desactivado)."
}

# El proceso principal ya usa el Task Broker en 5679; la ejecucion CLI usa otro puerto
$salida = docker exec -e N8N_RUNNERS_BROKER_PORT=5680 n8n n8n execute --id=$id --rawOutput 2>&1 | ForEach-Object { "$_" }
$rc = $LASTEXITCODE
$texto = $salida -join "`n"
$ini = $texto.IndexOf("`n{")
if ($rc -ne 0 -or $ini -lt 0) {
    $msg = $salida | Where-Object { $_ -match '^Error: ' } | Select-Object -First 1
    $nodo = $salida | Where-Object { $_ -match '"lastNodeExecuted"' } | Select-Object -First 1
    if ($msg) { $msg -replace ' \[line \d+\]$', '' }
    if ($nodo) { "Detenido en: " + ($nodo -replace '.*"lastNodeExecuted":\s*"([^"]+)".*', '$1') }
    throw "La ejecucion de importar_alquileres termino con error ($rc). Detalle en n8n (Executions) y en alq.ejecuciones_fuentes."
}
$run = $texto.Substring($ini + 1) | ConvertFrom-Json
$r = $run.data.resultData.runData.'Resumen'[0].data.main[0][0].json
"Ejecucion $($r.ejecucion) ($($r.modo)): $($run.status)"
$r.mensaje
$r.detalle | Format-Table ruta, estado, aceptadas, excluidas, rechazadas, motivo -AutoSize -Wrap | Out-String -Width 220
