from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from .models import EnvironmentSignals, ModuleName, Move, Opponent
from .utils import compute_forgiveness_rate, compute_parole_interval, noise_authenticity_test, power_ratio_mode


@dataclass
class ModulePlan:
    module: ModuleName
    move: Move
    rationale: str
    confidence: float
    tactical_notes: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    action_style: str = 'standard'


@dataclass
class ModifierOutcome:
    move: Move
    notes: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)


def _last_opp_move(opponent: Opponent) -> Optional[Move]:
    return opponent.history[-1].opponent_move if opponent.history else None


def _last_my_move(opponent: Opponent) -> Optional[Move]:
    return opponent.history[-1].my_move if opponent.history else None


def base_tft(opponent: Opponent, _: EnvironmentSignals) -> ModulePlan:
    last = _last_opp_move(opponent)
    if last is None:
        return ModulePlan(ModuleName.BASE_TFT, Move.COOPERATE, 'Start nice and test for reciprocal upside.', 0.88, ['Baseline policy for clean repeated bilateral play.'])
    if last == Move.COOPERATE:
        return ModulePlan(ModuleName.BASE_TFT, Move.COOPERATE, 'Mirror cooperation in a clean reciprocal loop.', 0.88, ['Continue stable reciprocity.'])
    return ModulePlan(ModuleName.BASE_TFT, Move.DEFECT, 'Retaliate once after a clear defection in a clean loop.', 0.88, ['Single-round retaliation keeps incentives aligned.'])


