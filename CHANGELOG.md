# Changelog

All notable changes to MetaTFT will be documented here.

## [1.0.0] — 2025

### Added
- Full MetaTFT spec implementation across 10 strategy modules
- Environment classifier with 5-signal system and confidence scoring
- Composable module stack with defined priority order
- Always-on ethics veto layer (3 hard constraints)
- GTFO threshold with cooperation deficit + EV projection formula
- Stochastic switching logic to defeat threshold-gaming
- Exponential time-decay memory (λ=0.85)
- Mandatory fresh-start parole probes at geometric intervals
- Wald-Wolfowitz runs test for noise authenticity detection
- Bayesian noise rate estimation from interaction history
- **Advisor mode** — 5-question guided interview → full recommendation
- **Simulator mode** — 6 classic bots (always-defect, always-cooperate, random, TFT, grudger, detective)
- **Journal mode** — log real interactions, GTFO alerts, reputation tracking
- **Heuristic mode** — 3-question shorthand + module reference
- **Settings mode** — all engine parameters configurable at runtime
- JSON state persistence to `~/.metatft/state.json`
- Export/import opponent data
