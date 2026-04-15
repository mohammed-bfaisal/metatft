import random
from dataclasses import dataclass
from typing import List, Optional
from .models import Move, ModuleName, Opponent, EnvironmentSignals, OpponentFlag
from .utils import (
    compute_forgiveness_rate, noise_authenticity_test,
    estimate_noise, compute_parole_interval
)


@dataclass
class ModuleResult:
    module: ModuleName
    recommended_move: Move
    rationale: str
    confidence: float
    tactical_notes: list
    flags: list


def _last_opp_move(opponent: Opponent) -> Optional[Move]:
    if opponent.history:
        return opponent.history[-1].opponent_move
    return None


def _last_my_move(opponent: Opponent) -> Optional[Move]:
    if opponent.history:
        return opponent.history[-1].my_move
    return None


# ── Module 1: Base TFT ────────────────────────────────────────────────────────
def base_tft(opponent: Opponent, signals: EnvironmentSignals) -> ModuleResult:
    last = _last_opp_move(opponent)
    if last is None:
        move = Move.COOPERATE
        rationale = "Round 1: always cooperate first (niceness principle)."
    elif last == Move.COOPERATE:
        move = Move.COOPERATE
        rationale = "Opponent cooperated last round. Mirror with cooperation."
    else:
        move = Move.DEFECT
        rationale = "Opponent defected last round. Mirror with defection (provocability)."

    return ModuleResult(
        module=ModuleName.BASE_TFT,
        recommended_move=move,
        rationale=rationale,
        confidence=0.90,
        tactical_notes=[
            "Clean iterated game detected — pure mirroring is optimal.",
            "Re-evaluate if noise or end-date signals emerge.",
        ],
        flags=[],
    )


# ── Module 2: Generous TFT ────────────────────────────────────────────────────
def generous_tft(opponent: Opponent, signals: EnvironmentSignals) -> ModuleResult:
    genuine_noise = noise_authenticity_test(opponent.history)
    forgive_rate = compute_forgiveness_rate(signals.noise_estimate, genuine_noise)

    last = _last_opp_move(opponent)
    flags = []

    if not genuine_noise:
        flags.append("NOISE_AUTHENTICITY_FAIL: defections appear clustered, not random — reducing forgiveness")

    # Check for 3 consecutive defections (override forgiveness)
    consecutive_defects = 0
    for entry in reversed(opponent.history[-3:]):
        if entry.opponent_move == Move.DEFECT:
            consecutive_defects += 1
        else:
            break

    if consecutive_defects >= 3:
        move = Move.DEFECT
        rationale = f"3 consecutive defections detected — forgiveness suspended. Punishing despite noisy channel."
        flags.append("CONSECUTIVE_DEFECT_OVERRIDE")
    elif last == Move.DEFECT:
        if random.random() < forgive_rate:
            move = Move.COOPERATE
            rationale = f"Opponent defected, but channel noise detected (ε≈{signals.noise_estimate:.2f}). Applying forgiveness (p={forgive_rate:.2f}) — cooperating."
        else:
            move = Move.DEFECT
            rationale = f"Opponent defected. Noise forgiveness roll failed (p={forgive_rate:.2f}) — defecting."
    elif last is None or last == Move.COOPERATE:
        move = Move.COOPERATE
        rationale = "Opponent cooperated (or round 1). Cooperating."
    else:
        move = Move.COOPERATE
        rationale = "Defaulting to cooperation under noisy conditions."

    return ModuleResult(
        module=ModuleName.GENEROUS_TFT,
        recommended_move=move,
        rationale=rationale,
        confidence=0.75,
        tactical_notes=[
            f"Noise estimate: ε = {signals.noise_estimate:.3f}",
            f"Forgiveness rate: p = {forgive_rate:.3f}",
            "Genuine noise: " + ("YES" if genuine_noise else "NO — may be strategic"),
            "3 consecutive defections always override forgiveness.",
        ],
        flags=flags,
    )


