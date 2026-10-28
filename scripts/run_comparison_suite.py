#!/usr/bin/env python3
"""Run independent seeds from a manifest and collect per-seed metrics."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/comparison.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'runs/comparison-suite')
    args = parser.parse_args()
    args.output = args.output.resolve()
    config = json.loads(args.config.read_text())
    seeds = config['seeds']
    if not seeds or len(set(seeds)) != len(seeds) or any(type(x) is not int for x in seeds):
        parser.error('seeds must contain unique integers')
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('Output directory must be empty')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    reports = []
    for seed in seeds:
        cmd = [sys.executable, str(ROOT / 'scripts/compare_ppo.py'),
               '--seed', str(seed), '--output', str(args.output / f'seed-{seed}'),
               '--games', str(config['games']), '--rollout-games', str(config['rollout_games']),
               '--epochs', str(config['epochs']), '--batch-size', str(config['batch_size']),
               '--eval-games', str(config['evaluation_games_per_matchup']),
               '--validation-games', str(config['validation_games_per_matchup']),
               '--time-budget', str(config.get('time_budget', 0))]
        for key, flag in [('train_decks', '--train-deck'), ('validation_decks', '--validation-deck'), ('evaluation_decks', '--eval-deck')]:
            if not config.get(key):
                raise ValueError(f'{key} must be nonempty')
            for path in config[key]:
                cmd.extend([flag, str(ROOT / path)])
        for opponent in config['eval_opponents']:
            cmd.extend(['--eval-opponent', opponent])
        if not config['eval_opponents']:
            raise ValueError('eval_opponents must be nonempty')
        print(f'시드 {seed}: 학습과 평가 시작', flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True)
        reports.append(json.loads((args.output / f'seed-{seed}' / 'report.json').read_text()))
    summaries = []
    for report in reports:
        shared, independent = report['runs']
        summaries.append({'seed': report['config']['seed'],
                          'shared_win_rate': shared['evaluation'][0]['win_rate'],
                          'independent_mean_win_rate': independent['mean_agent_win_rate'],
                          'validation_selected_win_rate': independent['selected_validation_model_final_win_rate'],
                          'shared_games': shared['games'], 'independent_games': independent['games'],
                          'shared_seconds': shared['train_seconds'], 'independent_seconds': independent['train_seconds']})
    summary = {'seeds': summaries, 'shared_mean': statistics.mean(x['shared_win_rate'] for x in summaries),
               'independent_mean': statistics.mean(x['independent_mean_win_rate'] for x in summaries),
               'warning': 'Seed means are descriptive; engine RNG is not controlled; inspect matchup counts and uncertainty.'}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'결과: {args.output / "summary.json"}')


if __name__ == '__main__':
    main()
