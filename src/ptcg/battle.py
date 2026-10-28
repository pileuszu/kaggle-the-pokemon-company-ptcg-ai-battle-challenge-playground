"""Turn-by-turn single-game adapter around the official sample engine.

The native library stores the current battle globally. Only one game may run
per process; parallel games must use separate processes.
"""
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / 'data/playground/sample_submission/sample_submission/sample_submission'
_active = False


def sample_deck():
    path = SAMPLE / 'deck.csv'
    if not path.is_file():
        raise FileNotFoundError('대회 자료가 없습니다. sh scripts/setup.sh를 먼저 실행하세요.')
    deck = [int(line) for line in path.read_text().splitlines() if line.strip()]
    if len(deck) != 60:
        raise ValueError('덱에는 카드 ID 60개가 필요합니다.')
    return deck


def validate_selection(selection, action):
    if not isinstance(action, list) or any(type(i) is not int for i in action):
        raise ValueError('행동은 정수 인덱스의 리스트여야 합니다.')
    if len(action) != len(set(action)):
        raise ValueError('선택 인덱스는 중복될 수 없습니다.')
    if not selection['minCount'] <= len(action) <= selection['maxCount']:
        raise ValueError('선택 개수가 허용 범위를 벗어났습니다.')
    if any(i < 0 or i >= len(selection['option']) for i in action):
        raise ValueError('선택 인덱스가 범위를 벗어났습니다.')


class SingleGame:
    def __init__(self, deck0, deck1, reverse_player=False):
        global _active
        if _active:
            raise RuntimeError('네이티브 엔진은 프로세스당 한 게임만 지원합니다.')
        if not (SAMPLE / 'cg').is_dir():
            raise FileNotFoundError('대회 엔진이 없습니다. sh scripts/setup.sh를 실행하세요.')
        sys.path.insert(0, str(SAMPLE))
        from cg import game
        self._game = game
        self._closed = True
        obs, start = game.battle_start(list(deck0), list(deck1), reverse_player)
        if obs is None:
            raise ValueError(f'대전 시작 오류: player={start.errorPlayer}, type={start.errorType}')
        self._closed = False
        _active = True
        self._observation = obs

    @property
    def result(self):
        return self._observation['current']['result']

    @property
    def player(self):
        if self.result >= 0:
            raise RuntimeError('종료된 게임에는 현재 플레이어가 없습니다.')
        return self._observation['current']['yourIndex']

    def observation(self):
        if self._closed:
            raise RuntimeError('종료된 엔진입니다.')
        # Opaque simulator state is excluded from policy input: it is only for
        # engine search and has not been audited for hidden information.
        obs = deepcopy(self._observation)
        obs.pop('search_begin_input', None)
        if self.result < 0:
            opponent = 1 - self.player
            if obs['current']['players'][opponent].get('hand') is not None:
                raise RuntimeError('상대 손패가 관찰에 노출되어 학습을 중단합니다.')
            if any(card is not None for card in obs['current']['players'][opponent].get('prize', [])):
                raise RuntimeError('상대 프라이즈 카드가 관찰에 노출되어 학습을 중단합니다.')
        return obs

    def step(self, action):
        if self._closed or self.result >= 0:
            raise RuntimeError('이미 종료된 게임입니다.')
        validate_selection(self._observation['select'], action)
        self._observation = self._game.battle_select(action)
        return self.observation()

    def close(self):
        global _active
        if not self._closed:
            self._game.battle_finish()
            self._closed = True
            _active = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