# ── Module 3: Stake-and-Signal ────────────────────────────────────────────────
def stake_and_signal(opponent: Opponent, signals: EnvironmentSignals) -> ModuleResult:
    rounds_played = len(opponent.history)

    if rounds_played == 0:
        move = Move.COOPERATE
        rationale = "Round 1 of one-shot game: open with a costly signal (cooperation + commitment)."
        notes = [
            "Lead with a verifiable commitment — something irrational to offer if you intend to defect.",
            "Examples: deposit, public statement, escrow, information surrender.",
            "Signal cost must exceed gain from defecting after signal.",
            "Watch for reciprocal signal from opponent next round.",
        ]
    elif rounds_played == 1:
        last = _last_opp_move(opponent)
        if last == Move.COOPERATE:
            move = Move.COOPERATE
            rationale = "Opponent reciprocated signal. Proceed with cooperation."
            notes = ["Signal exchange successful. Cooperate and monitor."]
        else:
            move = Move.DEFECT
            rationale = "Opponent did not reciprocate signal. Minimize exposure."
            notes = [
                "No signal reciprocation detected.",
                "Cooperate minimally and prepare to exit.",
                "Consider whether signal infrastructure exists at all.",
            ]
    else:
        defect_rate = opponent.defection_rate()
        if defect_rate > 0.5:
            move = Move.DEFECT
            rationale = "Sustained defection in short game. Exit mode."
            notes = ["High defection rate in limited-round game — exit when possible."]
        else:
            move = Move.COOPERATE
            rationale = "Cooperation established in short game. Maintain."
            notes = ["Short game with established cooperation — maintain through conclusion."]

    return ModuleResult(
        module=ModuleName.STAKE_AND_SIGNAL,
        recommended_move=move,
        rationale=rationale,
        confidence=0.70,
        tactical_notes=notes if 'notes' in dir() else [],
        flags=["ONE_SHOT_MODE"],
    )


# ── Module 4: Pavlov ──────────────────────────────────────────────────────────
def pavlov(opponent: Opponent, signals: EnvironmentSignals) -> ModuleResult:
    rounds_played = len(opponent.history)

    if rounds_played < 5:
        # Not enough history — fall back to base TFT
        result = base_tft(opponent, signals)
        result.module = ModuleName.PAVLOV
        result.tactical_notes.insert(0, "Insufficient history for Pavlov (<5 rounds). Using base TFT temporarily.")
        return result

    last_my = _last_my_move(opponent)
    last_opp = _last_opp_move(opponent)

    # Did I win last round?
    if last_my and last_opp:
        my_payoff, _ = (3, 3) if (last_my == Move.COOPERATE and last_opp == Move.COOPERATE) else \
                       (0, 5) if (last_my == Move.COOPERATE and last_opp == Move.DEFECT) else \
                       (5, 0) if (last_my == Move.DEFECT and last_opp == Move.COOPERATE) else \
                       (1, 1)
        # Win = payoff > 1 (mutual defect baseline)
        won = my_payoff > 1

        if won:
            move = last_my  # stay
            rationale = f"Win-stay: last round was {'mutual coop' if last_my == Move.COOPERATE else 'exploitation'} (payoff {my_payoff}). Repeating."
        else:
            move = Move.COOPERATE if last_my == Move.DEFECT else Move.DEFECT
            rationale = f"Lose-shift: last round payoff was {my_payoff}. Switching move."
    else:
        move = Move.COOPERATE
        rationale = "Round 1 — cooperate first."

    # Detect Pavlov lock (both defecting for 3+ rounds)
    recent = opponent.history[-3:]
    if len(recent) == 3 and all(
        r.my_move == Move.DEFECT and r.opponent_move == Move.DEFECT for r in recent
    ):
        move = Move.COOPERATE
        rationale = "Pavlov lock detected (3 mutual defects). Forcing cooperation reset."

    return ModuleResult(
        module=ModuleName.PAVLOV,
        recommended_move=move,
        rationale=rationale,
        confidence=0.80,
        tactical_notes=[
            "Win-stay, lose-shift logic active.",
            "Optimized for impatient opponents needing quick cooperation proof.",
            "Auto-breaks mutual defect lock after 3 rounds.",
        ],
        flags=["IMPATIENT_MODE"],
    )


