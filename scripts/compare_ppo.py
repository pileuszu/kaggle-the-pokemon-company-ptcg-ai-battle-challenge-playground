#!/usr/bin/env python3
"""Small, reproducible-by-configuration PPO comparison (engine RNG is uncontrolled)."""
import argparse
import copy
import hashlib
import subprocess
import json
import math
from pathlib import Path
import random
import sys
import time

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ptcg.battle import SingleGame, sample_deck
from ptcg.ppo import Policy, finish_trajectory, sample, update


def fixed_action(obs, rng, kind):
    s = obs['select']
    if kind == 'first':
        return list(range(s['maxCount']))
    n = rng.randint(s['minCount'], s['maxCount'])
    return rng.sample(range(len(s['option'])), n)


def play(deck, players, trainable, rng, max_actions, reverse=False, greedy=False):
    trajectories = [[], []]
    decisions = [0, 0]
    inference_seconds = [0.0, 0.0]
    with SingleGame(deck, deck, reverse) as game:
        for _ in range(max_actions):
            if game.result >= 0:
                result = game.result
                for player in (0, 1):
                    reward = 0 if result == 2 else (1 if result == player else -1)
                    finish_trajectory(trajectories[player], reward)
                return result, trajectories, decisions, inference_seconds
            player = game.player
            obs = game.observation()
            decisions[player] += 1
            policy = players[player]
            if isinstance(policy, str):
                action = fixed_action(obs, rng, policy)
            else:
                t = time.perf_counter()
                action, transition = sample(policy, obs, greedy=greedy)
                inference_seconds[player] += time.perf_counter() - t
                if trainable[player]:
                    trajectories[player].append(transition)
            game.step(action)
    raise RuntimeError('게임 행동 제한에 도달했습니다. 정상 승패로 처리하지 않습니다.')


