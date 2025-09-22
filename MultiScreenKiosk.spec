# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_root = Path(__file__).resolve().parent
modules_dir = project_root / "kiosk_app" / "modules"

# Application data bundles
_datas = [
    (str(modules_dir / "config.json"), "config.json"),
    (str(modules_dir / "assets"), "modules/assets"),
]

# Collect PyQt5 resources (equivalent to --collect-all PyQt5)
_pyqt5_datas, _pyqt5_binaries, _pyqt5_hiddenimports = collect_all("PyQt5")
_datas += _pyqt5_datas
_binaries = list(_pyqt5_binaries)
_hiddenimports = list(_pyqt5_hiddenimports)

# Collect PyQtWebEngine resources to ensure QtWebEngine assets are bundled
_pyqtwe_datas, _pyqtwe_binaries, _pyqtwe_hiddenimports = collect_all("PyQtWebEngine")
_datas += _pyqtwe_datas
for binary in _pyqtwe_binaries:
    if binary not in _binaries:
        _binaries.append(binary)
for hidden in _pyqtwe_hiddenimports:
    if hidden not in _hiddenimports:
        _hiddenimports.append(hidden)

# Bundle the MSVC runtime so the executable works on clean machines.
_msvc_dlls = [
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
]

if sys.platform == "win32":
    try:
        from PyInstaller.utils.win32.winmanifest import find_msvcr
    except Exception:
        def find_msvcr():  # type: ignore
            return []

    candidate_dirs = [
        Path(sys.prefix) / "DLLs",
        Path(sys.prefix),

        Path(sys.base_prefix) / "DLLs",
        Path(sys.base_prefix),
    ]

    system_root_env = os.environ.get("SystemRoot")
    system_root = Path(system_root_env) if system_root_env else Path(r"C:\\Windows")
    candidate_dirs.extend(

        [
            system_root / "System32",
            system_root / "SysWOW64",
        ]
    )


    dll_roots = []
    seen = set()
    for directory in candidate_dirs:
        resolved = directory.resolve()
        normalized = str(resolved).lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        dll_roots.append(resolved)

    found_by_pyinstaller = {}
    for resolved_path in find_msvcr() or []:
        path_obj = Path(resolved_path)
        found_by_pyinstaller[path_obj.name.lower()] = path_obj

    for dll_name in _msvc_dlls:
        dll_path = found_by_pyinstaller.get(dll_name.lower())
        if dll_path is None:
            for root in dll_roots:
                candidate = root / dll_name
                if candidate.exists():
                    dll_path = candidate
                    break
        if dll_path is None:
            search_paths = ", ".join(str(p) for p in dll_roots)
            raise FileNotFoundError(
                f"Unable to locate {dll_name} via PyInstaller's find_msvcr() or in directories: {search_paths}"
            )
        binary_entry = (str(dll_path), ".")
        if binary_entry not in _binaries:
            _binaries.append(binary_entry)
else:
    print("MSVC runtime DLL bundling is skipped because the build host is not Windows.")


a = Analysis(
    ['kiosk_app/modules/main.py'],
    pathex=[str(modules_dir)],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MultiScreenKiosk',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