# ── Module 5: Grim-with-Parole ────────────────────────────────────────────────
def grim_with_parole(opponent: Opponent, signals: EnvironmentSignals) -> ModuleResult:
    defect_rate = opponent.defection_rate()
    parole_k = compute_parole_interval(defect_rate)
    opponent.parole_interval = parole_k

    # Determine if we're in a parole probe round
    opponent.rounds_since_parole += 1
    is_parole_round = opponent.rounds_since_parole >= parole_k

    if is_parole_round:
        opponent.rounds_since_parole = 0
        # Graduated probe: small cooperative gesture
        last_3 = opponent.history[-3:] if len(opponent.history) >= 3 else opponent.history
        probe_reciprocated = any(r.opponent_move == Move.COOPERATE for r in last_3)

        if probe_reciprocated:
            move = Move.COOPERATE
            rationale = f"Parole probe: opponent cooperated in last 3 rounds. Resetting to Base TFT."
            flags = ["PAROLE_SUCCESS", "RESET_TO_BASE_TFT"]
        else:
            # Small cooperative gesture, not full trust
            move = Move.COOPERATE
            rationale = f"Parole probe round (interval={parole_k}). Offering one cooperative gesture. Watching for response."
            flags = ["PAROLE_PROBE"]
    else:
        move = Move.DEFECT
        remaining = parole_k - opponent.rounds_since_parole
        rationale = f"Grim phase active. Pure defector classification maintained. Next parole probe in {remaining} rounds."
        flags = ["GRIM_PHASE"]

    return ModuleResult(
        module=ModuleName.GRIM_WITH_PAROLE,
        recommended_move=move,
        rationale=rationale,
        confidence=0.85,
        tactical_notes=[
            f"Defection rate: {defect_rate:.1%}",
            f"Parole interval K: {parole_k} rounds",
            f"Rounds since last parole: {opponent.rounds_since_parole}",
            "3 failed paroles triggers GTFO threshold evaluation.",
        ],
        flags=flags if 'flags' in dir() else [],
    )


# ── Module 6: Network TFT ─────────────────────────────────────────────────────
def network_tft(opponent: Opponent, signals: EnvironmentSignals) -> ModuleResult:
    rep = opponent.reputation_score
    R_COOP = 0.60
    R_DEFECT = 0.35

    if rep >= R_COOP:
        move = Move.COOPERATE
        rationale = f"Network reputation score {rep:.2f} ≥ threshold {R_COOP}. Cooperating based on network standing."
        flags = ["HIGH_REP_COOP"]
    elif rep <= R_DEFECT:
        move = Move.DEFECT
        rationale = f"Network reputation score {rep:.2f} ≤ threshold {R_DEFECT}. Defecting based on network standing."
        flags = ["LOW_REP_DEFECT"]
    else:
        # Middle band — use bilateral history
        last = _last_opp_move(opponent)
        move = Move.COOPERATE if (last is None or last == Move.COOPERATE) else Move.DEFECT
        rationale = f"Reputation {rep:.2f} in ambiguous range. Falling back to bilateral mirroring."
        flags = ["AMBIGUOUS_REP"]

    return ModuleResult(
        module=ModuleName.NETWORK_TFT,
        recommended_move=move,
        rationale=rationale,
        confidence=0.78,
        tactical_notes=[
            f"Reputation score: {rep:.2f} (0=worst, 1=best)",
            f"Coop threshold: {R_COOP}, Defect threshold: {R_DEFECT}",
            "Weight reputation by source independence — clustered social networks count as one voice.",
            "Make your moves observable when possible — your reputation is the primary asset here.",
        ],
        flags=flags if 'flags' in dir() else [],
    )


# ── Module 7: Shadow-Extender ─────────────────────────────────────────────────
def shadow_extender(opponent: Opponent, signals: EnvironmentSignals) -> ModuleResult:
    last = _last_opp_move(opponent)

    if last is None or last == Move.COOPERATE:
        move = Move.COOPERATE
        rationale = "Extending shadow of future: cooperating and building reputation stakes that outlast this game."
    else:
        move = Move.DEFECT
        rationale = "Opponent defected. Punishing, but maintaining reputation record for post-game reference."

    return ModuleResult(
        module=ModuleName.SHADOW_EXTENDER,
        recommended_move=move,
        rationale=rationale,
        confidence=0.72,
        tactical_notes=[
            "Introduce ongoing stakes: reputation, future business, public record.",
            "Create binding mid-game commitments costly to violate on 'last' round.",
            "Reframe: make opponent aware you'll interact with their reputation after this game.",
            "If shadow-extension impossible, fall through to Stake-and-Signal.",
        ],
        flags=["BOUNDED_GAME"],
    )


