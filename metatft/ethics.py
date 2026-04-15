from dataclasses import dataclass
from .models import Move, EnvironmentSignals, Opponent, OpponentFlag


@dataclass
class EthicsVetoResult:
    vetoed: bool
    reason: str
    overridden_move: Move
    constraint_triggered: int  # 1, 2, or 3


def ethics_veto(result, signals, opponent: Opponent, settings: dict) -> EthicsVetoResult:
    """
    Always-on ethics layer. Three hard constraints.
    Runs BEFORE move is enacted. Cannot be overridden by any module.
    """
    from .modules import ModuleResult

    move = result.recommended_move
    fairness_mult = settings.get("fairness_multiplier", 3.0)

    # Constraint 3: Categorical exit — check first (highest priority)
    # Flagged externally via opponent notes or classification
    if "CATEGORICAL_HARM" in (opponent.notes or "").upper():
        return EthicsVetoResult(
            vetoed=True,
            reason="Constraint 3: Opponent's goals require harm to third parties not party to this game. Categorical exit triggered.",
            overridden_move=Move.DEFECT,
            constraint_triggered=3,
        )

    # Constraint 1: No third-party harm
    # If opponent is cooperative but context suggests collusion at others' expense
    if "THIRD_PARTY_HARM" in result.flags:
        return EthicsVetoResult(
            vetoed=True,
            reason="Constraint 1: Cooperation with this actor would harm uninvolved third parties.",
            overridden_move=Move.DEFECT,
            constraint_triggered=1,
        )

    # Constraint 2: Fairness floor
    # Don't exploit significant power asymmetry IN YOUR FAVOR
    # If we're about to defect against an opponent who can't retaliate
    if move == Move.DEFECT and opponent.classification == OpponentFlag.COOPERATIVE:
        if len(opponent.history) >= 3:
            recent_coop = sum(
                1 for r in opponent.history[-5:]
                if r.opponent_move == Move.COOPERATE
            )
            # If opponent is 80%+ cooperative and we're defecting unprovoked
            if recent_coop / min(5, len(opponent.history)) >= 0.80:
                return EthicsVetoResult(
                    vetoed=True,
                    reason=f"Constraint 2: Fairness floor — defecting against consistently cooperative opponent violates fairness multiplier ({fairness_mult}x). Overriding to cooperate.",
                    overridden_move=Move.COOPERATE,
                    constraint_triggered=2,
                )

    return EthicsVetoResult(
        vetoed=False,
        reason="No ethics constraints triggered.",
        overridden_move=move,
        constraint_triggered=0,
    )
