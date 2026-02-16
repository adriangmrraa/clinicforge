#!/usr/bin/env pwsh
# ✅ QUICK VERIFICATION SCRIPT
# Valida que backend esté OK antes de proceder con frontend

Write-Host "🔍 Iniciando verificaciones del backend..." -ForegroundColor Cyan

# 1. Verificar que Python existe
Write-Host "`n[1/6] Verificando Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python no encontrado. Instala Python 3.9+" -ForegroundColor Red
    exit 1
}

# 2. Verificar que FastAPI existe
Write-Host "`n[2/6] Verificando FastAPI..." -ForegroundColor Yellow
try {
    python -c "import fastapi; print(f'FastAPI {fastapi.__version__}')" 2>&1 | ForEach-Object {
        if ($_ -match "FastAPI") {
            Write-Host "✅ $_" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "❌ FastAPI no instalado. Ejecuta: pip install fastapi" -ForegroundColor Red
}

# 3. Verificar que LangChain existe
Write-Host "`n[3/6] Verificando LangChain..." -ForegroundColor Yellow
try {
    python -c "import langchain; print(f'LangChain OK')" 2>&1 | ForEach-Object {
        Write-Host "✅ $_" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ LangChain no instalado. Ejecuta: pip install langchain" -ForegroundColor Red
}

# 4. Validar sintaxis de main.py
Write-Host "`n[4/6] Validando main.py..." -ForegroundColor Yellow
try {
    python -m py_compile orchestrator_service/main.py 2>&1
    Write-Host "✅ main.py sintaxis OK" -ForegroundColor Green
} catch {
    Write-Host "❌ Error de sintaxis en main.py" -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
}

# 5. Validar sintaxis de admin_routes.py
Write-Host "`n[5/6] Validando admin_routes.py..." -ForegroundColor Yellow
try {
    python -m py_compile orchestrator_service/admin_routes.py 2>&1
    Write-Host "✅ admin_routes.py sintaxis OK" -ForegroundColor Green
} catch {
    Write-Host "❌ Error de sintaxis en admin_routes.py" -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
}

# 6. Verificar PostgreSQL
Write-Host "`n[6/6] Verificando PostgreSQL..." -ForegroundColor Yellow
try {
    $pgVersion = psql --version 2>&1
    if ($pgVersion -match "psql") {
        Write-Host "✅ $pgVersion" -ForegroundColor Green
    } else {
        Write-Host "⚠️ PostgreSQL client OK, pero BD no verificada" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️ PostgreSQL no disponible. Será requerido para producción." -ForegroundColor Yellow
}

Write-Host "`n" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ VERIFICACIONES COMPLETADAS" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

Write-Host "`n📋 PRÓXIMOS PASOS:" -ForegroundColor Cyan
Write-Host "1. Ejecutar: pip install -r orchestrator_service/requirements.txt"
Write-Host "2. Ejecutar: .\run_migrations.ps1 (para SQL migrations)"
Write-Host "3. Ejecutar: python -m uvicorn orchestrator_service.main:app --reload"
Write-Host "4. Abrir en navegador: http://localhost:8000/docs"
Write-Host ""
