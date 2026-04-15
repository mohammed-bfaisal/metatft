import json
import os
from pathlib import Path
from .models import MetaTFTState

STATE_DIR = Path.home() / ".metatft"
STATE_FILE = STATE_DIR / "state.json"


def load_state() -> MetaTFTState:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            return MetaTFTState.from_dict(data)
        except Exception:
            return MetaTFTState()
    return MetaTFTState()


def save_state(state: MetaTFTState):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state.to_dict(), f, indent=2)


def export_opponent(state: MetaTFTState, name: str, path: str):
    if name not in state.opponents:
        raise ValueError(f"No opponent named '{name}'")
    opp = state.opponents[name]
    with open(path, "w") as f:
        json.dump(opp.to_dict(), f, indent=2)


def import_opponent(state: MetaTFTState, path: str):
    from .models import Opponent
    with open(path, "r") as f:
        data = json.load(f)
    opp = Opponent.from_dict(data)
    state.opponents[opp.name] = opp
    return opp
