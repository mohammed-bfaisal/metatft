from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
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

    def to_dict(self):
        return {
            "horizon": self.horizon.value,
            "noise": self.noise.value,
            "players": self.players.value,
            "opponent_type": self.opponent_type.value,
            "temporal": self.temporal.value,
            "confidence": self.confidence,
            "noise_estimate": self.noise_estimate,
        }


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

    def to_dict(self):
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
    def from_dict(cls, d):
        d = d.copy()
        d["my_move"] = Move(d["my_move"])
        d["opponent_move"] = Move(d["opponent_move"])
        return cls(**d)


@dataclass
class Opponent:
    name: str
    history: list = field(default_factory=list)  # list of RoundEntry
    reputation_score: float = 0.5
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

    def cooperation_deficit(self, decay: float = 0.85) -> float:
        deficit = 0.0
        for i, entry in enumerate(reversed(self.history)):
            weight = decay ** i
            my_val = 1 if entry.my_move == Move.COOPERATE else -1
            opp_val = 1 if entry.opponent_move == Move.COOPERATE else -1
            deficit += (my_val - opp_val) * weight
        return deficit

    def to_dict(self):
        return {
            "name": self.name,
            "history": [r.to_dict() for r in self.history],
            "reputation_score": self.reputation_score,
            "parole_interval": self.parole_interval,
            "rounds_since_parole": self.rounds_since_parole,
            "classification": self.classification.value,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d):
        d = d.copy()
        d["history"] = [RoundEntry.from_dict(r) for r in d["history"]]
        d["classification"] = OpponentFlag(d["classification"])
        return cls(**d)


@dataclass
class MetaTFTState:
    opponents: dict = field(default_factory=dict)  # name -> Opponent
    settings: dict = field(default_factory=lambda: {
        "stochastic_block": 0.15,
        "decay_lambda": 0.85,
        "fairness_multiplier": 3.0,
        "re_eval_interval": 5,
        "gtfo_threshold": 2.0,
    })

    def to_dict(self):
        return {
            "opponents": {k: v.to_dict() for k, v in self.opponents.items()},
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, d):
        opponents = {k: Opponent.from_dict(v) for k, v in d.get("opponents", {}).items()}
        return cls(opponents=opponents, settings=d.get("settings", {}))
