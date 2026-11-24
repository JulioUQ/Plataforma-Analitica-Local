--Crear usuarios con permisos en la BBDD Test_Analytics
USE master;
GO
CREATE LOGIN analytics_etl
    WITH PASSWORD = '<CONTRASEÑA_EN_GESTOR>',
         CHECK_POLICY = ON,
         DEFAULT_DATABASE = Test_Analytics;
GO

USE Test_Analytics;
GO
CREATE USER analytics_etl FOR LOGIN analytics_etl;
ALTER ROLE db_datareader ADD MEMBER analytics_etl;
ALTER ROLE db_datawriter ADD MEMBER analytics_etl;
ALTER ROLE db_ddladmin   ADD MEMBER analytics_etl;
GO

--Ejecutar esto para comprobar que existe:
SELECT name, type_desc
FROM sys.database_principals
WHERE name = 'analytics_etl';

--Ejecutar esto para dar permisos:
SELECT dp.name AS usuario, rp.name AS rol
FROM sys.database_role_members drm
JOIN sys.database_principals rp ON rp.principal_id = drm.role_principal_id
JOIN sys.database_principals dp ON dp.principal_id = drm.member_principal_id
WHERE dp.name = 'analytics_etl' ;

--Ejecutar esto para cambiar la contraseña:
ALTER LOGIN analytics_etl WITH PASSWORD = '<CONTRASEÑA_EN_GESTOR>';