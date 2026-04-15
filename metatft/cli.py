import sys
import random
from typing import Optional

import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich import box

from .models import (
    Move, MetaTFTState, Opponent,
    HorizonFlag, NoiseFlag, PlayerFlag, OpponentFlag, TemporalFlag, ModuleName
)
from .engine import MetaTFTEngine
from .storage import load_state, save_state, export_opponent, import_opponent
from .utils import get_payoff, project_ev

console = Console()

Q_STYLE = Style([
    ("qmark",     "fg:#5DCAA5 bold"),
    ("question",  "bold"),
    ("answer",    "fg:#7F77DD bold"),
    ("pointer",   "fg:#5DCAA5 bold"),
    ("highlighted","fg:#5DCAA5 bold"),
    ("selected",  "fg:#5DCAA5"),
    ("separator", "fg:#444441"),
    ("instruction","fg:#888780"),
])

MODULE_COLORS = {
    "Base TFT":           "cyan",
    "Generous TFT":       "green",
    "Stake-and-Signal":   "yellow",
    "Pavlov":             "magenta",
    "Grim-with-Parole":   "red",
    "Network TFT":        "blue",
    "Shadow-Extender":    "purple4",
    "Irrationality Mode": "bright_red",
    "Commons Mode":       "bright_green",
    "Power-Asymmetry":    "orange3",
}

