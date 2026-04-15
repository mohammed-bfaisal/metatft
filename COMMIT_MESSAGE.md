feat: MetaTFT v2 — align engine with spec, redesign CLI around user jobs, and add layered decision explainability

This commit upgrades MetaTFT from a promising prototype into a much stronger spec-aligned CLI decision system.

Strategic core
- replace the mostly symbolic module-selection flow with real policy selection
- introduce a clearer separation between base policy choice and modifier application
- add explicit stack construction so commons, noise, power asymmetry, and irrationality concerns are represented coherently
- add a real power modifier that can soften retaliation when the opponent holds structural leverage
- improve classifier outputs with exploit risk, misread risk, endgame risk, relationship value, and evidence traces
- improve confidence scoring so it reflects more than simple field availability
- correct GTFO scoring so projected recovery is not effectively multiplied by horizon twice

Decision quality and explainability
- add layered recommendation objects with executive summary, strategic explanation, evidence lines, action steps, avoid steps, and answer-change conditions
- add nearest-alternative candidate scoring so the CLI can answer “why not the other modules?”
- add clearer tactical notes and flag traces for each recommendation
- preserve ethics veto handling while making its effect explicit in the final result

CLI redesign
- reframe the product around user jobs instead of raw internal modes
- replace the old framing with a more honest product identity: a system for when to cooperate, retaliate, forgive, and leave
- add stronger analysis dashboards using rich panels, tables, gauges, and timelines
- improve analyze and recommend flows so users can inspect reasoning before logging outcomes
- improve simulation output with clearer summaries and module usage reporting
- improve journal readability with opponent profile views and round timelines
- add a stronger learn/explain mode so the app teaches the model as well as applying it

Data model and utilities
- expand environment signals to include power ratio, risk metrics, relationship value, and evidence
- add richer result and candidate dataclasses for structured rendering
- improve noise estimation and noise-authenticity checks
- add trust scoring and ASCII gauge/timeline helpers for terminal visualization
- preserve backward-friendly JSON state persistence through the existing storage layer

Repo and packaging
- bump version to 2.0.0
- refresh README so the repo narrative matches the improved engine and CLI
- update requirements and setup metadata
- add this commit note file for maintainable GitHub history and handoff clarity

Net effect
- MetaTFT now behaves much closer to the design intent described in the spec
- recommendations are more inspectable, more actionable, and more legible in the terminal
- the project is packaged more cleanly for direct GitHub use and future iteration
