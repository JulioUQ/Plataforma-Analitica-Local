# Plataforma · Analítica de alquileres

Canalización local que importa datos de alquileres con n8n, los almacena en SQL Server y permite explorar indicadores mensuales en Dash. La demo pública muestra una exportación de ejemplo.

[![Sitio en vivo](https://img.shields.io/badge/Sitio_en_vivo-0369A1?style=flat)](https://juliouq.github.io/Plataforma-Analitica-Local/) · [Demo en GitHub Pages](https://juliouq.github.io/Plataforma-Analitica-Local/)

[![Estado del despliegue](https://github.com/JulioUQ/Plataforma-Analitica-Local/actions/workflows/pages.yml/badge.svg)](https://github.com/JulioUQ/Plataforma-Analitica-Local/actions/workflows/pages.yml)

## Tecnologías

n8n, SQL Server, Python y Dash

## Explorar el repositorio

- [`etl`](./etl)
- [`python`](./python)

## Documentación

Dashboard de alquileres de Airbnb y Booking. n8n importa los Excel a SQL Server y Python consulta los datos para mostrarlos en Dash.


#### Uso local

Deja los Excel en `data/`. El flujo `importar_alquileres` se ejecuta cada día a las **09:00 (Europe/Madrid)** si n8n y SQL Server están en marcha. Puedes consultar las ejecuciones en el [editor de n8n](http://localhost:5678).

Para importar a mano y arrancar Dash, ejecuta desde la raíz en PowerShell:

```powershell
.\etl\n8n\importar_alquileres.ps1
.\.venv\Scripts\python.exe python\dashboard_alquileres.py
```

Abre [Dash local](http://127.0.0.1:8060) para consultar los indicadores mensuales y filtrar por plataforma y periodo.

#### Actualizar el sitio público

GitHub Pages muestra la última exportación de los agregados mensuales. Los Excel y los datos individuales se quedan en el equipo. Para publicar cifras nuevas después de una importación:

```powershell
.\.venv\Scripts\python.exe python\exportar_agregados.py
git add publicacion/agregados_alquileres.json
git commit -m "Actualiza los agregados publicados"
git push
```

GitHub Actions reconstruye la página tras el push a `main`.

#### Documentación

- [Guía operativa](GUIA_OPERATIVA.md) · Configuración de SQL Server, Docker, n8n y Python 3.13, formatos admitidos y significado de los indicadores.
- [Demo con datos ficticios](etl/n8n/README.md) · Ejemplo de carga desde un CSV.
