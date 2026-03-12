# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the bugpilot CLI.
#
# Build with:
#   pyinstaller src/cli/bugpilot.spec --distpath dist --workpath build
#
# PyInstaller must be run on the target OS — cross-compilation is not supported.
# The GitHub Actions release workflow (release.yml) builds on each OS in a matrix.

import sys
from pathlib import Path

# Locate the CLI package root so imports resolve correctly.
# SPECPATH is the directory containing this .spec file (i.e. src/cli/).
cli_root = str(Path(SPECPATH))  # noqa: F821 — SPECPATH is injected by PyInstaller

a = Analysis(
    [str(Path(SPECPATH) / "bugpilot" / "main.py")],  # noqa: F821
    pathex=[cli_root],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Typer introspects click internals at runtime; ensure they are bundled.
        "click",
        "typer",
        "typer.main",
        "typer.core",
        # Rich console sub-modules loaded dynamically.
        "rich.console",
        "rich.table",
        "rich.panel",
        "rich.prompt",
        "rich.syntax",
        "rich.text",
        "rich.progress",
        # httpx transports resolved at runtime.
        "httpx._transports.default",
        "httpx._transports.asgi",
        # anyio backends — include both; the correct one is selected at runtime.
        "anyio._backends._asyncio",
        "anyio._backends._trio",
        # pydantic v2 uses Rust extensions; core module must be explicit.
        "pydantic",
        "pydantic.v1",
        "pydantic_core",
        # yaml loader.
        "yaml",
        # dateutil used for timestamp parsing.
        "dateutil",
        "dateutil.parser",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Never needed in a CLI binary.
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
        "IPython",
        "notebook",
        "pytest",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="bugpilot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,           # UPX compression — reduces binary size ~40 %
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,       # CLI tool — always console mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,   # use host arch; set to "x86_64" or "arm64" for explicit cross
    codesign_identity=None,   # set to your Developer ID for macOS notarization
    entitlements_file=None,
    icon=None,
)