MOVE_COLOR = {Move.COOPERATE: "green", Move.DEFECT: "red"}
MOVE_ICON  = {Move.COOPERATE: "C", Move.DEFECT: "D"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def header():
    console.print()
    console.print(Panel(
        "[bold]MetaTFT[/bold]  [dim]—  Universal Adaptive Cooperation Strategy[/dim]",
        border_style="dim",
        padding=(0, 2),
    ))
    console.print()


def section(title: str):
    console.print()
    console.print(Rule(f"[dim]{title}[/dim]", style="dim"))
    console.print()


def move_badge(move: Move) -> str:
    color = MOVE_COLOR[move]
    icon = MOVE_ICON[move]
    return f"[{color} bold]{icon}[/{color} bold]"


def module_badge(name: str) -> str:
    color = MODULE_COLORS.get(name, "white")
    return f"[{color}]{name}[/{color}]"


def confidence_bar(score: float, width: int = 20) -> str:
    filled = int(score * width)
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if score >= 0.7 else "yellow" if score >= 0.5 else "red"
    return f"[{color}]{bar}[/{color}] {score:.0%}"


def get_or_create_opponent(state: MetaTFTState, prompt_text: str = "Opponent name") -> Optional[Opponent]:
    names = list(state.opponents.keys())
    choices = names + ["[ + Create new ]"]
    choice = questionary.select(prompt_text, choices=choices, style=Q_STYLE).ask()
    if choice is None:
        return None
    if choice == "[ + Create new ]":
        name = questionary.text("Enter a name for this opponent:", style=Q_STYLE).ask()
        if not name:
            return None
        name = name.strip()
        opp = Opponent(name=name)
        state.opponents[name] = opp
        save_state(state)
        console.print(f"[green]Created opponent:[/green] {name}")
        return opp
    return state.opponents[choice]


# ── Mode 1: Advisor ───────────────────────────────────────────────────────────

def advisor_mode(state: MetaTFTState):
    engine = MetaTFTEngine(state)
    section("ADVISOR MODE")
    console.print("[dim]Describe your real situation. MetaTFT will classify the environment and recommend a strategy.[/dim]")
    console.print()

    opp = get_or_create_opponent(state, "Who are you dealing with?")
    if opp is None:
        return

    # Questionnaire
    console.print()
    console.print("[dim]Answer a few questions to calibrate the classifier:[/dim]")
    console.print()

    # Q1: Horizon
    horizon_raw = questionary.select(
        "Will you interact with this person again?",
        choices=[
            "Yes, many times (open-ended relationship)",
            "A few more times (short but repeated)",
            "Just this one time",
            "Not sure",
        ],
        style=Q_STYLE,
    ).ask()
    horizon_map = {
        "Yes, many times (open-ended relationship)": HorizonFlag.REPEATED,
        "A few more times (short but repeated)": HorizonFlag.SHORT,
        "Just this one time": HorizonFlag.ONE_SHOT,
        "Not sure": HorizonFlag.UNKNOWN,
    }
    horizon = horizon_map.get(horizon_raw, HorizonFlag.UNKNOWN)

    # Q2: Noise
    noise_raw = questionary.select(
        "How clean is communication with them?",
        choices=[
            "Very clear — we understand each other well",
            "Sometimes things get misread or misunderstood",
            "Frequently unclear, ambiguous signals",
        ],
        style=Q_STYLE,
    ).ask()
    noise_map = {
        "Very clear — we understand each other well":        (NoiseFlag.LOW,   0.03),
        "Sometimes things get misread or misunderstood":     (NoiseFlag.NOISY, 0.10),
        "Frequently unclear, ambiguous signals":             (NoiseFlag.HIGH,  0.25),
    }
    noise_flag, noise_est = noise_map.get(noise_raw, (NoiseFlag.LOW, 0.05))

    # Q3: Players
    players_raw = questionary.select(
        "Is this purely a 1-on-1 dynamic, or are others watching/involved?",
        choices=[
            "Just the two of us — private",
            "Others can see our behavior (reputation matters)",
            "Multiple parties all affecting each other",
            "This affects a shared resource (commons)",
        ],
        style=Q_STYLE,
    ).ask()
    players_map = {
        "Just the two of us — private":                       PlayerFlag.BILATERAL,
        "Others can see our behavior (reputation matters)":   PlayerFlag.NETWORKED,
        "Multiple parties all affecting each other":          PlayerFlag.MULTI_PLAYER,
        "This affects a shared resource (commons)":           PlayerFlag.COLLECTIVE,
    }
    players = players_map.get(players_raw, PlayerFlag.BILATERAL)

    # Q4: Opponent type
    opp_raw = questionary.select(
        "How has this person behaved so far?",
        choices=[
            "Mostly cooperative and good faith",
            "Mixed — sometimes cooperative, sometimes not",
            "Mostly uncooperative / self-interested",
            "Consistently hostile or exploitative",
            "Unpredictable — doesn't seem to respond to incentives",
        ],
        style=Q_STYLE,
    ).ask()
    opp_map = {
        "Mostly cooperative and good faith":                         OpponentFlag.COOPERATIVE,
        "Mixed — sometimes cooperative, sometimes not":              OpponentFlag.MIXED,
        "Mostly uncooperative / self-interested":                    OpponentFlag.COND_DEFECT,
        "Consistently hostile or exploitative":                      OpponentFlag.PURE_DEFECT,
        "Unpredictable — doesn't seem to respond to incentives":     OpponentFlag.IRRATIONAL,
    }
    opp_type = opp_map.get(opp_raw, OpponentFlag.UNKNOWN)

    # Q5: Temporal
    temporal_raw = questionary.select(
        "What's the time structure of this situation?",
        choices=[
            "Open-ended — no fixed deadline",
            "Has a known end point (contract ends, project finishes, etc.)",
            "They're impatient or under pressure for quick results",
            "They have significantly more power than me",
        ],
        style=Q_STYLE,
    ).ask()
    temporal_map = {
        "Open-ended — no fixed deadline":                            TemporalFlag.OPEN,
        "Has a known end point (contract ends, project finishes, etc.)": TemporalFlag.BOUNDED,
        "They're impatient or under pressure for quick results":     TemporalFlag.IMPATIENT,
        "They have significantly more power than me":                TemporalFlag.ASYMMETRIC,
    }
    temporal = temporal_map.get(temporal_raw, TemporalFlag.OPEN)

    power_ratio = 1.0
    if temporal == TemporalFlag.ASYMMETRIC:
        pr_raw = questionary.select(
            "Roughly how much more power do they have?",
            choices=["About 2x", "About 3-5x", "Much more than 5x"],
            style=Q_STYLE,
        ).ask()
        power_ratio = {"About 2x": 2.5, "About 3-5x": 4.0, "Much more than 5x": 7.0}.get(pr_raw, 3.0)

    overrides = {
        "horizon": horizon,
        "noise": noise_flag,
        "noise_estimate": noise_est,
        "players": players,
        "opponent_type": opp_type,
        "temporal": temporal,
    }

    # Run engine
    result, signals, ethics = engine.decide(opp, overrides, power_ratio)

    # ── Display result ────────────────────────────────────────────────────────
    section("RECOMMENDATION")

    move_color = MOVE_COLOR[result.recommended_move]
    move_word = result.recommended_move.value.upper()

    console.print(Panel(
        f"[{move_color} bold]  {move_word}  [/{move_color} bold]",
        title=f"Recommended Move — {module_badge(result.module.value)}",
        border_style=move_color,
        padding=(1, 4),
    ))
    console.print()

    # Rationale
    console.print(f"[bold]Rationale[/bold]")
    console.print(f"  {result.rationale}")
    console.print()

    # Signals table
    t = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    t.add_column("Signal", style="dim", width=18)
    t.add_column("Reading", width=22)
    t.add_column("Confidence")
    t.add_row("Horizon",       signals.horizon.value,        "")
    t.add_row("Noise",         f"{signals.noise.value} (ε={signals.noise_estimate:.2f})", "")
    t.add_row("Players",       signals.players.value,        "")
    t.add_row("Opponent type", signals.opponent_type.value,  "")
    t.add_row("Temporal",      signals.temporal.value,       "")
    t.add_row("Classifier",    "",                           confidence_bar(signals.confidence))
    console.print(Panel(t, title="[dim]Environment signals[/dim]", border_style="dim"))

    # Tactical notes
    if result.tactical_notes:
        console.print()
        console.print("[bold]Tactical notes[/bold]")
        for note in result.tactical_notes:
            console.print(f"  [dim]•[/dim] {note}")

    # Flags
    if result.flags:
        console.print()
        flag_str = "  " + "  ".join(f"[yellow]{f}[/yellow]" for f in result.flags)
        console.print(flag_str)

    # Ethics
    if ethics.vetoed:
        console.print()
        console.print(Panel(
            f"[red bold]ETHICS VETO TRIGGERED[/red bold]\n{ethics.reason}",
            border_style="red",
        ))
    elif ethics.constraint_triggered == 0:
        console.print()
        console.print("[dim]  Ethics layer: all clear[/dim]")

    # GTFO check
    gtfo = engine.evaluate_gtfo(opp)
    if gtfo["triggered"]:
        console.print()
        console.print(Panel(
            f"[red bold]GTFO THRESHOLD REACHED[/red bold]\n"
            f"Score: {gtfo['score']:.2f} > threshold {gtfo['threshold']}\n"
            f"Cooperation deficit: {gtfo['cooperation_deficit']}\n"
            f"EV projection: {gtfo['ev_projection']}\n\n"
            "[yellow]Consider exiting this interaction.[/yellow]",
            border_style="red",
            title="Exit Evaluation",
        ))

    # Log this round?
    console.print()
    log_it = questionary.confirm("Log this interaction round?", default=True, style=Q_STYLE).ask()
    if log_it:
        opp_move_raw = questionary.select(
            "What did they actually do?",
            choices=["Cooperated", "Defected", "Skip / not resolved yet"],
            style=Q_STYLE,
        ).ask()
        if opp_move_raw != "Skip / not resolved yet":
            opp_move = Move.COOPERATE if opp_move_raw == "Cooperated" else Move.DEFECT
            my_payoff, _ = get_payoff(result.recommended_move, opp_move)
            notes = questionary.text("Context notes (optional):", style=Q_STYLE).ask() or ""
            engine.record_round(opp, result.recommended_move, opp_move, result.module, signals, my_payoff, notes)
            save_state(state)
            console.print(f"[green]Round logged.[/green] Payoff: {my_payoff}")


# ── Mode 2: Simulator ─────────────────────────────────────────────────────────

def simulator_mode(state: MetaTFTState):
    engine = MetaTFTEngine(state)
    section("SIMULATOR MODE")
    console.print("[dim]Run MetaTFT against classic game-theory bots and see the results.[/dim]")
    console.print()

    bot = questionary.select(
        "Choose opponent bot:",
        choices=[
            "always_cooperate  — always cooperates",
            "always_defect     — always defects",
            "random            — 50/50 random",
            "tft               — classic Tit-for-Tat",
            "grudger           — cooperates until first defect, then never again",
            "detective         — probes then exploits if you don't retaliate",
        ],
        style=Q_STYLE,
    ).ask()
    bot_name = bot.split()[0]

    rounds = questionary.text("Number of rounds (default 50):", default="50", style=Q_STYLE).ask()
    try:
        rounds = int(rounds)
    except ValueError:
        rounds = 50

    noise_raw = questionary.select(
        "Channel noise level:",
        choices=["None (ε=0)", "Low (ε=0.05)", "Moderate (ε=0.10)", "High (ε=0.20)"],
        style=Q_STYLE,
    ).ask()
    noise_map = {"None (ε=0)": 0.0, "Low (ε=0.05)": 0.05, "Moderate (ε=0.10)": 0.10, "High (ε=0.20)": 0.20}
    noise = noise_map.get(noise_raw, 0.0)

    console.print()
    with console.status(f"[dim]Simulating {rounds} rounds vs {bot_name}...[/dim]"):
        sim = engine.simulate(bot_name, rounds, noise)

    if "error" in sim:
        console.print(f"[red]{sim['error']}[/red]")
        return

    # Results panel
    result_color = "green" if sim["my_total"] >= sim["bot_total"] else "red"
    diff = sim["my_total"] - sim["bot_total"]
    diff_str = f"[green]+{diff}[/green]" if diff >= 0 else f"[red]{diff}[/red]"

    console.print(Panel(
        f"MetaTFT vs [bold]{bot_name}[/bold]  |  {rounds} rounds  |  noise ε={noise}",
        border_style="dim",
    ))
    console.print()

    # Score table
    t = Table(box=box.SIMPLE, show_header=True, header_style="dim", width=60)
    t.add_column("", style="bold", width=14)
    t.add_column("Total score", justify="right")
    t.add_column("Avg/round", justify="right")
    t.add_column("Coop rate", justify="right")
    t.add_row(
        "MetaTFT",
        f"[{result_color}]{sim['my_total']}[/{result_color}]",
        str(sim["my_avg"]),
        f"{sim['my_coop_rate']:.0%}",
    )
    t.add_row(
        bot_name,
        str(sim["bot_total"]),
        str(sim["bot_avg"]),
        f"{sim['bot_coop_rate']:.0%}",
    )
    console.print(t)
    console.print(f"  Score difference: {diff_str}")
    console.print()

    # Module usage breakdown
    module_counts: dict = {}
    for entry in sim["rounds_log"]:
        m = entry["module"]
        module_counts[m] = module_counts.get(m, 0) + 1

    console.print("[bold]Module usage[/bold]")
    for m, count in sorted(module_counts.items(), key=lambda x: -x[1]):
        bar = "█" * int(count / rounds * 30)
        color = MODULE_COLORS.get(m, "white")
        console.print(f"  [{color}]{m:<22}[/{color}]  {bar} {count}")

    # Show last 10 rounds
    console.print()
    show_log = questionary.confirm("Show round-by-round log (last 20)?", default=False, style=Q_STYLE).ask()
    if show_log:
        t2 = Table(box=box.SIMPLE, show_header=True, header_style="dim")
        t2.add_column("Rd", width=4)
        t2.add_column("MetaTFT", width=10)
        t2.add_column("Bot", width=10)
        t2.add_column("My +", width=6)
        t2.add_column("Module", width=22)
        for entry in sim["rounds_log"][-20:]:
            mc = "green" if entry["my_move"] == "cooperate" else "red"
            bc = "green" if entry["bot_move"] == "cooperate" else "red"
            t2.add_row(
                str(entry["round"]),
                f"[{mc}]{entry['my_move'][0].upper()}[/{mc}]",
                f"[{bc}]{entry['bot_move'][0].upper()}[/{bc}]",
                str(entry["my_payoff"]),
                module_badge(entry["module"]),
            )
        console.print(t2)


# ── Mode 3: Journal ───────────────────────────────────────────────────────────

def journal_mode(state: MetaTFTState):
    section("JOURNAL MODE")
    console.print("[dim]View and manage your interaction history with tracked opponents.[/dim]")
    console.print()

    while True:
        action = questionary.select(
            "Journal action:",
            choices=[
                "View opponent history",
                "Add manual round entry",
                "View GTFO evaluation",
                "Edit opponent notes",
                "Set opponent reputation score",
                "Delete opponent",
                "Export opponent data",
                "Back to main menu",
            ],
            style=Q_STYLE,
        ).ask()

        if action is None or action == "Back to main menu":
            break
        elif action == "View opponent history":
            _journal_view(state)
        elif action == "Add manual round entry":
            _journal_add_entry(state)
        elif action == "View GTFO evaluation":
            _journal_gtfo(state)
        elif action == "Edit opponent notes":
            _journal_notes(state)
        elif action == "Set opponent reputation score":
            _journal_reputation(state)
        elif action == "Delete opponent":
            _journal_delete(state)
        elif action == "Export opponent data":
            _journal_export(state)


def _journal_view(state: MetaTFTState):
    if not state.opponents:
        console.print("[dim]No opponents tracked yet.[/dim]")
        return
    opp = get_or_create_opponent(state, "View history for:")
    if opp is None:
        return

    console.print()
    console.print(Panel(
        f"[bold]{opp.name}[/bold]\n"
        f"Rounds logged: {len(opp.history)}\n"
        f"Classification: [yellow]{opp.classification.value}[/yellow]\n"
        f"Defection rate (last 10): [red]{opp.defection_rate():.1%}[/red]\n"
        f"Cooperation deficit: {opp.cooperation_deficit():.2f}\n"
        f"Reputation score: {opp.reputation_score:.2f}\n"
        f"Notes: [dim]{opp.notes or 'none'}[/dim]",
        title="Opponent profile",
        border_style="dim",
    ))
    console.print()

    if not opp.history:
        console.print("[dim]No rounds logged yet.[/dim]")
        return

    t = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    t.add_column("Rd", width=4)
    t.add_column("Mine", width=6)
    t.add_column("Theirs", width=8)
    t.add_column("Payoff", width=8)
    t.add_column("Module", width=22)
    t.add_column("Notes", width=20)

    for entry in opp.history[-30:]:
        mc = "green" if entry.my_move == Move.COOPERATE else "red"
        oc = "green" if entry.opponent_move == Move.COOPERATE else "red"
        t.add_row(
            str(entry.round_num),
            f"[{mc}]{entry.my_move.value[0].upper()}[/{mc}]",
            f"[{oc}]{entry.opponent_move.value[0].upper()}[/{oc}]",
            str(entry.payoff),
            module_badge(entry.active_module),
            entry.context_notes[:18] or "[dim]—[/dim]",
        )
    console.print(t)
    if len(opp.history) > 30:
        console.print(f"[dim]Showing last 30 of {len(opp.history)} rounds.[/dim]")

    ev = project_ev(opp.history)
    console.print(f"\n  [dim]EV projection (next 10 rounds): {ev}[/dim]")


def _journal_add_entry(state: MetaTFTState):
    opp = get_or_create_opponent(state, "Add entry for:")
    if opp is None:
        return
    engine = MetaTFTEngine(state)
    signals = engine.classify_environment(opp)

    my_raw = questionary.select("Your move:", choices=["Cooperated", "Defected"], style=Q_STYLE).ask()
    opp_raw = questionary.select("Their move:", choices=["Cooperated", "Defected"], style=Q_STYLE).ask()
    notes = questionary.text("Context notes (optional):", style=Q_STYLE).ask() or ""

    my_move = Move.COOPERATE if my_raw == "Cooperated" else Move.DEFECT
    opp_move = Move.COOPERATE if opp_raw == "Cooperated" else Move.DEFECT
    payoff, _ = get_payoff(my_move, opp_move)

    engine.record_round(opp, my_move, opp_move, from_string_to_module(opp.classification), signals, payoff, notes)
    save_state(state)
    console.print(f"[green]Entry logged.[/green] Round {len(opp.history)}  payoff: {payoff}")


def from_string_to_module(classification):
    """Map opponent classification to most likely module for manual entries."""
    from .models import ModuleName, OpponentFlag
    m = {
        OpponentFlag.COOPERATIVE: ModuleName.BASE_TFT,
        OpponentFlag.MIXED: ModuleName.BASE_TFT,
        OpponentFlag.COND_DEFECT: ModuleName.GRIM_WITH_PAROLE,
        OpponentFlag.PURE_DEFECT: ModuleName.GRIM_WITH_PAROLE,
        OpponentFlag.IRRATIONAL: ModuleName.IRRATIONALITY_MODE,
        OpponentFlag.UNKNOWN: ModuleName.BASE_TFT,
    }
    return m.get(classification, ModuleName.BASE_TFT)


def _journal_gtfo(state: MetaTFTState):
    opp = get_or_create_opponent(state, "GTFO evaluation for:")
    if opp is None:
        return
    engine = MetaTFTEngine(state)
    gtfo = engine.evaluate_gtfo(opp)
    color = "red" if gtfo["triggered"] else "green"
    verdict = "EXIT RECOMMENDED" if gtfo["triggered"] else "Staying is rational"
    console.print()
    console.print(Panel(
        f"[{color} bold]{verdict}[/{color} bold]\n\n"
        f"GTFO score:          {gtfo['score']:.3f}\n"
        f"Threshold:           {gtfo['threshold']}\n"
        f"Cooperation deficit: {gtfo['cooperation_deficit']}\n"
        f"EV projection:       {gtfo['ev_projection']}\n"
        f"Horizon assumed:     {gtfo['horizon_assumed']} rounds",
        title=f"GTFO Evaluation — {opp.name}",
        border_style=color,
    ))


def _journal_notes(state: MetaTFTState):
    if not state.opponents:
        return
    opp = get_or_create_opponent(state, "Edit notes for:")
    if opp is None:
        return
    notes = questionary.text(
        "Notes (add CATEGORICAL_HARM to trigger ethics Constraint 3):",
        default=opp.notes,
        style=Q_STYLE,
    ).ask()
    if notes is not None:
        opp.notes = notes
        save_state(state)
        console.print("[green]Notes saved.[/green]")


def _journal_reputation(state: MetaTFTState):
    if not state.opponents:
        return
    opp = get_or_create_opponent(state, "Set reputation for:")
    if opp is None:
        return
    raw = questionary.text(
        f"Reputation score 0.0–1.0 (current: {opp.reputation_score:.2f}):",
        style=Q_STYLE,
    ).ask()
    try:
        val = float(raw)
        val = max(0.0, min(1.0, val))
        opp.reputation_score = val
        save_state(state)
        console.print(f"[green]Reputation set to {val:.2f}[/green]")
    except (ValueError, TypeError):
        console.print("[red]Invalid value.[/red]")


def _journal_delete(state: MetaTFTState):
    if not state.opponents:
        return
    names = list(state.opponents.keys())
    name = questionary.select("Delete opponent:", choices=names + ["Cancel"], style=Q_STYLE).ask()
    if name and name != "Cancel":
        confirm = questionary.confirm(f"Delete all history for '{name}'?", default=False, style=Q_STYLE).ask()
        if confirm:
            del state.opponents[name]
            save_state(state)
            console.print(f"[green]Deleted {name}.[/green]")


def _journal_export(state: MetaTFTState):
    if not state.opponents:
        return
    opp = get_or_create_opponent(state, "Export:")
    if opp is None:
        return
    path = questionary.text(
        "Export path (e.g. ~/Desktop/export.json):",
        default=f"./{opp.name.replace(' ','_')}.json",
        style=Q_STYLE,
    ).ask()
    if path:
        import os
        path = os.path.expanduser(path)
        export_opponent(state, opp.name, path)
        console.print(f"[green]Exported to {path}[/green]")


# ── Mode 4: Settings ──────────────────────────────────────────────────────────

def settings_mode(state: MetaTFTState):
    section("SETTINGS")
    s = state.settings
    console.print(f"  stochastic_block    {s['stochastic_block']}   [dim](% chance to NOT switch module even when signal fires)[/dim]")
    console.print(f"  decay_lambda        {s['decay_lambda']}   [dim](memory decay — lower = forget faster)[/dim]")
    console.print(f"  fairness_multiplier {s['fairness_multiplier']}   [dim](max ratio of your gain to their gain)[/dim]")
    console.print(f"  re_eval_interval    {s['re_eval_interval']}   [dim](rounds between module re-evaluations)[/dim]")
    console.print(f"  gtfo_threshold      {s['gtfo_threshold']}   [dim](exit score above which exit is recommended)[/dim]")
    console.print()

    edit = questionary.confirm("Edit settings?", default=False, style=Q_STYLE).ask()
    if not edit:
        return

    for key in s:
        raw = questionary.text(f"{key} (current: {s[key]}):", default=str(s[key]), style=Q_STYLE).ask()
        try:
            s[key] = float(raw)
        except (ValueError, TypeError):
            pass
    save_state(state)
    console.print("[green]Settings saved.[/green]")


# ── Mode 5: Heuristic Shorthand ───────────────────────────────────────────────

def heuristic_mode():
    section("HEURISTIC SHORTHAND")
    console.print(Panel(
        "[bold]Before any move, ask three things:[/bold]\n\n"
        "[cyan]1.[/cyan] [bold]Will I interact with this person again, and does the future matter to them?[/bold]\n"
        "   If no: signal honestly and exit if not reciprocated.\n\n"
        "[cyan]2.[/cyan] [bold]Am I reading them accurately, or is this situation messy?[/bold]\n"
        "   If messy: be more forgiving than you feel you should be.\n\n"
        "[cyan]3.[/cyan] [bold]Are the rules of this game fair and bilateral?[/bold]\n"
        "   If not: stop trying to win the game; start trying to change it.\n\n"
        "[dim]Otherwise: cooperate first, mirror what you receive,\n"
        "forgive once, punish consistently, and stay legible.[/dim]",
        title="MetaTFT in three questions",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()
    console.print("[bold]The 10 modules at a glance:[/bold]")
    console.print()
    rows = [
        ("Base TFT",           "Clean iterated bilateral game",                      "cyan"),
        ("Generous TFT",       "Noisy / ambiguous channel",                          "green"),
        ("Stake-and-Signal",   "One-shot / single encounter",                        "yellow"),
        ("Pavlov",             "Impatient opponent, need quick lock-in",             "magenta"),
        ("Grim-with-Parole",   "Pure defector, schedule resets",                     "red"),
        ("Network TFT",        "Multi-player, reputation is the asset",              "blue"),
        ("Shadow-Extender",    "Known end date, prevent backward induction",         "purple4"),
        ("Irrationality Mode", "Opponent ignores incentives, minimize exposure",     "bright_red"),
        ("Commons Mode",       "Public goods / collective resource game",            "bright_green"),
        ("Power-Asymmetry",    "Opponent has far more structural power",             "orange3"),
    ]
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column("Module", width=22)
    t.add_column("When to use", width=42)
    for name, when, color in rows:
        t.add_row(f"[{color}]{name}[/{color}]", f"[dim]{when}[/dim]")
    console.print(t)


# ── Main menu ─────────────────────────────────────────────────────────────────

def main():
    state = load_state()
    header()

    while True:
        n_opponents = len(state.opponents)
        n_rounds = sum(len(o.history) for o in state.opponents.values())

        console.print(f"[dim]  {n_opponents} opponent(s) tracked  ·  {n_rounds} rounds logged[/dim]")
        console.print()

        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "Advisor    — get a move recommendation for a real situation",
                "Simulator  — run MetaTFT against classic bots",
                "Journal    — view and manage interaction history",
                "Heuristic  — quick-reference guide",
                "Settings   — configure engine parameters",
                "Quit",
            ],
            style=Q_STYLE,
        ).ask()

        if choice is None or choice.startswith("Quit"):
            console.print()
            console.print("[dim]Goodbye.[/dim]")
            console.print()
            sys.exit(0)
        elif choice.startswith("Advisor"):
            advisor_mode(state)
        elif choice.startswith("Simulator"):
            simulator_mode(state)
        elif choice.startswith("Journal"):
            journal_mode(state)
        elif choice.startswith("Heuristic"):
            heuristic_mode()
        elif choice.startswith("Settings"):
            settings_mode(state)
