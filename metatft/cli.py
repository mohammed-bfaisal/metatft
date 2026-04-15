from __future__ import annotations

import random
import sys
from typing import Optional

import questionary
from questionary import Style
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .engine import MetaTFTEngine
from .models import (
    HorizonFlag,
    MetaTFTState,
    ModuleName,
    Move,
    NoiseFlag,
    Opponent,
    OpponentFlag,
    PlayerFlag,
    TemporalFlag,
)
from .storage import export_opponent, import_opponent, load_state, save_state
from .utils import ascii_bar, cooperation_timeline, get_payoff, move_symbol, outcome_label, sparkline, trust_score


console = Console()
Q_STYLE = Style([
    ("qmark", "fg:#5DCAA5 bold"),
    ("question", "bold"),
    ("answer", "fg:#7F77DD bold"),
    ("pointer", "fg:#5DCAA5 bold"),
    ("highlighted", "fg:#5DCAA5 bold"),
    ("selected", "fg:#5DCAA5"),
])

MODULE_COLORS = {
    "Base TFT": "cyan",
    "Generous TFT": "green",
    "Stake-and-Signal": "yellow",
    "Pavlov": "magenta",
    "Grim-with-Parole": "red",
    "Network TFT": "blue",
    "Shadow-Extender": "purple4",
    "Irrationality Mode": "bright_red",
    "Commons Mode": "bright_green",
    "Power-Asymmetry": "orange3",
}


def header(state: MetaTFTState) -> None:
    tracked = len(state.opponents)
    risk_alerts = 0
    for opp in state.opponents.values():
        if opp.cooperation_deficit() > state.settings.get("gtfo_threshold", 2.0):
            risk_alerts += 1
    console.print()
    console.print(Panel(
        f"[bold]MetaTFT[/bold]\n"
        f"[dim]A decision system for when to cooperate, when to retaliate, when to forgive, and when to leave.[/dim]\n\n"
        f"Tracked relationships: [bold]{tracked}[/bold]\n"
        f"Open risk alerts: [bold]{risk_alerts}[/bold]\n"
        f"Simulation seed: [bold]{state.settings.get('sim_seed', 433)}[/bold]\n"
        f"Easy language mode: [bold]{'ON' if state.settings.get('easy_mode', True) else 'OFF'}[/bold]",
        title="Adaptive Cooperation Intelligence",
        border_style="dim",
        padding=(1, 2),
    ))


def section(title: str) -> None:
    console.print()
    console.print(Rule(f"[dim]{title}[/dim]", style="dim"))


def module_badge(name: str) -> str:
    color = MODULE_COLORS.get(name, "white")
    return f"[{color}]{name}[/{color}]"


def plain_label(value: str) -> str:
    return value.replace('_', ' ').replace('-', ' ').strip()


def pretty_move(move: Move, easy_mode: bool = True) -> str:
    return (f"{move_symbol(move)} Work with them" if move == Move.COOPERATE else f"{move_symbol(move)} Protect yourself") if easy_mode else move.value.upper()


def render_turn_playback(rounds_log: list[dict], easy_mode: bool = True, title: str = "Turn-by-turn view") -> None:
    if not rounds_log:
        return
    table = Table(box=box.SIMPLE_HEAVY, title=title)
    table.add_column("Turn", justify="right")
    table.add_column("MetaTFT")
    table.add_column("Other side")
    table.add_column("What happened")
    table.add_column("Points", justify="right")
    table.add_column("Approach")
    for row in rounds_log:
        my_move = Move(row["my_move"]) if isinstance(row["my_move"], str) else row["my_move"]
        opp_move = Move(row["bot_move"]) if "bot_move" in row else Move(row["opponent_move"]) if isinstance(row.get("opponent_move"), str) else row.get("opponent_move")
        what = outcome_label(my_move, opp_move) if easy_mode else f"{my_move.value} vs {opp_move.value}"
        table.add_row(
            str(row["round"]),
            pretty_move(my_move, easy_mode),
            pretty_move(opp_move, easy_mode),
            what,
            str(row.get("my_payoff", row.get("payoff", "—"))),
            module_badge(row["module"]),
        )
    console.print(table)


