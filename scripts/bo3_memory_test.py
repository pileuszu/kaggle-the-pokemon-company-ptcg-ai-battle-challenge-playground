#!/usr/bin/env python3
"""Probe per-agent memory across games with Kaggle's local BO3 interpreter."""
import argparse
import json
from collections import Counter
from pathlib import Path
import random

from kaggle_environments import make

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / 'data/playground/sample_submission/sample_submission/sample_submission/deck.csv'


class Probe:
    def __init__(self, player, deck, seed):
        self.player, self.deck = player, deck
        self.rng = random.Random(seed + player)
        self.round = 0
        self.cards = set()
        self.opponent_events = []
        self.previous_logs = set()
        self.transitions = []
        self.rounds = Counter()

    def __call__(self, obs, configuration=None):
        current = obs.get('current')
        if current is None:
            return self.deck
        round_no = current.get('round', 1)
        logs = obs.get('logs') or []
        opponent = 1 - self.player
        if round_no > self.round and self.round:
            snapshot = {'player': self.player, 'from_round': self.round, 'to_round': round_no,
                        'previous_opponent_cards': sorted(self.cards),
                        'previous_opponent_events': len(self.opponent_events),
                        'first_observation_logs': len(logs),
                        'matching_prior_log_entries': sum(json.dumps(e, sort_keys=True) in self.previous_logs for e in logs),
                        'first_observation_opponent_events': sum(e.get('playerIndex') == opponent for e in logs if isinstance(e, dict)),
                        'score': [p.get('win') for p in current.get('players', [])],
                        'draws': current.get('draw')}
            self.transitions.append(snapshot)
            print('ROUND_TRANSITION ' + json.dumps(snapshot))
        self.round = round_no
        self.previous_logs.update(json.dumps(e, sort_keys=True) for e in logs)
        self.rounds[round_no] += 1
        players = current.get('players') or []
        if len(players) > opponent:
            state = players[opponent]
            for zone in ('active', 'bench', 'discard'):
                for card in state.get(zone) or []:
                    if isinstance(card, dict) and card.get('id') is not None:
                        self.cards.add(card['id'])
        for event in logs:
            if isinstance(event, dict) and event.get('playerIndex') == opponent:
                self.opponent_events.append(event)
        select = obs.get('select')
        if select is None:
            raise RuntimeError('Active agent was called without legal choices')
        return self.rng.sample(range(len(select['option'])), select['maxCount'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--seed', type=int, default=42)
    args = p.parse_args()
    if not DECK.exists():
        raise SystemExit('먼저 sh scripts/setup.sh를 실행하세요.')
    deck = [int(x) for x in DECK.read_text().splitlines() if x.strip()]
    players = [Probe(i, deck, args.seed) for i in range(2)]
    env = make('cabt', configuration={'bo': 3, 'version': 2}, debug=True)
    steps = env.run(players)
    print('FINAL ' + json.dumps({'statuses': [s.status for s in steps[-1]],
                                 'rewards': [s.reward for s in steps[-1]],
                                 'games': getattr(env, 'result', None), 'steps': len(steps)}))
    if not all(s.status == 'DONE' for s in steps[-1]):
        raise RuntimeError('대전이 정상 종료되지 않았습니다.')
    if not all(p.transitions for p in players):
        raise RuntimeError('두 에이전트 모두 다음 게임을 관찰하지 못했습니다.')
    if not any(t['previous_opponent_cards'] and t['previous_opponent_events'] for p in players for t in p.transitions):
        raise RuntimeError('상대 카드와 행동 기록을 이전 게임에서 수집하지 못했습니다.')


if __name__ == '__main__':
    main()
