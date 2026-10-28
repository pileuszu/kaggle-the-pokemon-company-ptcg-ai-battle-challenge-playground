#!/usr/bin/env python3
"""Play one local game and export a self-contained browser replay."""
import argparse
from contextlib import ExitStack
import csv
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ptcg.battle import SingleGame, sample_deck
from ptcg.external import ExternalAgent


def read_deck(path):
    if not path:
        return sample_deck()
    deck = [int(x) for x in Path(path).read_text().splitlines() if x.strip()]
    if len(deck) != 60:
        raise ValueError(f'{path}: 덱에는 60개 카드가 필요합니다.')
    return deck


def metadata():
    path = ROOT / 'data/playground/EN_Card_Data_R2_full.csv'
    if not path.exists():
        raise FileNotFoundError('대회 카드 자료가 없습니다. sh scripts/setup.sh를 먼저 실행하세요.')
    cards = {}
    with path.open(encoding='utf-8-sig', newline='') as file:
        for row in csv.DictReader(file):
            cards.setdefault(row['Card ID'], {'name': row['Card Name'],
                'set': row['Expansion'], 'number': row['Collection No.']})
    return cards


def load_player(spec, deck_path, stack):
    if spec in ('random', 'first'):
        return spec, read_deck(deck_path)
    if spec.startswith('agent:'):
        bundle = Path(spec[len('agent:'):])
        if deck_path:
            raise ValueError('외부 에이전트는 자체 deck.csv를 사용합니다.')
        return stack.enter_context(ExternalAgent(bundle)), read_deck(bundle / 'deck.csv')
    if spec.startswith('checkpoint:'):
        import torch
        from ptcg.ppo import Policy
        path = Path(spec[len('checkpoint:'):])
        policy = Policy()
        policy.load_state_dict(torch.load(path, map_location='cpu', weights_only=True))
        policy.eval()
        torch.set_num_threads(1)
        return policy, read_deck(deck_path)
    raise ValueError(f'지원하지 않는 에이전트: {spec}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--agent0', default='random', help='random, first, checkpoint:PATH 또는 agent:DIR')
    p.add_argument('--agent1', default='random', help='random, first, checkpoint:PATH 또는 agent:DIR')
    p.add_argument('--deck0')
    p.add_argument('--deck1')
    p.add_argument('--seed', type=int, default=42, help='무작위 에이전트의 행동 시드 (엔진의 섞기 시드는 고정하지 않음)')
    p.add_argument('--max-actions', type=int, default=10000)
    p.add_argument('--output', type=Path, default=ROOT / 'runs/replays/battle.html')
    p.add_argument('--force', action='store_true', help='기존 출력 파일 덮어쓰기')
    args = p.parse_args()
    if args.max_actions < 1:
        p.error('--max-actions는 양수여야 합니다.')
    if args.output.exists() and not args.force:
        p.error(f'출력 파일이 이미 있습니다: {args.output} (변경하거나 --force 사용)')
    rng = random.Random(args.seed)
    with ExitStack() as stack:
        a0, d0 = load_player(args.agent0, args.deck0, stack)
        a1, d1 = load_player(args.agent1, args.deck1, stack)
        agents = [a0, a1]
        with SingleGame(d0, d1) as game:
            for _ in range(args.max_actions):
                if game.result >= 0:
                    break
                obs, player = game.observation(), game.player
                sel, agent = obs['select'], agents[player]
                if agent == 'random':
                    action = rng.sample(range(len(sel['option'])), sel['maxCount'])
                elif agent == 'first':
                    action = list(range(sel['maxCount']))
                elif isinstance(agent, ExternalAgent):
                    action = agent.act(obs)
                else:
                    from ptcg.ppo import sample
                    action, _ = sample(agent, obs, greedy=True)
                game.step(action)
            else:
                raise RuntimeError('행동 횟수 제한에 도달했습니다.')
            frames = json.loads(game._game.visualize_data())
            result = game.result
    if not frames:
        raise RuntimeError('엔진이 리플레이 프레임을 반환하지 않았습니다.')
    template = (ROOT / 'replay/viewer.html').read_text()
    payload = json.dumps({'frames': frames, 'cards': metadata(), 'agents': [args.agent0, args.agent1]}, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = template.replace('/*__REPLAY_CSS__*/', (ROOT / 'replay/viewer.css').read_text())
    template = template.replace('/*__REPLAY_JS__*/', (ROOT / 'replay/viewer.js').read_text())
    template = template.replace('__REPLAY_DATA__', payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template, encoding='utf-8')
    print(f'리플레이 저장: {args.output.resolve()} (프레임 {len(frames)}, 결과 {result})')


if __name__ == '__main__':
    main()
