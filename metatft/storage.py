from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import MetaTFTState, Opponent

STATE_DIR = Path.home() / '.metatft'
STATE_FILE = STATE_DIR / 'state.json'
EXPORT_DIR = STATE_DIR / 'exports'


def load_state() -> MetaTFTState:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            return MetaTFTState.from_dict(json.loads(STATE_FILE.read_text()))
        except Exception:
            return MetaTFTState()
    return MetaTFTState()


def save_state(state: MetaTFTState) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state.to_dict(), indent=2))


def export_opponent(opponent: Opponent, path: Optional[str] = None) -> str:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(path) if path else EXPORT_DIR / f"{opponent.name.replace(' ', '_').lower()}.json"
    out.write_text(json.dumps(opponent.to_dict(), indent=2))
    return str(out)


def import_opponent(path: str) -> Opponent:
    return Opponent.from_dict(json.loads(Path(path).read_text()))
