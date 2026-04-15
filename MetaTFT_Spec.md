# MetaTFT — A Universal Adaptive Cooperation Strategy
**Version 1.0 | Full Specification**

---

## 0. Preamble

Tit-for-Tat (TFT) is the most robust cooperation strategy discovered in iterated game theory. It is nice, provocable, forgiving, and clear. But it is context-blind — it assumes a clean, bilateral, iterated, symmetric, rational game with no noise. The real world violates every one of those assumptions.

MetaTFT is a meta-strategy: a system that reads the game environment before each move and deploys the appropriate TFT variant. Base TFT is not replaced — it is the engine that all modules inherit from. MetaTFT adds three layers above it: an environment classifier, a module library, and switching logic. An ethics constraint and exit conditions operate as vertical vetoes across all layers.

**Design priorities (in order):**
1. Maximum long-term payoff
2. Fairness / ethical grounding
3. Robustness against exploitation
4. Relationship preservation

---

## 1. Core Principles (Inherited by All Modules)

Every module in MetaTFT preserves TFT's four foundational properties:

| Property | Definition | Why it matters |
|---|---|---|
| **Niceness** | Never defect first | Avoids unnecessary conflict, signals non-aggression |
| **Provocability** | Punish defection immediately | Removes incentive to exploit |
| **Forgiveness** | Return to cooperation when opponent cooperates | Prevents lock-in to mutual defect |
| **Clarity** | Behavior is legible and consistent within a module | Reduces defensive defection from uncertainty |

These are non-negotiable. Any "fix" that requires violating one of these properties is itself a bug, not a solution.

---

## 2. System Architecture

MetaTFT operates as three stacked layers with two cross-cutting systems:

```
┌──────────────────────────────────────────────────┐
│  ETHICS VETO (always-on, runs before any output) │
├──────────────────────────────────────────────────┤
│  L1: Environment Classifier                      │
│      5 signals → confidence score → module select│
├──────────────────────────────────────────────────┤
│  L2: Module Library (composable)                 │
│      8 modules, stackable with priority rules    │
│      ┌──────────────────────────────────────┐   │
│      │  Switching Logic (stochastic)        │   │
│      └──────────────────────────────────────┘   │
├──────────────────────────────────────────────────┤
│  L3: Base TFT Engine                             │
│      Mirror last move. Inherited by all modules  │
├──────────────────────────────────────────────────┤
│  REPUTATION LOG (feedback into L1 next round)    │
│  EXIT THRESHOLD (cross-layer veto)               │
└──────────────────────────────────────────────────┘
```

---

## 3. Environment Classifier

Before every move, score these five signals. Each signal has a **confidence weight** (0.0–1.0). If aggregate confidence < 0.5, default to **Generous TFT** regardless of signal values — uncertainty is itself a signal.

### Signal 1: Game Horizon
**Question:** How many future rounds are expected?

| Reading | Threshold | Flag |
|---|---|---|
| Open-ended / unknown | N > 10 expected | `REPEATED` |
| Short / finite | 1 < N ≤ 10 | `SHORT` |
| Single encounter | N = 1 | `ONE_SHOT` |

**Confidence degraders:** Ambiguous relationship length, no prior history, opponent could exit at any time.

### Signal 2: Channel Noise
**Question:** How likely is a cooperative move to be misread as defection (or vice versa)?

Estimate noise rate `ε` from: communication channel quality, cultural/linguistic gap, third-party interference, track record of misunderstandings.

| Reading | Threshold | Flag |
|---|---|---|
| Clean channel | ε < 0.05 | `LOW_NOISE` |
| Moderate noise | 0.05 ≤ ε < 0.20 | `NOISY` |
| High noise | ε ≥ 0.20 | `HIGH_NOISE` |

**Critical:** Run a noise authenticity test. True noise is random (Poisson-distributed). Strategic noise-mimicry clusters around payoff-rich moments. If opponent defections correlate with your high-value cooperative offers, reclassify as strategic, not noisy.

