"""공식 출제기준(taxonomy) 로드 — 과목명 → 주요항목 → 세부항목.

`config/*_syllabus.json` 을 읽어 통합 요약노트의 조립 뼈대로 쓴다. lesson 의 `subject`
로 taxonomy 파일을 고르고(없으면 첫 파일), 세부항목의 **평탄화 순서 목록**과 각 세부항목이
어느 과목/주요항목에 속하는지 제공한다. taxonomy 가 없으면 None → 호출부에서 subject 그룹 폴백.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CONFIG = Path(__file__).resolve().parents[1] / "config"


@lru_cache(maxsize=8)
def _all_files() -> tuple[Path, ...]:
    if not _CONFIG.is_dir():
        return ()
    return tuple(sorted(_CONFIG.glob("*_syllabus.json")))


def load_taxonomy(subject: str = "") -> dict | None:
    """subject 로 taxonomy 파일 선택(name/파일명에 부분일치). 없으면 첫 파일. 파일 없으면 None."""
    files = _all_files()
    if not files:
        return None
    subj = (subject or "").strip().lower()
    if subj:
        for p in files:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            name = str(data.get("name") or "").lower()
            if subj in name or name in subj or subj in p.stem.lower():
                return data
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return None


def flat_topics(tax: dict) -> list[tuple[str, str, str]]:
    """(과목명, 주요항목, 세부항목) 을 출제기준 순서대로 평탄화."""
    out: list[tuple[str, str, str]] = []
    for subj in tax.get("subjects") or []:
        sname = subj.get("name") or ""
        for cat in subj.get("categories") or []:
            cname = cat.get("name") or ""
            for topic in cat.get("topics") or []:
                out.append((sname, cname, str(topic)))
    return out


def topic_names(tax: dict) -> list[str]:
    """세부항목 이름만 순서대로."""
    return [t for _s, _c, t in flat_topics(tax)]