def train(mode, cfg, deck):
    rng = random.Random(cfg.seed)
    torch.manual_seed(cfg.seed)
    models = [Policy()] if mode == 'shared' else [Policy(), Policy()]
    # Shared and A begin with the same initial policy; B is independent.
    optimizers = [torch.optim.Adam(p.parameters(), lr=cfg.lr) for p in models]
    histories = [[copy.deepcopy(p).eval()] for p in models]
    data = [[] for _ in models]
    result = {'mode': mode, 'games': 0, 'decisions': 0, 'updates': [0] * len(models),
              'transitions': [0] * len(models), 'opponents': {'current': 0, 'history': 0, 'fixed': 0},
              'errors': 0, 'seed': cfg.seed}
    t0 = time.perf_counter()
    categories = ('current', 'history', 'fixed')
    for g in range(cfg.games):
        category = categories[g % len(categories)]
        result['opponents'][category] += 1
        learner = (g // len(categories)) % 2
        opponent = 1 - learner
        assigned = [0, 0] if mode == 'shared' else ([0, 1] if (g // 2) % 2 == 0 else [1, 0])
        players = [models[assigned[0]], models[assigned[1]]]
        trainable = [True, True]
        if category != 'current':
            trainable[opponent] = False
            if category == 'fixed':
                players[opponent] = 'random'
            else:
                players[opponent] = rng.choice(histories[assigned[opponent]])
        try:
            outcome, trajectories, counts, _ = play(deck, players, trainable, rng, cfg.max_actions, bool(g % 2))
        except Exception:
            result['errors'] += 1
            raise
        result['games'] += 1
        result['decisions'] += sum(counts)
        for seat in (0, 1):
            if trainable[seat]:
                data[assigned[seat]].extend(trajectories[seat])
        if (g + 1) % cfg.rollout_games == 0 or g + 1 == cfg.games or (cfg.time_budget and time.perf_counter() - t0 >= cfg.time_budget):
            for i, (p, opt) in enumerate(zip(models, optimizers)):
                metrics = update(p, opt, data[i], epochs=cfg.epochs, batch_size=cfg.batch_size, rng=rng)
                result['updates'][i] += metrics['updates']
                result['transitions'][i] += metrics['transitions']
                data[i] = []
                histories[i].append(copy.deepcopy(p).eval())
                histories[i] = histories[i][-cfg.history:]
        if cfg.time_budget and time.perf_counter() - t0 >= cfg.time_budget:
            break
    result['train_seconds'] = round(time.perf_counter() - t0, 3)
    return models, result


def wilson(wins, games):
    z = 1.96
    p = wins / games
    d = 1 + z*z/games
    center = (p + z*z/(2*games))/d
    margin = z*math.sqrt(p*(1-p)/games + z*z/(4*games*games))/d
    return [round(center-margin, 4), round(center+margin, 4)]


def evaluate(policy, deck, count, seed, max_actions):
    rng = random.Random(seed)
    torch.manual_seed(seed)
    wins = losses = draws = 0
    seats = {str(i): {'wins': 0, 'games': 0} for i in (0, 1)}
    t0 = time.perf_counter()
    inference_seconds = 0.0
    inference_decisions = 0
    for g in range(count):
        seat = g % 2
        players = ['first', 'first']
        players[seat] = policy
        result, _, decisions, timings = play(deck, players, [False, False], rng, max_actions, bool((g // 2) % 2), greedy=True)
        inference_seconds += timings[seat]
        inference_decisions += decisions[seat]
        seats[str(seat)]['games'] += 1
        if result == 2:
            draws += 1
        elif result == seat:
            wins += 1
            seats[str(seat)]['wins'] += 1
        else:
            losses += 1
    return {'wins': wins, 'losses': losses, 'draws': draws, 'games': count,
            'win_rate': wins / count, 'wilson_win_interval': wilson(wins, count),
            'seat_results': seats, 'seconds': round(time.perf_counter() - t0, 3),
            'opponent': 'first', 'deck': 'official_sample',
            'inference_decisions': inference_decisions,
            'mean_inference_ms': round(inference_seconds * 1000 / max(1, inference_decisions), 4)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--games', type=int, default=12)
    p.add_argument('--eval-games', type=int, default=8)
    p.add_argument('--rollout-games', type=int, default=6)
    p.add_argument('--epochs', type=int, default=2)
    p.add_argument('--batch-size', type=int, default=128)
    p.add_argument('--history', type=int, default=4)
    p.add_argument('--max-actions', type=int, default=10000)
    p.add_argument('--validation-games', type=int, default=4)
    p.add_argument('--time-budget', type=float, default=0, help='Per-method seconds, checked after each completed game/update; 0 disables')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--lr', type=float, default=0.0003)
    p.add_argument('--output', type=Path, default=ROOT / 'runs/ppo-comparison')
    cfg = p.parse_args()
    if min(cfg.games, cfg.eval_games, cfg.rollout_games, cfg.epochs, cfg.batch_size, cfg.history, cfg.max_actions, cfg.validation_games) < 1 or cfg.lr <= 0 or cfg.time_budget < 0:
        p.error('Counts and learning rate must be positive')
    if cfg.output.exists() and any(cfg.output.iterdir()):
        p.error('Output directory is not empty; choose a new --output directory')
    cfg.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    deck = sample_deck()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    report = {'revision': revision, 'torch_version': torch.__version__,
              'deck_sha256': hashlib.sha256(','.join(map(str, deck)).encode()).hexdigest(), 'config': {k: str(v) if isinstance(v, Path) else v for k, v in vars(cfg).items()},
              'engine_seed_controlled': False, 'time_budget_note': 'Checked after completed games; final update may exceed budget.', 'runs': []}
    for mode in ('shared', 'independent'):
        models, metrics = train(mode, cfg, deck)
        metrics['evaluation'] = []
        if mode == 'independent':
            validation = [evaluate(m, deck, cfg.validation_games, cfg.seed + 5000, cfg.max_actions) for m in models]
            metrics['validation'] = validation
            metrics['selected_model'] = max(range(len(models)), key=lambda i: validation[i]['win_rate'])
        for i, model in enumerate(models):
            result = evaluate(model, deck, cfg.eval_games, cfg.seed + 10000, cfg.max_actions)
            metrics['evaluation'].append(result)
            model_path = cfg.output / f'{mode}-{i}.pt'
            torch.save(model.state_dict(), model_path)
            result['model_bytes'] = model_path.stat().st_size
        if mode == 'independent':
            metrics['mean_agent_win_rate'] = sum(x['win_rate'] for x in metrics['evaluation']) / 2
            metrics['selected_validation_model_final_win_rate'] = metrics['evaluation'][metrics['selected_model']]['win_rate']
        report['runs'].append(metrics)
        print(json.dumps(metrics, ensure_ascii=False), flush=True)
    (cfg.output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(f'report={cfg.output / "report.json"}')


if __name__ == '__main__':
    main()
