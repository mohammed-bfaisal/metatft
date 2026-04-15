from __future__ import annotations

import random
from typing import Dict, List, Tuple

from .ethics import ethics_veto
from .models import (
    AnalysisResult,
    CandidateScore,
    EnvironmentSignals,
    HorizonFlag,
    MetaTFTState,
    ModuleName,
    Move,
    Opponent,
    OpponentFlag,
    PlayerFlag,
    RoundEntry,
    TemporalFlag,
    NoiseFlag,
)
from .modules import (
    ModulePlan,
    apply_power_modifier,
    base_tft,
    commons_mode,
    generous_tft,
    grim_with_parole,
    irrationality_mode,
    network_tft,
    pavlov,
    shadow_extender,
    stake_and_signal,
)
from .utils import (
    compute_gtfo_score,
    estimate_noise,
    get_payoff,
    noise_authenticity_test,
    project_ev,
    should_switch,
    trust_score,
)


BASE_POLICY_FUNCS = {
    ModuleName.BASE_TFT: base_tft,
    ModuleName.GENEROUS_TFT: generous_tft,
    ModuleName.STAKE_AND_SIGNAL: stake_and_signal,
    ModuleName.PAVLOV: pavlov,
    ModuleName.GRIM_WITH_PAROLE: grim_with_parole,
    ModuleName.NETWORK_TFT: network_tft,
    ModuleName.SHADOW_EXTENDER: shadow_extender,
    ModuleName.IRRATIONALITY_MODE: irrationality_mode,
    ModuleName.COMMONS_MODE: commons_mode,
}


