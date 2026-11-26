<div align="center">

![Ingeniería De Datos](https://img.shields.io/badge/INGENIER%C3%8DA_DE_DATOS-EF6C00?style=for-the-badge)

# Plataforma local de analítica

Pipeline local que importa hojas de cálculo de alquileres a SQL Server con n8n y presenta los indicadores mensuales en un dashboard de Dash, con una versión pública en GitHub Pages.

[![Demo en vivo: Ver dashboard](https://img.shields.io/badge/DEMO_EN_VIVO-Ver_dashboard-2EA043?style=for-the-badge&logo=googlechrome&logoColor=white)](https://juliouq.github.io/plataforma-analitica-local/)

![n8n](https://img.shields.io/badge/n8n-EA4B71?style=flat-square&logo=n8n&logoColor=white) ![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?style=flat-square) ![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![Dash](https://img.shields.io/badge/Dash-008DE4?style=flat-square&logo=plotly&logoColor=white) ![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)

<img src="docs/captura-dashboard.png" alt="Dashboard público con indicadores mensuales de reservas por plataforma: reservas, noches, importes y gráfico de neto por mes" width="100%" />

<sub>Demo pública: agregados mensuales reales, sin reservas individuales.</sub>

</div>

---

## Descripción general

Automatiza el seguimiento de alquileres de Airbnb y Booking. Los Excel exportados de cada plataforma se dejan en una carpeta; n8n los importa cada día a SQL Server y un dashboard en Dash calcula los indicadores mensuales por plataforma y periodo.

La página pública solo publica agregados mensuales exportados a JSON: los Excel y los datos individuales se quedan en el equipo.

## Funcionalidades

- **Importación diaria** con n8n a las 09:00 (Europe/Madrid), o manual con un script de PowerShell.
- **Modelo en SQL Server** con scripts versionados en `sql/`.
- **Dashboard local** en Dash con filtros por plataforma y periodo.
- **Publicación segura:** exportación de agregados a JSON y despliegue automático en GitHub Pages con GitHub Actions.
- **Demo reproducible** con datos ficticios desde un CSV.

## Tecnologías y herramientas

| Ámbito | Herramientas |
| --- | --- |
| Orquestación | n8n |
| Base de datos | SQL Server (T-SQL), Docker |
| Análisis y dashboard | Python, pandas, Dash |
| Publicación | GitHub Actions, GitHub Pages |

## Estructura del proyecto

```text
.
├── etl/n8n/          # Flujo de importación, scripts de carga y demo con datos ficticios
├── sql/              # Esquema y consultas de SQL Server
├── python/           # Dashboards, exportación de agregados y generación de la página
├── publicacion/      # agregados_alquileres.json (lo único que se publica)
├── .github/workflows/pages.yml
├── GUIA_OPERATIVA.md # Configuración de SQL Server, Docker, n8n y Python
└── requirements.txt
```

## Instalación y uso

Deja los Excel en `data/`. Para importar a mano y arrancar el dashboard, desde la raíz en PowerShell:

```powershell
.\etl\n8n\importar_alquileres.ps1
.\.venv\Scripts\python.exe python\dashboard_alquileres.py
```

Abre [Dash local](http://127.0.0.1:8060) para consultar los indicadores.

Para publicar cifras nuevas después de una importación:

```powershell
.\.venv\Scripts\python.exe python\exportar_agregados.py
git add publicacion/agregados_alquileres.json
git commit -m "Actualiza los agregados publicados"
git push
```

GitHub Actions reconstruye la página tras el push a `main`. La [guía operativa](GUIA_OPERATIVA.md) explica la instalación completa y la [demo con datos ficticios](etl/n8n/README.md) permite probar el flujo sin datos reales.

## Resultados

- [Caso de estudio en el portfolio](https://juliouq.github.io/Portfolio-Web---JulioUQ/es/casos/plataforma-analitica/): arquitectura, decisiones y límites del proyecto.

## Aspectos técnicos destacados

- Separación estricta entre datos privados (locales) y datos publicados (agregados).
- Pipeline completo: ingesta programada, base de datos relacional, análisis y publicación continua.

## Autor

**Julio Úbeda Quesada** · Data Scientist

[![Portfolio](https://img.shields.io/badge/Portfolio-0B2545?style=flat-square&logo=astro&logoColor=white)](https://juliouq.github.io/Portfolio-Web---JulioUQ/es/) [![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=flat-square)](https://www.linkedin.com/in/juliouq/) [![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/JulioUQ)
