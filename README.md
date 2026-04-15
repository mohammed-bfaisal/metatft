# MetaTFT

MetaTFT is a terminal-based decision system for reciprocal strategy.

It is **not** built on the claim that Tit for Tat is always best. Instead, it treats plain TFT as a strong baseline for clean repeated bilateral play, then adds environment classification, policy selection, modifiers, ethics checks, and exit logic for cases where plain TFT breaks down.

## What changed in this build

This version upgrades the original prototype in the places that mattered most:

- real policy selection instead of a mostly cosmetic module stack
- layered recommendation output: executive answer, strategic explanation, technical evidence
- clearer CLI organized around user jobs instead of raw internal modes
- candidate-module comparison so the app explains **why not the alternatives**
- stronger signal dashboard with risk bars and relationship summaries
- corrected GTFO math so projected recovery is not double-counted
- improved environment confidence scoring and evidence trace
- better repo packaging for GitHub

## Core idea

MetaTFT asks five questions before recommending a move:

1. Will this interaction repeat?
2. How noisy or ambiguous is the signal channel?
3. Is this bilateral, networked, multiplayer, or a commons problem?
4. What kind of opponent are you facing?
5. Is there a bounded horizon, impatience, or strong power asymmetry?

Then it chooses a policy such as:

- Base TFT
- Generous TFT
- Stake-and-Signal
- Pavlov
- Grim-with-Parole
- Network TFT
- Shadow-Extender
- Irrationality Mode
- Commons Mode

And finally applies modifiers such as power-aware softening and an ethics veto.

## CLI jobs

The CLI is organized around five user jobs:

- **Analyze an interaction**
- **Get a next-move recommendation**
- **Simulate scenarios**
- **Review relationship journal**
- **Learn the model**

## Repository structure

```text
metatft_repo/
├── CHANGELOG.md
├── LICENSE
├── MetaTFT_Spec.md
├── README.md
├── requirements.txt
├── setup.py
└── metatft/
    ├── __init__.py
    ├── __main__.py
    ├── cli.py
    ├── engine.py
    ├── ethics.py
    ├── models.py
    ├── modules.py
    ├── storage.py
    └── utils.py
```

## Installation

```bash
pip install -r requirements.txt
pip install .
```

## Run

```bash
metatft
```

Or:

```bash
python -m metatft
```

## What the recommendation screen now shows

Each recommendation is layered:

- **Executive answer**
- **Strategic explanation**
- **Technical evidence**
- **Do this / Avoid this**
- **What would change the answer**
- **Why not the nearest alternatives**

That makes the tool more legible, more inspectable, and more useful in real situations.

## Simulation

The simulator supports classic opponents:

- always cooperate
- always defect
- random
- TFT
- grudger
- detective

It reports score, average payoff, cooperation rate, and module usage.

## Journal

The journal stores relationship history across sessions and supports:

- opponent timelines
- cooperation deficit tracking
- GTFO evaluation
- notes and reputation scores
- import/export of opponent profiles

## Philosophy

MetaTFT is best thought of as:

> a decision system for when to cooperate, when to retaliate, when to forgive, and when to leave.

That is more honest and more powerful than claiming one strategy wins everywhere.
