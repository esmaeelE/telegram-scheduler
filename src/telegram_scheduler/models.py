from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class SendResult:
    contact: str
    ok: bool
    action: str
    scheduled_for: str | None = None
    error: str | None = None
    attempts: int = 0


def results_to_json(results: list[SendResult]) -> list[dict[str, Any]]:
    return [asdict(result) for result in results]
