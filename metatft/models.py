from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List
import time


class Move(Enum):
    COOPERATE = "cooperate"
    DEFECT = "defect"


class HorizonFlag(Enum):
    REPEATED = "repeated"
    SHORT = "short"
    ONE_SHOT = "one_shot"
    UNKNOWN = "unknown"


class NoiseFlag(Enum):
    LOW = "low"
    NOISY = "noisy"
    HIGH = "high"
    UNKNOWN = "unknown"


class PlayerFlag(Enum):
    BILATERAL = "bilateral"
    NETWORKED = "networked"
    MULTI_PLAYER = "multi_player"
    COLLECTIVE = "collective"


class OpponentFlag(Enum):
    COOPERATIVE = "cooperative"
    MIXED = "mixed"
    COND_DEFECT = "cond_defect"
    PURE_DEFECT = "pure_defect"
    IRRATIONAL = "irrational"
    UNKNOWN = "unknown"


class TemporalFlag(Enum):
    OPEN = "open"
    BOUNDED = "bounded"
    IMPATIENT = "impatient"
    ASYMMETRIC = "asymmetric"


class ModuleName(Enum):
    BASE_TFT = "Base TFT"
    GENEROUS_TFT = "Generous TFT"
    STAKE_AND_SIGNAL = "Stake-and-Signal"
    PAVLOV = "Pavlov"
    GRIM_WITH_PAROLE = "Grim-with-Parole"
    NETWORK_TFT = "Network TFT"
    SHADOW_EXTENDER = "Shadow-Extender"
    IRRATIONALITY_MODE = "Irrationality Mode"
    COMMONS_MODE = "Commons Mode"
    POWER_ASYMMETRY = "Power-Asymmetry"


@dataclass
class EnvironmentSignals:
    horizon: HorizonFlag = HorizonFlag.UNKNOWN
    noise: NoiseFlag = NoiseFlag.UNKNOWN
    players: PlayerFlag = PlayerFlag.BILATERAL
    opponent_type: OpponentFlag = OpponentFlag.UNKNOWN
    temporal: TemporalFlag = TemporalFlag.OPEN
    confidence: float = 0.5
    noise_estimate: float = 0.05
    power_ratio: float = 1.0
    exploit_risk: float = 0.3
    misread_risk: float = 0.2
    endgame_risk: float = 0.1
    relationship_value: float = 0.5
    evidence: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "horizon": self.horizon.value,
            "noise": self.noise.value,
            "players": self.players.value,
            "opponent_type": self.opponent_type.value,
            "temporal": self.temporal.value,
            "confidence": self.confidence,
            "noise_estimate": self.noise_estimate,
            "power_ratio": self.power_ratio,
            "exploit_risk": self.exploit_risk,
            "misread_risk": self.misread_risk,
            "endgame_risk": self.endgame_risk,
            "relationship_value": self.relationship_value,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EnvironmentSignals":
        if not d:
            return cls()
        data = d.copy()
        data["horizon"] = HorizonFlag(data.get("horizon", HorizonFlag.UNKNOWN.value))
        data["noise"] = NoiseFlag(data.get("noise", NoiseFlag.UNKNOWN.value))
        data["players"] = PlayerFlag(data.get("players", PlayerFlag.BILATERAL.value))
        data["opponent_type"] = OpponentFlag(data.get("opponent_type", OpponentFlag.UNKNOWN.value))
        data["temporal"] = TemporalFlag(data.get("temporal", TemporalFlag.OPEN.value))
        return cls(**data)


@dataclass
class RoundEntry:
    round_num: int
    my_move: Move
    opponent_move: Move
    active_module: str
    signals: dict
    classifier_confidence: float
    payoff: float
    context_notes: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "round_num": self.round_num,
            "my_move": self.my_move.value,
            "opponent_move": self.opponent_move.value,
            "active_module": self.active_module,
            "signals": self.signals,
            "classifier_confidence": self.classifier_confidence,
            "payoff": self.payoff,
            "context_notes": self.context_notes,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RoundEntry":
        data = d.copy()
        data["my_move"] = Move(data["my_move"])
        data["opponent_move"] = Move(data["opponent_move"])
        return cls(**data)


@dataclass
class Opponent:
    name: str
    history: List[RoundEntry] = field(default_factory=list)
    reputation_score: float = 0.5
    source_independence: float = 0.7
    parole_interval: int = 5
    rounds_since_parole: int = 0
    classification: OpponentFlag = OpponentFlag.UNKNOWN
    notes: str = ""
    created_at: float = field(default_factory=time.time)

    def defection_rate(self, window: int = 10) -> float:
        recent = self.history[-window:] if len(self.history) >= window else self.history
        if not recent:
            return 0.0
        defects = sum(1 for r in recent if r.opponent_move == Move.DEFECT)
        return defects / len(recent)

    def cooperation_rate(self, window: int = 10) -> float:
        return 1.0 - self.defection_rate(window)

    def cooperation_deficit(self, decay: float = 0.85) -> float:
        deficit = 0.0
        for i, entry in enumerate(reversed(self.history)):
            weight = decay ** i
            my_val = 1 if entry.my_move == Move.COOPERATE else -1
            opp_val = 1 if entry.opponent_move == Move.COOPERATE else -1
            deficit += (my_val - opp_val) * weight
        return round(deficit, 3)

    def recent_payoff_avg(self, window: int = 5) -> float:
        recent = self.history[-window:] if len(self.history) >= window else self.history
        if not recent:
            return 0.0
        return sum(r.payoff for r in recent) / len(recent)

    def total_rounds(self) -> int:
        return len(self.history)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "history": [r.to_dict() for r in self.history],
            "reputation_score": self.reputation_score,
            "source_independence": self.source_independence,
            "parole_interval": self.parole_interval,
            "rounds_since_parole": self.rounds_since_parole,
            "classification": self.classification.value,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Opponent":
        data = d.copy()
        data["history"] = [RoundEntry.from_dict(r) for r in d.get("history", [])]
        data["classification"] = OpponentFlag(d.get("classification", OpponentFlag.UNKNOWN.value))
        data.setdefault("source_independence", 0.7)
        return cls(**data)


@dataclass
class CandidateScore:
    module: ModuleName
    score: float
    why: str


@dataclass
class AnalysisResult:
    module: ModuleName
    recommended_move: Move
    module_stack: List[ModuleName]
    rationale: str
    executive_summary: str
    strategic_explanation: str
    evidence_lines: List[str]
    action_steps: List[str]
    avoid_steps: List[str]
    what_changes: List[str]
    why_not: List[str]
    tactical_notes: List[str]
    flags: List[str]
    confidence: float
    gtfo_score: float
    gtfo_triggered: bool
    ethics_vetoed: bool = False
    ethics_reason: str = ""
    alternatives: List[CandidateScore] = field(default_factory=list)


@dataclass
class MetaTFTState:
    opponents: Dict[str, Opponent] = field(default_factory=dict)
    settings: dict = field(default_factory=lambda: {
        "stochastic_block": 0.15,
        "decay_lambda": 0.85,
        "fairness_multiplier": 3.0,
        "re_eval_interval": 5,
        "gtfo_threshold": 2.0,
        "sim_seed": 433,
    })

    def to_dict(self) -> dict:
        return {
            "opponents": {k: v.to_dict() for k, v in self.opponents.items()},
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MetaTFTState":
        opponents = {k: Opponent.from_dict(v) for k, v in d.get("opponents", {}).items()}
        state = cls(opponents=opponents, settings=d.get("settings", {}))
        defaults = cls().settings
        merged = defaults.copy()
        merged.update(state.settings)
        state.settings = merged
        return state
