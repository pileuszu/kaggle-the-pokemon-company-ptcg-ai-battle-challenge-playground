#!/usr/bin/env python3
"""Create small, auditable smoke-test decks from official card IDs."""
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ptcg.battle import SingleGame, sample_deck

DEST = ROOT / 'data/experiment-decks'
# Simple synthetic examples, not competitive deck recommendations. Each
# contains four each of three different basic Pokémon and 48 matching Energy.
RECIPES = {
    'train-water-a': ([108, 154, 179], 3),
    'train-fire': ([31, 46, 76], 2),
    'validation-water-a': ([33, 103, 105], 3),
    'validation-lightning': ([36, 37, 160], 4),
    'eval-water-a': ([101, 159, 180], 3),
    'eval-grass': ([25, 27, 45], 1),
}


def main():
    source = ROOT / 'data/playground/EN_Card_Data_R2_full.csv'
    with source.open(encoding='utf-8-sig', newline='') as file:
        rows = list(csv.DictReader(file))
    available = {int(row['Card ID']) for row in rows}
    decks = {'train-official-sample': sample_deck()}
    decks.update({name: [card for card in cards for _ in range(4)] + [energy] * 48 for name, (cards, energy) in RECIPES.items()})
    for name, deck in decks.items():
        if len(deck) != 60 or set(deck) - available:
            raise ValueError(f'{name}: invalid deck or unknown card ID')
        with SingleGame(deck, sample_deck()):
            pass
    DEST.mkdir(parents=True, exist_ok=True)
    for name, deck in decks.items():
        path = DEST / (name + '.csv')
        expected = ''.join(f'{card}\n' for card in deck)
        if path.exists() and path.read_text() != expected:
            raise FileExistsError(f'{path} exists with different contents')
    for name, deck in decks.items():
        (DEST / (name + '.csv')).write_text(''.join(f'{card}\n' for card in deck))
    print(f'{len(decks)} decks validated and prepared in {DEST}')


if __name__ == '__main__':
    main()