def generous_tft(opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
    genuine_noise = noise_authenticity_test(opponent.history)
    p = compute_forgiveness_rate(signals.noise_estimate, genuine_noise)
    last = _last_opp_move(opponent)
    flags: List[str] = []
    if not genuine_noise:
        flags.append('NOISE_MAY_BE_STRATEGIC')
    consecutive_defects = 0
    for entry in reversed(opponent.history[-3:]):
        if entry.opponent_move == Move.DEFECT:
            consecutive_defects += 1
        else:
            break
    if consecutive_defects >= 3:
        return ModulePlan(ModuleName.GENEROUS_TFT, Move.DEFECT, 'Three consecutive defections override noise forgiveness.', 0.76, [f'Forgiveness gate p={p:.2f}'], flags + ['CONSECUTIVE_DEFECT_OVERRIDE'], 'guarded_probe')
    if last == Move.DEFECT and random.random() < p:
        return ModulePlan(ModuleName.GENEROUS_TFT, Move.COOPERATE, f'Forgive once under noisy conditions (p={p:.2f}) to prevent a false escalation spiral.', 0.76, [f'Noise estimate ε≈{signals.noise_estimate:.2f}'], flags, 'guarded_probe')
    if last == Move.DEFECT:
        return ModulePlan(ModuleName.GENEROUS_TFT, Move.DEFECT, f'Defect this round because the forgiveness gate did not fire (p={p:.2f}).', 0.76, [f'Noise estimate ε≈{signals.noise_estimate:.2f}'], flags, 'guarded_probe')
    return ModulePlan(ModuleName.GENEROUS_TFT, Move.COOPERATE, 'No clear exploit signal in a noisy environment, so preserve cooperation.', 0.76, [f'Noise estimate ε≈{signals.noise_estimate:.2f}'], flags, 'guarded_probe')


def stake_and_signal(opponent: Opponent, _: EnvironmentSignals) -> ModulePlan:
    last = _last_opp_move(opponent)
    if last is None:
        move, why = Move.COOPERATE, 'Open with a bounded costly signal instead of blind trust.'
    elif last == Move.COOPERATE:
        move, why = Move.COOPERATE, 'Reciprocal signal detected, so continue with constrained cooperation.'
    else:
        move, why = Move.DEFECT, 'Signal was not reciprocated, so minimize exposure.'
    return ModulePlan(ModuleName.STAKE_AND_SIGNAL, move, why, 0.72, ['Use escrow, deposits, or public commitments.', 'Keep the first gesture narrow.'], ['SHORT_HORIZON'], 'bounded_signal')


def pavlov(opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
    if len(opponent.history) < 5:
        plan = base_tft(opponent, signals)
        plan.module = ModuleName.PAVLOV
        plan.tactical_notes.insert(0, 'Use base behavior until a 5-round track record exists.')
        return plan
    last_my = _last_my_move(opponent)
    last_opp = _last_opp_move(opponent)
    if last_my is None or last_opp is None:
        return ModulePlan(ModuleName.PAVLOV, Move.COOPERATE, 'Bootstrap cooperation.', 0.65)
    won = (last_my == Move.COOPERATE and last_opp == Move.COOPERATE) or (last_my == Move.DEFECT and last_opp == Move.COOPERATE)
    if won:
        move, why = last_my, 'Win-stay: the last pattern worked well enough, so repeat it.'
    else:
        move = Move.COOPERATE if last_my == Move.DEFECT else Move.DEFECT
        why = 'Lose-shift: switch once to search for a better lock-in.'
    return ModulePlan(ModuleName.PAVLOV, move, why, 0.74, ['Use only when impatience is independently credible.'], ['IMPATIENCE_ACCELERATOR'])


def grim_with_parole(opponent: Opponent, _: EnvironmentSignals) -> ModulePlan:
    defect_rate = opponent.defection_rate()
    parole_k = compute_parole_interval(defect_rate)
    opponent.parole_interval = parole_k
    opponent.rounds_since_parole += 1
    if opponent.rounds_since_parole >= parole_k:
        opponent.rounds_since_parole = 0
        return ModulePlan(ModuleName.GRIM_WITH_PAROLE, Move.COOPERATE, 'Scheduled parole probe: offer one small reset opportunity.', 0.84, [f'Parole interval: every {parole_k} rounds', 'Use small probes, not full resets.'], ['PAROLE_PROBE'], 'containment')
    return ModulePlan(ModuleName.GRIM_WITH_PAROLE, Move.DEFECT, 'Exploit pattern remains too strong, so stay in grim phase.', 0.84, [f'Defection rate: {defect_rate:.0%}', f'Parole interval: every {parole_k} rounds'], ['GRIM_PHASE'], 'containment')


def network_tft(opponent: Opponent, _: EnvironmentSignals) -> ModulePlan:
    verified_rep = opponent.reputation_score * opponent.source_independence
    last = _last_opp_move(opponent)
    if verified_rep >= 0.55:
        move, why = Move.COOPERATE, 'Network evidence is strong enough to justify cooperation despite local ambiguity.'
    elif verified_rep <= 0.25:
        move, why = Move.DEFECT, 'Network evidence is poor enough that bilateral generosity is too risky.'
    else:
        move = Move.COOPERATE if last in (None, Move.COOPERATE) else Move.DEFECT
        why = 'Network evidence is mixed, so fall back to the bilateral trace.'
    return ModulePlan(ModuleName.NETWORK_TFT, move, why, 0.77, [f'Verified reputation: {verified_rep:.2f}'], ['NETWORKED_ENVIRONMENT'])


def shadow_extender(opponent: Opponent, _: EnvironmentSignals) -> ModulePlan:
    last = _last_opp_move(opponent)
    move = Move.COOPERATE if last in (None, Move.COOPERATE) else Move.DEFECT
    return ModulePlan(ModuleName.SHADOW_EXTENDER, move, 'Known end-date detected, so make this round reputation-carrying instead of terminal.', 0.71, ['Add durable stakes: records, references, or future commitments.', 'If no shadow can be extended, fall back toward Stake-and-Signal.'], ['BOUNDED_GAME'], 'shadow_extension')


def irrationality_mode(_: Opponent, __: EnvironmentSignals) -> ModulePlan:
    return ModulePlan(ModuleName.IRRATIONALITY_MODE, Move.DEFECT, 'The opponent looks weakly responsive to incentives, so the goal shifts to exposure control.', 0.67, ['Keep engagement minimal.', 'Document behavior.', 'Shift attention to shielding or exit.'], ['IRRATIONALITY_OVERRIDE'], 'minimal_exposure')


def commons_mode(_: Opponent, __: EnvironmentSignals) -> ModulePlan:
    return ModulePlan(ModuleName.COMMONS_MODE, Move.COOPERATE, 'Commons logic is active, so bilateral retaliation would damage the shared pool.', 0.79, ['Make cooperative contributions visible.', 'Push for rules, monitoring, and institutional enforcement.'], ['COMMONS_OVERRIDE'], 'institutional_signal')


def apply_power_modifier(move: Move, power_ratio: float) -> ModifierOutcome:
    mode = power_ratio_mode(power_ratio)
    if mode == 'strategic_compliance':
        return ModifierOutcome(Move.COOPERATE, [f'Power modifier: ratio {power_ratio:.1f}:1 forced strategic compliance.'], ['POWER_COMPLIANCE'])
    if mode == 'modified_tft' and move == Move.DEFECT and random.random() < 0.55:
        return ModifierOutcome(Move.COOPERATE, [f'Power modifier softened retaliation under ratio {power_ratio:.1f}:1.'], ['POWER_SOFTENED_RETALIATION'])
    return ModifierOutcome(move, ['Power modifier left the move unchanged.'], [])
