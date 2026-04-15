from __future__ import annotations

import math
import random
from statistics import pstdev
from typing import Iterable, List, Tuple

from .models import Move, RoundEntry


PAYOFF_MATRIX = {
    (Move.COOPERATE, Move.COOPERATE): (3, 3),
    (Move.COOPERATE, Move.DEFECT): (0, 5),
    (Move.DEFECT, Move.COOPERATE): (5, 0),
    (Move.DEFECT, Move.DEFECT): (1, 1),
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def get_payoff(my_move: Move, opp_move: Move) -> Tuple[int, int]:
    return PAYOFF_MATRIX[(my_move, opp_move)]


def weighted_recent_values(values: Iterable[float], decay: float = 0.85) -> float:
    seq = list(values)
    if not seq:
        return 0.0
    weights = [decay ** i for i in range(len(seq) - 1, -1, -1)]
    denom = sum(weights) or 1.0
    return sum(v * w for v, w in zip(seq, weights)) / denom


def estimate_noise(history: List[RoundEntry], window: int = 20) -> float:
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 4:
        return 0.05

    ambiguous_flips = 0
    total_checks = 0
    opportunistic_spikes = 0

    for i in range(1, len(recent)):
        prev = recent[i - 1]
        cur = recent[i]
        total_checks += 1
        if prev.my_move == Move.COOPERATE and cur.opponent_move == Move.DEFECT:
            ambiguous_flips += 1
        if prev.my_move == Move.COOPERATE and cur.opponent_move == Move.DEFECT and prev.payoff >= 3:
            opportunistic_spikes += 1

    raw = ambiguous_flips / max(total_checks, 1)
    opportunism_penalty = opportunistic_spikes / max(total_checks, 1)
    estimate = 0.05 + 0.6 * raw - 0.25 * opportunism_penalty
    return round(clamp(estimate, 0.01, 0.40), 3)


def noise_authenticity_test(history: List[RoundEntry], window: int = 20) -> bool:
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 8:
        return True

    bits = [1 if r.opponent_move == Move.DEFECT else 0 for r in recent]
    n1 = sum(bits)
    n2 = len(bits) - n1
    if n1 == 0:
        return True
    if n2 == 0:
        return False

    runs = 1
    for i in range(1, len(bits)):
        if bits[i] != bits[i - 1]:
            runs += 1

    expected_runs = (2 * n1 * n2) / (n1 + n2) + 1
    variance = (2 * n1 * n2 * (2 * n1 * n2 - n1 - n2)) / (((n1 + n2) ** 2) * (n1 + n2 - 1))
    if variance <= 0:
        return True
    z = (runs - expected_runs) / math.sqrt(variance)
    clustered = z < -1.96

    payoff_timed_defections = 0
    for i in range(1, len(recent)):
        prev = recent[i - 1]
        cur = recent[i]
        if prev.my_move == Move.COOPERATE and prev.payoff >= 3 and cur.opponent_move == Move.DEFECT:
            payoff_timed_defections += 1
    strategic_pattern = payoff_timed_defections >= max(2, len(recent) // 5)
    return not (clustered or strategic_pattern)


def compute_parole_interval(defection_rate: float, discount_factor: float = 0.85) -> int:
    if defection_rate <= 0:
        return 10
    raw = math.ceil((1 / defection_rate) * (1 / max(discount_factor, 0.01)))
    return int(clamp(raw, 3, 30))


def compute_forgiveness_rate(noise_estimate: float, is_genuine_noise: bool) -> float:
    base = min(noise_estimate * 1.5, 0.25)
    if not is_genuine_noise:
        base *= 0.5
    return round(clamp(base, 0.02, 0.25), 3)


def project_ev(history: List[RoundEntry], horizon: int = 10, decay: float = 0.85) -> float:
    if not history:
        return 1.5
    recent = history[-5:] if len(history) >= 5 else history
    avg_recent = sum(r.payoff for r in recent) / len(recent)
    if len(recent) >= 3:
        first = sum(r.payoff for r in recent[: len(recent) // 2]) / max(len(recent) // 2, 1)
        second = sum(r.payoff for r in recent[len(recent) // 2 :]) / max(len(recent) - len(recent) // 2, 1)
        trend = second - first
    else:
        trend = 0.0
    per_round_projection = clamp(avg_recent + trend * 0.35, 0.0, 5.0)
    discounted = per_round_projection * (1 - decay ** horizon) / (1 - decay)
    return round(discounted, 2)


def compute_gtfo_score(cooperation_deficit: float, ev_recovery_total: float) -> float:
    if ev_recovery_total <= 0:
        return float("inf")
    return round(cooperation_deficit / ev_recovery_total, 3)


def power_ratio_mode(ratio: float) -> str:
    if ratio < 2.0:
        return "normal"
    if ratio < 5.0:
        return "modified_tft"
    return "strategic_compliance"


def should_switch(signal_triggered: bool, stochastic_block: float = 0.15) -> bool:
    if not signal_triggered:
        return False
    return random.random() > stochastic_block


def ascii_bar(value: float, width: int = 10) -> str:
    value = clamp(value, 0.0, 1.0)
    filled = int(round(value * width))
    return "█" * filled + "░" * (width - filled)


def cooperation_timeline(history: List[RoundEntry], width: int = 15) -> Tuple[str, str, str]:
    recent = history[-width:]
    rounds = " ".join(f"{r.round_num:02d}" for r in recent)
    my = " ".join("C" if r.my_move == Move.COOPERATE else "D" for r in recent)
    opp = " ".join("C" if r.opponent_move == Move.COOPERATE else "D" for r in recent)
    return rounds, my, opp


def trust_score(history: List[RoundEntry]) -> float:
    if not history:
        return 0.5
    rates = [1.0 if r.opponent_move == Move.COOPERATE else 0.0 for r in history[-10:]]
    base = weighted_recent_values(rates)
    volatility = pstdev(rates) if len(rates) > 1 else 0.0
    return round(clamp(base - 0.2 * volatility, 0.0, 1.0), 3)
