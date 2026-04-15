from __future__ import annotations

import argparse
from rich.console import Console
from rich.panel import Panel

from . import __version__
from .cli import main as interactive_main
from .engine import MetaTFTEngine, SCENARIO_PACKS
from .storage import load_state
from .utils import move_symbol, sparkline

console = Console()


def run() -> None:
    parser = argparse.ArgumentParser(prog='metatft', description='Adaptive cooperation intelligence for the terminal.')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('interactive', help='Open the full interactive CLI.')
    sub.add_parser('doctor', help='Check install and state health.')
    explain = sub.add_parser('explain', help='Explain a module or concept.')
    explain.add_argument('topic', nargs='?', default='overview')
    sim = sub.add_parser('simulate-pack', help='Run a named scenario pack.')
    sim.add_argument('pack', choices=sorted(SCENARIO_PACKS.keys()))
    parser.add_argument('--version', action='store_true', help='Show version and exit.')
    args = parser.parse_args()

    if args.version:
        console.print(f'MetaTFT {__version__}')
        return
    if not args.command or args.command == 'interactive':
        interactive_main()
        return
    if args.command == 'doctor':
        state = load_state()
        console.print(Panel(f'Version: {__version__}\nTracked relationships: {len(state.opponents)}\nSettings loaded: {len(state.settings)}\nState file is readable: yes', title='MetaTFT doctor', border_style='green'))
        return
    if args.command == 'explain':
        topic = args.topic.lower()
        topics = {
            'overview': 'MetaTFT first classifies the environment, then chooses a base policy, applies structural modifiers, runs ethics constraints, and checks whether exit is wiser than continued play.',
            'generous_tft': 'Generous TFT is standard reciprocity with calibrated forgiveness under noisy conditions.',
            'grim_with_parole': 'Grim-with-Parole contains exploiters while keeping small scheduled reset probes alive.',
            'power': 'The power modifier softens retaliation when the opponent can impose disproportionate costs.',
            'commons': 'Commons Mode protects shared pools where bilateral retaliation would worsen collective outcomes.',
        }
        console.print(Panel(topics.get(topic, topics['overview']), title=f'Explain: {args.topic}', border_style='blue'))
        return
    if args.command == 'simulate-pack':
        state = load_state()
        engine = MetaTFTEngine(state)
        res = engine.simulate_pack(args.pack, seed=state.settings.get('sim_seed', 433))
        rounds = res.get('rounds_log', [])[-20:]
        visual = ''
        if rounds:
            turn_ids = ' '.join(f"{r['round']:02d}" for r in rounds)
            mine = ' '.join(move_symbol(r['my_move']) for r in rounds)
            theirs = ' '.join(move_symbol(r['bot_move']) for r in rounds)
            scores = sparkline([float(r['my_payoff']) for r in rounds], width=min(20, len(rounds)))
            visual = f"\n\nLast turns\nTurns: {turn_ids}\nYou:   {mine}\nOther: {theirs}\nScore: {scores}"
        console.print(Panel(f"Pack: {args.pack}\nDescription: {res['description']}\nMy total: {res['my_total']}\nBot total: {res['bot_total']}\nMy avg: {res['my_avg']}\nMy coop rate: {res['my_coop_rate']:.0%}{visual}", title='Scenario pack result', border_style='magenta'))
        return


if __name__ == '__main__':
    run()
