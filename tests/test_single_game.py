import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ptcg.battle import SingleGame, sample_deck, validate_selection


class SelectionTest(unittest.TestCase):
    def test_optional_multi_choice_and_invalid_actions(self):
        select = {'minCount': 0, 'maxCount': 2, 'option': [1, 2, 3]}
        for action in ([], [0], [1, 2]):
            validate_selection(select, action)
        for action in ([0, 0], [-1], [3], [0, 1, 2], [True], (0,)):
            with self.subTest(action=action), self.assertRaises(ValueError):
                validate_selection(select, action)

    def test_required_choice(self):
        with self.assertRaises(ValueError):
            validate_selection({'minCount': 1, 'maxCount': 1, 'option': [1]}, [])


class EngineTest(unittest.TestCase):
    def test_complete_game_with_private_observations_and_reusable_engine(self):
        deck = sample_deck()
        rng = random.Random(3)
        for reverse in (False, True):
            seen = set()
            with SingleGame(deck, deck, reverse) as game:
                with self.assertRaises(RuntimeError):
                    SingleGame(deck, deck)
                for _ in range(100000):
                    if game.result >= 0:
                        break
                    obs = game.observation()
                    seen.add(game.player)
                    self.assertNotIn('search_begin_input', obs)
                    self.assertIsNone(obs['current']['players'][1 - game.player]['hand'])
                    s = obs['select']
                    game.step(rng.sample(range(len(s['option'])), s['maxCount']))
                self.assertIn(game.result, (0, 1, 2))
                self.assertEqual(seen, {0, 1})
            with self.assertRaises(RuntimeError):
                game.observation()


if __name__ == '__main__':
    unittest.main()
