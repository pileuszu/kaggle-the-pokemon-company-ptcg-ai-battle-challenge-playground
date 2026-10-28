#!/usr/bin/env python3
"""Download the official competition files without overwriting local data."""
from pathlib import Path
import shutil
import sys
import tempfile

import kagglehub

COMPETITION = "the-pokemon-company-ptcg-ai-battle-challenge-playground"
ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "data" / "playground"
REQUIRED = (
    "ptcg_engine_playground",
    "sample_submission",
    "Card_ID_List_EN.pdf",
    "Card_ID_List_JP.pdf",
    "EN_Card_Data_R2_full.csv",
    "JP_Card_Data_R2_full.csv",
)


def main():
    if DESTINATION.exists():
        missing = [name for name in REQUIRED if not (DESTINATION / name).exists()]
        if missing:
            raise RuntimeError(f"Existing {DESTINATION} is incomplete; preserve or move it before retrying: {missing}")
        print(f"이미 설치된 자료를 사용합니다: {DESTINATION}")
        return

    try:
        source = Path(kagglehub.competition_download(COMPETITION))
    except Exception as exc:
        raise RuntimeError(
            "Kaggle 다운로드 실패. API 인증 및 대회 데이터 접근 권한을 확인하세요: "
            "https://www.kaggle.com/docs/api#authentication"
        ) from exc
    missing = [name for name in REQUIRED if not (source / name).exists()]
    if missing:
        raise RuntimeError(f"다운로드에 필요한 항목이 없습니다: {missing}")
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".playground-", dir=DESTINATION.parent) as tmp:
        staging = Path(tmp) / "files"
        shutil.copytree(source, staging)
        staging.rename(DESTINATION)
    print(f"대회 자료 설치 완료: {DESTINATION}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"오류: {error}", file=sys.stderr)
        sys.exit(1)
