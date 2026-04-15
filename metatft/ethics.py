from __future__ import annotations

from dataclasses import dataclass

from .models import Move, Opponent, EnvironmentSignals


@dataclass
class EthicsVetoResult:
    vetoed: bool
    overridden_move: Move
    reason: str = ""


def ethics_veto(recommended_move: Move, signals: EnvironmentSignals, opponent: Opponent, settings: dict) -> EthicsVetoResult:
    notes = (opponent.notes or "").lower()
    if "categorical_harm" in notes or "third-party harm" in notes:
        return EthicsVetoResult(True, Move.DEFECT, "Ethics veto: do not cooperate into third-party harm.")

    if signals.power_ratio >= settings.get("fairness_multiplier", 3.0) and recommended_move == Move.DEFECT:
        return EthicsVetoResult(True, Move.COOPERATE, "Ethics veto: retaliation would exploit a severe power asymmetry.")

    return EthicsVetoResult(False, recommended_move, "")
