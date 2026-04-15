import random
from typing import List, Optional, Tuple
from .models import (
    Move, ModuleName, EnvironmentSignals,
    HorizonFlag, NoiseFlag, PlayerFlag, OpponentFlag, TemporalFlag,
    Opponent, RoundEntry, MetaTFTState
)
from .modules import (
    ModuleResult,
    base_tft, generous_tft, stake_and_signal, pavlov,
    grim_with_parole, network_tft, shadow_extender,
    irrationality_mode, commons_mode, power_asymmetry_mode,
)
from .utils import (
    estimate_noise, noise_authenticity_test, project_ev,
    compute_gtfo_score, should_switch
)
from .ethics import ethics_veto, EthicsVetoResult


class MetaTFTEngine:

    def __init__(self, state: MetaTFTState):
        self.state = state

    # ── Classifier ────────────────────────────────────────────────────────────
    def classify_environment(self, opponent: Opponent, overrides: dict = None) -> EnvironmentSignals:
        """
        Derive environment signals from opponent history + optional manual overrides.
        Overrides come from the advisor questionnaire.
        """
        overrides = overrides or {}
        history = opponent.history

        # Signal 1: Horizon
        horizon = overrides.get("horizon", HorizonFlag.UNKNOWN)

        # Signal 2: Noise — estimate from history
        if len(history) >= 4:
            noise_est = estimate_noise(history)
        else:
            noise_est = overrides.get("noise_estimate", 0.05)

        if "noise" in overrides:
            noise_flag = overrides["noise"]
        elif noise_est < 0.05:
            noise_flag = NoiseFlag.LOW
        elif noise_est < 0.20:
            noise_flag = NoiseFlag.NOISY
        else:
            noise_flag = NoiseFlag.HIGH

        # Signal 3: Players
        players = overrides.get("players", PlayerFlag.BILATERAL)

        # Signal 4: Opponent type — from history
        defect_rate = opponent.defection_rate()
        if "opponent_type" in overrides:
            opp_type = overrides["opponent_type"]
        elif len(history) < 3:
            opp_type = OpponentFlag.UNKNOWN
        elif defect_rate < 0.20:
            opp_type = OpponentFlag.COOPERATIVE
        elif defect_rate < 0.60:
            opp_type = OpponentFlag.MIXED
        elif defect_rate < 0.80:
            opp_type = OpponentFlag.COND_DEFECT
        else:
            # Check irrationality: is defection self-damaging?
            if overrides.get("irrationality_suspected", False):
                opp_type = OpponentFlag.IRRATIONAL
            else:
                opp_type = OpponentFlag.PURE_DEFECT

        opponent.classification = opp_type

        # Signal 5: Temporal
        temporal = overrides.get("temporal", TemporalFlag.OPEN)

        # Confidence score
        confidence_components = []
        confidence_components.append(0.9 if horizon != HorizonFlag.UNKNOWN else 0.3)
        confidence_components.append(0.9 if len(history) >= 5 else 0.4)
        confidence_components.append(0.9 if players != PlayerFlag.BILATERAL or len(history) > 0 else 0.5)
        confidence_components.append(0.9 if opp_type != OpponentFlag.UNKNOWN else 0.3)
        confidence_components.append(0.8)
        confidence = round(sum(confidence_components) / len(confidence_components), 2)

        return EnvironmentSignals(
            horizon=horizon,
            noise=noise_flag,
            players=players,
            opponent_type=opp_type,
            temporal=temporal,
            confidence=confidence,
            noise_estimate=noise_est,
        )

    # ── Module Selector + Composer ────────────────────────────────────────────
    def select_modules(
        self,
        signals: EnvironmentSignals,
        power_ratio: float = 1.0
    ) -> List[ModuleName]:
        """
        Returns ordered list of modules to compose.
        Priority order: irrationality > noise > collective > power > domain > base.
        """
        if signals.confidence < 0.5:
            return [ModuleName.GENEROUS_TFT]

        stack = []

        # Layer 1: Irrationality overrides all
        if signals.opponent_type == OpponentFlag.IRRATIONAL:
            return [ModuleName.IRRATIONALITY_MODE]

        # Layer 2: Commons overrides bilateral optimization
        if signals.players == PlayerFlag.COLLECTIVE:
            return [ModuleName.COMMONS_MODE]

        # Layer 3: Power asymmetry modifies execution
        if power_ratio >= 2.0:
            stack.append(ModuleName.POWER_ASYMMETRY)

        # Layer 4: Noise wraps everything
        if signals.noise in (NoiseFlag.NOISY, NoiseFlag.HIGH):
            stack.append(ModuleName.GENEROUS_TFT)

        # Layer 5: Domain modules
        if signals.horizon == HorizonFlag.ONE_SHOT:
            stack.append(ModuleName.STAKE_AND_SIGNAL)
        elif signals.players in (PlayerFlag.NETWORKED, PlayerFlag.MULTI_PLAYER):
            stack.append(ModuleName.NETWORK_TFT)
        elif signals.opponent_type in (OpponentFlag.PURE_DEFECT, OpponentFlag.COND_DEFECT):
            stack.append(ModuleName.GRIM_WITH_PAROLE)
        elif signals.temporal == TemporalFlag.BOUNDED:
            stack.append(ModuleName.SHADOW_EXTENDER)
        elif signals.temporal == TemporalFlag.IMPATIENT:
            stack.append(ModuleName.PAVLOV)

        # Layer 6: Base TFT if nothing else
        if not stack or stack == [ModuleName.POWER_ASYMMETRY]:
            stack.append(ModuleName.BASE_TFT)
        elif not stack:
            stack.append(ModuleName.BASE_TFT)

        return stack

    def execute_module(
        self,
        module: ModuleName,
        opponent: Opponent,
        signals: EnvironmentSignals,
        power_ratio: float = 1.0,
    ) -> ModuleResult:
        dispatch = {
            ModuleName.BASE_TFT: lambda: base_tft(opponent, signals),
            ModuleName.GENEROUS_TFT: lambda: generous_tft(opponent, signals),
            ModuleName.STAKE_AND_SIGNAL: lambda: stake_and_signal(opponent, signals),
            ModuleName.PAVLOV: lambda: pavlov(opponent, signals),
            ModuleName.GRIM_WITH_PAROLE: lambda: grim_with_parole(opponent, signals),
            ModuleName.NETWORK_TFT: lambda: network_tft(opponent, signals),
            ModuleName.SHADOW_EXTENDER: lambda: shadow_extender(opponent, signals),
            ModuleName.IRRATIONALITY_MODE: lambda: irrationality_mode(opponent, signals),
            ModuleName.COMMONS_MODE: lambda: commons_mode(opponent, signals),
            ModuleName.POWER_ASYMMETRY: lambda: power_asymmetry_mode(opponent, signals, power_ratio),
        }
        return dispatch[module]()

    # ── Full Decision Pipeline ────────────────────────────────────────────────
    def decide(
        self,
        opponent: Opponent,
        overrides: dict = None,
        power_ratio: float = 1.0,
    ) -> Tuple[ModuleResult, EnvironmentSignals, EthicsVetoResult]:
        """
        Full MetaTFT decision pipeline.
        Returns (module_result, signals, ethics_result).
        """
        overrides = overrides or {}
        signals = self.classify_environment(opponent, overrides)
        modules = self.select_modules(signals, power_ratio)

        # Execute primary module
        primary_module = modules[-1]  # deepest domain module
        result = self.execute_module(primary_module, opponent, signals, power_ratio)

        # Ethics veto
        ethics = ethics_veto(result, signals, opponent, self.state.settings)

        if ethics.vetoed:
            result.recommended_move = ethics.overridden_move
            result.rationale = f"[ETHICS VETO] {ethics.reason} | Original: {result.rationale}"
            result.flags.append("ETHICS_VETO")

        return result, signals, ethics

    # ── Stochastic switching check ────────────────────────────────────────────
    def should_reeval(self, opponent: Opponent) -> bool:
        n = len(opponent.history)
        interval = self.state.settings.get("re_eval_interval", 5)
        if n > 0 and n % interval == 0:
            block = self.state.settings.get("stochastic_block", 0.15)
            return should_switch(True, block)
        return False

    # ── Record round ──────────────────────────────────────────────────────────
    def record_round(
        self,
        opponent: Opponent,
        my_move: Move,
        opp_move: Move,
        module: ModuleName,
        signals: EnvironmentSignals,
        payoff: float,
        notes: str = "",
    ):
        entry = RoundEntry(
            round_num=len(opponent.history) + 1,
            my_move=my_move,
            opponent_move=opp_move,
            active_module=module.value,
            signals=signals.to_dict(),
            classifier_confidence=signals.confidence,
            payoff=payoff,
            context_notes=notes,
        )
        opponent.history.append(entry)

    # ── GTFO evaluation ───────────────────────────────────────────────────────
    def evaluate_gtfo(self, opponent: Opponent) -> dict:
        deficit = opponent.cooperation_deficit()
        ev = project_ev(opponent.history)
        horizon = 10  # assume 10 more rounds
        score = compute_gtfo_score(deficit, ev, horizon)
        threshold = self.state.settings.get("gtfo_threshold", 2.0)
        return {
            "score": score,
            "threshold": threshold,
            "triggered": score > threshold,
            "cooperation_deficit": round(deficit, 3),
            "ev_projection": ev,
            "horizon_assumed": horizon,
        }

    # ── Simulation against classic bots ──────────────────────────────────────
    def simulate(
        self,
        bot_name: str,
        rounds: int = 50,
        noise: float = 0.0,
    ) -> dict:
        """
        Run MetaTFT against a classic game theory bot.
        Returns summary stats.
        """
        bots = {
            "always_cooperate": lambda _: Move.COOPERATE,
            "always_defect":    lambda _: Move.DEFECT,
            "random":           lambda _: random.choice([Move.COOPERATE, Move.DEFECT]),
            "tft":              lambda hist: Move.COOPERATE if not hist or hist[-1][0] == Move.COOPERATE else Move.DEFECT,
            "grudger":          lambda hist: Move.DEFECT if any(m == Move.DEFECT for _, m in hist) else Move.COOPERATE,
            "detective":        lambda hist: _detective(hist),
        }

        if bot_name not in bots:
            return {"error": f"Unknown bot: {bot_name}"}

        bot_fn = bots[bot_name]
        sim_opp = Opponent(name=f"sim_{bot_name}")
        bot_history = []  # list of (my_move, opp_move) for bot's perspective

        my_total = 0
        bot_total = 0
        rounds_log = []

        for r in range(rounds):
            # MetaTFT decides
            overrides = {"horizon": HorizonFlag.REPEATED}
            if noise > 0:
                overrides["noise_estimate"] = noise
                overrides["noise"] = NoiseFlag.NOISY if noise < 0.2 else NoiseFlag.HIGH

            result, signals, _ = self.decide(sim_opp, overrides)
            my_move = result.recommended_move

            # Apply noise to my move (channel noise)
            if noise > 0 and random.random() < noise:
                my_move = Move.DEFECT if my_move == Move.COOPERATE else Move.COOPERATE

            # Bot decides
            opp_move = bot_fn(bot_history)

            # Payoffs
            from .utils import get_payoff
            my_p, bot_p = get_payoff(my_move, opp_move)
            my_total += my_p
            bot_total += bot_p

            # Record
            self.record_round(sim_opp, my_move, opp_move, result.module, signals, my_p)
            bot_history.append((opp_move, my_move))
            rounds_log.append({
                "round": r + 1,
                "my_move": my_move.value,
                "bot_move": opp_move.value,
                "my_payoff": my_p,
                "module": result.module.value,
            })

        coop_rate = sum(1 for l in rounds_log if l["my_move"] == "cooperate") / rounds
        bot_coop = sum(1 for l in rounds_log if l["bot_move"] == "cooperate") / rounds

        return {
            "bot": bot_name,
            "rounds": rounds,
            "noise": noise,
            "my_total": my_total,
            "bot_total": bot_total,
            "my_avg": round(my_total / rounds, 2),
            "bot_avg": round(bot_total / rounds, 2),
            "my_coop_rate": round(coop_rate, 2),
            "bot_coop_rate": round(bot_coop, 2),
            "rounds_log": rounds_log,
        }


# ── Detective bot helper ──────────────────────────────────────────────────────
def _detective(history):
    """Detective: probes C,D,C,C then defects if no retaliation, else plays TFT."""
    probe = [Move.COOPERATE, Move.DEFECT, Move.COOPERATE, Move.COOPERATE]
    r = len(history)
    if r < 4:
        return probe[r]
    # Check if opponent retaliated during probe
    retaliated = any(h[1] == Move.DEFECT for h in history[:4])
    if not retaliated:
        return Move.DEFECT
    # TFT mode
    return Move.COOPERATE if not history or history[-1][0] == Move.COOPERATE else Move.DEFECT