def render_visual_strip(rounds_log: list[dict], title: str = "Visual flow") -> None:
    if not rounds_log:
        return
    rounds = ' '.join(f'{r["round"]:02d}' for r in rounds_log)
    mine = ' '.join(move_symbol(r['my_move']) for r in rounds_log)
    theirs = ' '.join(move_symbol(r.get('bot_move', r.get('opponent_move'))) for r in rounds_log)
    score_trace = [float(r.get('my_payoff', r.get('payoff', 0))) for r in rounds_log]
    line = f"Turns:   {rounds}\nYou:     {mine}\nOther:   {theirs}\nScore:   {sparkline(score_trace, width=min(20, len(score_trace)))}"
    console.print(Panel(line, title=title, border_style='dim'))


def get_or_create_opponent(state: MetaTFTState, prompt_text: str = "Opponent") -> Optional[Opponent]:
    names = list(state.opponents.keys())
    choices = names + ["[ + Create new ]"] if names else ["[ + Create new ]"]
    choice = questionary.select(prompt_text, choices=choices, style=Q_STYLE).ask()
    if choice is None:
        return None
    if choice == "[ + Create new ]":
        name = questionary.text("Enter a name:", style=Q_STYLE).ask()
        if not name:
            return None
        opp = Opponent(name=name.strip())
        state.opponents[opp.name] = opp
        save_state(state)
        return opp
    return state.opponents[choice]


def prompt_overrides() -> tuple[dict, float]:
    horizon_raw = questionary.select(
        "How repeated is this interaction?",
        choices=["Open-ended / repeated", "Short but repeated", "One-shot", "Unknown"],
        style=Q_STYLE,
    ).ask()
    horizon = {
        "Open-ended / repeated": HorizonFlag.REPEATED,
        "Short but repeated": HorizonFlag.SHORT,
        "One-shot": HorizonFlag.ONE_SHOT,
        "Unknown": HorizonFlag.UNKNOWN,
    }[horizon_raw]

    noise_raw = questionary.select(
        "How noisy is the channel?",
        choices=["Clean", "Sometimes misread", "Often ambiguous"],
        style=Q_STYLE,
    ).ask()
    noise_map = {
        "Clean": (NoiseFlag.LOW, 0.03),
        "Sometimes misread": (NoiseFlag.NOISY, 0.10),
        "Often ambiguous": (NoiseFlag.HIGH, 0.22),
    }
    noise_flag, noise_est = noise_map[noise_raw]

    players_raw = questionary.select(
        "What is the player structure?",
        choices=["Bilateral", "Networked / visible", "Multi-player", "Commons / shared pool"],
        style=Q_STYLE,
    ).ask()
    players = {
        "Bilateral": PlayerFlag.BILATERAL,
        "Networked / visible": PlayerFlag.NETWORKED,
        "Multi-player": PlayerFlag.MULTI_PLAYER,
        "Commons / shared pool": PlayerFlag.COLLECTIVE,
    }[players_raw]

    opp_raw = questionary.select(
        "How has the opponent behaved?",
        choices=["Mostly cooperative", "Mixed", "Conditionally exploitative", "Consistently exploitative", "Unpredictable / irrational"],
        style=Q_STYLE,
    ).ask()
    opp_type = {
        "Mostly cooperative": OpponentFlag.COOPERATIVE,
        "Mixed": OpponentFlag.MIXED,
        "Conditionally exploitative": OpponentFlag.COND_DEFECT,
        "Consistently exploitative": OpponentFlag.PURE_DEFECT,
        "Unpredictable / irrational": OpponentFlag.IRRATIONAL,
    }[opp_raw]

    temporal_raw = questionary.select(
        "What is special about the time structure?",
        choices=["Open / unknown end", "Known end-date", "Opponent is impatient", "Opponent has much more power"],
        style=Q_STYLE,
    ).ask()
    temporal = {
        "Open / unknown end": TemporalFlag.OPEN,
        "Known end-date": TemporalFlag.BOUNDED,
        "Opponent is impatient": TemporalFlag.IMPATIENT,
        "Opponent has much more power": TemporalFlag.ASYMMETRIC,
    }[temporal_raw]

    power_ratio = 1.0
    if temporal == TemporalFlag.ASYMMETRIC:
        power_choice = questionary.select("Approximate power gap:", choices=["2x", "3-5x", ">5x"], style=Q_STYLE).ask()
        power_ratio = {"2x": 2.0, "3-5x": 4.0, ">5x": 6.0}[power_choice]

    overrides = {
        "horizon": horizon,
        "noise": noise_flag,
        "noise_estimate": noise_est,
        "players": players,
        "opponent_type": opp_type,
        "temporal": temporal,
    }
    return overrides, power_ratio


