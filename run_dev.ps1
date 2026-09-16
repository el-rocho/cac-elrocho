# Script de arranque en desarrollo para PowerShell
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    🩺 cac-elrocho - Modo Desarrollo Local" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path "venv\Scripts\python.exe")) {
    Write-Host "[!] Entorno virtual no encontrado. Creándolo..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "[*] Instalando dependencias..." -ForegroundColor Yellow
    .\venv\Scripts\pip install -r requirements.txt
}

if (!(Test-Path ".env")) {
    Write-Host "[i] Creando archivo .env a partir de .env.example..." -ForegroundColor Yellow
    Copy-Item .env.example .env
}

Write-Host "[*] URL de la aplicación:  http://localhost:8000" -ForegroundColor Green
Write-Host "[*] Documentación API:     http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Presiona Ctrl + C para detener el servidor." -ForegroundColor Gray
Write-Host "===================================================" -ForegroundColor Cyan

Start-Process "http://localhost:8000"

.\venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
