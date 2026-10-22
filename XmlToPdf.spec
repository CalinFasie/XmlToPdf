# PyInstaller onefile/windowed build. Paths are anchored to this spec file.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs


ROOT = Path(SPECPATH).resolve()
tray_datas, tray_binaries, tray_hiddenimports = collect_all("pystray")

a = Analysis(
    [str(ROOT / "tools" / "windows_entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=collect_dynamic_libs("lxml") + tray_binaries,
    datas=[
        (str(ROOT / "src" / "xmltopdf" / "templates"), "xmltopdf/templates"),
        (str(ROOT / "src" / "xmltopdf" / "static"), "xmltopdf/static"),
        *tray_datas,
    ],
    hiddenimports=tray_hiddenimports,
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
    a.binaries,
    a.datas,
    name="XmlToPdf",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
)
