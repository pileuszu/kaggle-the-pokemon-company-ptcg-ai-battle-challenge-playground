import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from compare_ppo import deck_hash, fixed_action, load_decks


class ExperimentTest(unittest.TestCase):
    def test_deck_hash_uses_card_multiset(self):
        self.assertEqual(deck_hash([1, 2, 1]), deck_hash([2, 1, 1]))
        self.assertNotEqual(deck_hash([1, 2, 1]), deck_hash([2, 2, 1]))

    def test_duplicate_decks_rejected_even_if_reordered(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / 'a.csv'
            second = Path(tmp) / 'b.csv'
            first.write_text('1\n' * 59 + '2\n')
            second.write_text('2\n' + '1\n' * 59)
            with self.assertRaisesRegex(ValueError, 'Duplicate decks'):
                load_decks([first, second])

    def test_fixed_opponents_select_valid_and_distinct_options(self):
        obs = {'select': {'minCount': 1, 'maxCount': 2, 'option': [0, 1, 2, 3]}}
        self.assertEqual(fixed_action(obs, random.Random(1), 'first'), [0, 1])
        self.assertEqual(fixed_action(obs, random.Random(1), 'last'), [2, 3])
        with self.assertRaises(ValueError):
            fixed_action(obs, random.Random(1), 'unknown')


if __name__ == '__main__':
    unittest.main()