def render_analysis(state: MetaTFTState, opp: Opponent, result, signals, gtfo) -> None:
    summary = Panel(
        f"[bold]{opp.name}[/bold]\n"
        f"Rounds logged: {len(opp.history)}\n"
        f"Defection rate: {opp.defection_rate():.0%}\n"
        f"Reputation: {opp.reputation_score:.2f}",
        title="Situation Summary",
        border_style="dim",
    )
    recommendation = Panel(
        f"Move: [bold]{result.recommended_move.value.upper()}[/bold]\n"
        f"Policy: {module_badge(result.module.value)}\n"
        f"Confidence: {result.confidence:.0%}\n"
        f"GTFO: {'TRIGGERED' if result.gtfo_triggered else 'Not triggered'}",
        title="Recommendation",
        border_style="green" if result.recommended_move == Move.COOPERATE else "red",
    )
    console.print(Columns([summary, recommendation]))

    signals_table = Table(box=box.SIMPLE_HEAVY, title="What the app sees" if easy_mode else "Environment Signals", show_header=False)
    signals_table.add_column("Signal", style="bold")
    signals_table.add_column("Value")
    signals_table.add_row("Will this continue?" if easy_mode else "Horizon", f"{plain_label(signals.horizon.value)}  {ascii_bar(0.9 if signals.horizon != HorizonFlag.UNKNOWN else 0.4)}")
    signals_table.add_row("Chance of misunderstanding" if easy_mode else "Noise", f"{plain_label(signals.noise.value)}  {ascii_bar(signals.misread_risk)}")
    signals_table.add_row("Who is involved?" if easy_mode else "Players", plain_label(signals.players.value))
    signals_table.add_row("Other side pattern" if easy_mode else "Opponent", plain_label(signals.opponent_type.value))
    signals_table.add_row("How sure is the app?" if easy_mode else "Confidence", f"{signals.confidence:.0%}  {ascii_bar(signals.confidence)}")

    risk_table = Table(box=box.SIMPLE_HEAVY, title="Risk profile", show_header=False)
    risk_table.add_column("Risk", style="bold")
    risk_table.add_column("Value")
    risk_table.add_row("Exploitation", f"{signals.exploit_risk:.2f}  {ascii_bar(signals.exploit_risk)}")
    risk_table.add_row("Misread", f"{signals.misread_risk:.2f}  {ascii_bar(signals.misread_risk)}")
    risk_table.add_row("Endgame", f"{signals.endgame_risk:.2f}  {ascii_bar(signals.endgame_risk)}")
    risk_table.add_row("Relationship", f"{signals.relationship_value:.2f}  {ascii_bar(signals.relationship_value)}")
    risk_table.add_row("GTFO score", f"{gtfo['score']:.2f} (threshold {gtfo['threshold']})")
    console.print(Columns([signals_table, risk_table]))

    console.print(Panel(result.executive_summary + "\n\n" + result.strategic_explanation, title="Why this recommendation?", border_style="dim"))

    evidence = Table(box=box.SIMPLE, title=evidence_title)
    evidence.add_column("Line")
    for line in result.evidence_lines:
        evidence.add_row(line)
    console.print(evidence)

    action_cols = [
        Panel("\n".join(f"• {x}" for x in result.action_steps), title="Do this", border_style="green"),
        Panel("\n".join(f"• {x}" for x in result.avoid_steps), title="Avoid this", border_style="yellow"),
    ]
    console.print(Columns(action_cols))

    if result.what_changes:
        console.print(Panel("\n".join(f"• {x}" for x in result.what_changes), title="What would change the answer?", border_style="blue"))
    if result.why_not:
        console.print(Panel("\n".join(f"• {x}" for x in result.why_not), title="Why not the nearest alternatives?", border_style="magenta"))

    comp = Table(box=box.SIMPLE_HEAVY, title="Top candidate modules")
    comp.add_column("Rank", justify="right")
    comp.add_column("Module")
    comp.add_column("Score", justify="right")
    for idx, cand in enumerate(result.alternatives, start=1):
        comp.add_row(str(idx), module_badge(cand.module.value), f"{cand.score:.3f}")
    console.print(comp)

    rounds, mine, theirs = cooperation_timeline(opp.history)
    if rounds:
        console.print(Panel(f"Rounds:   {rounds}\nYou:      {mine}\nOpponent: {theirs}", title="Recent timeline", border_style="dim"))

    if result.tactical_notes:
        console.print(Panel("\n".join(f"• {x}" for x in result.tactical_notes), title="Tactical notes", border_style="dim"))
    if result.ethics_vetoed:
        console.print(Panel(result.ethics_reason, title="Ethics veto", border_style="red"))