### Signal 3: Player Count
**Question:** Are there third parties whose actions affect your payoffs or reputation?

| Reading | Flag |
|---|---|
| Two-player bilateral | `BILATERAL` |
| Observable by third parties | `NETWORKED` |
| Multi-player with coalition dynamics | `MULTI_PLAYER` |
| Commons / public goods structure | `COLLECTIVE` |

### Signal 4: Opponent Type
Classify based on observed defection rate over the last N rounds (minimum 3 rounds before classification):

| Defection Rate | Classification | Flag |
|---|---|---|
| 0–20% | Cooperative | `COOP` |
| 20–60% | Mixed / strategic | `MIXED` |
| 60–80% | Conditionally defective | `COND_DEFECT` |
| > 80% | Pure defector | `PURE_DEFECT` |
| Uncorrelated with payoff | Irrational / ideological | `IRRATIONAL` |

**Irrational detection:** If defection continues even when it visibly costs the opponent and no third-party audience is present, flag as `IRRATIONAL`. Strategic irrationality-mimicry always requires an audience or downstream payoff.

### Signal 5: Temporal Context
| Reading | Flag |
|---|---|
| End date unknown / ambiguous | `OPEN` |
| End date known to both players | `BOUNDED` |
| Opponent is highly impatient (short time-discount) | `IMPATIENT` |
| Power asymmetry: opponent >> you | `ASYMMETRIC` |

### Confidence Scoring
Rate your confidence in each signal read from 0.0 (pure guess) to 1.0 (verified). Aggregate confidence = mean of all five. If aggregate < 0.5, deploy **Generous TFT** and flag environment as `UNCERTAIN`.

---

## 4. Module Library

### Module Stacking Rules

Modules are not always mutually exclusive. Apply the following priority order when multiple flags are active:

