@echo off
chcp 65001 >nul
title cac-elrocho - Servidor de Desarrollo

echo ===================================================
echo     [+] cac-elrocho - Modo Desarrollo Local
echo ===================================================
echo.

:: Comprobar si existe el entorno virtual
if not exist "venv\Scripts\python.exe" (
    echo [!] No se encontro el entorno virtual en \venv.
    echo Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual. Asegurate de tener Python instalado.
        pause
        exit /b 1
    )
    echo Instalando dependencias...
    call .\venv\Scripts\pip.exe install -r requirements.txt
)

:: Comprobar si existe .env
if not exist ".env" (
    echo [i] Creando archivo .env a partir de .env.example...
    copy .env.example .env >nul
)

:: Informar al usuario
echo [*] Servidor listo.
echo.
echo     URL de la aplicacion:  http://localhost:8000
echo     Documentacion API:     http://localhost:8000/docs
echo.
echo Pulsa Ctrl + C en esta ventana para detener el servidor.
echo ===================================================
echo.

:: Abrir navegador tras 2 segundos en segundo plano
start "" cmd /c "timeout /t 2 >nul & start http://localhost:8000"

:: Iniciar uvicorn con recarga en vivo
.\venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000

pause