def analyze_interaction(state: MetaTFTState, save_after: bool = False) -> None:
    engine = MetaTFTEngine(state)
    section("ANALYZE INTERACTION")
    opp = get_or_create_opponent(state, "Choose opponent:")
    if opp is None:
        return
    questionary.text("Describe what happened (for your own notes):", style=Q_STYLE).ask()
    overrides, power_ratio = prompt_overrides()
    result, signals, gtfo = engine.decide(opp, overrides, power_ratio)
    render_analysis(state, opp, result, signals, gtfo)
    if save_after and questionary.confirm("Log a round now?", default=True, style=Q_STYLE).ask():
        log_round(state, opp, result, signals)


def recommend_next_move(state: MetaTFTState) -> None:
    analyze_interaction(state, save_after=True)


def log_round(state: MetaTFTState, opp: Opponent, result, signals) -> None:
    my_move = result.recommended_move
    opp_raw = questionary.select("What did the opponent do?", choices=["Cooperated", "Defected"], style=Q_STYLE).ask()
    opp_move = Move.COOPERATE if opp_raw == "Cooperated" else Move.DEFECT
    payoff, _ = get_payoff(my_move, opp_move)
    notes = questionary.text("Context note (optional):", style=Q_STYLE).ask() or ""
    engine = MetaTFTEngine(state)
    engine.record_round(opp, my_move, opp_move, result.module, signals, payoff, notes)
    save_state(state)
    console.print(f"[green]Round saved.[/green] Round {len(opp.history)} | payoff {payoff}")


def simulate_scenarios(state: MetaTFTState) -> None:
    engine = MetaTFTEngine(state)
    section("SIMULATE SCENARIOS")
    bot = questionary.select(
        "Choose opponent bot:",
        choices=["always_cooperate", "always_defect", "random", "tft", "grudger", "detective"],
        style=Q_STYLE,
    ).ask()
    rounds = int(questionary.text("Rounds:", default="50", style=Q_STYLE).ask() or "50")
    noise = float(questionary.select("Noise:", choices=["0.0", "0.05", "0.10", "0.20"], style=Q_STYLE).ask())
    compare = questionary.confirm("Also compare baseline TFT view verbally?", default=True, style=Q_STYLE).ask()
    sim = engine.simulate(bot, rounds, noise, seed=state.settings.get("sim_seed", 433))
    if "error" in sim:
        console.print(f"[red]{sim['error']}[/red]")
        return

    t = Table(box=box.SIMPLE_HEAVY, title="Simulation Summary")
    t.add_column("Metric")
    t.add_column("MetaTFT", justify="right")
    t.add_column(bot, justify="right")
    t.add_row("Total score", str(sim["my_total"]), str(sim["bot_total"]))
    t.add_row("Avg/round", str(sim["my_avg"]), str(sim["bot_avg"]))
    t.add_row("Coop rate", f"{sim['my_coop_rate']:.0%}", f"{sim['bot_coop_rate']:.0%}")
    console.print(t)

    module_counts = {}
    for entry in sim["rounds_log"]:
        module_counts[entry["module"]] = module_counts.get(entry["module"], 0) + 1
    usage = Table(box=box.SIMPLE, title="Module usage")
    usage.add_column("Module")
    usage.add_column("Count", justify="right")
    for module, count in sorted(module_counts.items(), key=lambda x: -x[1]):
        usage.add_row(module_badge(module), str(count))
    console.print(usage)

    if compare:
        diff = sim["my_total"] - sim["bot_total"]
        line = "MetaTFT preserved flexibility across phases." if diff >= 0 else "This bot shape exposed a weakness worth inspecting."
        console.print(Panel(line, title="Interpretation", border_style="dim"))

    easy_mode = state.settings.get("easy_mode", True)
    show_turns_default = True if easy_mode else False
    if questionary.confirm("Show turn-by-turn view?", default=show_turns_default, style=Q_STYLE).ask():
        recent = sim["rounds_log"][-20:]
        render_visual_strip(recent, title="Visual flow of the last 20 turns")
        render_turn_playback(recent, easy_mode=easy_mode, title="What happened each turn")