# ── Module 8: Irrationality Mode ──────────────────────────────────────────────
def irrationality_mode(opponent: Opponent, signals: EnvironmentSignals) -> ModuleResult:
    return ModuleResult(
        module=ModuleName.IRRATIONALITY_MODE,
        recommended_move=Move.DEFECT,
        rationale="Opponent classified as irrational (defections uncorrelated with payoff, self-damaging, no audience). Standard incentive logic doesn't apply. Minimizing exposure.",
        confidence=0.65,
        tactical_notes=[
            "Stop optimizing for bilateral cooperation — it won't work.",
            "Minimize exposure: avoid large cooperative gestures.",
            "Signal to third-party observers — behavior is now primarily reputational.",
            "Engage only at minimal necessary levels.",
            "Investigate whether opponent is rational within a DIFFERENT payoff structure before finalizing this classification.",
            "Document and exit when GTFO threshold is reached.",
        ],
        flags=["IRRATIONAL_DETECTED", "MINIMIZE_EXPOSURE"],
    )


# ── Module 9: Commons Mode ────────────────────────────────────────────────────
def commons_mode(opponent: Opponent, signals: EnvironmentSignals) -> ModuleResult:
    return ModuleResult(
        module=ModuleName.COMMONS_MODE,
        recommended_move=Move.COOPERATE,
        rationale="Commons/collective game detected. Individual TFT mirroring would produce collective defection. Cooperating unconditionally into the commons and signaling norm-adherence.",
        confidence=0.80,
        tactical_notes=[
            "Cooperate unconditionally into the commons.",
            "Make cooperation visible — signal norm-adherence to ALL players.",
            "Actively advocate for coordination infrastructure (rules, monitoring, sanctions).",
            "Direct punishment at defectors' REPUTATION, not bilateral interaction.",
            "Escalate to institutional actors if defection is systemic.",
            "Goal: change the game's payoff structure, not win bilateral exchanges.",
        ],
        flags=["COLLECTIVE_GAME"],
    )


# ── Module 10: Power-Asymmetry Mode ──────────────────────────────────────────
def power_asymmetry_mode(opponent: Opponent, signals: EnvironmentSignals, power_ratio: float = 3.0) -> ModuleResult:
    from .utils import power_ratio_mode
    mode = power_ratio_mode(power_ratio)

    if mode == "strategic_compliance":
        move = Move.COOPERATE
        rationale = f"Power ratio {power_ratio:.1f}:1 (opponent >> you). Strategic compliance mode: cooperating beyond strict reciprocity to preserve relationship while building leverage."
    elif mode == "modified_tft":
        last = _last_opp_move(opponent)
        if last == Move.DEFECT:
            # Don't always retaliate when they're more powerful
            move = Move.COOPERATE if random.random() < 0.4 else Move.DEFECT
            rationale = f"Power ratio {power_ratio:.1f}:1. Modified TFT: absorbing some defections rather than full retaliation."
        else:
            move = Move.COOPERATE
            rationale = f"Power ratio {power_ratio:.1f}:1. Modified TFT: cooperating."
    else:
        result = base_tft(opponent, signals)
        result.module = ModuleName.POWER_ASYMMETRY
        return result

    return ModuleResult(
        module=ModuleName.POWER_ASYMMETRY,
        recommended_move=move,
        rationale=rationale,
        confidence=0.70,
        tactical_notes=[
            f"Power ratio: {power_ratio:.1f}:1 → {mode.replace('_', ' ').title()} mode",
            "Build reputation with third parties who may rebalance the dynamic.",
            "Accumulate leverage quietly: information, allies, alternatives.",
            "Maintain PRIVATE red lines — known to yourself even if not announced.",
            "Exit when sufficient leverage is built, not before.",
        ],
        flags=[f"POWER_RATIO_{mode.upper()}"],
    )
