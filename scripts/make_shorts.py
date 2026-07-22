"""SQLD 문제 쇼츠(9:16) 생성 CLI. 쇼츠는 '한 문제 = 한 JSON = 한 영상'.

기본(무음·자리표시자 아바타)으로 지금 바로 동작한다.

  # 문제 하나(파일 하나) → 쇼츠 하나
  python scripts/make_shorts.py samples/sqld_shorts/sqld_02.json -o out/shorts

  # 폴더 안의 모든 문제 → 쇼츠 여러 개 일괄
  python scripts/make_shorts.py samples/sqld_shorts -o out/shorts

옵션:
    --avatar face.png  좌측 아바타 정지 이미지(투명 PNG 권장) baked

TTS/립싱크 클립 연동은 docs/SHORTS_AVATAR.md 참고(mp4maker.shorts.build_short 의
audio_*/avatar_clip_* 인자로 주입).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mp4maker.shorts import build_from_lesson  # noqa: E402


def _lesson_files(target: Path) -> list[Path]:
    """파일이면 그 하나, 폴더면 안의 *.json 전부(정렬)."""
    if target.is_dir():
        return sorted(target.glob("*.json"))
    return [target]


def main() -> int:
    ap = argparse.ArgumentParser(description="SQLD 9:16 문제 쇼츠 생성기 (한 문제=한 영상)")
    ap.add_argument("lesson", help="문제 JSON 파일 또는 폴더 (예: samples/sqld_shorts)")
    ap.add_argument("-o", "--out", default="out/shorts", help="출력 폴더")
    ap.add_argument("--avatar", default=None, help="좌측 아바타 정지 이미지(투명 PNG)")
    args = ap.parse_args()

    files = _lesson_files(Path(args.lesson))
    if not files:
        print(f"[오류] JSON 을 찾지 못했습니다: {args.lesson}")
        return 1

    made: list[Path] = []
    for f in files:
        made += build_from_lesson(f, args.out, avatar_img=args.avatar)

    print(f"\n완료: {len(made)}개 쇼츠 생성 -> {Path(args.out).resolve()}")
    for p in made:
        print("  -", p.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
