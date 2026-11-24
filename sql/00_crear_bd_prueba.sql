IF DB_ID('Test_Analytics') IS NULL
    CREATE DATABASE Test_Analytics;
GO

SELECT name, collation_name
FROM sys.databases
WHERE name = 'Test_Analytics';