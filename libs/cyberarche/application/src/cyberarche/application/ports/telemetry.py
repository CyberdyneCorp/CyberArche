"""Clock and ID ports so use cases stay deterministic and testable."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> datetime: ...


class IdPort(Protocol):
    def new_id(self) -> str: ...