def review_journal(state: MetaTFTState) -> None:
    section("RELATIONSHIP JOURNAL")
    if not state.opponents:
        console.print("[dim]No tracked relationships yet.[/dim]")
        return
    opp = get_or_create_opponent(state, "Select relationship:")
    if opp is None:
        return
    engine = MetaTFTEngine(state)
    gtfo = engine.evaluate_gtfo(opp)
    profile = Panel(
        f"[bold]{opp.name}[/bold]\n"
        f"Rounds: {len(opp.history)}\n"
        f"Classification: {opp.classification.value}\n"
        f"Defection rate: {opp.defection_rate():.0%}\n"
        f"Cooperation deficit: {opp.cooperation_deficit():.2f}\n"
        f"Reputation: {opp.reputation_score:.2f}\n"
        f"GTFO score: {gtfo['score']:.2f}",
        title="Opponent Profile",
        border_style="dim",
    )
    console.print(profile)

    rounds, mine, theirs = cooperation_timeline(opp.history, width=20)
    if rounds:
        console.print(Panel(f"Rounds:   {rounds}\nYou:      {mine}\nOpponent: {theirs}", title="Timeline", border_style="dim"))

    if opp.history:
        recent_visual = [{"round": e.round_num, "my_move": e.my_move.value, "opponent_move": e.opponent_move.value, "payoff": e.payoff, "module": e.active_module} for e in opp.history[-12:]]
        render_visual_strip([{"round": r["round"], "my_move": r["my_move"], "opponent_move": r["opponent_move"], "payoff": r["payoff"], "module": r["module"]} for r in recent_visual], title="How the last turns looked")
        hist = Table(box=box.SIMPLE_HEAVY, title="Recent rounds")
        hist.add_column("Rd", justify="right")
        hist.add_column("You")
        hist.add_column("Opp")
        hist.add_column("Payoff", justify="right")
        hist.add_column("Module")
        hist.add_column("Notes")
        for entry in opp.history[-15:]:
            hist.add_row(str(entry.round_num), pretty_move(entry.my_move, easy_mode), pretty_move(entry.opponent_move, easy_mode), str(entry.payoff), module_badge(entry.active_module), entry.context_notes[:24] or "—")
        console.print(hist)

    action = questionary.select(
        "Journal action:",
        choices=["Add manual round", "Edit notes", "Set reputation", "Export opponent", "Import opponent", "Delete opponent", "Back"],
        style=Q_STYLE,
    ).ask()
    if action == "Add manual round":
        my_raw = questionary.select("Your move:", choices=["Cooperated", "Defected"], style=Q_STYLE).ask()
        opp_raw = questionary.select("Opponent move:", choices=["Cooperated", "Defected"], style=Q_STYLE).ask()
        my_move = Move.COOPERATE if my_raw == "Cooperated" else Move.DEFECT
        opp_move = Move.COOPERATE if opp_raw == "Cooperated" else Move.DEFECT
        notes = questionary.text("Notes:", style=Q_STYLE).ask() or ""
        payoff, _ = get_payoff(my_move, opp_move)
        signals = engine.classify_environment(opp)
        engine.record_round(opp, my_move, opp_move, ModuleName.BASE_TFT, signals, payoff, notes)
        save_state(state)
    elif action == "Edit notes":
        opp.notes = questionary.text("Notes:", default=opp.notes, style=Q_STYLE).ask() or ""
        save_state(state)
    elif action == "Set reputation":
        opp.reputation_score = max(0.0, min(1.0, float(questionary.text("Reputation 0.0-1.0:", default=f"{opp.reputation_score:.2f}", style=Q_STYLE).ask() or opp.reputation_score)))
        save_state(state)
    elif action == "Export opponent":
        path = export_opponent(opp)
        console.print(f"[green]Exported:[/green] {path}")
    elif action == "Import opponent":
        path = questionary.text("Path to exported JSON:", style=Q_STYLE).ask()
        if path:
            imported = import_opponent(path)
            state.opponents[imported.name] = imported
            save_state(state)
    elif action == "Delete opponent":
        if questionary.confirm(f"Delete {opp.name}?", default=False, style=Q_STYLE).ask():
            del state.opponents[opp.name]
            save_state(state)


