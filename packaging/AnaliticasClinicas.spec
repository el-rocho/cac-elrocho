# -*- mode: python ; coding: utf-8 -*-
"""Definición reproducible de PyInstaller para el cliente Windows."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata


# ``SPECPATH`` depende de cómo se invoque PyInstaller. ``SPEC`` identifica el
# archivo concreto, por lo que su ruta absoluta es estable desde PowerShell, CI
# y una compilación manual desde cualquier directorio.
PROJECT_ROOT = Path(SPEC).resolve().parent.parent

# Mantener los recursos junto al paquete ``app`` permite que el código que usa
# Path(__file__).parent / "static" funcione igual desde fuentes y congelado.
datas = [(str(PROJECT_ROOT / "app" / "static"), "app/static")]
datas += [(str(PROJECT_ROOT / "assets"), "assets")]
datas += collect_data_files("webview")
datas += copy_metadata("keyring")

binaries = collect_dynamic_libs("fitz") + collect_dynamic_libs("webview")
# Uvicorn resuelve por cadena sus formateadores, protocolos, bucles y ciclo de
# vida. El análisis estático no ve esas importaciones; recoger el paquete evita
# que el ejecutable falle al configurar el log de arranque.
hiddenimports = (
    ["app.main"]
    + collect_submodules("uvicorn")
    + collect_submodules("webview")
    # SecretStore importa keyring de forma diferida. Incluir sus backends evita
    # que la versión congelada caiga innecesariamente al respaldo local.
    + collect_submodules("keyring")
)

a = Analysis(
    [str(PROJECT_ROOT / "launcher.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AnaliticasClinicas",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(PROJECT_ROOT / "assets" / "logo.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AnaliticasClinicas",
)
