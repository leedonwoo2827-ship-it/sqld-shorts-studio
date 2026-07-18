"""문제집/강의(lesson) JSON → mp4maker 대본(chNN_script.json) 컴파일러.

사용자가 붙여넣는 입력은 순서 있는 `blocks` 배열이다. 각 블록은 `kind`로 구분:
    section  구분 타이틀
    concept  개념카드(제목 + 불릿)
    ox       OX 정리(문항 + O/X)
    table    표/도식(columns + rows)
    problem  문제 + 정답·해설  → 기본 2씬(문제 제시 / 정답·해설)

각 블록을 순서대로 펼쳐 파이프라인이 이미 소비하는 대본 스키마
(scenes[] with {scene, title, narration_text, narration_seconds, image_filename,
video_filename, slide})로 변환한다. slide 키는 슬라이드 렌더러(slides/)만 읽고
TTS(app/synth.py)·mp4maker 는 무시한다.

원본 대본 경로(services/script_gen.py)와 동일한 톤: 순수 함수, 동기.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

CPS = 6.5                    # SuperTonic3 실측(한국어 ~6.5자/초) — script_prompt.CPS 와 동일
MIN_SECONDS = 4              # 씬 최소 길이(초). 너무 짧으면 자막/렌더가 불안정
MAX_NARR_CHARS = 300         # 씬당 낭독 상한(≈46초). 넘으면 해설을 페이지 분할
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"

# 문제집 영상 기본 음성 = 또렷한 강의체(다큐 M5 대신). 파일 `voice`/`speed` 로 덮어씀.
WORKBOOK_DEFAULT_VOICE = "F2"
WORKBOOK_DEFAULT_SPEED = 1.05


def _source_ref(b: dict, default_round: str) -> str:
    """문제 출처 문자열 '제50회 12번'. source 우선, 없으면 round+source_no 조합."""
    s = str(b.get("source") or "").strip()
    if s:
        return s
    rnd = str(b.get("round") or default_round or "").strip()
    no = b.get("source_no")
    if rnd and no is not None:
        return f"{rnd} {no}번"
    if rnd:
        return rnd
    if no is not None:
        return f"{no}번"
    return ""


# ----------------------------- 파싱/정규화 -----------------------------
def parse_lesson_doc(text: str) -> Optional[dict]:
    """코드펜스/앞뒤 잡텍스트를 허용하고 첫 '{' ~ 마지막 '}' 를 파싱.

    blocks[] 또는 problems[] 가 있으면 정규화해서 반환, 아니면 None.
    """
    s = (text or "").strip()
    if not s:
        return None
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        doc = json.loads(s[i:j + 1])
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    doc = normalize_doc(doc)
    return doc if doc.get("blocks") else None


def normalize_doc(doc: dict) -> dict:
    """problems 만 있는 하위호환 입력을 blocks 로 변환. blocks 는 그대로 둔다."""
    doc = dict(doc)
    blocks = doc.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        problems = doc.get("problems")
        if isinstance(problems, list) and problems:
            blocks = [{"kind": "problem", **p} if "kind" not in p else p for p in problems]
        else:
            blocks = []
    # kind 기본값 = problem (number/question 이 있으면 문제로 간주)
    norm = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        b = dict(b)
        if not b.get("kind"):
            b["kind"] = "problem" if (b.get("question") or b.get("choices")) else "section"
        norm.append(b)
    doc["blocks"] = norm
    return doc


# ----------------------------- 유효성 검사 -----------------------------
def validate_lesson(doc: dict) -> list[str]:
    warnings: list[str] = []
    blocks = doc.get("blocks") or []
    if not blocks:
        warnings.append("blocks 가 비어 있습니다.")
    for n, b in enumerate(blocks, 1):
        kind = b.get("kind")
        if kind == "problem":
            if not (b.get("question") or "").strip():
                warnings.append(f"{n}번째 블록(문제): question 이 비어 있음")
            if not str(b.get("answer") or "").strip() and b.get("answer_index") is None:
                warnings.append(f"{n}번째 블록(문제 {b.get('number')}): answer 가 없음")
        elif kind == "concept":
            if not b.get("bullets"):
                warnings.append(f"{n}번째 블록(개념): bullets 가 비어 있음")
        elif kind == "table":
            if not b.get("rows"):
                warnings.append(f"{n}번째 블록(표): rows 가 비어 있음")
        elif kind == "ox":
            if not b.get("items"):
                warnings.append(f"{n}번째 블록(OX): items 가 비어 있음")
    return warnings


# ----------------------------- 낭독 텍스트 -----------------------------
def _answer_number(p: dict) -> Optional[int]:
    """1-based 정답 번호. answer_index 우선, 없으면 answer 문자열에서 유추."""
    ai = p.get("answer_index")
    if isinstance(ai, int):
        return ai + 1
    ans = str(p.get("answer") or "").strip()
    if not ans:
        return None
    if ans[0] in _CIRCLED:
        return _CIRCLED.index(ans[0]) + 1
    m = re.match(r"\s*(\d+)", ans)
    return int(m.group(1)) if m else None


def _problem_question_narration(p: dict) -> str:
    num = p.get("number")
    head = f"{num}번 문제. " if num is not None else ""
    q = (p.get("question") or "").strip()
    typ = p.get("type") or ("ox" if not p.get("choices") and str(p.get("answer")) in ("O", "X", "참", "거짓") else "multiple_choice")
    choices = p.get("choices") or []
    if choices:
        parts = ", ".join(f"{i + 1}번, {str(c).strip()}" for i, c in enumerate(choices))
        return f"{head}{q} 보기. {parts}."
    if typ == "ox":
        return f"{head}{q} 참인지 거짓인지 생각해 보세요."
    return f"{head}{q}"


def _answer_narration(p: dict, explanation: str) -> str:
    n = _answer_number(p)
    choices = p.get("choices") or []
    ans = str(p.get("answer") or "").strip()
    if choices and n is not None:
        lead = f"정답은 {n}번입니다. "
    elif ans:
        lead = f"정답은 {ans} 입니다. "
    else:
        lead = "정답입니다. "
    return (lead + (explanation or "")).strip()


def _secs(text: str) -> int:
    return max(MIN_SECONDS, round(len((text or "").strip()) / CPS))


def _paginate(text: str, max_chars: int = MAX_NARR_CHARS) -> list[str]:
    """긴 해설을 문장 경계로 나눠 각 페이지가 max_chars 이하가 되게 한다."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return [text] if text else [""]
    # 한국어/영어 문장 종결 기준으로 자른다.
    sentences = re.split(r"(?<=[.!?。」”。])\s+|(?<=다\.)\s*", text)
    sentences = [s.strip() for s in sentences if s and s.strip()]
    pages, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) + 1 > max_chars:
            pages.append(cur.strip())
            cur = s
        else:
            cur = (cur + " " + s).strip() if cur else s
    if cur:
        pages.append(cur.strip())
    return pages or [text[:max_chars]]


