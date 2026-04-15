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
    NoiseFlag,
    Opponent,
    OpponentFlag,
    PlayerFlag,
    RoundEntry,
    TemporalFlag,
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
from .utils import compute_gtfo_score, detect_regime, estimate_noise, get_payoff, noise_authenticity_test, project_ev, should_switch, trust_score

BASE_POLICIES = {
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

SCENARIO_PACKS: Dict[str, Dict[str, object]] = {
    'clean_repeated': {'bot': 'tft', 'rounds': 60, 'noise': 0.0, 'description': 'Clean repeated bilateral reciprocity.'},
    'noisy_repeated': {'bot': 'tft', 'rounds': 60, 'noise': 0.10, 'description': 'Repeated play with accidental signal corruption.'},
    'short_horizon_opportunist': {'bot': 'detective', 'rounds': 12, 'noise': 0.0, 'description': 'Short interaction with opportunistic probing.'},
    'hard_defector': {'bot': 'always_defect', 'rounds': 40, 'noise': 0.0, 'description': 'Persistent exploitation pressure.'},
    'desperate_actor': {'bot': 'random', 'rounds': 40, 'noise': 0.20, 'description': 'Chaotic and short-sighted environment.'},
}


class MetaTFTEngine:
    def __init__(self, state: MetaTFTState):
        self.state = state

    def classify_environment(self, opponent: Opponent, overrides: dict | None = None, power_ratio: float = 1.0) -> EnvironmentSignals:
        overrides = overrides or {}
        history = opponent.history
        rounds = len(history)
        horizon = overrides.get('horizon', HorizonFlag.UNKNOWN)
        noise_est = overrides.get('noise_estimate', estimate_noise(history) if rounds >= 4 else 0.05)
        if 'noise' in overrides:
            noise = overrides['noise']
        elif noise_est < 0.05:
            noise = NoiseFlag.LOW
        elif noise_est < 0.20:
            noise = NoiseFlag.NOISY
        else:
            noise = NoiseFlag.HIGH
        players = overrides.get('players', PlayerFlag.BILATERAL)
        temporal = overrides.get('temporal', TemporalFlag.OPEN)
        defect_rate = opponent.defection_rate()
        trust = trust_score(history)
        genuine_noise = noise_authenticity_test(history)
        self_damage_defections = sum(1 for entry in history[-6:] if entry.opponent_move == Move.DEFECT and entry.payoff <= 1)

        if 'opponent_type' in overrides:
            opp_type = overrides['opponent_type']
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

        signal_stability = 1 - min(1.0, abs(defect_rate - 0.5) * 0.8 + (0.15 if not genuine_noise else 0.0))
        confidence_parts = {
            'history_depth': min(rounds / 10, 1.0),
            'horizon_known': 0.95 if horizon != HorizonFlag.UNKNOWN else 0.30,
            'player_structure': 0.90 if players != PlayerFlag.BILATERAL or rounds > 0 else 0.50,
            'signal_stability': signal_stability,
            'opponent_read': 0.90 if opp_type != OpponentFlag.UNKNOWN else 0.35,
        }
        confidence = round(sum(confidence_parts.values()) / len(confidence_parts), 2)

        exploit_risk = min(1.0, defect_rate * 0.7 + (1 - trust) * 0.4 + (0.15 if temporal == TemporalFlag.BOUNDED else 0.0))
        misread_risk = min(1.0, noise_est * 1.8 + (0.1 if not genuine_noise else 0.0))
        endgame_risk = 0.75 if temporal == TemporalFlag.BOUNDED else 0.15 if horizon == HorizonFlag.SHORT else 0.05
        relationship_value = min(1.0, 0.25 + trust * 0.45 + (0.2 if horizon == HorizonFlag.REPEATED else 0.0) + (0.1 if players != PlayerFlag.BILATERAL else 0.0))

        evidence = {
            'history_depth': f'{rounds} logged rounds',
            'defection_rate': f'{defect_rate:.0%} opponent defection rate',
            'trust_score': f'{trust:.2f} trust score',
            'noise_read': f'ε≈{noise_est:.2f} and {'random-like' if genuine_noise else 'possibly strategic'} defection pattern',
            'power_ratio': f'{power_ratio:.1f}:1 power ratio',
            'regime': detect_regime(history),
        }
        return EnvironmentSignals(horizon=horizon, noise=noise, players=players, opponent_type=opp_type, temporal=temporal, confidence=confidence, noise_estimate=noise_est, power_ratio=power_ratio, exploit_risk=round(exploit_risk, 2), misread_risk=round(misread_risk, 2), endgame_risk=round(endgame_risk, 2), relationship_value=round(relationship_value, 2), evidence=evidence)

    def choose_base_policy(self, signals: EnvironmentSignals) -> ModuleName:
        if signals.players == PlayerFlag.COLLECTIVE:
            return ModuleName.COMMONS_MODE
        if signals.opponent_type == OpponentFlag.IRRATIONAL:
            return ModuleName.IRRATIONALITY_MODE
        if signals.confidence < 0.5:
            return ModuleName.GENEROUS_TFT
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
        if signals.players == PlayerFlag.COLLECTIVE:
            stack.append(ModuleName.COMMONS_MODE)
        if signals.opponent_type == OpponentFlag.IRRATIONAL and base_policy != ModuleName.IRRATIONALITY_MODE:
            stack.append(ModuleName.IRRATIONALITY_MODE)
        if signals.players in (PlayerFlag.NETWORKED, PlayerFlag.MULTI_PLAYER) and base_policy != ModuleName.NETWORK_TFT:
            stack.append(ModuleName.NETWORK_TFT)
        if signals.temporal == TemporalFlag.BOUNDED and base_policy != ModuleName.SHADOW_EXTENDER:
            stack.append(ModuleName.SHADOW_EXTENDER)
        if signals.noise in (NoiseFlag.NOISY, NoiseFlag.HIGH) and base_policy != ModuleName.GENEROUS_TFT:
            stack.append(ModuleName.GENEROUS_TFT)
        if signals.power_ratio >= 2.0:
            stack.append(ModuleName.POWER_ASYMMETRY)
        if base_policy not in stack:
            stack.append(base_policy)
        return stack

    def execute_base_policy(self, module: ModuleName, opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
        return BASE_POLICIES[module](opponent, signals)

    def _apply_modifiers(self, plan: ModulePlan, stack: List[ModuleName], opponent: Opponent, signals: EnvironmentSignals) -> ModulePlan:
        notes = list(plan.tactical_notes)
        flags = list(plan.flags)
        move = plan.move
        if ModuleName.GENEROUS_TFT in stack and plan.module != ModuleName.GENEROUS_TFT and signals.misread_risk >= 0.45 and move == Move.DEFECT and should_switch(True, self.state.settings.get('stochastic_block', 0.15)):
            move = Move.COOPERATE
            notes.append('Noise wrapper softened retaliation under elevated misread risk.')
            flags.append('NOISE_WRAPPER_SOFTEN')
        if ModuleName.NETWORK_TFT in stack and signals.players in (PlayerFlag.NETWORKED, PlayerFlag.MULTI_PLAYER):
            verified_rep = opponent.reputation_score * opponent.source_independence
            notes.append(f'Network modifier checked verified reputation {verified_rep:.2f}.')
            if verified_rep >= 0.75:
                move = Move.COOPERATE
                flags.append('NETWORK_TRUST_BONUS')
        if ModuleName.SHADOW_EXTENDER in stack and signals.temporal == TemporalFlag.BOUNDED:
            notes.append('Shadow modifier recommends visible commitments and durable records.')
            flags.append('SHADOW_WRAP')
        if ModuleName.POWER_ASYMMETRY in stack:
            mod = apply_power_modifier(move, signals.power_ratio)
            move = mod.move
            notes.extend(mod.notes)
            flags.extend(mod.flags)
        plan.move = move
        plan.tactical_notes = notes
        plan.flags = flags
        return plan

    def compare_candidates(self, opponent: Opponent, signals: EnvironmentSignals) -> List[CandidateScore]:
        candidates: List[CandidateScore] = []
        for module in [ModuleName.GENEROUS_TFT, ModuleName.BASE_TFT, ModuleName.GRIM_WITH_PAROLE, ModuleName.STAKE_AND_SIGNAL, ModuleName.PAVLOV, ModuleName.NETWORK_TFT, ModuleName.SHADOW_EXTENDER]:
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
        deficit = opponent.cooperation_deficit(self.state.settings.get('decay_lambda', 0.85))
        ev = project_ev(opponent.history)
        score = compute_gtfo_score(deficit, ev)
        threshold = self.state.settings.get('gtfo_threshold', 2.0)
        return {'score': score, 'threshold': threshold, 'triggered': score > threshold, 'cooperation_deficit': round(deficit, 3), 'ev_projection': ev, 'horizon_assumed': 10}

    def decide(self, opponent: Opponent, overrides: dict | None = None, power_ratio: float = 1.0) -> Tuple[AnalysisResult, EnvironmentSignals, dict]:
        signals = self.classify_environment(opponent, overrides or {}, power_ratio)
        base_policy = self.choose_base_policy(signals)
        stack = self.build_module_stack(base_policy, signals)
        plan = self.execute_base_policy(base_policy, opponent, signals)
        plan = self._apply_modifiers(plan, stack, opponent, signals)
        ethics = ethics_veto(plan.move, signals, opponent, self.state.settings)
        if ethics.vetoed:
            plan.move = ethics.overridden_move
        gtfo = self.evaluate_gtfo(opponent)
        alternatives = self.compare_candidates(opponent, signals)
        move_phrase = 'cooperate' if plan.move == Move.COOPERATE else 'defect'
        executive_summary = f'Recommended move: {move_phrase} using {plan.module.value}.'
        strategic_explanation = f"The environment scores as {signals.horizon.value.replace('_', ' ')} with {signals.noise.value} noise, {signals.players.value.replace('_', ' ')} structure, and {signals.opponent_type.value.replace('_', ' ')} opponent behavior. {plan.rationale}"
        evidence_lines = [
            f"Horizon: {signals.horizon.value.replace('_', ' ')}",
            f"Noise: {signals.noise.value} (ε≈{signals.noise_estimate:.2f})",
            f"Players: {signals.players.value.replace('_', ' ')}",
            f"Opponent type: {signals.opponent_type.value.replace('_', ' ')}",
            f"Power ratio: {signals.power_ratio:.1f}:1",
            f"Classifier confidence: {signals.confidence:.0%}",
            f"Current regime: {signals.evidence.get('regime', 'unknown')}",
        ]
        result = AnalysisResult(
            module=plan.module,
            recommended_move=plan.move,
            module_stack=stack,
            rationale=plan.rationale,
            executive_summary=executive_summary,
            strategic_explanation=strategic_explanation,
            evidence_lines=evidence_lines,
            action_steps=self._action_steps(plan, signals),
            avoid_steps=self._avoid_steps(plan, signals),
            what_changes=self._what_changes(signals),
            why_not=self._why_not(alternatives, plan.module),
            tactical_notes=plan.tactical_notes,
            flags=plan.flags,
            confidence=round(min(0.97, (signals.confidence + plan.confidence) / 2), 2),
            gtfo_score=gtfo['score'],
            gtfo_triggered=gtfo['triggered'],
            ethics_vetoed=ethics.vetoed,
            ethics_reason=ethics.reason,
            alternatives=alternatives,
        )
        return result, signals, gtfo

    def _action_steps(self, plan: ModulePlan, signals: EnvironmentSignals) -> List[str]:
        steps = ['Make one limited good-faith move.', 'Ask for a specific reciprocal action.', 'Keep scope narrow until reciprocity is confirmed.'] if plan.move == Move.COOPERATE else ['Withhold additional trust this round.', 'Signal the boundary clearly and calmly.', 'Preserve documentation for the next decision cycle.']
        if plan.module == ModuleName.STAKE_AND_SIGNAL:
            steps.insert(0, 'Use escrow, a deposit, or a public commitment instead of open-ended trust.')
        if signals.players in (PlayerFlag.NETWORKED, PlayerFlag.MULTI_PLAYER, PlayerFlag.COLLECTIVE):
            steps.append('Make the move legible to relevant third parties when appropriate.')
        return steps

    def _avoid_steps(self, _: ModulePlan, signals: EnvironmentSignals) -> List[str]:
        avoid = ['Do not over-update on a single ambiguous signal.', 'Do not grant full trust when the evidence is still thin.']
        if signals.noise in (NoiseFlag.NOISY, NoiseFlag.HIGH):
            avoid.append('Do not escalate on one possibly noisy defection.')
        if signals.power_ratio >= 2.0:
            avoid.append('Do not provoke a stronger actor without a buffering plan.')
        return avoid

    def _what_changes(self, signals: EnvironmentSignals) -> List[str]:
        changes = ['Two more clear, non-noisy defections would justify a harsher containment posture.', 'A confirmed one-shot horizon would push the policy toward Stake-and-Signal.']
        if signals.players == PlayerFlag.COLLECTIVE:
            changes.append('Clear evidence that the shared pool is not at stake would reduce the need for Commons Mode.')
        if signals.temporal == TemporalFlag.BOUNDED:
            changes.append('A newly opened future relationship would weaken endgame pressure.')
        return changes

    def _why_not(self, alternatives: List[CandidateScore], chosen: ModuleName) -> List[str]:
        out: List[str] = []
        for alt in alternatives:
            if alt.module == chosen:
                continue
            out.append(f"Not {alt.module.value}: {alt.why}")
        return out[:2]

    def record_round(self, opponent: Opponent, my_move: Move, opp_move: Move, module: ModuleName, signals: EnvironmentSignals, payoff: float, context_notes: str = '') -> None:
        opponent.history.append(RoundEntry(round_num=len(opponent.history) + 1, my_move=my_move, opponent_move=opp_move, active_module=module.value, signals=signals.to_dict(), classifier_confidence=signals.confidence, payoff=payoff, context_notes=context_notes))

    def _bot_move(self, bot_name: str, bot_state: dict, my_prev: Move | None) -> Move:
        if bot_name == 'always_cooperate':
            return Move.COOPERATE
        if bot_name == 'always_defect':
            return Move.DEFECT
        if bot_name == 'random':
            return random.choice([Move.COOPERATE, Move.DEFECT])
        if bot_name == 'tft':
            return bot_state.get('my_last_move', Move.COOPERATE)
        if bot_name == 'grudger':
            if bot_state.get('grudge', False):
                return Move.DEFECT
            return Move.COOPERATE
        if bot_name == 'detective':
            script = [Move.COOPERATE, Move.DEFECT, Move.COOPERATE, Move.COOPERATE]
            idx = bot_state.get('round', 0)
            if idx < len(script):
                return script[idx]
            if bot_state.get('ever_exploited', False):
                return bot_state.get('my_last_move', Move.COOPERATE)
            return Move.DEFECT
        raise ValueError(f'Unknown bot: {bot_name}')

    def simulate(self, bot_name: str, rounds: int = 50, noise: float = 0.0, seed: int | None = None) -> dict:
        if seed is not None:
            random.seed(seed)
        allowed = {'always_cooperate', 'always_defect', 'random', 'tft', 'grudger', 'detective'}
        if bot_name not in allowed:
            return {'error': f'Unknown bot: {bot_name}'}
        opp = Opponent(name=f'sim::{bot_name}')
        bot_state = {'round': 0, 'grudge': False, 'my_last_move': Move.COOPERATE, 'ever_exploited': False}
        my_total = 0
        bot_total = 0
        rounds_log = []
        for r in range(1, rounds + 1):
            result, signals, _ = self.decide(opp)
            my_move = result.recommended_move
            bot_move = self._bot_move(bot_name, bot_state, opp.history[-1].my_move if opp.history else None)
            if random.random() < noise:
                bot_move = Move.DEFECT if bot_move == Move.COOPERATE else Move.COOPERATE
            my_payoff, bot_payoff = get_payoff(my_move, bot_move)
            my_total += my_payoff
            bot_total += bot_payoff
            self.record_round(opp, my_move, bot_move, result.module, signals, my_payoff, 'simulation')
            if bot_name == 'grudger' and my_move == Move.DEFECT:
                bot_state['grudge'] = True
            if bot_name == 'detective' and my_move == Move.DEFECT:
                bot_state['ever_exploited'] = True
            bot_state['round'] = r
            bot_state['my_last_move'] = my_move
            rounds_log.append({'round': r, 'my_move': my_move.value, 'bot_move': bot_move.value, 'my_payoff': my_payoff, 'bot_payoff': bot_payoff, 'module': result.module.value})
        my_coop = sum(1 for x in rounds_log if x['my_move'] == Move.COOPERATE.value)
        bot_coop = sum(1 for x in rounds_log if x['bot_move'] == Move.COOPERATE.value)
        return {'my_total': my_total, 'bot_total': bot_total, 'my_avg': round(my_total / rounds, 2), 'bot_avg': round(bot_total / rounds, 2), 'my_coop_rate': round(my_coop / rounds, 3), 'bot_coop_rate': round(bot_coop / rounds, 3), 'rounds_log': rounds_log}

    def simulate_pack(self, pack_name: str, seed: int | None = None) -> dict:
        if pack_name not in SCENARIO_PACKS:
            return {'error': f'Unknown pack: {pack_name}'}
        pack = SCENARIO_PACKS[pack_name]
        result = self.simulate(str(pack['bot']), int(pack['rounds']), float(pack['noise']), seed=seed)
        result['pack'] = pack_name
        result['description'] = pack['description']
        return result
