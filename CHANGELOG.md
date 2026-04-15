# Changelog

## 2.0.0

### Strategic core
- Reworked the engine so recommendations now come from real policy selection instead of a mostly symbolic stack.
- Added a base-policy chooser that maps environment signals to the most appropriate strategy family.
- Added stack construction so noise, power, commons, and irrationality concerns are represented explicitly.
- Implemented a real power modifier that can soften retaliation when structural asymmetry is high.
- Improved classifier evidence with exploitation risk, misread risk, endgame risk, relationship value, and a clearer confidence model.
- Corrected GTFO scoring so projected recovery is not effectively multiplied by horizon twice.

### Recommendation quality
- Added layered explanations: executive summary, strategic explanation, evidence lines, action steps, avoid steps, and change conditions.
- Added candidate-module comparison so users can inspect the nearest alternatives.
- Added “why not” explanation lines for stronger trust in the recommendation.

### CLI redesign
- Reframed the top-level product around user jobs rather than raw internal modes.
- Added more visual dashboards using rich panels, tables, gauges, and timelines.
- Improved analyze and recommend flows so users can inspect the reasoning before logging outcomes.
- Expanded Learn mode so the product can also explain itself.

### Packaging
- Refreshed README to match the stronger framing.
- Kept installation simple with requirements.txt and setup.py.
