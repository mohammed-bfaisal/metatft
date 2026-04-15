import math
import random
from typing import List
from .models import Move, RoundEntry


# ── Payoff matrix (Prisoner's Dilemma defaults) ──────────────────────────────
PAYOFF_MATRIX = {
    (Move.COOPERATE, Move.COOPERATE): (3, 3),   # mutual cooperation
    (Move.COOPERATE, Move.DEFECT):    (0, 5),   # sucker / exploiter
    (Move.DEFECT,    Move.COOPERATE): (5, 0),   # exploiter / sucker
    (Move.DEFECT,    Move.DEFECT):    (1, 1),   # mutual defection
}


def get_payoff(my_move: Move, opp_move: Move) -> tuple:
    return PAYOFF_MATRIX[(my_move, opp_move)]


# ── Noise estimate ────────────────────────────────────────────────────────────
def estimate_noise(history: List[RoundEntry], window: int = 20) -> float:
    """
    Bayesian estimate of channel noise rate.
    Noise = variance in opponent's move pattern unexplained by our moves.
    """
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 4:
        return 0.05  # prior

    # Look at transitions: C→D after we cooperated might be noise
    noise_signals = 0
    total = 0
    for i in range(1, len(recent)):
        prev = recent[i - 1]
        curr = recent[i]
        if prev.my_move == Move.COOPERATE and curr.opponent_move == Move.DEFECT:
            noise_signals += 1
        total += 1

    if total == 0:
        return 0.05
    raw = noise_signals / total
    # Bayesian update from prior 0.05
    prior = 0.05
    alpha, beta_param = 1 + noise_signals, 1 + (total - noise_signals)
    posterior = (alpha + prior * 10) / (alpha + beta_param + 10)
    return round(min(posterior, 0.40), 3)


def noise_authenticity_test(history: List[RoundEntry], window: int = 20) -> bool:
    """
    Runs test for randomness of defections.
    Returns True if defections appear genuinely random (noise),
    False if they cluster (strategic).
    Uses Wald-Wolfowitz runs test approximation.
    """
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 8:
        return True  # insufficient data, assume noise

    moves = [1 if r.opponent_move == Move.DEFECT else 0 for r in recent]
    n1 = sum(moves)
    n2 = len(moves) - n1

    if n1 == 0 or n2 == 0:
        return n1 == 0  # all cooperate = not noise; all defect = treat as strategic

    runs = 1
    for i in range(1, len(moves)):
        if moves[i] != moves[i - 1]:
            runs += 1

    expected_runs = (2 * n1 * n2) / (n1 + n2) + 1
    variance = (2 * n1 * n2 * (2 * n1 * n2 - n1 - n2)) / ((n1 + n2) ** 2 * (n1 + n2 - 1))

    if variance <= 0:
        return True

    z = (runs - expected_runs) / math.sqrt(variance)
    # If z < -1.96, significantly fewer runs than expected → clustering → strategic
    return z >= -1.96


# ── Parole interval ───────────────────────────────────────────────────────────
def compute_parole_interval(defection_rate: float, discount_factor: float = 0.85) -> int:
    if defection_rate <= 0:
        return 10
    raw = math.ceil(1 / defection_rate * (1 / max(discount_factor, 0.01)))
    return max(3, min(raw, 30))


# ── Forgiveness rate ──────────────────────────────────────────────────────────
def compute_forgiveness_rate(noise_estimate: float, is_genuine_noise: bool) -> float:
    base = min(noise_estimate * 1.5, 0.25)
    if not is_genuine_noise:
        base *= 0.5
    return round(base, 3)


# ── EV projection ─────────────────────────────────────────────────────────────
def project_ev(history: List[RoundEntry], horizon: int = 10, decay: float = 0.85) -> float:
    """Simple EV projection: extrapolate recent payoff trend forward."""
    if not history:
        return 1.5  # neutral baseline

    recent = history[-5:] if len(history) >= 5 else history
    avg_recent = sum(r.payoff for r in recent) / len(recent)

    # Trend: is payoff improving or degrading?
    if len(recent) >= 3:
        first_half = sum(r.payoff for r in recent[:len(recent)//2]) / max(len(recent)//2, 1)
        second_half = sum(r.payoff for r in recent[len(recent)//2:]) / max(len(recent) - len(recent)//2, 1)
        trend = second_half - first_half
    else:
        trend = 0

    projected = avg_recent + trend * 0.5
    discounted_sum = projected * (1 - decay ** horizon) / (1 - decay)
    return round(discounted_sum, 2)


# ── GTFO score ────────────────────────────────────────────────────────────────
def compute_gtfo_score(
    cooperation_deficit: float,
    ev_recovery: float,
    rounds_remaining: int
) -> float:
    denominator = ev_recovery * max(rounds_remaining, 1)
    if denominator <= 0:
        return float('inf')
    return round(cooperation_deficit / denominator, 3)


# ── Power ratio ───────────────────────────────────────────────────────────────
def power_ratio_mode(ratio: float) -> str:
    if ratio < 2.0:
        return "normal"
    elif ratio < 5.0:
        return "modified_tft"
    else:
        return "strategic_compliance"


# ── Stochastic switch guard ───────────────────────────────────────────────────
def should_switch(signal_triggered: bool, stochastic_block: float = 0.15) -> bool:
    if not signal_triggered:
        return False
    return random.random() > stochastic_block
