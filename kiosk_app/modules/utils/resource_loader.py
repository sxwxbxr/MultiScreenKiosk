"""Helpers to access bundled assets regardless of runtime environment.

This module provides a thin abstraction for reading non-Python resources that
ship with the ``modules`` package.  During development the assets live on the
filesystem next to the sources, while frozen builds (PyInstaller) may unpack
them to a temporary directory.  Some launchers forget to pass ``--add-data``
flags which causes the splash animation or default config to be missing.  By
materialising resources on demand via :func:`pkgutil.get_data` we make sure the
files are always available and also hint PyInstaller to include them.
"""

from __future__ import annotations

import atexit
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from pkgutil import get_data
from typing import Dict, Iterable, List, Optional

PACKAGE_NAME = "modules"
MODULE_ROOT = Path(__file__).resolve().parent.parent

# Create a dedicated temporary directory for materialised resources.  We keep
# the directory for the lifetime of the interpreter so Qt can access the files
# while the application is running, then clean it up at exit.
_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="msk_assets_"))
atexit.register(shutil.rmtree, _TEMP_ROOT, ignore_errors=True)


def _collect_resource_relpaths() -> List[str]:
    """Return relative POSIX paths of known resource files."""

    paths: List[str] = []
    cfg = MODULE_ROOT / "config.json"
    if cfg.exists():
        paths.append("config.json")

    assets_root = MODULE_ROOT / "assets"
    if assets_root.exists():
        for file_path in assets_root.rglob("*"):
            if file_path.is_file():
                rel = file_path.relative_to(MODULE_ROOT).as_posix()
                paths.append(rel)

    return paths


_ALL_RESOURCES: List[str] = sorted(set(_collect_resource_relpaths()))
_DATA_CACHE: Dict[str, bytes] = {}
_PATH_CACHE: Dict[str, Path] = {}

# Map directory names to contained resource files for quick extraction when a
# caller requests a directory.
_DIR_CONTENTS: Dict[str, List[str]] = {}
for _rel in _ALL_RESOURCES:
    parent = str(PurePosixPath(_rel).parent)
    _DIR_CONTENTS.setdefault(parent, []).append(_rel)


def _normalise(relative: str) -> str:
    return str(PurePosixPath(relative))


def _load_bytes(relative: str) -> Optional[bytes]:
    """Return resource bytes either from cache or via ``pkgutil``."""

    rel = _normalise(relative)
    if rel in _DATA_CACHE:
        return _DATA_CACHE[rel]

    try:
        data = get_data(PACKAGE_NAME, rel)
    except Exception:
        data = None

    if data:
        _DATA_CACHE[rel] = data
    return data


# Hint PyInstaller that these data files are required.  When the analysis step
# sees the literal ``get_data`` calls it will bundle the matching resources even
# if users forget ``--add-data``.
for _hint in _ALL_RESOURCES:
    try:  # pragma: no cover - import side effect only used in frozen builds
        if _hint not in _DATA_CACHE:
            value = get_data(PACKAGE_NAME, _hint)
            if value:
                _DATA_CACHE[_hint] = value
    except Exception:
        pass


def load_resource_bytes(relative: str) -> Optional[bytes]:
    """Return the raw bytes of a packaged resource if available."""

    return _load_bytes(relative)


def load_resource_text(relative: str, encoding: str = "utf-8") -> Optional[str]:
    """Return a decoded string representation of a resource file."""

    data = load_resource_bytes(relative)
    if data is None:
        return None
    try:
        return data.decode(encoding)
    except Exception:
        return None


def get_resource_path(relative: str) -> Optional[Path]:
    """Materialise ``relative`` resource file and return a filesystem path."""

    rel = _normalise(relative)

    candidate = MODULE_ROOT / rel
    if candidate.exists():
        return candidate

    if rel in _PATH_CACHE and _PATH_CACHE[rel].exists():
        return _PATH_CACHE[rel]

    data = _load_bytes(rel)
    if data is None:
        return None

    target = _TEMP_ROOT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(data)

    _PATH_CACHE[rel] = target
    return target


def get_resource_dir(relative: str) -> Optional[Path]:
    """Ensure all files within ``relative`` directory are available locally."""

    rel = _normalise(relative)

    candidate = MODULE_ROOT / rel
    if candidate.exists():
        return candidate

    members: Iterable[str] = _DIR_CONTENTS.get(rel, [])
    if not members:
        # Fall back to a slow prefix search for directories that contain
        # sub-directories.
        prefix = f"{rel}/" if rel and rel != "." else ""
        members = [name for name in _ALL_RESOURCES if name.startswith(prefix)]
        if not members:
            return None

    for child in members:
        get_resource_path(child)

    target_dir = _TEMP_ROOT / rel
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir

