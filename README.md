# Pokémon TCG AI Battle Challenge Playground

## 시작하기

Python 3.11 이상과 인터넷 연결이 필요하다. 사용자가 먼저 다음을 준비한다.

1. [Kaggle 대회 페이지](https://www.kaggle.com/competitions/the-pokemon-company-ptcg-ai-battle-challenge-playground)에서 참가 및 데이터 접근 권한을 확인한다.
2. [Kaggle API 토큰 설정](https://www.kaggle.com/settings/api)에서 새 API 토큰을 발급하고, [공식 인증 안내](https://www.kaggle.com/docs/api#authentication)에 따라 로컬 환경에 설정한다. 토큰은 비밀로 유지하고 저장소에 추가하지 않는다.
3. 저장소에서 설치 스크립트를 실행한다.

```sh
sh scripts/setup.sh
```

스크립트는 `.venv-kaggle` 가상환경에 `kagglehub`를 설치하고, 카드 데이터·샘플 제출물·엔진 파일을 `data/playground/`에 내려받는다. 이 자료와 가상환경은 Git에서 제외된다. 기존 자료는 덮어쓰지 않는다. 기존 폴더가 불완전하면 보관하거나 옮긴 후 다시 실행한다.

기본 Python 명령은 `python3.11`이다. 다른 Python 3.11 이상 실행 파일을 사용하려면 `PYTHON=python3.12 sh scripts/setup.sh`처럼 지정한다. 기존 `.venv-kaggle`이 있으면 그 환경을 재사용한다.

Kaggle의 최신 대회 자료를 받으므로 다운로드 시점마다 내용이 달라질 수 있다.

## 로컬 샘플 대전

자료 설정 후 아래 명령으로 제공된 무작위 샘플 에이전트와 샘플 덱을 사용해 한 게임을 실행할 수 있다.

```sh
.venv-kaggle/bin/python scripts/sample_battle.py
```

제공된 `cg` 네이티브 엔진을 직접 호출하며 추가 패키지는 필요하지 않다. 결과 코드 `0`과 `1`은 각 플레이어의 승리, `2`는 무승부를 뜻한다. `--seed`는 샘플 에이전트의 무작위 선택에만 적용되므로 엔진의 무작위 결과까지 재현하지는 않는다. 이 명령은 단일 게임을 확인하며 Kaggle의 BO3 평가와 프로세스 격리·시간 제한을 재현하지 않는다.

## BO3 경기 간 메모리 테스트

로컬 공식 BO3 래퍼를 사용하는 테스트에는 별도 의존성이 필요하다. 아래 명령은 CABT 테스트에 필요한 최소 패키지만 설치한다. 다른 Kaggle 환경을 불러올 때 누락된 선택적 의존성 경고가 나올 수 있다.

```sh
.venv-kaggle/bin/python -m pip install 'jsonschema>=4,<5'
.venv-kaggle/bin/python -m pip install --no-deps 'kaggle-environments==1.33.2'
.venv-kaggle/bin/python scripts/bo3_memory_test.py
```

두 독립 에이전트 객체가 관찰한 상대의 공개 카드 ID와 `playerIndex`가 상대인 로그 이벤트를 자체 메모리에 저장한다. 각 게임 전환 시 유지된 기록 수와 새 관찰의 로그 수, 현재 점수를 표시한다. 이벤트 수는 관찰 때마다 반복 수집될 수 있으므로 고유 행동 수가 아니다. 같은 내용의 로그가 다른 게임에 우연히 다시 나타날 수 있어 `matching_prior_log_entries`는 이전 로그가 자동으로 전달됐다는 증거가 아니다. 무작위 선택의 `--seed`는 네이티브 엔진의 난수까지 고정하지 않는다.

이 테스트는 로컬의 `kaggle-environments` 1.33.2에서 같은 Python 프로세스 안에 객체를 유지한다. 실제 Kaggle 제출 환경의 프로세스 수명, 게임 사이의 메모리 지속 여부나 로그 전달을 보장하지 않는다.