def learn_model(_: MetaTFTState) -> None:
    section("LEARN / EXPLAIN")
    topic = questionary.select(
        "Choose a concept:",
        choices=["Why plain TFT works", "Why plain TFT fails", "What MetaTFT changes", "Module glossary", "Three-question shorthand"],
        style=Q_STYLE,
    ).ask()
    if topic == "Why plain TFT works":
        text = "Tit for Tat works best in repeated, legible, bilateral environments because it is nice, retaliatory, forgiving, and easy to learn."
    elif topic == "Why plain TFT fails":
        text = "It breaks under noise, one-shot games, fixed end dates, strong power asymmetry, irrational actors, and multi-player commons problems."
    elif topic == "What MetaTFT changes":
        text = "MetaTFT treats TFT as a baseline, not a religion. It classifies the environment first, then decides whether to keep TFT, soften it, wrap it, suspend it, or exit the game."
    elif topic == "Module glossary":
        text = "Base TFT: clean reciprocity. Generous TFT: noise correction. Stake-and-Signal: short horizon. Pavlov: impatience accelerator. Grim-with-Parole: contain defectors. Network TFT: reputation-weighted play. Shadow-Extender: bounded games. Irrationality Mode: minimize exposure. Commons Mode: protect the shared pool. Power-Asymmetry: soften retaliation when the opponent can crush you."
    else:
        text = "Ask: Will this repeat? Could this be noise? Can I afford retaliation? If repeated and clean, use TFT. If noisy, forgive once. If short-horizon, demand a signal. If exploitative, contain. If hopeless, leave."
    console.print(Panel(text, border_style="dim"))


def settings_menu(state: MetaTFTState) -> None:
    section("SETTINGS")
    t = Table(box=box.SIMPLE_HEAVY)
    t.add_column("Setting")
    t.add_column("Value")
    labels = {
        "easy_mode": "Easy language mode",
        "stochastic_block": "Switch randomness block",
        "decay_lambda": "Memory decay",
        "fairness_multiplier": "Fairness multiplier",
        "re_eval_interval": "Re-check interval",
        "gtfo_threshold": "Leave threshold",
        "sim_seed": "Simulation seed",
    }
    for k, v in state.settings.items():
        shown = "On" if k == "easy_mode" and v else "Off" if k == "easy_mode" else str(v)
        t.add_row(labels.get(k, k), shown)
    console.print(t)
    choice = questionary.select("Change a setting?", choices=["easy_mode", *[k for k in state.settings.keys() if k != "easy_mode"], "Back"], style=Q_STYLE).ask()
    if choice == "easy_mode":
        current = state.settings.get("easy_mode", True)
        state.settings["easy_mode"] = not current
        save_state(state)
        console.print(f"[green]Easy language mode is now {'ON' if state.settings['easy_mode'] else 'OFF'}.[/green]")
        return
    if choice and choice != "Back":
        raw = questionary.text(f"New value for {choice}:", default=str(state.settings[choice]), style=Q_STYLE).ask()
        if raw is not None:
            try:
                state.settings[choice] = int(raw) if raw.isdigit() else float(raw)
            except ValueError:
                state.settings[choice] = raw
            save_state(state)


def main() -> None:
    random.seed(433)
    state = load_state()
    while True:
        header(state)
        choice = questionary.select(
            "Choose an action:",
            choices=[
                "Analyze an interaction",
                "Get a next-move recommendation",
                "Simulate scenarios",
                "Review relationship journal",
                "Learn the model",
                "Settings",
                "Exit",
            ],
            style=Q_STYLE,
        ).ask()
        if choice is None or choice == "Exit":
            console.print("[dim]Goodbye.[/dim]")
            sys.exit(0)
        if choice == "Analyze an interaction":
            analyze_interaction(state, save_after=False)
        elif choice == "Get a next-move recommendation":
            recommend_next_move(state)
        elif choice == "Simulate scenarios":
            simulate_scenarios(state)
        elif choice == "Review relationship journal":
            review_journal(state)
        elif choice == "Learn the model":
            learn_model(state)
        elif choice == "Settings":
            settings_menu(state)
