-- MVP de alquileres reales (Airbnb y Booking) en Gestion_Alquileres, esquema alq.
-- Separado de dbo.cobros (demo ficticia). Repetible: crea lo que falta y redefine
-- procedimientos, vista y permisos. Ejecutar como administrador:
--   sqlcmd -S "tcp:localhost,1433" -E -C -b -i sql\05_alquileres_mvp.sql
--
-- Diseño
-- - Una fila por reserva (alq.reservas) y por pago liquidado (alq.pagos). La clave es el
--   SHA-256 de plataforma|tipo|código: los códigos de reserva/pago no se guardan en claro.
-- - n8n valida cada archivo y llama a alq.registrar_fuente con el lote en JSON (parámetro).
--   El procedimiento vuelve a validar, carga en UNA transacción (MERGE por clave) y registra
--   la ejecución. Un archivo con el mismo SHA-256 que otro ya cargado se omite.
-- - analytics_etl solo puede EJECUTAR los dos procedimientos y LEER la vista y el registro.
SET NOCOUNT ON;
USE master;
GO
IF DB_ID(N'Gestion_Alquileres') IS NULL
    THROW 50001, N'Falta Gestion_Alquileres: ejecuta antes sql/03_gestion_alquileres_cobros.sql', 1;
GO
USE Gestion_Alquileres;
GO
IF SCHEMA_ID(N'alq') IS NULL EXEC (N'CREATE SCHEMA alq AUTHORIZATION dbo');
GO

-- Plataformas admitidas y si su export incluye pagos liquidados
IF OBJECT_ID(N'alq.plataformas', N'U') IS NULL
    CREATE TABLE alq.plataformas (
        plataforma    VARCHAR(10)   NOT NULL CONSTRAINT PK_alq_plataformas PRIMARY KEY,
        nombre        NVARCHAR(40)  NOT NULL,
        informa_pagos BIT           NOT NULL
    );
GO
MERGE alq.plataformas AS t
USING (VALUES ('airbnb', N'Airbnb', 1), ('booking', N'Booking', 0)) AS s (plataforma, nombre, informa_pagos)
ON t.plataforma = s.plataforma
WHEN MATCHED THEN UPDATE SET nombre = s.nombre, informa_pagos = s.informa_pagos
WHEN NOT MATCHED THEN INSERT (plataforma, nombre, informa_pagos) VALUES (s.plataforma, s.nombre, s.informa_pagos);
GO

IF OBJECT_ID(N'alq.reservas', N'U') IS NULL
    CREATE TABLE alq.reservas (
        plataforma      VARCHAR(10)   NOT NULL CONSTRAINT FK_alq_reservas_plataforma REFERENCES alq.plataformas,
        clave           CHAR(64)      NOT NULL,          -- SHA-256 de plataforma|reserva|código
        fecha_reserva   DATE          NULL,
        fecha_llegada   DATE          NOT NULL,          -- determina el mes de las métricas de reserva
        fecha_salida    DATE          NOT NULL,
        noches          INT           NOT NULL CONSTRAINT CK_alq_reservas_noches CHECK (noches >= 0),
        estado          NVARCHAR(40)  NOT NULL,
        incluida        BIT           NOT NULL,          -- 0 = cancelada / no presentada: no suma
        moneda          CHAR(3)       NOT NULL,
        importe_original DECIMAL(14,3) NULL,             -- Booking: Original amount
        importe_bruto   DECIMAL(14,3) NOT NULL,          -- antes de comisiones de la plataforma
        comision        DECIMAL(14,3) NOT NULL,
        gastos_pago     DECIMAL(14,3) NOT NULL,
        neto            DECIMAL(14,3) NOT NULL,          -- bruto - comisión - gastos de pago
        limpieza        DECIMAL(14,3) NULL,
        impuestos       DECIMAL(14,3) NULL,
        fuente          NVARCHAR(400) NOT NULL,          -- ruta relativa del último archivo que la cargó
        cargado_en      DATETIME2(0)  NOT NULL CONSTRAINT DF_alq_reservas_cargado DEFAULT SYSDATETIME(),
        actualizado_en  DATETIME2(0)  NULL,
        CONSTRAINT PK_alq_reservas PRIMARY KEY (plataforma, clave)
    );
GO

