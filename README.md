# MetaTFT

MetaTFT is a terminal-first decision system for reciprocal strategy.

It does **not** assume Tit for Tat is universally best. Instead, it treats plain TFT as a strong baseline for clean repeated bilateral play, then adds environment classification, policy selection, structural modifiers, ethics checks, and exit logic for the cases where plain TFT breaks down.

## What is new in this pass

This pass closes several of the remaining gaps from the earlier build:

- stronger policy selection and modifier application
- explicit command-line tooling beyond the interactive menu
- scenario-pack simulation for common edge-case environments
- journal regime detection
- repository cleanup for GitHub use
- automated tests for core decision logic
- fixed storage/export behavior and cleaner packaging

## Product framing

MetaTFT is best thought of as:

> a decision system for when to cooperate, when to retaliate, when to forgive, and when to leave.

## Core decision flow

MetaTFT asks:

1. Will this interaction repeat?
2. How noisy or ambiguous is the signal channel?
3. Is this bilateral, networked, multi-player, or a commons problem?
4. What kind of opponent are you facing?
5. Is there a bounded horizon, impatience, or strong power asymmetry?

Then it chooses a base policy such as:

- Base TFT
- Generous TFT
- Stake-and-Signal
- Pavlov
- Grim-with-Parole
- Network TFT
- Shadow-Extender
- Irrationality Mode
- Commons Mode

Then it applies structural modifiers such as:

- noise softening
- network trust boost
- shadow extension reminders
- power-aware retaliation softening
- ethics veto
- GTFO threshold

## Interactive CLI jobs

The interactive UI is organized around:

- **Analyze an interaction**
- **Get a next-move recommendation**
- **Simulate scenarios**
- **Review relationship journal**
- **Learn the model**
- **Settings**

## Additional command mode

You can also use direct commands:

```bash
metatft doctor
metatft explain overview
metatft explain generous_tft
metatft simulate-pack clean_repeated
metatft simulate-pack hard_defector
```

## Scenario packs

The current repo includes named packs for:

- `clean_repeated`
- `noisy_repeated`
- `short_horizon_opportunist`
- `hard_defector`
- `desperate_actor`

These make it easier to test MetaTFT against specific failure modes rather than only generic bots.

## Recommendation output

Each recommendation is layered:

- executive answer
- strategic explanation
- technical evidence
- do this / avoid this
- what would change the answer
- why not the nearest alternatives

## Journal features

The journal now supports:

- opponent timelines
- cooperation deficit tracking
- GTFO evaluation
- notes and reputation scores
- import/export of opponent profiles
- lightweight regime detection, such as:
  - stable reciprocity
  - noisy disruption
  - opportunistic extraction
  - hardened defection

## Repository structure

```text
metatft_repo/
├── .gitignore
├── CHANGELOG.md
├── LICENSE
├── MetaTFT_Spec.md
├── README.md
├── requirements.txt
├── setup.py
├── metatft/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── engine.py
│   ├── ethics.py
│   ├── models.py
│   ├── modules.py
│   ├── storage.py
│   └── utils.py
└── tests/
    └── test_engine.py
```

## Install

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

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Philosophy

MetaTFT is not trying to prove one elegant policy wins everywhere.
It is trying to help the user classify the environment first, then respond in a way that is strategically sound, legible, and humane.
