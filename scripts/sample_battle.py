#!/usr/bin/env python3
"""Run one local battle using the downloaded sample agent and engine."""
from pathlib import Path
import argparse
import os
import random
import sys

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data/playground/sample_submission/sample_submission/sample_submission"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="Sample agent random seed")
    parser.add_argument("--max-actions", type=int, default=100000)
    args = parser.parse_args()
    if args.max_actions < 1:
        parser.error("--max-actions must be positive")
    if not (SAMPLE / "main.py").is_file():
        raise SystemExit("샘플 자료가 없습니다. 먼저 sh scripts/setup.sh를 실행하세요.")
    sys.path.insert(0, str(SAMPLE))
    os.chdir(SAMPLE)  # The official sample loads deck.csv from the current directory.
    import main as sample
    from cg import game

    random.seed(args.seed)  # Controls Python choices, not the native engine's randomness.
    deck = sample.read_deck_csv()
    obs, start = game.battle_start(deck, deck)
    if obs is None:
        raise SystemExit(f"대전 시작 실패: player={start.errorPlayer}, error={start.errorType}")
    try:
        for step in range(args.max_actions):
            current = obs.get("current") or {}
            if current.get("result", -1) >= 0:
                print(f"대전 완료: 선택 횟수={step}, 결과 코드={current['result']}, 무승부={current.get('draw')}, 턴={current.get('turn')}")
                return
            if obs.get("select") is None:
                raise RuntimeError("종료되지 않은 대전에 선택지가 없습니다.")
            obs = game.battle_select(sample.agent(obs))
        raise RuntimeError(f"선택 횟수 제한({args.max_actions})에 도달했습니다.")
    finally:
        game.battle_finish()


if __name__ == "__main__":
    main()