IF OBJECT_ID(N'alq.pagos', N'U') IS NULL
    CREATE TABLE alq.pagos (
        plataforma      VARCHAR(10)   NOT NULL CONSTRAINT FK_alq_pagos_plataforma REFERENCES alq.plataformas,
        clave           CHAR(64)      NOT NULL,          -- SHA-256 de plataforma|pago|código de referencia
        fecha_pago      DATE          NOT NULL,          -- determina el mes del importe cobrado
        fecha_llegada_estimada DATE   NULL,
        moneda          CHAR(3)       NOT NULL,
        importe_cobrado DECIMAL(14,3) NOT NULL,
        fuente          NVARCHAR(400) NOT NULL,
        cargado_en      DATETIME2(0)  NOT NULL CONSTRAINT DF_alq_pagos_cargado DEFAULT SYSDATETIME(),
        actualizado_en  DATETIME2(0)  NULL,
        CONSTRAINT PK_alq_pagos PRIMARY KEY (plataforma, clave)
    );
GO

-- Archivos cargados (para omitir los que no cambian)
IF OBJECT_ID(N'alq.fuentes', N'U') IS NULL
    CREATE TABLE alq.fuentes (
        ruta            NVARCHAR(400) NOT NULL CONSTRAINT PK_alq_fuentes PRIMARY KEY,
        plataforma      VARCHAR(10)   NOT NULL,
        sha256          CHAR(64)      NOT NULL,
        filas_aceptadas INT           NOT NULL,
        filas_excluidas INT           NOT NULL,
        primera_carga   DATETIME2(0)  NOT NULL CONSTRAINT DF_alq_fuentes_primera DEFAULT SYSDATETIME(),
        ultima_carga    DATETIME2(0)  NOT NULL CONSTRAINT DF_alq_fuentes_ultima DEFAULT SYSDATETIME(),
        ejecucion_n8n   NVARCHAR(40)  NOT NULL
    );
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_alq_fuentes_sha256')
    CREATE INDEX IX_alq_fuentes_sha256 ON alq.fuentes (sha256);
GO

-- Registro por ejecución y por archivo (sin datos personales: rutas, recuentos y motivos)
IF OBJECT_ID(N'alq.ejecuciones', N'U') IS NULL
    CREATE TABLE alq.ejecuciones (
        ejecucion_n8n        NVARCHAR(40) NOT NULL CONSTRAINT PK_alq_ejecuciones PRIMARY KEY,
        modo                 NVARCHAR(20) NOT NULL,      -- programada | manual_editor | manual_cli
        inicio               DATETIME2(0) NOT NULL CONSTRAINT DF_alq_ejecuciones_inicio DEFAULT SYSDATETIME(),
        fin                  DATETIME2(0) NULL,
        estado               NVARCHAR(20) NOT NULL CONSTRAINT DF_alq_ejecuciones_estado DEFAULT N'en_curso',
        fuentes_cargadas     INT NULL,
        fuentes_sin_cambios  INT NULL,
        fuentes_rechazadas   INT NULL,
        filas_aceptadas      INT NULL,
        filas_excluidas      INT NULL,
        filas_rechazadas     INT NULL,
        filas_insertadas     INT NULL,
        filas_actualizadas   INT NULL
    );
GO
IF OBJECT_ID(N'alq.ejecuciones_fuentes', N'U') IS NULL
    CREATE TABLE alq.ejecuciones_fuentes (
        id               INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_alq_ejecuciones_fuentes PRIMARY KEY,
        ejecucion_n8n    NVARCHAR(40)  NOT NULL CONSTRAINT FK_alq_ef_ejecucion REFERENCES alq.ejecuciones,
        ruta             NVARCHAR(400) NOT NULL,
        plataforma       VARCHAR(10)   NULL,
        sha256           CHAR(64)      NULL,
        estado           NVARCHAR(20)  NOT NULL,         -- cargada | sin_cambios | rechazada
        filas_leidas     INT NOT NULL CONSTRAINT DF_alq_ef_leidas DEFAULT 0,
        filas_aceptadas  INT NOT NULL CONSTRAINT DF_alq_ef_aceptadas DEFAULT 0,
        filas_excluidas  INT NOT NULL CONSTRAINT DF_alq_ef_excluidas DEFAULT 0,
        filas_rechazadas INT NOT NULL CONSTRAINT DF_alq_ef_rechazadas DEFAULT 0,
        filas_insertadas INT NOT NULL CONSTRAINT DF_alq_ef_insertadas DEFAULT 0,
        filas_actualizadas INT NOT NULL CONSTRAINT DF_alq_ef_actualizadas DEFAULT 0,
        motivo           NVARCHAR(2000) NULL,
        registrado_en    DATETIME2(0)  NOT NULL CONSTRAINT DF_alq_ef_registrado DEFAULT SYSDATETIME()
    );
