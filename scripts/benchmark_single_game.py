#!/usr/bin/env python3
"""Measure complete random-policy single games, not model inference."""
import argparse
from collections import Counter
from pathlib import Path
import random
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ptcg.battle import SingleGame, sample_deck


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--games', type=int, default=100)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--max-actions', type=int, default=100000)
    args = parser.parse_args()
    if args.games < 1 or args.max_actions < 1:
        parser.error('games 및 max-actions는 양수여야 합니다.')
    rng = random.Random(args.seed)
    deck = sample_deck()
    results, decisions, observations = Counter(), 0, Counter()
    start = perf_counter()
    for game_index in range(args.games):
        with SingleGame(deck, deck, reverse_player=bool(game_index % 2)) as game:
            for _ in range(args.max_actions):
                if game.result >= 0:
                    results[game.result] += 1
                    break
                obs = game.observation()
                player = game.player
                observations[player] += 1
                select = obs['select']
                count = rng.randint(select['minCount'], select['maxCount'])
                game.step(rng.sample(range(len(select['option'])), count))
                decisions += 1
            else:
                raise RuntimeError(f'게임 {game_index}이 행동 횟수 제한을 초과했습니다.')
    elapsed = perf_counter() - start
    print(f'games={args.games} seconds={elapsed:.3f} games_per_second={args.games/elapsed:.2f} decisions={decisions} results={dict(results)} observations={dict(observations)}')
    print('시드는 Python 선택에만 적용되며 엔진 난수는 고정하지 않습니다. 모델 추론 시간은 포함되지 않습니다.')


if __name__ == '__main__':
    main()
