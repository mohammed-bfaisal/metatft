from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from .models import Move, ModuleName, Opponent, EnvironmentSignals
from .utils import compute_forgiveness_rate, noise_authenticity_test, compute_parole_interval, power_ratio_mode


@dataclass
class ModulePlan:
    module: ModuleName
    move: Move
    rationale: str
    confidence: float
    tactical_notes: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    action_style: str = "standard"


@dataclass
class ModifierOutcome:
    move: Move
    notes: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)


def _last_opp_move(opponent: Opponent) -> Optional[Move]:
    return opponent.history[-1].opponent_move if opponent.history else None


def _last_my_move(opponent: Opponent) -> Optional[Move]:
    return opponent.history[-1].my_move if opponent.history else None


def base_tft(opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
    last = _last_opp_move(opponent)
    if last is None:
        move = Move.COOPERATE
        rationale = "Start nice: cooperate first to test for reciprocal upside."
    elif last == Move.COOPERATE:
        move = Move.COOPERATE
        rationale = "Clean reciprocal loop detected, so mirror cooperation."
    else:
        move = Move.DEFECT
        rationale = "Opponent defected last round in a clean bilateral loop, so retaliate once."
    return ModulePlan(ModuleName.BASE_TFT, move, rationale, 0.88, ["Baseline policy for clean repeated bilateral play."], [])


def generous_tft(opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
    genuine_noise = noise_authenticity_test(opponent.history)
    p = compute_forgiveness_rate(signals.noise_estimate, genuine_noise)
    last = _last_opp_move(opponent)
    flags: List[str] = []
    if not genuine_noise:
        flags.append("NOISE_MAY_BE_STRATEGIC")

    consecutive_defects = 0
    for entry in reversed(opponent.history[-3:]):
        if entry.opponent_move == Move.DEFECT:
            consecutive_defects += 1
        else:
            break

    if consecutive_defects >= 3:
        move = Move.DEFECT
        rationale = "Three consecutive defections override noise forgiveness."
        flags.append("CONSECUTIVE_DEFECT_OVERRIDE")
    elif last == Move.DEFECT and random.random() < p:
        move = Move.COOPERATE
        rationale = f"Forgive once under noisy conditions (p={p:.2f}) to avoid a false retaliation spiral."
    elif last == Move.DEFECT:
        move = Move.DEFECT
        rationale = f"Defect this round because the forgiveness gate did not fire (p={p:.2f})."
    else:
        move = Move.COOPERATE
        rationale = "Noisy environment but no clear exploit signal, so preserve cooperation."

    return ModulePlan(
        ModuleName.GENEROUS_TFT,
        move,
        rationale,
        0.76,
        [f"Noise estimate ε≈{signals.noise_estimate:.2f}", f"Noise authenticity: {'genuine' if genuine_noise else 'suspicious'}"],
        flags,
        action_style="guarded_probe",
    )


def stake_and_signal(opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
    last = _last_opp_move(opponent)
    if last is None:
        move = Move.COOPERATE
        rationale = "One-shot or short-horizon game: open with a costly but bounded signal instead of blind trust."
    elif last == Move.COOPERATE:
        move = Move.COOPERATE
        rationale = "Reciprocal signal detected, so continue with constrained cooperation."
    else:
        move = Move.DEFECT
        rationale = "Signal was not reciprocated, so minimize exposure and avoid a cheap exploit."
    return ModulePlan(
        ModuleName.STAKE_AND_SIGNAL,
        move,
        rationale,
        0.72,
        ["Use escrow, deposits, public commitments, or verifiable concessions.", "Keep the first cooperative gesture limited in scope."],
        ["SHORT_HORIZON"],
        action_style="bounded_signal",
    )


def pavlov(opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
    if len(opponent.history) < 5:
        plan = base_tft(opponent, signals)
        plan.module = ModuleName.PAVLOV
        plan.tactical_notes.insert(0, "Using base behavior until a 5-round track record exists.")
        return plan
    last_my = _last_my_move(opponent)
    last_opp = _last_opp_move(opponent)
    if last_my is None or last_opp is None:
        return ModulePlan(ModuleName.PAVLOV, Move.COOPERATE, "Bootstrap cooperation.", 0.65)
    won = (last_my == Move.COOPERATE and last_opp == Move.COOPERATE) or (last_my == Move.DEFECT and last_opp == Move.COOPERATE)
    if won:
        move = last_my
        rationale = "Win-stay: the last pattern worked well enough, so repeat it."
    else:
        move = Move.COOPERATE if last_my == Move.DEFECT else Move.DEFECT
        rationale = "Lose-shift: the last pattern underperformed, so switch once to search for a better lock-in."
    return ModulePlan(ModuleName.PAVLOV, move, rationale, 0.74, ["Only use when impatience is independently credible."], ["IMPATIENCE_ACCELERATOR"])


def grim_with_parole(opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
    defect_rate = opponent.defection_rate()
    parole_k = compute_parole_interval(defect_rate)
    opponent.parole_interval = parole_k
    opponent.rounds_since_parole += 1
    if opponent.rounds_since_parole >= parole_k:
        opponent.rounds_since_parole = 0
        move = Move.COOPERATE
        rationale = "Scheduled parole probe: offer one limited reset opportunity without restoring full trust."
        flags = ["PAROLE_PROBE"]
    else:
        move = Move.DEFECT
        rationale = "Exploit pattern remains too strong, so stay in grim phase until the next probe."
        flags = ["GRIM_PHASE"]
    return ModulePlan(
        ModuleName.GRIM_WITH_PAROLE,
        move,
        rationale,
        0.84,
        [f"Defection rate: {defect_rate:.0%}", f"Parole interval: every {parole_k} rounds", "Use small probes, not full resets."],
        flags,
        action_style="containment",
    )


def network_tft(opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
    verified_rep = opponent.reputation_score * opponent.source_independence
    last = _last_opp_move(opponent)
    if verified_rep >= 0.55:
        move = Move.COOPERATE
        rationale = "Network evidence is strong enough to justify cooperation despite local ambiguity."
    elif verified_rep <= 0.25:
        move = Move.DEFECT
        rationale = "Network evidence is poor enough that bilateral generosity is too risky."
    else:
        move = Move.COOPERATE if last in (None, Move.COOPERATE) else Move.DEFECT
        rationale = "Network evidence is mixed, so fall back to the bilateral trace."
    return ModulePlan(
        ModuleName.NETWORK_TFT,
        move,
        rationale,
        0.77,
        [f"Raw reputation: {opponent.reputation_score:.2f}", f"Source independence: {opponent.source_independence:.2f}", f"Verified reputation: {verified_rep:.2f}"],
        ["NETWORKED_ENVIRONMENT"],
    )


def shadow_extender(opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
    last = _last_opp_move(opponent)
    move = Move.COOPERATE if last in (None, Move.COOPERATE) else Move.DEFECT
    rationale = "Known end-date detected, so convert this round into a reputation-carrying round rather than a terminal round."
    return ModulePlan(
        ModuleName.SHADOW_EXTENDER,
        move,
        rationale,
        0.71,
        ["Add durable stakes: records, future references, public commitments.", "If no shadow can be extended, drop toward Stake-and-Signal."],
        ["BOUNDED_GAME"],
        action_style="shadow_extension",
    )


def irrationality_mode(opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
    return ModulePlan(
        ModuleName.IRRATIONALITY_MODE,
        Move.DEFECT,
        "The opponent looks weakly responsive to incentives, so the goal shifts from cooperation to exposure control.",
        0.67,
        ["Keep engagement minimal.", "Document behavior.", "Shift attention to third-party shielding or exit."],
        ["IRRATIONALITY_OVERRIDE"],
        action_style="minimal_exposure",
    )


def commons_mode(opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
    return ModulePlan(
        ModuleName.COMMONS_MODE,
        Move.COOPERATE,
        "Commons logic is active, so bilateral retaliation would damage the shared pool more than it helps.",
        0.79,
        ["Make cooperative contributions visible.", "Push for rules, monitoring, and institutional enforcement."],
        ["COMMONS_OVERRIDE"],
        action_style="institutional_signal",
    )


def apply_power_modifier(move: Move, power_ratio: float) -> ModifierOutcome:
    mode = power_ratio_mode(power_ratio)
    if mode == "strategic_compliance":
        return ModifierOutcome(Move.COOPERATE, [f"Power modifier: ratio {power_ratio:.1f}:1 forced strategic compliance."], ["POWER_COMPLIANCE"])
    if mode == "modified_tft" and move == Move.DEFECT:
        if random.random() < 0.55:
            return ModifierOutcome(Move.COOPERATE, [f"Power modifier softened retaliation under ratio {power_ratio:.1f}:1."], ["POWER_SOFTENED_RETALIATION"])
    return ModifierOutcome(move, ["Power modifier left the move unchanged."], [])
