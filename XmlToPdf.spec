# PyInstaller onedir build. Invoke from the repository root with --distpath dist.
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs


ROOT = Path(SPECPATH).resolve()

a = Analysis(
    [str(ROOT / "tools" / "windows_entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=collect_dynamic_libs("lxml"),
    datas=[
        (str(ROOT / "src" / "xmltopdf" / "templates"), "xmltopdf/templates"),
        (str(ROOT / "src" / "xmltopdf" / "static"), "xmltopdf/static"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="XmlToPdf",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="XmlToPdf",
)