# ----------------------------- 컴파일 -----------------------------
def _chapter_id(chapter: int) -> str:
    return f"ch{int(chapter):02d}"


def _slug(kind: str, num: Optional[int]) -> str:
    return f"{kind}{num:02d}" if isinstance(num, int) else kind


def lesson_to_script(doc: dict, chapter: Optional[int] = None) -> dict:
    """lesson 문서를 대본(scenes[]) dict 로 변환. 씬 인덱스는 전체 순차(1..)."""
    doc = normalize_doc(doc)
    chap = int(chapter if chapter is not None else (doc.get("chapter") or 1))
    cid = _chapter_id(chap)
    theme = doc.get("theme") or ""
    subject = doc.get("subject") or ""
    spp = int(doc.get("scenes_per_problem") or 2)
    # include_lecture=False 면 문제(problem) 블록만 영상 씬으로 만든다.
    # (section/concept/ox/table 강의 블록은 JSON 에 남지만 렌더/영상에는 안 들어감)
    include_lecture = bool(doc.get("include_lecture", True))
    default_round = str(doc.get("round") or "").strip()
    voice = (doc.get("voice") or WORKBOOK_DEFAULT_VOICE)
    speed = doc.get("speed", WORKBOOK_DEFAULT_SPEED)

    scenes: list[dict] = []

    def add_scene(title: str, narration: str, slug: str, slide: dict) -> None:
        idx = len(scenes) + 1
        narration = (narration or "").strip() or title or "…"
        scenes.append({
            "scene": idx,
            "title": title,
            "narration_text": narration,
            "narration_seconds": _secs(narration),
            "image_filename": f"{cid}_{idx:02d}_{slug}.png",
            "video_filename": f"{cid}_{idx:02d}.mp4",
            "slide": slide,
        })

    for b in doc.get("blocks") or []:
        kind = b.get("kind")
        if not include_lecture and kind != "problem":
            continue
        if kind == "section":
            add_scene(
                b.get("title") or "섹션",
                b.get("narration") or b.get("title") or "",
                "section",
                {"kind": "section", "title": b.get("title") or "",
                 "subtitle": b.get("subtitle") or ""},
            )
        elif kind == "concept":
            heading = b.get("heading") or b.get("title") or "개념"
            bullets = [str(x) for x in (b.get("bullets") or [])]
            add_scene(
                heading, b.get("narration") or heading, "concept",
                {"kind": "concept", "heading": heading, "bullets": bullets},
            )
        elif kind == "ox":
            heading = b.get("heading") or "OX"
            items = b.get("items") or []
            add_scene(
                heading, b.get("narration") or heading, "ox",
                {"kind": "ox", "heading": heading, "items": items},
            )
        elif kind == "table":
            heading = b.get("heading") or "정리"
            add_scene(
                heading, b.get("narration") or heading, "table",
                {"kind": "table", "heading": heading,
                 "columns": b.get("columns") or [], "rows": b.get("rows") or []},
            )
        elif kind == "problem":
            num = b.get("number")
            question = (b.get("question") or "").strip()
            choices = [str(c) for c in (b.get("choices") or [])]
            passage = (b.get("passage") or "").strip()
            meta = {k: b.get(k) for k in ("difficulty", "points", "type") if b.get(k) is not None}
            src = _source_ref(b, default_round)
            # 씬 A — 문제 제시
            q_narr = (b.get("narration_question") or "").strip() or _problem_question_narration(b)
            add_scene(
                f"문제 {num}" if num is not None else "문제",
                q_narr, _slug("q", num),
                {"kind": "problem", "number": num, "question": question,
                 "choices": choices, "passage": passage, "meta": meta, "source": src},
            )
            if spp <= 1:
                continue
            # 씬 B — 정답·해설 (길면 페이지 분할)
            explanation = (b.get("explanation") or "").strip()
            custom = (b.get("narration_answer") or "").strip()
            pages = _paginate(explanation) if not custom else [explanation]
            n_pages = len(pages)
            for pi, page in enumerate(pages):
                if pi == 0:
                    narr = custom or _answer_narration(b, page)
                else:
                    narr = page
                title = f"정답 및 해설 {num}" if num is not None else "정답 및 해설"
                if n_pages > 1:
                    title += f" ({pi + 1}/{n_pages})"
                add_scene(
                    title, narr, _slug("a", num),
                    {"kind": "answer", "number": num, "question": question,
                     "choices": choices, "answer": b.get("answer"),
                     "answer_index": b.get("answer_index"),
                     "explanation": page, "meta": meta, "source": src,
                     "page": pi + 1, "total_pages": n_pages,
                     "show_choices": pi == 0},
                )

    return {
        "version": "1.0",
        "kind": "lesson",
        "chapter": chap,
        "title": doc.get("title") or "",
        "subject": subject,
        "theme": theme,
        "round": default_round,
        "voice": voice,
        "speed": speed,
        "aspect_ratio": "16:9",
        "scenes": scenes,
    }


def problem_count(doc: dict) -> int:
    return sum(1 for b in (normalize_doc(doc).get("blocks") or []) if b.get("kind") == "problem")


def block_count(doc: dict) -> int:
    return len(normalize_doc(doc).get("blocks") or [])
