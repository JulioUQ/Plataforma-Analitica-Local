-- Comprobación independiente de la carga de cobros (solo lectura).
--   sqlcmd -S "tcp:localhost,1433" -E -C -W -i sql\04_verificar_cobros.sql
-- Esperado con etl/n8n/ejemplos/cobros.csv: 20 filas, 20 IDs distintos y
-- 2026-08 3446.50 | 2026-09 3326.65 | 2026-10 3361.55 | 2026-11 3398.40 | TOTAL 13533.10
SET NOCOUNT ON;
USE Gestion_Alquileres;

SELECT COUNT(*) AS filas, COUNT(DISTINCT cobro_id) AS ids_distintos,
       SUM(CASE WHEN actualizado_en IS NOT NULL THEN 1 ELSE 0 END) AS filas_actualizadas_alguna_vez
FROM dbo.cobros;

SELECT mes, cobros, total
FROM (
    SELECT CONVERT(char(7), fecha_cobro, 126) AS mes, COUNT(*) AS cobros, SUM(importe) AS total, 0 AS orden
    FROM dbo.cobros
    GROUP BY CONVERT(char(7), fecha_cobro, 126)
    UNION ALL
    SELECT 'TOTAL', COUNT(*), SUM(importe), 1 FROM dbo.cobros
) AS r
ORDER BY orden, mes;
