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
    if kind == 'last':
        return list(range(len(s['option']) - s['maxCount'], len(s['option'])))
    if kind != 'random':
        raise ValueError(f'Unknown fixed opponent: {kind}')
    n = rng.randint(s['minCount'], s['maxCount'])
    return rng.sample(range(len(s['option'])), n)


def play(decks, players, trainable, rng, max_actions, reverse=False, greedy=False):
    trajectories = [[], []]
    decisions = [0, 0]
    inference_seconds = [0.0, 0.0]
    first_player = None
    with SingleGame(decks[0], decks[1], reverse) as game:
        for _ in range(max_actions):
            if game.result >= 0:
                result = game.result
                for player in (0, 1):
                    reward = 0 if result == 2 else (1 if result == player else -1)
                    finish_trajectory(trajectories[player], reward)
                return result, trajectories, decisions, inference_seconds, first_player
            player = game.player
            obs = game.observation()
            first = obs['current'].get('firstPlayer')
            if first in (0, 1):
                first_player = first
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


def train(mode, cfg, decks):
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
    result['deck_matchups'] = {}
    t0 = time.perf_counter()
    categories = ('current', 'history', 'fixed')
    for g in range(cfg.games):
        category = categories[g % len(categories)]
        d0 = (g // len(categories)) % len(decks)
        d1 = (g // (len(categories) * len(decks))) % len(decks)
        matchup = f'{decks[d0][0]} vs {decks[d1][0]}'
        result['deck_matchups'][matchup] = result['deck_matchups'].get(matchup, 0) + 1
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
            outcome, trajectories, counts, _, _ = play([decks[d0][1], decks[d1][1]], players, trainable, rng, cfg.max_actions, bool((g // (len(categories) * len(decks) * len(decks))) % 2))
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


def evaluate(policy, decks, opponents, count, seed, max_actions):
    resolved = {}
    for name in opponents:
        if name in ('first', 'last'):
            resolved[name] = (name, None)
        elif name.startswith('checkpoint:'):
            path = Path(name[len('checkpoint:'):])
            if not path.is_file():
                raise ValueError(f'Opponent checkpoint not found: {path}')
            opponent_policy = Policy()
            opponent_policy.load_state_dict(torch.load(path, map_location='cpu', weights_only=True))
            opponent_policy.eval()
            resolved[name] = (opponent_policy, hashlib.sha256(path.read_bytes()).hexdigest())
        else:
            raise ValueError(f'Unknown evaluation opponent: {name}')
    rng = random.Random(seed)
    torch.manual_seed(seed)
    rows = []
    for own_name, own_deck in decks:
        for other_name, other_deck in decks:
            for opponent in opponents:
                wins = losses = draws = 0
                seats = {str(i): {'wins': 0, 'losses': 0, 'draws': 0, 'games': 0} for i in (0, 1)}
                orders = {str(i): {'wins': 0, 'losses': 0, 'draws': 0, 'games': 0} for i in (0, 1)}
                elapsed = total_time = 0.0
                total_decisions = 0
                for g in range(count):
                    seat = g % 2
                    players = [resolved[opponent][0], resolved[opponent][0]]
                    players[seat] = policy
                    game_decks = [other_deck, other_deck]
                    game_decks[seat] = own_deck
                    start = time.perf_counter()
                    result, _, decisions, timings, first_player = play(game_decks, players, [False, False], rng, max_actions, bool((g // 2) % 2), greedy=True)
                    elapsed += time.perf_counter() - start
                    total_time += timings[seat]
                    total_decisions += decisions[seat]
                    outcome = 'draws' if result == 2 else ('wins' if result == seat else 'losses')
                    wins += outcome == 'wins'
                    losses += outcome == 'losses'
                    draws += outcome == 'draws'
                    seats[str(seat)]['games'] += 1
                    seats[str(seat)][outcome] += 1
                    if first_player in (0, 1):
                        order = str(int(first_player != seat))
                        orders[order]['games'] += 1
                        orders[order][outcome] += 1
                rows.append({'own_deck': own_name, 'opponent_deck': other_name, 'opponent': opponent, 'opponent_sha256': resolved[opponent][1],
                             'wins': wins, 'losses': losses, 'draws': draws, 'games': count,
                             'win_rate': wins / count, 'wilson_win_interval': wilson(wins, count),
                             'seat_results': seats, 'turn_order_results': orders,
                             'inference_decisions': total_decisions, 'inference_seconds': total_time,
                             'seconds': elapsed})
    wins = sum(row['wins'] for row in rows)
    losses = sum(row['losses'] for row in rows)
    draws = sum(row['draws'] for row in rows)
    total = wins + losses + draws
    decisions = sum(row['inference_decisions'] for row in rows)
    return {'wins': wins, 'losses': losses, 'draws': draws, 'games': total,
            'win_rate': wins / total, 'wilson_win_interval': wilson(wins, total),
            'mean_inference_ms': round(sum(row['inference_seconds'] for row in rows) * 1000 / max(1, decisions), 4),
            'matchups': rows}


def load_decks(paths):
    if not paths:
        return [('official_sample', sample_deck())]
    decks = []
    for path in paths:
        path = Path(path)
        cards = [int(line) for line in path.read_text().splitlines() if line.strip()]
        if len(cards) != 60:
            raise ValueError(f'{path}: expected 60 card IDs')
        decks.append((path.stem, cards))
    if len({name for name, _ in decks}) != len(decks):
        raise ValueError('Duplicate deck names')
    if len({deck_hash(deck) for _, deck in decks}) != len(decks):
        raise ValueError('Duplicate decks in pool')
    return decks


def deck_hash(deck):
    return hashlib.sha256(','.join(map(str, sorted(deck))).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--train-deck', action='append', default=[])
    p.add_argument('--validation-deck', action='append', default=[])
    p.add_argument('--eval-deck', action='append', default=[])
    p.add_argument('--eval-opponent', action='append', default=[], help='first, last, or checkpoint:PATH')
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
    if len(set(cfg.eval_opponent)) != len(cfg.eval_opponent):
        p.error('Evaluation opponents must be unique')
    if min(cfg.games, cfg.eval_games, cfg.rollout_games, cfg.epochs, cfg.batch_size, cfg.history, cfg.max_actions, cfg.validation_games) < 1 or cfg.lr <= 0 or cfg.time_budget < 0:
        p.error('Counts and learning rate must be positive')
    if cfg.output.exists() and any(cfg.output.iterdir()):
        p.error('Output directory is not empty; choose a new --output directory')
    cfg.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    train_decks = load_decks(cfg.train_deck)
    validation_decks = load_decks(cfg.validation_deck)
    eval_decks = load_decks(cfg.eval_deck)
    if any((cfg.train_deck, cfg.validation_deck, cfg.eval_deck)):
        if not all((cfg.train_deck, cfg.validation_deck, cfg.eval_deck)):
            p.error('Specify train, validation and evaluation deck pools together')
        pools = [{deck_hash(deck) for _, deck in group} for group in (train_decks, validation_decks, eval_decks)]
        if any(pools[i] & pools[j] for i in range(3) for j in range(i + 1, 3)):
            p.error('Train, validation and evaluation decks must be disjoint by card counts')
    for pool in (train_decks, validation_decks, eval_decks):
        for name, deck in pool:
            with SingleGame(deck, deck):
                pass
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    report = {'revision': revision, 'torch_version': torch.__version__, 'working_tree_dirty': bool(subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, text=True, capture_output=True).stdout.strip()),
              'deck_pools': {name: [{'name': n, 'sha256': deck_hash(d)} for n, d in pool] for name, pool in [('train', train_decks), ('validation', validation_decks), ('evaluation', eval_decks)]}, 'config': {k: str(v) if isinstance(v, Path) else v for k, v in vars(cfg).items()},
              'engine_seed_controlled': False, 'time_budget_note': 'Checked after completed games; final update may exceed budget.', 'runs': []}
    for mode in ('shared', 'independent'):
        models, metrics = train(mode, cfg, train_decks)
        metrics['evaluation'] = []
        if mode == 'independent':
            validation = [evaluate(m, validation_decks, ['first'], cfg.validation_games, cfg.seed + 5000, cfg.max_actions) for m in models]
            metrics['validation'] = validation
            metrics['selected_model'] = max(range(len(models)), key=lambda i: validation[i]['win_rate'])
        for i, model in enumerate(models):
            result = evaluate(model, eval_decks, cfg.eval_opponent or ['first'], cfg.eval_games, cfg.seed + 10000, cfg.max_actions)
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
