# MetaTFT

**A universal adaptive cooperation strategy — Python CLI**

MetaTFT is a context-aware game-theory engine built on Tit-for-Tat. Standard TFT assumes a clean, bilateral, iterated, symmetric, rational game with no noise — the real world violates every one of those assumptions. MetaTFT fixes this by reading the environment before each move and deploying the appropriate strategy module.

```
┌──────────────────────────────────────────────────┐
│  Ethics Veto  (always-on, 3 hard constraints)    │
├──────────────────────────────────────────────────┤
│  Environment Classifier  (5 signals + confidence)│
├──────────────────────────────────────────────────┤
│  Module Composer  (composable priority stack)    │
├──────────────────────────────────────────────────┤
│  Base TFT Engine  (inherited by all modules)     │
├──────────────────────────────────────────────────┤
│  Reputation Log  (time-decayed, persisted)       │
└──────────────────────────────────────────────────┘
```

---

## Install

**Requirements:** Python 3.10+

```bash
git clone https://github.com/your-username/metatft.git
cd metatft
pip install -r requirements.txt
pip install .
```

## Run

```bash
metatft
# or
python -m metatft
```

---

## Modes

### Advisor
Answer 5 questions about a real-world situation. MetaTFT classifies the environment, selects the right module stack, recommends a move with full rationale, runs the ethics veto, checks the GTFO threshold, and optionally logs the round.

### Simulator
Run MetaTFT against 6 classic game-theory bots across any number of rounds with configurable channel noise. See scores, cooperation rates, and module usage breakdown.

| Bot | Behaviour |
|-----|-----------|
| `always_cooperate` | Cooperates every round |
| `always_defect` | Defects every round |
| `random` | 50/50 each round |
| `tft` | Classic Tit-for-Tat |
| `grudger` | Cooperates until first defect, then never again |
| `detective` | Probes C/D/C/C then exploits if no retaliation |

### Journal
Log real interactions over time. Tracks cooperation deficit, defection rate, EV projection, and alerts when the GTFO threshold is breached. Export opponent histories to JSON.

### Heuristic
Quick-reference mode — the 3-question shorthand derived from the full system, plus a module reference table.

### Settings
Configure all engine parameters at runtime: stochastic switching block rate, memory decay lambda, fairness multiplier, re-evaluation interval, GTFO threshold.

---

## The 10 Modules

| Module | Activated when | Core fix |
|--------|---------------|----------|
| **Base TFT** | Clean iterated bilateral game | Pure mirroring |
| **Generous TFT** | Noisy / ambiguous channel | Forgive `p = min(e*1.5, 0.25)` |
| **Stake-and-Signal** | One-shot encounter | Replace future-threat with present-cost |
| **Pavlov** | Impatient opponent | Win-stay, lose-shift for fast lock-in |
| **Grim-with-Parole** | Pure defector | Punish + graduated parole probes |
| **Network TFT** | Multi-player / reputation game | Cooperate based on network reputation score |
| **Shadow-Extender** | Known end date | Extend the shadow of the future |
| **Irrationality Mode** | Payoff-uncorrelated defection | Minimize exposure, signal third parties |
| **Commons Mode** | Public goods / collective game | Cooperate unconditionally, change the structure |
| **Power-Asymmetry** | Opponent has far more power | Strategic compliance + leverage accumulation |

Modules compose: when multiple edge cases apply simultaneously, MetaTFT stacks modules in priority order (irrationality > commons > power > noise > domain > base).

---

## Key Mechanisms

**Noise authenticity test** — Wald-Wolfowitz runs test distinguishes genuine channel noise (random) from strategic noise-mimicry (clustered). An opponent defecting at 9% to farm forgiveness is detected and the forgiveness rate is halved.

**Stochastic switching** — Module selection flips with 15% noise even when thresholds are met. The policy is known but the parameterization is private, preventing opponents from gaming the transitions.

**Time-decay memory** — Reputation log applies exponential decay (lambda=0.85). Recent behavior weights exponentially more. Opponents can genuinely reform.

**GTFO threshold** — When `cooperation_deficit / (ev_projection * remaining_rounds) > 2.0`, exit is recommended.

**Ethics veto** — Three hard constraints that cannot be overridden by any module:
1. No cooperation that requires third-party harm
2. Fairness floor — do not exploit power asymmetry in your favor
3. Categorical exit from actors whose goals require harm to others

---

## Heuristic Shorthand

Before any move, ask three things:

1. *Will I interact with this person again, and does the future matter to them?*
   If no: signal honestly and exit if not reciprocated.

2. *Am I reading them accurately, or is this situation messy?*
   If messy: be more forgiving than you feel you should be.

3. *Are the rules of this game fair and bilateral?*
   If not: stop trying to win the game; start trying to change it.

Otherwise: cooperate first, mirror what you receive, forgive once, punish consistently, and stay legible.

---

## Project Structure

```
metatft/
├── metatft/
│   ├── __init__.py       # package entry
│   ├── __main__.py       # python -m metatft
│   ├── cli.py            # full rich terminal UI (all 5 modes)
│   ├── engine.py         # classifier, composer, simulator, GTFO
│   ├── modules.py        # all 10 strategy modules
│   ├── models.py         # dataclasses, enums, state
│   ├── utils.py          # math: noise test, EV, forgiveness, payoffs
│   ├── ethics.py         # always-on 3-constraint veto layer
│   └── storage.py        # JSON persistence to ~/.metatft/
├── requirements.txt
├── setup.py
├── LICENSE
├── CHANGELOG.md
└── README.md
```

State persists to `~/.metatft/state.json` between sessions.

---

## Background

This project implements the MetaTFT specification, derived from adversarial self-critique of standard TFT across 4 rounds of debate covering: noise authenticity, module composability, stochastic switching, time-decay memory, irrationality detection, ethics constraints, exit conditions, power asymmetry, and collective-good games.

---
