# 실제 Playground 덱과 공개 평가 상대

조사일: 2026년 10월 28일. 이 문서는 관찰된 공개 경기와 공개 모델의 출처를 기록한다. 아래 덱은 리더보드 상위권 경기에서 관찰된 사례이며, 전체 대회에서의 점유율이나 대표성을 통계적으로 추정한 결과는 아니다. 순위와 점수는 계속 바뀐다.

## 공개 경기에서 확인한 덱

Kaggle 공개 에피소드의 초기 덱 선택을 사용했다. 제출 ID와 에피소드 ID, 좌석 및 카드 구성 해시는 `configs/real_benchmark_sources.json`에 고정되어 있다. 전체 카드 목록은 대회 자료이므로 `data/real-benchmark/`에만 저장하며 Git에 추가하지 않는다. 학습·검증·평가를 카드 구성 기준으로 분리하지만, 같은 전략 계열의 서로 다른 목록이 여러 집합에 있을 수 있다.

| 구분 | 에피소드와 좌석 | 관찰된 주요 카드 | 당시 제출 ID |
| --- | --- | --- | --- |
| 학습 | 125524767 / 0 | Dragapult ex, Blaziken ex | 57666077 |
| 학습 | 125524580 / 0 | Metagross, Mega Excadrill ex | 57563897 |
| 학습 | 125524849 / 0 | Mega Kangaskhan ex, Crustle | 57235766 |
| 검증 | 125524767 / 1 | Mega Kangaskhan ex, Teal Mask Ogerpon ex | 57697887 |
| 검증 | 125523728 / 1 | Mega Lopunny ex, Dudunsparce | 57624561 |
| 평가 | 125523652 / 1 | Dragapult ex | 57699225 |
| 평가 | 125525059 / 1 | Banette, Dhelmise | 57653237 |

공개 경기는 [Playground 리더보드](https://www.kaggle.com/competitions/the-pokemon-company-ptcg-ai-battle-challenge-playground/leaderboard)와 [시뮬레이션 대회 API 문서](https://github.com/Kaggle/kaggle-cli/blob/main/docs/simulation_competitions.md)에서 확인할 수 있다. 관찰된 덱 자체가 상대의 플레이 정책을 제공하지는 않는다.

## 공개 학습 모델 상대

[PTCG Playground public baseline](https://www.kaggle.com/datasets/cristobaltudela/ptcg-playground-public-baseline) 버전 1은 Dipam Chakraborty의 기존 Transformer 모델을 Cristobal Tudela가 Playground 카드 풀에 맞게 이식한 공개 에이전트다. 제공된 `LICENSE`는 원본 코드·가중치의 MIT 라이선스를 명시한다. 이 벤치마크는 해당 원본과 제공된 Hydrapple ex / Meganium / Teal Mask Ogerpon ex 덱을 함께 사용하며 임의의 덱으로 교체하지 않는다. 라이브 리더보드 상위 팀의 **현재 제출물과 동일한 에이전트라고 주장하지 않는다.**

[공개 BO3 비교 노트북](https://www.kaggle.com/code/dariushafshar/ptcg-bo3-gauntlet-your-agent-vs-6-public-bots)은 이 이식본의 좌석과 선공 처리에 문제 가능성을 보고한다. 여기서는 원본을 수정하지 않았으며 좌석·선공별 결과를 따로 보고한다. 이 레퍼런스는 Kaggle 서버의 메모리·시간 제한을 완전히 재현하지 않는 로컬 단일 게임 상대다.

로컬 점검에서 이 공개 모델을 샘플 덱 기반 단순 상대와 각각 10게임씩 대전시켜 `first`에 6승 4패, 무작위 정책에 10승을 기록했고 매 게임 모델 추론이 실제 실행되는 것을 확인했다. 표본이 작고 덱이 다르므로 이 결과는 대회 실력이나 통계적으로 확정된 우위를 의미하지 않는다.

## 실행

```sh
sh scripts/setup.sh
.venv-kaggle/bin/python scripts/prepare_real_benchmark.py
.venv-kaggle/bin/python scripts/run_comparison_suite.py --config configs/real_comparison.json --output runs/real-comparison
```

준비 스크립트는 Kaggle API 인증과 대회 데이터 접근이 필요하다. 공개 경기 5개 및 고정된 버전의 공개 모델을 내려받고, 덱 해시·모델 파일 해시와 네이티브 엔진의 대전 시작 검사를 확인한다. 기존 출력 디렉터리는 덮어쓰지 않는다. 공개 모델과 공식 카드 자료는 `data/real-benchmark/`에만 보관된다.

상대 모델은 프로젝트 정책과 충돌하지 않도록 별도 Python 프로세스에서 실행하며 API 토큰 환경 변수를 상속하지 않는다. 이는 **보안 샌드박스가 아니다**. 신뢰할 수 있는 코드와 가중치만 사용해야 한다. 외부 에이전트 예외로 인한 무작위 대체를 감지하면 평가를 중단한다. 원본 모델 추론 횟수는 매 경기 `opponent_model_forwards`에 기록된다.

`configs/real_comparison.json`은 학습 3덱, 검증 2덱, 평가 2덱과 `first`, `last`, 공개 모델 상대를 지정한다. 공개 모델은 자기 덱만 사용한다. 결과는 상대별 성능과 상대별 가중치를 동일하게 둔 평균을 함께 기록한다. 기본 게임 수는 실행 점검용이며, 엔진 난수 통제 불가와 표본 수에 주의해야 한다. 실제 평가 전 덱·상대·시드·예산을 확정하고 표본 수와 실행 시간을 늘려야 한다.