1. **Irrationality module** (overrides all others — standard incentive logic doesn't apply)
2. **Noise correction** (wraps output of any other module — misread signals corrupt everything else)
3. **Collective/commons module** (overrides bilateral optimization when commons structure detected)
4. **Power asymmetry module** (modifies reciprocation intensity before other modules execute)
5. **Domain-specific module** (multi-player, one-shot, end-date, impatient)
6. **Base TFT** (default when no flags are raised)

---

### Module 1: Base TFT
**Activates when:** `REPEATED + LOW_NOISE + BILATERAL + MIXED/COOP + OPEN`

The unchanged original. Cooperate round 1, then mirror exactly.

**Behavior:** Cooperate if opponent cooperated last round. Defect if opponent defected last round.

---

### Module 2: Generous TFT
**Activates when:** `NOISY` or `HIGH_NOISE` or `UNCERTAIN`

**Core fix:** In noisy environments, strict mirroring punishes accidents. Forgive a fraction of defections to prevent retaliation spirals.

**Forgiveness rate formula:**
```
p_forgive = min(ε_estimated × 1.5, 0.25)
```
Where `ε_estimated` is the estimated noise rate. Cap at 0.25 — forgiveness above 25% becomes exploitable regardless of noise levels.

**Noise authenticity test:** Compute the runs test statistic on opponent's defection history. If defections cluster (p < 0.05), reclassify to strategic and reduce `p_forgive` by 50%.

**Behavior:** Defect last round → cooperate with probability `p_forgive`, defect with `1 - p_forgive`. Three consecutive defections always trigger punishment regardless of forgiveness rate.

---

### Module 3: Stake-and-Signal
**Activates when:** `ONE_SHOT` or `SHORT + LOW_TRUST`

**Core fix:** The TFT threat (I'll mirror you next round) has no weight in one-shot games. Replace future-threat with present-cost.

**Mechanism:**
1. Open with a **costly signal** — a commitment that is irrational to make if you intend to defect. Examples: deposits, public statements, third-party escrow, information asymmetry surrender.
2. Signal cost must exceed the gain from defecting after signal (otherwise it's cheap talk).
3. If opponent does not reciprocate with a commensurate signal within 1–2 rounds, cooperate minimally and prepare to exit.
4. If no signal infrastructure exists (anonymous, no third parties, no escrow), fall through to exit.

**Low-trust calibration:** In environments where costly signals aren't recognized or understood culturally, use third-party-verified signals (contracts, institutional witnesses) rather than self-reported ones.

---

### Module 4: Pavlov (Win-Stay, Lose-Shift)
**Activates when:** `IMPATIENT + COOP/MIXED + REPEATED` (never as a primary module, only as a lock-in accelerator)

**Core fix:** TFT is slow to establish mutual cooperation. Impatient opponents need proof-of-concept quickly. Pavlov finds mutual cooperation faster.

**Behavior:** Did I "win" last round (mutual cooperation or exploiting defector)?
- Yes → repeat last move
- No → switch move

**Prerequisites before activation:**
- Minimum 5 rounds of history (never deploy cold)
- Impatience signal independently confirmed by non-game cues (explicit deadline, urgency language, prior pattern)
- Switch back to base TFT if Pavlov creates a defection lock (both players stuck defecting for 3+ rounds)

---

### Module 5: Grim-with-Parole
**Activates when:** `PURE_DEFECT + REPEATED`

**Core fix:** Against always-defectors, base TFT locks in mutual defect. Grim-with-Parole defects indefinitely but tests for genuine change.

**Mechanism:**
1. Opponent classified as `PURE_DEFECT` after ≥ 5 consecutive defections
2. Switch to permanent defect
3. Schedule parole probes at interval `K`:
   ```
   K = ceil(1 / defection_rate × (1 / discount_factor))
   ```
4. Parole probe: offer a **graduated** cooperative gesture (small, not full), not full cooperation — exposure is limited
5. If probe is met with cooperation → reset to base TFT, start fresh
6. If probe is met with defection → extend grim phase, double K for next probe

**Exit condition:** After 3 failed paroles with no improvement, trigger GTFO threshold evaluation.

---

### Module 6: Network TFT
**Activates when:** `NETWORKED` or `MULTI_PLAYER`

**Core fix:** In multi-player environments, bilateral mirroring is insufficient. Your reputation across the network is the primary asset, not any single interaction's outcome.

**Mechanism:**
1. Compute opponent's **network reputation score** from independent observers (weight by source independence — tightly clustered social networks give a single effective opinion, not multiple)
2. Cooperate with agents whose reputation score > threshold `R_coop`
3. Defect with agents below `R_defect` regardless of their bilateral behavior toward you
4. **Make your moves observable** when possible — defections against known bad actors build your reputation; cooperations with good actors are demonstrated
5. Adjust your own behavior based on what observers can see, not just bilateral payoffs

**Reputation verification:**
```
verified_reputation = raw_score × source_independence_factor
source_independence_factor = 1 - (cluster_coefficient of observer network)
```
A reputation confirmed by friends-of-friends counts much less than one confirmed by structurally separate observers.

---

### Module 7: Shadow-Extender
**Activates when:** `BOUNDED` (known end date)

**Core fix:** Known end dates enable backward induction — cooperation unravels from the last round backward. Make the last round ambiguous or extend the shadow of the future.

**Mechanisms (in priority order):**
1. **Introduce ongoing stakes** that survive the game's formal end — reputation leakage into adjacent domains, documented history, public record
2. **Create binding mid-game commitments** that would be costly to violate even on the "last" round
3. **Obfuscate the horizon** — genuinely or by introducing contingencies that make the end date uncertain
4. **Reframe the game** — make the opponent aware that you'll interact with their reputation (not just them) after this game ends

**Fallback:** If all shadow-extension mechanisms are structurally impossible (fully anonymous, zero reputation overflow), fall through to Stake-and-Signal.

---

### Module 8: Irrationality Mode
**Activates when:** `IRRATIONAL`

**Core fix:** Standard TFT variants assume payoff-sensitive actors. Ideological, emotional, or revenge-motivated actors don't respond to cooperation incentives.

**Detection criteria** (all three must be present):
- Defection continues after your generous moves
- Defection is costly to the opponent (self-damaging behavior)
- No visible third-party audience (rules out strategic irrationality-mimicry)

**Behavior in Irrationality Mode:**
1. Stop optimizing for cooperation — it won't work
2. Minimize exposure: don't offer large cooperative gestures that can be exploited
3. Signal to third-party observers — your behavior is now primarily reputational, not bilateral
4. Engage only at minimal necessary levels
5. Document and exit when the GTFO threshold is reached

**Note:** Do not confuse irrationality with "playing a different game than you think." The opponent may be rational within a different payoff structure (loyalty, honor, ideology). Investigate the actual payoff structure before triggering this module.

---

### Module 9: Commons Mode
**Activates when:** `COLLECTIVE`

**Core fix:** In public-goods and commons games, individual MetaTFT applied by every player produces collective defection even when each player is locally rational. The problem is the game structure, not the players.

**Behavior:**
1. Cooperate unconditionally into the commons (don't mirror individual actors)
2. Make your cooperation visible — signal norm-adherence to all players
3. Actively advocate for coordination infrastructure (rules, monitoring, sanctions against defectors)
4. Direct punishment at defectors' reputation, not bilateral interaction
5. Escalate to institutional actors if defection is systemic

**The key insight:** In commons games, your goal is not to win bilateral exchanges — it is to change the game's payoff structure so that cooperation becomes the dominant strategy for everyone.

---

### Module 10: Power-Asymmetry Mode
**Activates when:** `ASYMMETRIC`

**Core fix:** When your opponent has overwhelming structural power, bilateral TFT reciprocation is suicidal. You cannot afford to match their defections, and they know it.

**Power ratio assessment:**
```
power_ratio = opponent_leverage / your_leverage
```
Where leverage = ability to impose costs on the other party.

| Power Ratio | Mode |
|---|---|
| < 2:1 | Normal module selection |
| 2:1 – 5:1 | Modified TFT (cooperate slightly more than strict reciprocity) |
| > 5:1 | Strategic compliance mode |

**Strategic compliance mode:**
1. Cooperate beyond strict reciprocity to preserve the relationship
2. Build reputation with third parties who may rebalance the dynamic
3. Accumulate leverage quietly (information, allies, alternatives)
4. Set and maintain **private red lines** — actions you will not perform regardless of pressure, known to yourself even if not announced
5. Exit when you've built sufficient leverage, not before

---

## 5. Switching Logic

### Re-evaluation Triggers
The module selection re-evaluates at:
1. Every `N` rounds (default: `N = max(5, game_length / 10)`)
2. On any **signal spike**: sudden change in defection rate (> 2σ from baseline), new player entry, horizon information update, explicit threat or offer

### Stochastic Switching
To prevent sophisticated opponents from gaming the switching thresholds:

```
switch_decision = (signal_score > threshold) AND (random() > stochastic_block)
stochastic_block = 0.15  # 15% of the time, don't switch even when threshold met
```

The stochasticity is a **known policy** (legible) but its exact parameterization is private. "I adapt to how you play, but not mechanically" is a comprehensible and honest signal.

**Important:** Stochasticity applies only to module *selection*. Once a module is deployed, it behaves consistently and predictably within that round-block. Partners experience consistent rules within interactions even if the meta-level is adaptive.

### Time-Decay Memory
The reputation log applies exponential decay:

```
weighted_reputation(t) = Σ move(t-i) × λ^i
λ = 0.85  # decay factor; tune to game length
```

Recent behavior weights more than old behavior. This prevents permanent lock-in to outdated opponent classifications and allows for genuine phase transitions in relationships.

### Mandatory Fresh-Start Probes
Regardless of current opponent classification, schedule a cooperative reset probe at geometric intervals:
- First probe: after `2K` rounds in punish mode
- Second probe: after `4K` rounds
- Third probe: after `8K` rounds
- After third failed probe: activate GTFO threshold evaluation

---

## 6. Reputation & Memory System

### What Gets Logged Each Round

```
move_log_entry = {
  round: int,
  my_move: cooperate | defect,
  opponent_move: cooperate | defect,
  active_module: string,
  classifier_signals: [s1, s2, s3, s4, s5],
  classifier_confidence: float,
  noise_test_result: random | clustered,
  payoff: float,
  context_notes: string
}
```

### Derived Metrics (updated each round)

- `defection_rate_rolling`: rolling defection rate over last 10 rounds
- `cooperation_deficit`: cumulative (my cooperation - opponent cooperation), weighted by recency
- `noise_estimate_ε`: updated using Bayesian update from observed move variance
- `opponent_type_confidence`: confidence in current opponent classification
- `EV_projection`: expected value projection of each available module over next 10 rounds

---

## 7. Ethics Layer (Always-On Veto)

The ethics layer runs before any module output is enacted. It cannot be overridden by any module, including Power-Asymmetry or Commons mode. It has three hard constraints:

### Constraint 1: No Third-Party Harm
Do not cooperate with an actor whose gains from your cooperation require harm to uninvolved third parties. Bilateral optimization that externalizes costs to others is not cooperation — it is collusion.

*Test:* Would a neutral third party with full information object to this cooperation?

### Constraint 2: Fairness Floor
Do not execute moves that exploit significant power asymmetry in your *favor*. This applies even when you *have* the power and even when it would maximize your payoff. The optimal long-term strategy is not the one that maximizes extraction — it is the one that maintains legitimacy.

*Operationalization:* If your payoff from this move exceeds the opponent's by more than `fairness_multiplier × their_payoff`, flag for review before executing.
Default `fairness_multiplier = 3.0` — you can gain more than them, but not arbitrarily more.

### Constraint 3: Categorical Exit
Do not cooperate with actors whose stated or demonstrated goals require harm to persons not party to the game. No payoff level justifies this cooperation. Trigger immediate exit.

---

## 8. Exit Conditions (GTFO Threshold)

Staying in a game with negative expected value is not a strategy — it is inertia. MetaTFT includes an explicit exit condition.

### Exit Evaluation (runs when triggered by module or probe failure)

```
EV_recovery = max(EV_projection across all modules)
cooperation_deficit_current = cumulative cooperation deficit
rounds_remaining = estimated horizon

exit_score = cooperation_deficit_current / (EV_recovery × rounds_remaining)
```

**If `exit_score > 2.0`**: initiate exit.

### Exit Protocol
1. **Signal intent** to exit where possible — don't ghost, especially in high-reputation environments
2. **Execute outstanding commitments** before leaving — unilateral exit on commitments is a reputational cost
3. **Document** the interaction for your reputation log and any relevant third parties
4. **Do not burn bridges** unless the exit is triggered by Constraint 3 (categorical harm), in which case public documentation may be appropriate

---

## 9. Heuristic Shorthand (Real-Time Version)

The full framework is too detailed for real-time human decision-making. Internalize this compressed version:

> **Before any move, ask three things:**
> 1. *Will I interact with this person again, and does the future matter to them?* → If no: signal honestly and exit if not reciprocated.
> 2. *Am I reading them accurately, or is this situation messy?* → If messy: be more forgiving than you feel you should be.
> 3. *Are the rules of this game fair and bilateral?* → If not: stop trying to win the game; start trying to change it.
>
> Otherwise: cooperate first, mirror what you receive, forgive once, punish consistently, and stay legible.

---

## 10. Worked Examples

### Example A: Business Partnership (noisy, bilateral, repeated)
Signals: `REPEATED`, `NOISY` (email communication, cultural gap), `BILATERAL`, `MIXED`, `OPEN`
Module: **Generous TFT**
In practice: When a partner misses a deadline or sends an ambiguous signal, don't retaliate immediately. Apply noise forgiveness (p ≈ 0.10). Respond with a direct clarifying question before assuming defection. After three instances of the same "noise," reclassify as strategic.

### Example B: One-time negotiation with a stranger
Signals: `ONE_SHOT`, `LOW_TRUST`, `BILATERAL`, `UNKNOWN`, `OPEN`
Module: **Stake-and-Signal**
In practice: Don't lead with trust. Lead with a verifiable commitment — a signed term sheet, a public offer, a money-in-escrow signal. Watch whether they reciprocate with something that costs them. If they do, cooperate. If they don't, minimize exposure and close the interaction.

### Example C: Workplace with a toxic colleague (pure defector, asymmetric power)
Signals: `REPEATED`, `LOW_NOISE`, `NETWORKED`, `PURE_DEFECT`, `ASYMMETRIC`
Modules stacked: **Power-Asymmetry** → **Grim-with-Parole** → **Network TFT**
In practice: Don't match their defections in ways that damage you. Cooperate minimally to preserve the professional relationship. Make your reliability visible to the broader network. Schedule a parole probe after 2–3 months. Simultaneously build leverage (document incidents, build alliances, develop alternatives). Exit when leverage permits.

### Example D: Social media / public discourse (multi-player, collective)
Signals: `NETWORKED`, `MULTI_PLAYER`, `COLLECTIVE`, `HIGH_NOISE`, `MIXED`
Modules stacked: **Commons Mode** → **Generous TFT**
In practice: Don't mirror bad actors — that amplifies them. Cooperate with the norm you want to establish. Make your cooperation visible. Advocate for platform-level coordination mechanisms. Punish defectors via reputation signaling to third parties, not bilateral escalation.

### Example E: High-stakes negotiation with known deadline (bounded, impatient, multi-player)
Signals: `SHORT`, `BOUNDED`, `NETWORKED`, `MIXED`, `IMPATIENT`
Modules stacked: **Shadow-Extender** → **Pavlov** (accelerator after cooperation established)
In practice: Early on, introduce reputation stakes that outlast the negotiation ("we'll work together again," "this deal will be public record"). Once mutual cooperation is established and the partner has signaled urgency, switch to Pavlov to lock in cooperation quickly before the deadline.

---

## 11. Known Limitations

1. **Signal accuracy is the foundational vulnerability.** MetaTFT is only as good as its environment reads. In deeply ambiguous or adversarially obscured environments, the classifier degrades and the system defaults to its most conservative posture (Generous TFT + uncertainty flag). This is correct but not powerful.

2. **The irrationality module is binary.** Real actors exist on a spectrum between pure payoff-maximizers and pure ideologues. The module handles endpoints well but provides less guidance for the middle.

3. **Cultural calibration is underspecified.** "Costly signal" means different things in different cultural contexts. The framework identifies the principle; the practitioner must calibrate the implementation to context.

4. **Collective good vs. individual payoff tension.** When Commons Mode is active, short-term individual payoff is explicitly sacrificed for collective benefit. This is ethically correct per the design priorities, but creates real costs. MetaTFT does not pretend otherwise.

5. **Exit is easier to specify than to execute.** The GTFO threshold gives a principled trigger; the social and psychological difficulty of actually exiting harmful games is a human problem that no strategy framework fully solves.

---

## 12. Version Notes

| Version | Change |
|---|---|
| v0.1 | Base TFT + 6 modules |
| v0.2 | Added module composability and stacking rules |
| v0.3 | Added stochastic switching to defeat threshold-gaming |
| v0.4 | Added time-decay memory and fresh-start probes |
| v0.5 | Added irrationality detection module |
| v0.6 | Added ethics veto layer |
| v0.7 | Added exit conditions (GTFO threshold) |
| v0.8 | Added power-asymmetry module |
| v0.9 | Added commons/collective-good module |
| v1.0 | Added noise authenticity test, heuristic shorthand, worked examples |

---

*MetaTFT is a living specification. The correct response to finding a new edge case is to extend the module library, not to patch the base engine.*
