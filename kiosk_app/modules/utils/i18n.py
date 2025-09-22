import json
import locale
from typing import Dict, Iterable, List, NamedTuple

from PyQt5.QtCore import QObject, pyqtSignal as Signal

from modules.utils.resource_loader import get_resource_dir


class LanguageInfo(NamedTuple):
    code: str
    name: str
    native_name: str


def _normalize_language_code(code: str) -> str:
    if not code:
        return ""
    lowered = code.lower()
    for sep in ("_", "-"):
        if sep in lowered:
            lowered = lowered.split(sep, 1)[0]
            break
    return lowered


def _detect_system_language(available: Iterable[str], fallback: str) -> str:
    try:
        lang, _ = locale.getdefaultlocale()
        normalized = _normalize_language_code(lang or "")
        if normalized and normalized in available:
            return normalized
    except Exception:
        pass
    return fallback if fallback in available else (next(iter(available), fallback))


class LanguageManager(QObject):
    language_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._translations: Dict[str, Dict[str, str]] = {}
        self._meta: Dict[str, Dict[str, str]] = {}
        self._fallback = "en"
        self._lang = "en"
        self.reload()
        self._lang = _detect_system_language(self._translations.keys(), self._fallback)

    def reload(self) -> None:
        translations: Dict[str, Dict[str, str]] = {}
        meta: Dict[str, Dict[str, str]] = {}

        translation_dir = get_resource_dir("assets/i18n")
        if translation_dir and translation_dir.exists():
            for file_path in sorted(translation_dir.glob("*.json")):
                code = _normalize_language_code(file_path.stem)
                if not code:
                    continue
                try:
                    with file_path.open("r", encoding="utf-8") as handle:
                        raw = json.load(handle)
                except Exception:
                    continue

                if not isinstance(raw, dict):
                    continue

                meta_info = {}
                if "__meta__" in raw and isinstance(raw["__meta__"], dict):
                    meta_info = {str(k): str(v) for k, v in raw["__meta__"].items() if isinstance(k, str)}
                    strings = {k: v for k, v in raw.items() if k != "__meta__"}
                else:
                    strings = raw

                translations[code] = {
                    str(key): str(value)
                    for key, value in strings.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
                meta[code] = {
                    "name": meta_info.get("name", code),
                    "native_name": meta_info.get(
                        "native",
                        meta_info.get("native_name", meta_info.get("name", code)),
                    ),
                }

        if not translations:
            translations = {"en": {}}
            meta = {"en": {"name": "English", "native_name": "English"}}

        self._translations = translations
        self._meta = meta

        if self._fallback not in self._translations:
            self._fallback = "en" if "en" in self._translations else next(iter(self._translations.keys()))
        if self._lang not in self._translations:
            self._lang = self._fallback

    def available_languages(self) -> List[LanguageInfo]:
        langs: List[LanguageInfo] = []
        for code in sorted(self._translations.keys()):
            info = self._meta.get(code, {})
            langs.append(
                LanguageInfo(
                    code=code,
                    name=info.get("name", code),
                    native_name=info.get("native_name", code),
                )
            )
        return langs

    def tr(self, key: str, **kwargs) -> str:
        text = self._translations.get(self._lang, {}).get(key)
        if text is None and self._fallback:
            text = self._translations.get(self._fallback, {}).get(key)
        if text is None:
            text = key
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def set_language(self, lang: str) -> None:
        normalized = _normalize_language_code(lang)
        if not normalized:
            return
        if normalized not in self._translations:
            normalized = self._fallback
        if normalized and normalized != self._lang:
            self._lang = normalized
            self.language_changed.emit(normalized)

    def get_language(self) -> str:
        return self._lang


i18n = LanguageManager()
tr = i18n.tr