class MetaTFTEngine:
    def __init__(self, state: MetaTFTState):
        self.state = state

    def classify_environment(self, opponent: Opponent, overrides: dict | None = None, power_ratio: float = 1.0) -> EnvironmentSignals:
        overrides = overrides or {}
        history = opponent.history
        rounds = len(history)

        horizon = overrides.get("horizon", HorizonFlag.UNKNOWN)

        noise_est = overrides.get("noise_estimate")
        if noise_est is None:
            noise_est = estimate_noise(history) if rounds >= 4 else 0.05
        if "noise" in overrides:
            noise = overrides["noise"]
        elif noise_est < 0.05:
            noise = NoiseFlag.LOW
        elif noise_est < 0.20:
            noise = NoiseFlag.NOISY
        else:
            noise = NoiseFlag.HIGH

        players = overrides.get("players", PlayerFlag.BILATERAL)
        temporal = overrides.get("temporal", TemporalFlag.OPEN)

        defect_rate = opponent.defection_rate()
        trust = trust_score(history)
        self_damage_defections = 0
        for entry in history[-6:]:
            if entry.opponent_move == Move.DEFECT and entry.payoff <= 1:
                self_damage_defections += 1
        genuine_noise = noise_authenticity_test(history)

        if "opponent_type" in overrides:
            opp_type = overrides["opponent_type"]
        elif rounds < 3:
            opp_type = OpponentFlag.UNKNOWN
        elif self_damage_defections >= 3 and defect_rate >= 0.5:
            opp_type = OpponentFlag.IRRATIONAL
        elif defect_rate < 0.20:
            opp_type = OpponentFlag.COOPERATIVE
        elif defect_rate < 0.60:
            opp_type = OpponentFlag.MIXED
        elif defect_rate < 0.80:
            opp_type = OpponentFlag.COND_DEFECT
        else:
            opp_type = OpponentFlag.PURE_DEFECT

        opponent.classification = opp_type

        confidence_parts = {
            "history_depth": min(rounds / 8, 1.0),
            "horizon_known": 0.95 if horizon != HorizonFlag.UNKNOWN else 0.35,
            "player_structure": 0.9 if players != PlayerFlag.BILATERAL or rounds > 0 else 0.5,
            "signal_stability": 0.8 if genuine_noise or noise == NoiseFlag.LOW else 0.6,
            "opponent_read": 0.9 if opp_type != OpponentFlag.UNKNOWN else 0.4,
        }
        confidence = round(sum(confidence_parts.values()) / len(confidence_parts), 2)

        exploit_risk = min(1.0, defect_rate * 0.7 + (1 - trust) * 0.4 + (0.15 if temporal == TemporalFlag.BOUNDED else 0.0))
        misread_risk = min(1.0, noise_est * 1.8 + (0.1 if not genuine_noise else 0.0))
        endgame_risk = 0.75 if temporal == TemporalFlag.BOUNDED else 0.15 if horizon == HorizonFlag.SHORT else 0.05
        relationship_value = min(1.0, 0.3 + trust * 0.4 + (0.2 if horizon == HorizonFlag.REPEATED else 0.0) + (0.1 if players != PlayerFlag.BILATERAL else 0.0))

        evidence = {
            "history_depth": f"{rounds} logged rounds",
            "defection_rate": f"{defect_rate:.0%} opponent defection rate",
            "trust_score": f"{trust:.2f} trust score",
            "noise_read": f"ε≈{noise_est:.2f} and {'random-like' if genuine_noise else 'possibly strategic'} defection pattern",
            "power_ratio": f"{power_ratio:.1f}:1 power ratio",
        }

        return EnvironmentSignals(
            horizon=horizon,
            noise=noise,
            players=players,
            opponent_type=opp_type,
            temporal=temporal,
            confidence=confidence,
            noise_estimate=noise_est,
            power_ratio=power_ratio,
            exploit_risk=round(exploit_risk, 2),
            misread_risk=round(misread_risk, 2),
            endgame_risk=round(endgame_risk, 2),
            relationship_value=round(relationship_value, 2),
            evidence=evidence,
        )

    def choose_base_policy(self, signals: EnvironmentSignals) -> ModuleName:
        if signals.confidence < 0.5:
            return ModuleName.GENEROUS_TFT
        if signals.opponent_type == OpponentFlag.IRRATIONAL:
            return ModuleName.IRRATIONALITY_MODE
        if signals.players == PlayerFlag.COLLECTIVE:
            return ModuleName.COMMONS_MODE
        if signals.horizon == HorizonFlag.ONE_SHOT:
            return ModuleName.STAKE_AND_SIGNAL
        if signals.players in (PlayerFlag.NETWORKED, PlayerFlag.MULTI_PLAYER):
            return ModuleName.NETWORK_TFT
        if signals.opponent_type in (OpponentFlag.PURE_DEFECT, OpponentFlag.COND_DEFECT):
            return ModuleName.GRIM_WITH_PAROLE
        if signals.temporal == TemporalFlag.BOUNDED:
            return ModuleName.SHADOW_EXTENDER
        if signals.temporal == TemporalFlag.IMPATIENT and signals.opponent_type in (OpponentFlag.COOPERATIVE, OpponentFlag.MIXED):
            return ModuleName.PAVLOV
        if signals.noise in (NoiseFlag.NOISY, NoiseFlag.HIGH):
            return ModuleName.GENEROUS_TFT
        return ModuleName.BASE_TFT

    def build_module_stack(self, base_policy: ModuleName, signals: EnvironmentSignals) -> List[ModuleName]:
        stack: List[ModuleName] = []
        if signals.opponent_type == OpponentFlag.IRRATIONAL:
            return [ModuleName.IRRATIONALITY_MODE]
        if signals.players == PlayerFlag.COLLECTIVE:
            stack.append(ModuleName.COMMONS_MODE)
        if signals.noise in (NoiseFlag.NOISY, NoiseFlag.HIGH) and base_policy != ModuleName.GENEROUS_TFT:
            stack.append(ModuleName.GENEROUS_TFT)
        if signals.power_ratio >= 2.0:
            stack.append(ModuleName.POWER_ASYMMETRY)
        if base_policy not in stack:
            stack.append(base_policy)
        return stack

    def execute_base_policy(self, module: ModuleName, opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
        return BASE_POLICY_FUNCS[module](opponent, signals)

    def compare_candidates(self, opponent: Opponent, signals: EnvironmentSignals) -> List[CandidateScore]:
        candidates: List[CandidateScore] = []
        for module in [
            ModuleName.GENEROUS_TFT,
            ModuleName.BASE_TFT,
            ModuleName.GRIM_WITH_PAROLE,
            ModuleName.STAKE_AND_SIGNAL,
            ModuleName.PAVLOV,
            ModuleName.NETWORK_TFT,
            ModuleName.SHADOW_EXTENDER,
        ]:
            plan = self.execute_base_policy(module, opponent, signals)
            score = plan.confidence
            if module == ModuleName.GENEROUS_TFT:
                score += (signals.misread_risk * 0.25) - (signals.exploit_risk * 0.05)
            elif module == ModuleName.BASE_TFT:
                score += (1 - signals.misread_risk) * 0.18 + (0.1 if signals.horizon == HorizonFlag.REPEATED else 0)
            elif module == ModuleName.GRIM_WITH_PAROLE:
                score += signals.exploit_risk * 0.22
            elif module == ModuleName.STAKE_AND_SIGNAL:
                score += 0.2 if signals.horizon == HorizonFlag.ONE_SHOT else 0.0
            elif module == ModuleName.PAVLOV:
                score += 0.15 if signals.temporal == TemporalFlag.IMPATIENT else -0.05
            elif module == ModuleName.NETWORK_TFT:
                score += 0.16 if signals.players in (PlayerFlag.NETWORKED, PlayerFlag.MULTI_PLAYER) else -0.05
            elif module == ModuleName.SHADOW_EXTENDER:
                score += 0.18 if signals.temporal == TemporalFlag.BOUNDED else -0.05
            candidates.append(CandidateScore(module, round(score, 3), plan.rationale))
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:3]

    def evaluate_gtfo(self, opponent: Opponent) -> dict:
        deficit = opponent.cooperation_deficit(self.state.settings.get("decay_lambda", 0.85))
        ev = project_ev(opponent.history)
        score = compute_gtfo_score(deficit, ev)
        threshold = self.state.settings.get("gtfo_threshold", 2.0)
        return {
            "score": score,
            "threshold": threshold,
            "triggered": score > threshold,
            "cooperation_deficit": round(deficit, 3),
            "ev_projection": ev,
            "horizon_assumed": 10,
        }

    def decide(self, opponent: Opponent, overrides: dict | None = None, power_ratio: float = 1.0) -> Tuple[AnalysisResult, EnvironmentSignals, dict]:
        overrides = overrides or {}
        signals = self.classify_environment(opponent, overrides, power_ratio)
        base_policy = self.choose_base_policy(signals)
        stack = self.build_module_stack(base_policy, signals)
        plan = self.execute_base_policy(base_policy, opponent, signals)

        modifier_notes: List[str] = []
        modifier_flags: List[str] = []
        if signals.power_ratio >= 2.0 and base_policy not in (ModuleName.IRRATIONALITY_MODE, ModuleName.COMMONS_MODE):
            mod = apply_power_modifier(plan.move, signals.power_ratio)
            plan.move = mod.move
            modifier_notes.extend(mod.notes)
            modifier_flags.extend(mod.flags)

        ethics = ethics_veto(plan.move, signals, opponent, self.state.settings)
        if ethics.vetoed:
            plan.move = ethics.overridden_move

        gtfo = self.evaluate_gtfo(opponent)
        alternatives = self.compare_candidates(opponent, signals)

        move_phrase = "cooperate" if plan.move == Move.COOPERATE else "defect"
        executive_summary = f"Recommended move: {move_phrase} using {plan.module.value}."
        strategic_explanation = (
            f"The environment scores as {signals.horizon.value.replace('_', ' ')} with {signals.noise.value} noise, "
            f"{signals.players.value.replace('_', ' ')} structure, and {signals.opponent_type.value.replace('_', ' ')} opponent behavior. "
            f"{plan.rationale}"
        )
        evidence_lines = [
            f"Horizon: {signals.horizon.value.replace('_', ' ')}",
            f"Noise: {signals.noise.value} (ε≈{signals.noise_estimate:.2f})",
            f"Players: {signals.players.value.replace('_', ' ')}",
            f"Opponent type: {signals.opponent_type.value.replace('_', ' ')}",
            f"Power ratio: {signals.power_ratio:.1f}:1",
            f"Classifier confidence: {signals.confidence:.0%}",
        ]
        action_steps = self._action_steps(plan, signals)
        avoid_steps = self._avoid_steps(plan, signals)
        what_changes = self._what_changes(signals)
        why_not = self._why_not(alternatives, plan.module)

        result = AnalysisResult(
            module=plan.module,
            recommended_move=plan.move,
            module_stack=stack,
            rationale=plan.rationale,
            executive_summary=executive_summary,
            strategic_explanation=strategic_explanation,
            evidence_lines=evidence_lines,
            action_steps=action_steps,
            avoid_steps=avoid_steps,
            what_changes=what_changes,
            why_not=why_not,
            tactical_notes=plan.tactical_notes + modifier_notes,
            flags=plan.flags + modifier_flags,
            confidence=round(min(0.97, (signals.confidence + plan.confidence) / 2), 2),
            gtfo_score=gtfo["score"],
            gtfo_triggered=gtfo["triggered"],
            ethics_vetoed=ethics.vetoed,
            ethics_reason=ethics.reason,
            alternatives=alternatives,
        )
        return result, signals, gtfo

    def _action_steps(self, plan: ModulePlan, signals: EnvironmentSignals) -> List[str]:
        if plan.move == Move.COOPERATE:
            steps = ["Make one limited good-faith move.", "Ask for a specific reciprocal action.", "Keep scope narrow until reciprocity is confirmed."]
        else:
            steps = ["Withhold additional trust this round.", "Signal the boundary clearly and calmly.", "Preserve documentation for the next decision cycle."]
        if plan.module == ModuleName.STAKE_AND_SIGNAL:
            steps.insert(0, "Use escrow, a deposit, or a public commitment instead of open-ended trust.")
        if signals.players in (PlayerFlag.NETWORKED, PlayerFlag.MULTI_PLAYER, PlayerFlag.COLLECTIVE):
            steps.append("Make the move legible to relevant third parties when appropriate.")
        return steps

    def _avoid_steps(self, plan: ModulePlan, signals: EnvironmentSignals) -> List[str]:
        avoid = ["Do not over-update on a single ambiguous signal.", "Do not grant full trust when the evidence is still thin."]
        if signals.noise in (NoiseFlag.NOISY, NoiseFlag.HIGH):
            avoid.append("Do not escalate on one possibly noisy defection.")
        if signals.power_ratio >= 2.0:
            avoid.append("Do not trigger a retaliation spiral you cannot afford.")
        if plan.module == ModuleName.GRIM_WITH_PAROLE:
            avoid.append("Do not mistake a parole probe for a full reset.")
        return avoid

    def _what_changes(self, signals: EnvironmentSignals) -> List[str]:
        changes = []
        if signals.noise in (NoiseFlag.NOISY, NoiseFlag.HIGH):
            changes.append("Two more clearly strategic defections would harden the stance toward Grim-with-Parole.")
        if signals.horizon != HorizonFlag.ONE_SHOT:
            changes.append("A confirmed one-shot horizon would push the policy toward Stake-and-Signal.")
        if signals.temporal != TemporalFlag.BOUNDED:
            changes.append("A fixed end date would raise the value of Shadow-Extender.")
        if signals.players == PlayerFlag.BILATERAL:
            changes.append("Higher third-party visibility would increase the importance of reputation-weighted play.")
        return changes[:3]

    def _why_not(self, alternatives: List[CandidateScore], chosen: ModuleName) -> List[str]:
        lines = []
        for alt in alternatives:
            if alt.module == chosen:
                continue
            lines.append(f"Why not {alt.module.value}? It scored lower here because {alt.why.lower()}")
        return lines[:2]

    def should_reeval(self, opponent: Opponent) -> bool:
        n = len(opponent.history)
        interval = self.state.settings.get("re_eval_interval", 5)
        if n > 0 and n % interval == 0:
            return should_switch(True, self.state.settings.get("stochastic_block", 0.15))
        return False

    def record_round(self, opponent: Opponent, my_move: Move, opp_move: Move, module: ModuleName, signals: EnvironmentSignals, payoff: float, notes: str = "") -> None:
        opponent.history.append(
            RoundEntry(
                round_num=len(opponent.history) + 1,
                my_move=my_move,
                opponent_move=opp_move,
                active_module=module.value,
                signals=signals.to_dict(),
                classifier_confidence=signals.confidence,
                payoff=payoff,
                context_notes=notes,
            )
        )

    def simulate(self, bot_name: str, rounds: int = 50, noise: float = 0.0, seed: int | None = None) -> dict:
        if seed is not None:
            random.seed(seed)
        bots = {
            "always_cooperate": lambda _: Move.COOPERATE,
            "always_defect": lambda _: Move.DEFECT,
            "random": lambda _: random.choice([Move.COOPERATE, Move.DEFECT]),
            "tft": lambda hist: Move.COOPERATE if not hist or hist[-1][0] == Move.COOPERATE else Move.DEFECT,
            "grudger": lambda hist: Move.DEFECT if any(m == Move.DEFECT for _, m in hist) else Move.COOPERATE,
            "detective": lambda hist: _detective(hist),
        }
        if bot_name not in bots:
            return {"error": f"Unknown bot: {bot_name}"}

        sim_opp = Opponent(name=f"sim_{bot_name}")
        bot_history: List[Tuple[Move, Move]] = []
        my_total = 0
        bot_total = 0
        rounds_log: List[dict] = []

        for r in range(rounds):
            overrides = {"horizon": HorizonFlag.REPEATED}
            if noise > 0:
                overrides["noise_estimate"] = noise
                overrides["noise"] = NoiseFlag.NOISY if noise < 0.2 else NoiseFlag.HIGH
            result, signals, _ = self.decide(sim_opp, overrides)
            my_move = result.recommended_move
            if noise > 0 and random.random() < noise:
                my_move = Move.DEFECT if my_move == Move.COOPERATE else Move.COOPERATE
            opp_move = bots[bot_name](bot_history)
            my_p, bot_p = get_payoff(my_move, opp_move)
            my_total += my_p
            bot_total += bot_p
            self.record_round(sim_opp, my_move, opp_move, result.module, signals, my_p)
            bot_history.append((opp_move, my_move))
            rounds_log.append({
                "round": r + 1,
                "my_move": my_move.value,
                "bot_move": opp_move.value,
                "my_payoff": my_p,
                "bot_payoff": bot_p,
                "module": result.module.value,
                "confidence": result.confidence,
            })

        return {
            "bot": bot_name,
            "rounds": rounds,
            "noise": noise,
            "my_total": my_total,
            "bot_total": bot_total,
            "my_avg": round(my_total / rounds, 2),
            "bot_avg": round(bot_total / rounds, 2),
            "my_coop_rate": round(sum(1 for r in rounds_log if r["my_move"] == "cooperate") / rounds, 2),
            "bot_coop_rate": round(sum(1 for r in rounds_log if r["bot_move"] == "cooperate") / rounds, 2),
            "rounds_log": rounds_log,
        }


def _detective(history: List[Tuple[Move, Move]]) -> Move:
    probe = [Move.COOPERATE, Move.DEFECT, Move.COOPERATE, Move.COOPERATE]
    r = len(history)
    if r < 4:
        return probe[r]
    retaliated = any(h[1] == Move.DEFECT for h in history[:4])
    if not retaliated:
        return Move.DEFECT
    return Move.COOPERATE if not history or history[-1][0] == Move.COOPERATE else Move.DEFECT
