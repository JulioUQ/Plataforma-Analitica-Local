-- Prepara Gestion_Alquileres y su tabla de cobros. Es repetible: crea solo lo que falta
-- y vuelve a aplicar los permisos.
-- Requiere una cuenta administradora (autenticación de Windows) y el login analytics_etl
-- creado con 01_crear_usuario_roles_prueba.sql. Desde la raíz del repo:
--   sqlcmd -S "tcp:localhost,1433" -E -C -b -i sql\03_gestion_alquileres_cobros.sql
USE master;
GO
IF DB_ID(N'Gestion_Alquileres') IS NULL
    CREATE DATABASE Gestion_Alquileres;
GO

USE Gestion_Alquileres;
GO
IF SUSER_ID(N'analytics_etl') IS NULL
    THROW 50001, N'Falta el login analytics_etl: ejecuta antes 01_crear_usuario_roles_prueba.sql', 1;
GO
IF DATABASE_PRINCIPAL_ID(N'analytics_etl') IS NULL
    CREATE USER analytics_etl FOR LOGIN analytics_etl;
GO

-- cobro_id es la identidad estable del cobro: una corrección del CSV actualiza la fila.
IF OBJECT_ID(N'dbo.cobros', N'U') IS NULL
    CREATE TABLE dbo.cobros (
        cobro_id       NVARCHAR(20)  NOT NULL CONSTRAINT PK_cobros PRIMARY KEY,
        inmueble       NVARCHAR(100) NOT NULL,
        fecha_cobro    DATE          NOT NULL,
        importe        DECIMAL(12,2) NOT NULL CONSTRAINT CK_cobros_importe CHECK (importe > 0),
        cargado_en     DATETIME2(0)  NOT NULL CONSTRAINT DF_cobros_cargado_en DEFAULT SYSDATETIME(),
        actualizado_en DATETIME2(0)  NULL
    );
GO

-- Mínimo para el upsert de n8n (MERGE): leer, insertar y actualizar. Sin DELETE ni DDL.
GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.cobros TO analytics_etl;
GO

-- Comprobación
SELECT DB_NAME() AS base, OBJECT_ID(N'dbo.cobros', N'U') AS id_tabla;
SELECT pr.name AS usuario, pe.permission_name AS permiso, OBJECT_NAME(pe.major_id) AS objeto
FROM sys.database_permissions AS pe
JOIN sys.database_principals AS pr ON pr.principal_id = pe.grantee_principal_id
WHERE pr.name = N'analytics_etl' AND pe.class = 1
ORDER BY pe.permission_name;
GO
