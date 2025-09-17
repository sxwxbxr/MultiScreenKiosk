"""Utilities for evaluating and applying content schedules.

This module keeps the scheduling logic independent from the Qt UI so it can
be unit tested without a running event loop.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from .config_loader import PaneSchedule

Minutes = int


def _time_to_minutes(value: str) -> Optional[Minutes]:
    try:
        parts = value.split(":", 1)
        if len(parts) != 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
        if not (0 <= hour < 24 and 0 <= minute < 60):
            return None
        return hour * 60 + minute
    except Exception:
        return None


@dataclass
class _PreparedBlock:
    start: Minutes
    end: Minutes
    source: str

    def is_active(self, minute: Minutes) -> bool:
        if self.start == self.end:
            return True
        if self.start < self.end:
            return self.start <= minute < self.end
        # wrap around midnight
        return minute >= self.start or minute < self.end


class ContentScheduler:
    """Evaluates pane schedules for the current time."""

    def __init__(
        self,
        schedules: Iterable[PaneSchedule],
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._now = now_provider or datetime.now
        self._schedules: Dict[int, Tuple[Optional[str], List[_PreparedBlock]]] = {}
        self.update_schedules(schedules)

    @property
    def has_rules(self) -> bool:
        return bool(self._schedules)

    def update_schedules(self, schedules: Iterable[PaneSchedule]) -> None:
        prepared: Dict[int, Tuple[Optional[str], List[_PreparedBlock]]] = {}
        for entry in schedules:
            if entry is None:
                continue
            default = entry.default_source or None
            blocks: List[_PreparedBlock] = []
            for block in entry.blocks:
                start = _time_to_minutes(block.start)
                end = _time_to_minutes(block.end)
                if start is None or end is None:
                    continue
                if not block.source:
                    continue
                blocks.append(_PreparedBlock(start=start, end=end, source=block.source))
            if default is None and not blocks:
                continue
            prepared[entry.pane] = (default, blocks)
        self._schedules = prepared

    def _current_minute(self, now: Optional[datetime] = None) -> Minutes:
        ts = now or self._now()
        return ts.hour * 60 + ts.minute

    def current_assignments(self, now: Optional[datetime] = None) -> Dict[int, str]:
        minute = self._current_minute(now)
        result: Dict[int, str] = {}
        for pane, (default, blocks) in self._schedules.items():
            selected: Optional[str] = None
            for block in blocks:
                if block.is_active(minute):
                    selected = block.source
                    break
            if selected is None:
                selected = default
            if selected:
                result[pane] = selected
        return result


def compute_slot_assignments(
    num_sources: int,
    assignments: Dict[int, str],
    name_to_index: Dict[str, int],
) -> Tuple[List[int], List[Tuple[int, str, str]]]:
    """Resolve the schedule mapping to concrete source indices.

    Returns a tuple ``(indices, conflicts)`` where ``indices`` is a list mapping
    each pane index to a source index, and ``conflicts`` describes entries that
    could not be honoured exactly (unknown sources, duplicates, ...).
    """

    if num_sources <= 0:
        return [], []

    indices: List[int] = list(range(num_sources))
    conflicts: List[Tuple[int, str, str]] = []
    used: Dict[int, int] = {}

    def _next_free(excluded: Optional[int] = None) -> Optional[int]:
        for candidate in range(num_sources):
            if candidate == excluded:
                continue
            if candidate not in used:
                return candidate
        return None

    for pane in range(num_sources):
        name = assignments.get(pane)
        chosen: Optional[int] = None
        reason: Optional[str] = None

        if name:
            chosen = name_to_index.get(name)
            if chosen is None:
                reason = "unknown source"
        if chosen is None:
            chosen = pane

        if chosen in used:
            reason = reason or "source already in use"
            fallback = _next_free()
            if fallback is not None:
                chosen = fallback
            else:
                chosen = pane

        indices[pane] = chosen
        used[chosen] = pane
        if reason:
            conflicts.append((pane, name or "", reason))

    return indices, conflicts


__all__ = ["ContentScheduler", "compute_slot_assignments"]
