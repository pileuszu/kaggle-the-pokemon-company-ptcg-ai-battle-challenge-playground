import copy
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import torch
from ptcg.battle import SingleGame, sample_deck, validate_selection
from ptcg.ppo import OPTION_SIZE, Policy, Transition, encode, finish_trajectory, update


class PPOTest(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(7)
        self.model = Policy()
        self.state = torch.zeros(20)
        self.options = torch.randn(4, OPTION_SIZE)

    def test_sequential_probability_and_validity(self):
        for minimum, maximum in ((0, 0), (0, 3), (1, 1), (2, 4)):
            for _ in range(20):
                action, seq, logp, _, _ = self.model.evaluate_action(self.state, self.options, minimum, maximum)
                validate_selection({'minCount': minimum, 'maxCount': maximum, 'option': [0]*4}, action)
                replay = self.model.evaluate_action(self.state, self.options, minimum, maximum, seq)
                self.assertEqual(replay[0], action)
                self.assertTrue(torch.allclose(replay[2], logp))

    def test_gae_terminal_rewards_and_ppo_update(self):
        records = []
        for _ in range(4):
            _, seq, logp, _, val = self.model.evaluate_action(self.state, self.options, 1, 2)
            records.append(Transition(self.state, self.options, 1, 2, seq, logp.item(), val.item()))
        finish_trajectory(records, 1.0, gamma=1.0, gae_lambda=1.0)
        for item in records:
            self.assertAlmostEqual(item.target, 1.0, places=5)
        before = [p.detach().clone() for p in self.model.parameters()]
        result = update(self.model, torch.optim.Adam(self.model.parameters(), lr=1e-3), records, epochs=1, batch_size=4, rng=random.Random(0))
        self.assertEqual(result['transitions'], 4)
        self.assertTrue(any(not torch.equal(a, b) for a, b in zip(before, self.model.parameters())))

    def test_encoding_ignores_opponent_private_state_and_opaque_search(self):
        deck = sample_deck()
        with SingleGame(deck, deck) as game:
            obs = game.observation()
            original = encode(obs)
            changed = copy.deepcopy(obs)
            opponent = 1 - changed['current']['yourIndex']
            changed['current']['players'][opponent]['hand'] = [{'id': 999999}]
            changed['current']['players'][opponent]['prize'] = [{'id': 12345} for _ in changed['current']['players'][opponent]['prize']]
            changed['search_begin_input'] = 'hidden'
            encoded = encode(changed)
            self.assertTrue(torch.equal(original[0], encoded[0]))
            self.assertTrue(torch.equal(original[1], encoded[1]))

    def test_reject_invalid_replayed_action(self):
        with self.assertRaises(ValueError):
            self.model.evaluate_action(self.state, self.options, 1, 2, [4])


if __name__ == '__main__':
    unittest.main()
