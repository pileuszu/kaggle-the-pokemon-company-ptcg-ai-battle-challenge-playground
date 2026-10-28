import os
import json
import random

_seen_round = 0
_cards = set()
_events = 0
_calls = 0

def agent(obs):
    global _seen_round, _events, _calls
    _calls += 1
    current = obs.get('current')
    if current is None:
        filename = '/kaggle_simulations/agent/deck.csv'
        if not os.path.exists(filename):
            filename = 'deck.csv'
        with open(filename) as deck_file:
            return [int(line) for line in deck_file if line.strip()]
    round_no = current.get('round', 1)
    if round_no != _seen_round:
        print('BO3_MEMORY_PROBE ' + json.dumps({'pid': os.getpid(), 'round': round_no, 'previous_round': _seen_round, 'calls': _calls, 'retained_cards': sorted(_cards), 'retained_events': _events, 'score': [p.get('win') for p in current.get('players', [])]}, separators=(',', ':')), flush=True)
        _seen_round = round_no
    opponent = 1 - current['yourIndex']
    players = current['players']
    for zone in ('active', 'bench', 'discard'):
        for card in players[opponent].get(zone) or []:
            if isinstance(card, dict) and card.get('id') is not None:
                _cards.add(card['id'])
    for event in obs.get('logs') or []:
        if isinstance(event, dict) and event.get('playerIndex') == opponent:
            _events += 1
    select = obs['select']
    return random.sample(range(len(select['option'])), select['maxCount'])
