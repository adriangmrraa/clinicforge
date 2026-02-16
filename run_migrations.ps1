#!/usr/bin/env powershell
# ========================================
# run_migrations.ps1
# Ejecuta todas las migraciones SQL
# ========================================

$ErrorActionPreference = "Stop"

# Variables
$POSTGRES_USER = "postgres"
$POSTGRES_PASSWORD = "postgres"  # Cambiar según tu setup
$POSTGRES_HOST = "localhost"
$POSTGRES_PORT = 5432
$DATABASE_NAME = "clinica_dental"
$MIGRATIONS_DIR = "db/init"

Write-Host "🚀 Iniciando migraciones SQL..." -ForegroundColor Green

# Verificar que psql está disponible
try {
    $psqlVersion = psql --version
    Write-Host "✅ PostgreSQL encontrado: $psqlVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: PostgreSQL no está instalado o no está en PATH" -ForegroundColor Red
    exit 1
}

# Función para ejecutar un archivo SQL
function Execute-SqlFile {
    param(
        [string]$FilePath,
        [string]$Description
    )
    
    Write-Host "`n📄 Ejecutando: $Description" -ForegroundColor Cyan
    Write-Host "   Archivo: $FilePath" -ForegroundColor Gray
    
    try {
        # Ejecutar el archivo
        $env:PGPASSWORD = $POSTGRES_PASSWORD
        psql `
            -h $POSTGRES_HOST `
            -p $POSTGRES_PORT `
            -U $POSTGRES_USER `
            -d $DATABASE_NAME `
            -f $FilePath
        
        Write-Host "   ✅ OK" -ForegroundColor Green
    } catch {
        Write-Host "   ❌ Error: $_" -ForegroundColor Red
        exit 1
    } finally {
        Remove-Item env:PGPASSWORD -ErrorAction SilentlyContinue
    }
}

# Verificar que la BD existe
Write-Host "`n🔍 Verificando base de datos '$DATABASE_NAME'..." -ForegroundColor Cyan
$env:PGPASSWORD = $POSTGRES_PASSWORD
$dbExists = psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -l | Select-String $DATABASE_NAME
Remove-Item env:PGPASSWORD -ErrorAction SilentlyContinue

if (-not $dbExists) {
    Write-Host "⚠️  La base de datos no existe. Creando..." -ForegroundColor Yellow
    try {
        $env:PGPASSWORD = $POSTGRES_PASSWORD
        psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -c "CREATE DATABASE $DATABASE_NAME;"
        Write-Host "✅ Base de datos creada" -ForegroundColor Green
    } catch {
        Write-Host "❌ Error al crear BD: $_" -ForegroundColor Red
        exit 1
    } finally {
        Remove-Item env:PGPASSWORD -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "✅ Base de datos encontrada" -ForegroundColor Green
}

# Ejecutar migraciones en orden
Write-Host "`n📦 Ejecutando migraciones..." -ForegroundColor Cyan

Execute-SqlFile `
    -FilePath "$MIGRATIONS_DIR/001_schema.sql" `
    -Description "Schema base (inbound_messages, chat_messages)"

Execute-SqlFile `
    -FilePath "$MIGRATIONS_DIR/002_platform_schema.sql" `
    -Description "Platform schema (tenants, credentials, system_events)"

Execute-SqlFile `
    -FilePath "$MIGRATIONS_DIR/004_dental_phase1_schema.sql" `
    -Description "Dental schema (patients, professionals, appointments, clinical_records)"

# Verificación final
Write-Host "`n✅ Migraciones completadas. Verificando tablas..." -ForegroundColor Green

$env:PGPASSWORD = $POSTGRES_PASSWORD
$tables = psql `
    -h $POSTGRES_HOST `
    -p $POSTGRES_PORT `
    -U $POSTGRES_USER `
    -d $DATABASE_NAME `
    -t `
    -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"
Remove-Item env:PGPASSWORD -ErrorAction SilentlyContinue

$tableCount = [int]$tables.Trim()
Write-Host "📊 Total de tablas creadas: $tableCount" -ForegroundColor Green

if ($tableCount -ge 10) {
    Write-Host "`n✅ ¡ÉXITO! Backend listo para funcionar" -ForegroundColor Green
    Write-Host "Próximo paso: Ejecutar main.py con uvicorn" -ForegroundColor Cyan
} else {
    Write-Host "`n⚠️  Advertencia: Se esperaban al menos 10 tablas, se encontraron $tableCount" -ForegroundColor Yellow
}

Write-Host "`n"
