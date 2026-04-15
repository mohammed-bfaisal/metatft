import unittest

from metatft.engine import MetaTFTEngine
from metatft.models import HorizonFlag, MetaTFTState, ModuleName, Move, NoiseFlag, Opponent, OpponentFlag, PlayerFlag, TemporalFlag
from metatft.utils import compute_gtfo_score, detect_regime, project_ev


class MetaTFTTests(unittest.TestCase):
    def setUp(self):
        self.engine = MetaTFTEngine(MetaTFTState())

    def test_one_shot_prefers_stake_and_signal(self):
        opp = Opponent('x')
        result, _, _ = self.engine.decide(opp, overrides={
            'horizon': HorizonFlag.ONE_SHOT,
            'noise': NoiseFlag.LOW,
            'players': PlayerFlag.BILATERAL,
            'opponent_type': OpponentFlag.MIXED,
            'temporal': TemporalFlag.OPEN,
        })
        self.assertEqual(result.module, ModuleName.STAKE_AND_SIGNAL)

    def test_collective_prefers_commons(self):
        opp = Opponent('x')
        result, _, _ = self.engine.decide(opp, overrides={'players': PlayerFlag.COLLECTIVE})
        self.assertEqual(result.module, ModuleName.COMMONS_MODE)

    def test_gtfo_score_nonnegative(self):
        self.assertEqual(compute_gtfo_score(-5, 10), 0.0)
        self.assertEqual(compute_gtfo_score(5, 10), 0.5)

    def test_regime_detection(self):
        opp = Opponent('x')
        for i in range(6):
            opp.history.append(type('R', (), {'my_move': Move.COOPERATE, 'opponent_move': Move.COOPERATE, 'payoff': 3, 'round_num': i+1})())
        self.assertEqual(detect_regime(opp.history), 'stable reciprocity')

    def test_simulate_pack_runs(self):
        result = self.engine.simulate_pack('hard_defector', seed=433)
        self.assertIn('my_total', result)
        self.assertEqual(result['pack'], 'hard_defector')

    def test_easy_mode_defaults_on(self):
        self.assertTrue(MetaTFTState().settings.get('easy_mode'))


if __name__ == '__main__':
    unittest.main()
