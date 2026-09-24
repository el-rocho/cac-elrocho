[CmdletBinding()]
param(
    [string]$PythonLauncher = "py",
    [string]$PythonVersion = "",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (Get-Process -Name "AnaliticasClinicas" -ErrorAction SilentlyContinue) {
    throw "AnaliticasClinicas.exe sigue abierto. Cierre la aplicación (o finalícela desde el Administrador de tareas) antes de reconstruir dist."
}

function Invoke-Checked {
    param(
        [string]$Description,
        [scriptblock]$Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description falló (código de salida $LASTEXITCODE). No se generó ningún ejecutable."
    }
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Se necesita Node.js/npm para generar los estilos locales de la interfaz."
}

Invoke-Checked "La instalación de dependencias de frontend" { npm ci }
Invoke-Checked "La generación de estilos locales" { npm run build:styles }

$VenvPython = Join-Path $ProjectRoot ".venv-win\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $venvArguments = @("-m", "venv", ".venv-win")
    if ($PythonVersion) {
        $venvArguments = @("-$PythonVersion") + $venvArguments
    }
    Invoke-Checked "La creación del entorno virtual de Windows" {
        & $PythonLauncher @venvArguments
    }
}

Invoke-Checked "La actualización de pip" { & $VenvPython -m pip install --upgrade pip }
Invoke-Checked "La instalación de dependencias Python" { & $VenvPython -m pip install -r requirements-desktop.txt }

if (-not $SkipTests) {
    Invoke-Checked "La batería de pruebas" { & $VenvPython -m unittest discover --start-directory tests --verbose }
}

Invoke-Checked "PyInstaller" { & $VenvPython -m PyInstaller --noconfirm --clean packaging\AnaliticasClinicas.spec }

if (-not (Test-Path "$ProjectRoot\dist\AnaliticasClinicas\AnaliticasClinicas.exe")) {
    throw "PyInstaller terminó sin crear AnaliticasClinicas.exe. Revise la salida anterior."
}

Write-Host "Ejecutable creado en: $ProjectRoot\dist\AnaliticasClinicas" -ForegroundColor Green
