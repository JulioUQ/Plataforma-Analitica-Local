# Crea o actualiza en n8n las credenciales Microsoft SQL (Test_Analytics y
# Gestion_Alquileres) a partir del .env de la raiz. Repetir tras rotar la contrasena.
# La contrasena viaja por stdin al contenedor y se borra el fichero temporal;
# no queda en el repo, en la linea de comandos ni en la salida.
# Uso (desde la raiz del repo, con el contenedor n8n en marcha):
#   .\etl\n8n\cargar_credencial.ps1
$ErrorActionPreference = 'Stop'
$raiz = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$cfg = @{}
Get-Content (Join-Path $raiz '.env') | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
    $k, $v = $_ -split '=', 2
    $cfg[$k.Trim()] = $v.Trim()
}

function New-MssqlCredential([string]$Id, [string]$Nombre, [string]$BaseDatos) {
    [ordered]@{
        id   = $Id
        name = $Nombre
        type = 'microsoftSql'
        data = [ordered]@{
            server                 = 'host.docker.internal'
            port                   = [int]$cfg['DB_PORT']
            database               = $BaseDatos
            user                   = $cfg['DB_USER']
            password               = $cfg['DB_PASSWORD']
            domain                 = ''
            tls                    = $true
            allowUnauthorizedCerts = $true   # certificado autofirmado del SQL Server local
            tdsVersion             = '7_4'
            connectTimeout         = 15000
            requestTimeout         = 15000
        }
    }
}

# Mismo login para ambas bases; cada flujo usa la credencial de su base.
$cred = @(
    (New-MssqlCredential 'mssqlTestAnalyti' 'SQL Server Test_Analytics (analytics_etl)' $cfg['DB_NAME']),
    (New-MssqlCredential 'mssqlGestionAlqu' 'SQL Server Gestion_Alquileres (analytics_etl)' 'Gestion_Alquileres')
)
$json = ConvertTo-Json -InputObject $cred -Depth 5 -Compress
# JSON en ASCII puro (\uXXXX para el resto): evita el BOM que PowerShell 5.1 antepone al canalizar en UTF-8
$json = [regex]::Replace($json, '[^\x00-\x7F]', { param($m) '\u{0:x4}' -f [int][char]$m.Value })

$OutputEncoding = [System.Text.Encoding]::ASCII
docker cp (Join-Path $PSScriptRoot 'importar_credencial.sh') n8n:/tmp/importar_credencial.sh
if ($LASTEXITCODE -ne 0) { throw "docker cp fallo ($LASTEXITCODE)" }
$json | docker exec -i n8n sh /tmp/importar_credencial.sh
if ($LASTEXITCODE -ne 0) { throw "import:credentials fallo ($LASTEXITCODE)" }
docker exec -u root n8n rm -f /tmp/importar_credencial.sh
Write-Host "Credenciales Microsoft SQL cargadas en n8n: $($cred.Count)."
