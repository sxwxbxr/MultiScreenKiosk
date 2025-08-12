from dataclasses import dataclass
from enum import Enum
from typing import Literal

class ViewMode(str, Enum):
    SINGLE = "single"
    QUAD = "quad"

@dataclass
class AppState:
    start_mode: Literal["single","quad"] = "single"
    active_index: int = 0

    @property
    def mode(self) -> ViewMode:
        return ViewMode(self.start_mode)

    def toggle_mode(self):
        self.start_mode = "quad" if self.start_mode == "single" else "single"

    def set_active(self, idx: int):
        self.active_index = max(0, min(3, idx))
# This module defines the application state for the Kiosk application.