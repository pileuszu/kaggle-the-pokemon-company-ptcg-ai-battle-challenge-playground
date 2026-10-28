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

## 단일 게임 환경 검증과 처리량 측정

```sh
.venv-kaggle/bin/python -m unittest discover -s tests -v
.venv-kaggle/bin/python scripts/benchmark_single_game.py --games 100
```

`src/ptcg/battle.py`는 제공된 네이티브 엔진을 단일 게임으로 감싸고 선택 개수·중복·인덱스 범위를 검사한다. 정책 관찰값에서 불투명한 검색 상태를 제거하고 상대 손패와 프라이즈가 숨겨져 있는지 확인한다. 게임이 끝나거나 오류가 나더라도 컨텍스트 관리자가 엔진 자원을 반환한다. 네이티브 엔진은 전역 상태를 사용하므로 한 프로세스에서 동시에 한 게임만 실행할 수 있다.

처리량 명령은 무작위 선택으로 단일 게임을 수행한다. 결과에는 시뮬레이터와 Python 처리 시간이 포함되지만 모델 추론·학습이나 BO3는 포함되지 않는다. `--seed`는 선택 정책만 제어한다. 이 어댑터는 같은 프로세스에서 실행하며 보안상 에이전트 격리를 제공하지 않는다. PPO 학습과 전체 정보 누출 검증은 아직 구현하지 않았다.

## 단일 게임 PPO 비교 실험

`sh scripts/setup.sh`로 설치한 뒤 다음 명령은 공유 모델과 독립 A·B 모델을 각각 같은 게임 수로 학습하고, 검증·평가 게임을 실행한다.

```sh
.venv-kaggle/bin/python scripts/compare_ppo.py --games 12 --eval-games 8 --validation-games 8 --output runs/ppo-example
```

출력 폴더에는 모델 가중치와 `report.json`이 저장된다. 기존 결과를 덮어쓰지 않으므로 매 실험마다 다른 출력 폴더를 지정한다. `--rollout-games`, `--epochs`, `--batch-size`, `--seed`로 수집·갱신 설정을 변경한다. 동일 시간 예산 실험은 두 방식 각각에 같은 시간 상한(초)을 적용하는 `--time-budget`을 사용하며, `--games`는 최대 게임 수다. 시간은 완료된 게임과 PPO 업데이트를 기준으로 검사하므로 지정 시간을 초과할 수 있고, GPU/CPU 연산량이 같다는 뜻은 아니다.

실험은 현재 정책 대전, 이전 체크포인트 대전, 무작위 고정 상대를 순환하며 양쪽을 동일한 비율로 사용한다. 평가에는 학습에 쓰지 않는 첫 선택 고정 상대와 공식 샘플 덱을 사용하고, A·B는 최종 평가와 별도인 검증 게임으로 선택한다. 결과의 Wilson 구간은 무승부를 비승리로 포함한 승리 비율에 대한 구간이다. Python과 PyTorch 난수는 지정하지만 엔진의 난수는 고정하지 못한다.

초기 정책은 제한된 공개 상태·선택지 수치 특징을 사용하는 작은 신경망이며, 강력한 모델이나 포괄적인 정보 누출 검증으로 간주할 수 없다. 평가 상대와 덱이 각각 하나이므로 본격적인 전략 우열 판단에는 다양한 미사용 상대·덱, 여러 학습 시드, 경기 수, 선공별 결과와 충분한 시간 예산 검증이 더 필요하다. 현재 스크립트는 로컬 학습 실험용이며 Kaggle 제출 패키징·BO3 학습은 포함하지 않는다.