GO

CREATE OR ALTER PROCEDURE alq.registrar_fuente
    @ejecucion       NVARCHAR(40),
    @modo            NVARCHAR(20),
    @ruta            NVARCHAR(400) = NULL,   -- NULL: la ejecución no encontró archivos
    @plataforma      VARCHAR(10)   = NULL,
    @sha256          CHAR(64)      = NULL,
    @valido          BIT           = 0,      -- resultado de la validación de n8n
    @motivo          NVARCHAR(2000) = NULL,
    @filas_leidas    INT           = 0,
    @filas_excluidas INT           = 0,
    @lote            NVARCHAR(MAX) = NULL    -- JSON con las filas normalizadas
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @estado NVARCHAR(20), @aceptadas INT = 0, @insertadas INT = 0, @actualizadas INT = 0,
            @rechazadas INT = 0, @r INT, @ruta_previa NVARCHAR(400);
    DECLARE @acciones TABLE (accion NVARCHAR(10) NOT NULL);

    IF NOT EXISTS (SELECT 1 FROM alq.ejecuciones WHERE ejecucion_n8n = @ejecucion)
    BEGIN TRY
        INSERT INTO alq.ejecuciones (ejecucion_n8n, modo) VALUES (@ejecucion, ISNULL(@modo, N'desconocido'));
    END TRY
    BEGIN CATCH
        IF ERROR_NUMBER() NOT IN (2627, 2601) THROW;   -- otra llamada de la misma ejecución ya la creó
    END CATCH;

    IF @ruta IS NULL
    BEGIN
        SELECT CAST(NULL AS NVARCHAR(400)) AS ruta, CAST(NULL AS VARCHAR(10)) AS plataforma, N'sin_fuentes' AS estado,
               0 AS filas_leidas, 0 AS filas_aceptadas, 0 AS filas_excluidas, 0 AS filas_rechazadas,
               0 AS filas_insertadas, 0 AS filas_actualizadas, N'No se encontró ningún Excel en el montaje' AS motivo;
        RETURN;
    END;

    IF @valido = 1
    BEGIN TRY
        BEGIN TRAN;
        -- Serializa importaciones: dos ejecuciones simultáneas no cargan el mismo lote a la vez
        EXEC @r = sp_getapplock @Resource = N'alq_importacion', @LockMode = N'Exclusive',
                                @LockOwner = N'Transaction', @LockTimeout = 120000;
        IF @r < 0 THROW 51000, N'No se obtuvo el bloqueo de importación (otra carga en curso)', 1;

        SELECT TOP (1) @ruta_previa = ruta FROM alq.fuentes WHERE sha256 = @sha256 ORDER BY CASE WHEN ruta = @ruta THEN 0 ELSE 1 END;
        IF @ruta_previa IS NOT NULL
        BEGIN
            SET @estado = N'sin_cambios';
            SET @motivo = CASE WHEN @ruta_previa = @ruta THEN N'Mismo contenido ya cargado'
                               ELSE N'Contenido idéntico a ' + @ruta_previa END;
            SET @aceptadas = 0;
            COMMIT;
        END
        ELSE
        BEGIN
            -- Desempaqueta y vuelve a validar el lote; las conversiones fallidas quedan en NULL
            SELECT j.tipo,
                   clave = CONVERT(CHAR(64), HASHBYTES('SHA2_256', CONCAT(@plataforma, N'|', j.tipo, N'|', j.codigo)), 2),
                   codigo_vacio = CASE WHEN NULLIF(LTRIM(RTRIM(j.codigo)), N'') IS NULL THEN 1 ELSE 0 END,
                   fecha_reserva = TRY_CONVERT(DATE, j.fecha_reserva, 23),
                   fecha_llegada = TRY_CONVERT(DATE, j.fecha_llegada, 23),
                   fecha_salida  = TRY_CONVERT(DATE, j.fecha_salida, 23),
                   noches        = TRY_CONVERT(INT, j.noches),
                   j.estado, j.incluida, j.moneda,
                   importe_original = TRY_CONVERT(DECIMAL(14,3), j.importe_original),
                   importe_bruto = TRY_CONVERT(DECIMAL(14,3), j.importe_bruto),
                   comision      = TRY_CONVERT(DECIMAL(14,3), j.comision),
                   gastos_pago   = TRY_CONVERT(DECIMAL(14,3), j.gastos_pago),
                   neto          = TRY_CONVERT(DECIMAL(14,3), j.neto),
                   limpieza      = TRY_CONVERT(DECIMAL(14,3), j.limpieza),
                   impuestos     = TRY_CONVERT(DECIMAL(14,3), j.impuestos),
                   fecha_pago    = TRY_CONVERT(DATE, j.fecha_pago, 23),
                   fecha_llegada_estimada = TRY_CONVERT(DATE, j.fecha_llegada_estimada, 23),
                   importe_cobrado = TRY_CONVERT(DECIMAL(14,3), j.importe_cobrado),
                   j.fecha_reserva AS fecha_reserva_txt, j.fecha_llegada_estimada AS fecha_estimada_txt,
                   j.importe_original AS importe_original_txt, j.limpieza AS limpieza_txt, j.impuestos AS impuestos_txt
            INTO #lote
            FROM OPENJSON(@lote) WITH (
                tipo NVARCHAR(10), codigo NVARCHAR(100), fecha_reserva NVARCHAR(20), fecha_llegada NVARCHAR(20),
                fecha_salida NVARCHAR(20), noches NVARCHAR(10), estado NVARCHAR(40), incluida BIT, moneda NVARCHAR(3),
                importe_original NVARCHAR(30), importe_bruto NVARCHAR(30), comision NVARCHAR(30), gastos_pago NVARCHAR(30),
                neto NVARCHAR(30), limpieza NVARCHAR(30), impuestos NVARCHAR(30), fecha_pago NVARCHAR(20),
                fecha_llegada_estimada NVARCHAR(20), importe_cobrado NVARCHAR(30)
            ) AS j;

            IF @plataforma IS NULL OR NOT EXISTS (SELECT 1 FROM alq.plataformas WHERE plataforma = @plataforma)
                THROW 51001, N'Plataforma no admitida', 1;
            IF @sha256 IS NULL OR @sha256 LIKE '%[^0-9a-f]%' OR LEN(@sha256) <> 64
                THROW 51002, N'Huella SHA-256 no válida', 1;
            IF NOT EXISTS (SELECT 1 FROM #lote)
                THROW 51003, N'Lote vacío', 1;
            IF (SELECT COUNT(*) FROM OPENJSON(@lote)) <> (SELECT COUNT(*) FROM #lote)
               OR EXISTS (SELECT 1 FROM #lote WHERE tipo NOT IN (N'reserva', N'pago') OR tipo IS NULL OR codigo_vacio = 1)
                THROW 51004, N'Lote con filas sin tipo o sin código', 1;
            IF EXISTS (SELECT 1 FROM #lote WHERE moneda IS NULL OR moneda <> N'EUR')
                THROW 51005, N'Divisa distinta de EUR (el MVP solo admite EUR)', 1;
            IF EXISTS (SELECT 1 FROM #lote WHERE tipo = N'reserva' AND (
                    fecha_llegada IS NULL OR fecha_salida IS NULL OR noches IS NULL OR estado IS NULL OR incluida IS NULL
                    OR importe_bruto IS NULL OR comision IS NULL OR gastos_pago IS NULL OR neto IS NULL
                    OR (fecha_reserva_txt IS NOT NULL AND fecha_reserva IS NULL)
                    OR (importe_original_txt IS NOT NULL AND importe_original IS NULL)
                    OR (limpieza_txt IS NOT NULL AND limpieza IS NULL)
                    OR (impuestos_txt IS NOT NULL AND impuestos IS NULL)
                    OR DATEDIFF(DAY, fecha_llegada, fecha_salida) <> noches
                    OR neto <> importe_bruto - comision - gastos_pago))
                THROW 51006, N'Reserva con campos obligatorios no válidos o importes incoherentes', 1;
            IF EXISTS (SELECT 1 FROM #lote WHERE tipo = N'pago' AND (
                    fecha_pago IS NULL OR importe_cobrado IS NULL
                    OR (fecha_estimada_txt IS NOT NULL AND fecha_llegada_estimada IS NULL)))
                THROW 51007, N'Pago con campos obligatorios no válidos', 1;
            IF EXISTS (SELECT clave FROM #lote GROUP BY clave HAVING COUNT(*) > 1)
                THROW 51008, N'Código repetido dentro del archivo', 1;

            MERGE alq.reservas WITH (HOLDLOCK) AS t
            USING (SELECT * FROM #lote WHERE tipo = N'reserva') AS s
            ON t.plataforma = @plataforma AND t.clave = s.clave
            WHEN MATCHED AND EXISTS (
                SELECT s.fecha_reserva, s.fecha_llegada, s.fecha_salida, s.noches, s.estado, s.incluida, s.moneda,
                       s.importe_original, s.importe_bruto, s.comision, s.gastos_pago, s.neto, s.limpieza, s.impuestos
                EXCEPT
                SELECT t.fecha_reserva, t.fecha_llegada, t.fecha_salida, t.noches, t.estado, t.incluida, t.moneda,
                       t.importe_original, t.importe_bruto, t.comision, t.gastos_pago, t.neto, t.limpieza, t.impuestos)
            THEN UPDATE SET fecha_reserva = s.fecha_reserva, fecha_llegada = s.fecha_llegada, fecha_salida = s.fecha_salida,
                            noches = s.noches, estado = s.estado, incluida = s.incluida, moneda = s.moneda,
                            importe_original = s.importe_original, importe_bruto = s.importe_bruto, comision = s.comision,
                            gastos_pago = s.gastos_pago, neto = s.neto, limpieza = s.limpieza, impuestos = s.impuestos,
                            fuente = @ruta, actualizado_en = SYSDATETIME()
            WHEN NOT MATCHED BY TARGET THEN
                INSERT (plataforma, clave, fecha_reserva, fecha_llegada, fecha_salida, noches, estado, incluida, moneda,
                        importe_original, importe_bruto, comision, gastos_pago, neto, limpieza, impuestos, fuente)
                VALUES (@plataforma, s.clave, s.fecha_reserva, s.fecha_llegada, s.fecha_salida, s.noches, s.estado, s.incluida,
                        s.moneda, s.importe_original, s.importe_bruto, s.comision, s.gastos_pago, s.neto, s.limpieza,
                        s.impuestos, @ruta)
            OUTPUT $action INTO @acciones;

            MERGE alq.pagos WITH (HOLDLOCK) AS t
            USING (SELECT * FROM #lote WHERE tipo = N'pago') AS s
            ON t.plataforma = @plataforma AND t.clave = s.clave
            WHEN MATCHED AND EXISTS (
                SELECT s.fecha_pago, s.fecha_llegada_estimada, s.moneda, s.importe_cobrado
                EXCEPT
                SELECT t.fecha_pago, t.fecha_llegada_estimada, t.moneda, t.importe_cobrado)
            THEN UPDATE SET fecha_pago = s.fecha_pago, fecha_llegada_estimada = s.fecha_llegada_estimada,
                            moneda = s.moneda, importe_cobrado = s.importe_cobrado, fuente = @ruta,
                            actualizado_en = SYSDATETIME()
            WHEN NOT MATCHED BY TARGET THEN
                INSERT (plataforma, clave, fecha_pago, fecha_llegada_estimada, moneda, importe_cobrado, fuente)
                VALUES (@plataforma, s.clave, s.fecha_pago, s.fecha_llegada_estimada, s.moneda, s.importe_cobrado, @ruta)
            OUTPUT $action INTO @acciones;

            SELECT @aceptadas = COUNT(*) FROM #lote;
            SELECT @insertadas = COUNT(*) FROM @acciones WHERE accion = N'INSERT';
            SELECT @actualizadas = COUNT(*) FROM @acciones WHERE accion = N'UPDATE';

            MERGE alq.fuentes AS t
            USING (SELECT @ruta AS ruta) AS s ON t.ruta = s.ruta
            WHEN MATCHED THEN UPDATE SET plataforma = @plataforma, sha256 = @sha256, filas_aceptadas = @aceptadas,
                                         filas_excluidas = @filas_excluidas, ultima_carga = SYSDATETIME(),
                                         ejecucion_n8n = @ejecucion
            WHEN NOT MATCHED THEN INSERT (ruta, plataforma, sha256, filas_aceptadas, filas_excluidas, ejecucion_n8n)
                                  VALUES (@ruta, @plataforma, @sha256, @aceptadas, @filas_excluidas, @ejecucion);
            SET @estado = N'cargada';
            SET @motivo = NULL;
            COMMIT;
        END
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK;
        SET @estado = N'rechazada';
        SET @aceptadas = 0; SET @insertadas = 0; SET @actualizadas = 0;
        SET @motivo = N'SQL Server rechazó el lote (' + CAST(ERROR_NUMBER() AS NVARCHAR(10)) + N'): ' + LEFT(ERROR_MESSAGE(), 500);
    END CATCH
    ELSE
        SET @estado = N'rechazada';

    IF @estado = N'rechazada' SET @rechazadas = @filas_leidas;
    INSERT INTO alq.ejecuciones_fuentes (ejecucion_n8n, ruta, plataforma, sha256, estado, filas_leidas, filas_aceptadas,
                                         filas_excluidas, filas_rechazadas, filas_insertadas, filas_actualizadas, motivo)
    VALUES (@ejecucion, @ruta, @plataforma, @sha256, @estado, @filas_leidas, @aceptadas,
            CASE WHEN @estado = N'cargada' THEN @filas_excluidas ELSE 0 END, @rechazadas, @insertadas, @actualizadas, @motivo);

    SELECT @ruta AS ruta, @plataforma AS plataforma, @estado AS estado, @filas_leidas AS filas_leidas,
           @aceptadas AS filas_aceptadas, CASE WHEN @estado = N'cargada' THEN @filas_excluidas ELSE 0 END AS filas_excluidas,
           @rechazadas AS filas_rechazadas, @insertadas AS filas_insertadas, @actualizadas AS filas_actualizadas, @motivo AS motivo;
END;
GO

CREATE OR ALTER PROCEDURE alq.cerrar_ejecucion
    @ejecucion NVARCHAR(40),
    @modo      NVARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM alq.ejecuciones WHERE ejecucion_n8n = @ejecucion)
        INSERT INTO alq.ejecuciones (ejecucion_n8n, modo) VALUES (@ejecucion, ISNULL(@modo, N'desconocido'));

    UPDATE e SET
        fin = SYSDATETIME(),
        fuentes_cargadas    = x.cargadas,
        fuentes_sin_cambios = x.sin_cambios,
        fuentes_rechazadas  = x.rechazadas,
        filas_aceptadas     = x.aceptadas,
        filas_excluidas     = x.excluidas,
        filas_rechazadas    = x.filas_rechazadas,
        filas_insertadas    = x.insertadas,
        filas_actualizadas  = x.actualizadas,
        estado = CASE WHEN x.rechazadas > 0 THEN N'con_errores'
                      WHEN x.cargadas > 0 THEN N'cargada'
                      WHEN x.sin_cambios > 0 THEN N'sin_cambios'
                      ELSE N'sin_fuentes' END
    FROM alq.ejecuciones AS e
    CROSS APPLY (
        SELECT cargadas    = COUNT(CASE WHEN estado = N'cargada' THEN 1 END),
               sin_cambios = COUNT(CASE WHEN estado = N'sin_cambios' THEN 1 END),
               rechazadas  = COUNT(CASE WHEN estado = N'rechazada' THEN 1 END),
               aceptadas   = ISNULL(SUM(filas_aceptadas), 0),
               excluidas   = ISNULL(SUM(filas_excluidas), 0),
               filas_rechazadas = ISNULL(SUM(filas_rechazadas), 0),
               insertadas  = ISNULL(SUM(filas_insertadas), 0),
               actualizadas = ISNULL(SUM(filas_actualizadas), 0)
        FROM alq.ejecuciones_fuentes WHERE ejecucion_n8n = e.ejecucion_n8n
    ) AS x
    WHERE e.ejecucion_n8n = @ejecucion;

    SELECT ejecucion_n8n, modo, inicio, fin, estado, fuentes_cargadas, fuentes_sin_cambios, fuentes_rechazadas,
           filas_aceptadas, filas_excluidas, filas_rechazadas, filas_insertadas, filas_actualizadas
    FROM alq.ejecuciones WHERE ejecucion_n8n = @ejecucion;
END;
GO

-- Agregados mensuales por plataforma. Dos bases de mes distintas, en columnas separadas:
--   * métricas de reserva: mes de la fecha de llegada (check-in), solo reservas incluidas;
--   * importe cobrado: mes de la fecha del pago liquidado (solo plataformas que lo informan).
CREATE OR ALTER VIEW alq.v_agregados_mensuales
AS
WITH r AS (
    SELECT plataforma, CONVERT(CHAR(7), fecha_llegada, 126) AS mes,
           SUM(CASE WHEN incluida = 1 THEN 1 ELSE 0 END)        AS reservas,
           SUM(CASE WHEN incluida = 0 THEN 1 ELSE 0 END)        AS reservas_excluidas,
           SUM(CASE WHEN incluida = 1 THEN noches ELSE 0 END)   AS noches,
           SUM(CASE WHEN incluida = 1 THEN importe_bruto ELSE 0 END) AS importe_bruto,
           SUM(CASE WHEN incluida = 1 THEN comision ELSE 0 END)      AS comisiones,
           SUM(CASE WHEN incluida = 1 THEN gastos_pago ELSE 0 END)   AS gastos_pago,
           SUM(CASE WHEN incluida = 1 THEN neto ELSE 0 END)          AS neto
    FROM alq.reservas
    GROUP BY plataforma, CONVERT(CHAR(7), fecha_llegada, 126)
), p AS (
    SELECT plataforma, CONVERT(CHAR(7), fecha_pago, 126) AS mes, COUNT(*) AS pagos, SUM(importe_cobrado) AS importe_cobrado
    FROM alq.pagos
    GROUP BY plataforma, CONVERT(CHAR(7), fecha_pago, 126)
)
SELECT COALESCE(r.plataforma, p.plataforma) AS plataforma,
       pl.nombre                            AS plataforma_nombre,
       COALESCE(r.mes, p.mes)               AS mes,
       ISNULL(r.reservas, 0)                AS reservas,
       ISNULL(r.reservas_excluidas, 0)      AS reservas_excluidas,
       ISNULL(r.noches, 0)                  AS noches,
       CAST(ISNULL(r.importe_bruto, 0) AS DECIMAL(16,3)) AS importe_bruto,
       CAST(ISNULL(r.comisiones, 0)    AS DECIMAL(16,3)) AS comisiones,
       CAST(ISNULL(r.gastos_pago, 0)   AS DECIMAL(16,3)) AS gastos_pago,
       CAST(ISNULL(r.neto, 0)          AS DECIMAL(16,3)) AS neto,
       CASE WHEN pl.informa_pagos = 1 THEN ISNULL(p.pagos, 0) END AS pagos,
       CASE WHEN pl.informa_pagos = 1 THEN CAST(ISNULL(p.importe_cobrado, 0) AS DECIMAL(16,3)) END AS importe_cobrado
FROM r
FULL OUTER JOIN p ON p.plataforma = r.plataforma AND p.mes = r.mes
JOIN alq.plataformas AS pl ON pl.plataforma = COALESCE(r.plataforma, p.plataforma);
GO

-- Permisos mínimos del login de n8n/Python en el MVP
GRANT EXECUTE ON OBJECT::alq.registrar_fuente      TO analytics_etl;
GRANT EXECUTE ON OBJECT::alq.cerrar_ejecucion      TO analytics_etl;
GRANT SELECT  ON OBJECT::alq.v_agregados_mensuales TO analytics_etl;
GRANT SELECT  ON OBJECT::alq.ejecuciones           TO analytics_etl;
GRANT SELECT  ON OBJECT::alq.ejecuciones_fuentes   TO analytics_etl;
GO

-- Comprobación
SELECT s.name AS esquema, o.name AS objeto, o.type_desc AS tipo
FROM sys.objects o JOIN sys.schemas s ON s.schema_id = o.schema_id
WHERE s.name = N'alq' AND o.type IN ('U', 'V', 'P')
ORDER BY o.type, o.name;
SELECT pe.permission_name AS permiso, SCHEMA_NAME(o.schema_id) + N'.' + o.name AS objeto
FROM sys.database_permissions pe
JOIN sys.database_principals pr ON pr.principal_id = pe.grantee_principal_id
JOIN sys.objects o ON o.object_id = pe.major_id
WHERE pr.name = N'analytics_etl' AND SCHEMA_NAME(o.schema_id) = N'alq'
ORDER BY objeto, permiso;
GO
