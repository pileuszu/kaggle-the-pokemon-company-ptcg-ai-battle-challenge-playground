#!/usr/bin/env python3
"""Download pinned public replay decks and the MIT public baseline locally."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

import kagglehub
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.competitions.types.competition_api_service import ApiGetEpisodeReplayRequest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ptcg.battle import SingleGame, sample_deck

MANIFEST = ROOT / 'configs/real_benchmark_sources.json'
DEST = ROOT / 'data/real-benchmark'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if DEST.exists():
        raise SystemExit(f'{DEST}가 이미 있습니다. 보관하거나 이동한 후 다시 실행하세요.')
    manifest = json.loads(MANIFEST.read_text())
    dataset = Path(kagglehub.dataset_download(manifest['baseline_dataset']))
    expected_files = set(manifest['baseline_checksums'])
    actual_files = {p.relative_to(dataset).as_posix() for p in dataset.rglob('*') if p.is_file()}
    if actual_files != expected_files:
        raise ValueError('Baseline file list differs from the pinned manifest')
    for filename, expected in manifest['baseline_checksums'].items():
        if digest((dataset / filename).read_bytes()) != expected:
            raise ValueError(f'baseline checksum mismatch: {filename}')
    api = KaggleApi()
    api.authenticate()
    client = api.build_kaggle_client().competitions.competition_api_client
    replays = {}
    decks = {}
    for item in manifest['decks']:
        eid = item['episode']
        if eid not in replays:
            request = ApiGetEpisodeReplayRequest()
            request.episode_id = eid
            response = client.get_episode_replay(request)
            replays[eid] = response.json()
        replay = replays[eid]
        cards = replay['steps'][1][item['seat']]['action']
        if not isinstance(cards, list) or len(cards) != 60 or any(type(x) is not int for x in cards):
            raise ValueError(f'episode {eid}: invalid initial deck')
        actual = digest(','.join(map(str, sorted(cards))).encode())
        if actual != item['sha256']:
            raise ValueError(f'episode {eid}: deck hash mismatch')
        with SingleGame(cards, sample_deck()):
            pass
        decks[item['name']] = cards
    DEST.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.real-benchmark-', dir=DEST.parent) as temp:
        stage = Path(temp) / 'files'
        (stage / 'decks').mkdir(parents=True)
        for name, cards in decks.items():
            (stage / 'decks' / f'{name}.csv').write_text(''.join(f'{x}\n' for x in cards))
        shutil.copytree(dataset, stage / 'opponent')
        # Competition card metadata stays in ignored local data only.
        shutil.copy2(ROOT / 'data/playground/EN_Card_Data_R2_full.csv', stage / 'opponent/EN_Card_Data.csv')
        (stage / 'sources.json').write_text(json.dumps(manifest, indent=2) + '\n')
        stage.rename(DEST)
    print(f'{len(decks)} verified replay decks and pinned baseline prepared at {DEST}')


if __name__ == '__main__':
    main()
