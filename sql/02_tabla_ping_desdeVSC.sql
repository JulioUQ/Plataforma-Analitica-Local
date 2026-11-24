CREATE TABLE Test_Analytics.dbo.ping (
    id      INT IDENTITY(1,1) PRIMARY KEY,
    mensaje NVARCHAR(100) NOT NULL,
    creado  DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

INSERT INTO Test_Analytics.dbo.ping (mensaje) VALUES (N'Hola desde VS Code');
GO

SELECT * FROM Test_Analytics.dbo.ping;
GO