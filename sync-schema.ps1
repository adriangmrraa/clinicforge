# Script de Sincronización de Esquemas Dentalogic
# Copia el esquema de la raíz a la carpeta interna del orquestador

$Source = "db\init\dentalogic_schema.sql"
$Dest = "orchestrator_service\db\init\dentalogic_schema.sql"

if (Test-Path $Source) {
    Copy-Item $Source $Dest -Force
    Write-Host "✅ Esquema sincronizado exitosamente de $Source a $Dest" -ForegroundColor Green
} else {
    Write-Error "❌ No se encontró el archivo de origen: $Source"
}
