# Importa (o actualiza) el workflow ping_n8n en n8n y lo ejecuta una vez.
# Uso (desde la raiz del repo, con el contenedor n8n en marcha y la credencial cargada):
#   .\etl\n8n\probar_ping.ps1
$ErrorActionPreference = 'Stop'
$wf = Join-Path $PSScriptRoot 'workflows\ping_n8n.json'

docker cp $wf n8n:/tmp/ping_n8n.json
docker exec n8n n8n import:workflow --input=/tmp/ping_n8n.json
if ($LASTEXITCODE -ne 0) { throw "import:workflow fallo ($LASTEXITCODE)" }

# El proceso principal ya usa el Task Broker en 5679; la ejecucion CLI usa otro puerto
docker exec -e N8N_RUNNERS_BROKER_PORT=5680 n8n n8n execute --id=pingN8nTestAnlyt --rawOutput
if ($LASTEXITCODE -ne 0) { throw "execute fallo ($LASTEXITCODE)" }
