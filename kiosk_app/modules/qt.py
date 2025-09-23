"""Compatibility layer that switches between PySide6 and PyQt6.

This module centralises the Qt binding selection so the rest of the code base
can stay agnostic and rely on a consistent API surface. The binding can be
forced via the ``MULTISCREENKIOSK_QT_API`` environment variable (``pyside6`` or
``pyqt6``). When unset the loader tries PySide6 first and then PyQt6.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Tuple

QT_API_ENV = os.environ.get("MULTISCREENKIOSK_QT_API", "").strip().lower()

if QT_API_ENV == "pyqt6":
    _BINDING_PREFERENCE: Tuple[str, ...] = ("PyQt6", "PySide6")
elif QT_API_ENV == "pyside6":
    _BINDING_PREFERENCE = ("PySide6", "PyQt6")
else:
    _BINDING_PREFERENCE = ("PySide6", "PyQt6")

QT_BINDING: str | None = None
QtCore = QtGui = QtWidgets = QtWebEngineWidgets = QtLottie = None  # type: ignore[assignment]
Signal = Slot = Property = None  # type: ignore[assignment]
_ERRORS: list[tuple[str, Exception]] = []

for name in _BINDING_PREFERENCE:
    try:
        if name == "PySide6":  # pragma: no cover - exercised in integration tests
            from PySide6 import QtCore as _QtCore  # type: ignore
            from PySide6 import QtGui as _QtGui  # type: ignore
            from PySide6 import QtWidgets as _QtWidgets  # type: ignore
            from PySide6 import QtWebEngineWidgets as _QtWebEngineWidgets  # type: ignore
            try:
                from PySide6 import QtLottie as _QtLottie  # type: ignore
            except Exception:  # pragma: no cover - optional dependency
                _QtLottie = None
            Signal = _QtCore.Signal
            Slot = _QtCore.Slot
            Property = _QtCore.Property
        else:
            from PyQt6 import QtCore as _QtCore  # type: ignore
            from PyQt6 import QtGui as _QtGui  # type: ignore
            from PyQt6 import QtWidgets as _QtWidgets  # type: ignore
            from PyQt6 import QtWebEngineWidgets as _QtWebEngineWidgets  # type: ignore
            try:
                from PyQt6 import QtLottie as _QtLottie  # type: ignore
            except Exception:  # pragma: no cover - optional dependency
                _QtLottie = None
            Signal = _QtCore.pyqtSignal  # type: ignore[attr-defined]
            Slot = _QtCore.pyqtSlot  # type: ignore[attr-defined]
            Property = _QtCore.pyqtProperty  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - import-time errors surface in CI
        _ERRORS.append((name, exc))
        continue

    QtCore = _QtCore
    QtGui = _QtGui
    QtWidgets = _QtWidgets
    QtWebEngineWidgets = _QtWebEngineWidgets
    QtLottie = _QtLottie
    QT_BINDING = name
    break

if QT_BINDING is None:  # pragma: no cover - makes failures easier to diagnose locally
    details = ", ".join(f"{name}: {exc}" for name, exc in _ERRORS) or "none"
    raise ImportError(
        "MultiScreenKiosk requires PySide6 or PyQt6 (with Qt WebEngine). "
        "Unable to import any binding. Details: " + details
    )

Qt = QtCore.Qt  # type: ignore[assignment]
IS_PYSIDE6 = QT_BINDING == "PySide6"
IS_PYQT6 = QT_BINDING == "PyQt6"


def _alias_qt_enum(target: Any, alias: str, path: Iterable[str]) -> None:
    obj = target
    for part in path:
        obj = getattr(obj, part, None)
        if obj is None:
            return
    if not hasattr(target, alias):
        setattr(target, alias, obj)


def _install_aliases() -> None:
    alias_map: Dict[str, Tuple[str, ...]] = {
        "AlignCenter": ("AlignmentFlag", "AlignCenter"),
        "AlignHCenter": ("AlignmentFlag", "AlignHCenter"),
        "AlignLeft": ("AlignmentFlag", "AlignLeft"),
        "AlignRight": ("AlignmentFlag", "AlignRight"),
        "AlignVCenter": ("AlignmentFlag", "AlignVCenter"),
        "Dialog": ("WindowType", "Dialog"),
        "FramelessWindowHint": ("WindowType", "FramelessWindowHint"),
        "LeftButton": ("MouseButton", "LeftButton"),
        "MatchExactly": ("MatchFlag", "MatchExactly"),
        "NonModal": ("WindowModality", "NonModal"),
        "ShiftModifier": ("KeyboardModifier", "ShiftModifier"),
        "SmoothTransformation": ("TransformationMode", "SmoothTransformation"),
        "SplashScreen": ("WindowType", "SplashScreen"),
        "StrongFocus": ("FocusPolicy", "StrongFocus"),
        "WA_DeleteOnClose": ("WidgetAttribute", "WA_DeleteOnClose"),
        "WA_DontCreateNativeAncestors": ("WidgetAttribute", "WA_DontCreateNativeAncestors"),
        "WA_NativeWindow": ("WidgetAttribute", "WA_NativeWindow"),
        "WA_TranslucentBackground": ("WidgetAttribute", "WA_TranslucentBackground"),
        "WA_TransparentForMouseEvents": ("WidgetAttribute", "WA_TransparentForMouseEvents"),
        "Window": ("WindowType", "Window"),
        "WindowContextHelpButtonHint": ("WindowType", "WindowContextHelpButtonHint"),
        "WindowMinimized": ("WindowState", "WindowMinimized"),
        "WindowStaysOnTopHint": ("WindowType", "WindowStaysOnTopHint"),
    }

    for alias, path in alias_map.items():
        _alias_qt_enum(Qt, alias, path)


_install_aliases()

if QtLottie is not None and hasattr(QtLottie, "QLottieAnimation"):
    QLottieAnimation = QtLottie.QLottieAnimation  # type: ignore[attr-defined]
else:
    QLottieAnimation = None

HAVE_QT_LOTTIE = QLottieAnimation is not None

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtWebEngineWidgets",
    "Qt",
    "Signal",
    "Slot",
    "Property",
    "QT_BINDING",
    "IS_PYSIDE6",
    "IS_PYQT6",
    "HAVE_QT_LOTTIE",
    "QLottieAnimation",
]
