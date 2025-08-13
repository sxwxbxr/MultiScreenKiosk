# modules/utils/log_tools.py
from __future__ import annotations
import json
import re
from typing import Dict, Optional
from modules.utils.logger import get_log_path

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

def _parse_level(line: str) -> Optional[str]:
    s = line.strip()
    if not s:
        return None
    # JSON Modus
    if s.startswith("{") and s.endswith("}"):
        try:
            obj = json.loads(s)
            lv = obj.get("level")
            if isinstance(lv, str):
                u = lv.upper()
                return u if u in LEVELS else None
        except Exception:
            return None
    # Plain Modus: 2025-... LEVEL ...
    m = re.match(r"^\d{4}-\d{2}-\d{2}\s+\S+\s+([A-Z]+)\s", s)
    if m:
        u = m.group(1).upper()
        return u if u in LEVELS else None
    # Fallback: naive Suche
    for lv in LEVELS:
        if f" {lv} " in s:
            return lv
    return None

def compute_log_stats(path: Optional[str] = None) -> Dict[str, int]:
    path = path or get_log_path()
    counts: Dict[str, int] = {lv: 0 for lv in LEVELS}
    counts["TOTAL"] = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                lv = _parse_level(line)
                if lv:
                    counts[lv] += 1
                    counts["TOTAL"] += 1
    except FileNotFoundError:
        # nichts gefunden, counts bleiben 0
        pass
    return counts
