"""요약노트 생성 — 번들의 문제·정답·해설을 모아 LLM 으로 학습 요약노트(Markdown) 작성.

services/script_gen.py 의 generate_youtube_meta 패턴을 그대로 미러한다(동기, 활성
LLM 공급자 사용). 반환 text 는 라우트에서 draft/chNN_summary.md 로 저장된다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from .llm import backend
from . import script_prompt


def _llm(prompt: str, model: Optional[str]) -> str:
    client = backend.active_client()
    mdl = (model or "").strip() or (backend.get_model() or None)
    return client.chat(mdl, [{"role": "user", "content": prompt}], max_tokens=8000).text


def _collect_items(data: dict) -> list[dict]:
    """대본 scenes 의 slide(kind=answer/problem)에서 문제 항목을 모은다."""
    items: dict[Any, dict] = {}
    order: list[Any] = []
    for sc in data.get("scenes") or []:
        slide = sc.get("slide") or {}
        kind = slide.get("kind")
        if kind not in ("problem", "answer"):
            continue
        num = slide.get("number")
        key = num if num is not None else f"_{len(order)}"
        if key not in items:
            items[key] = {"number": num, "question": "", "answer": "", "explanation": "", "source": ""}
            order.append(key)
        it = items[key]
        if slide.get("source") and not it["source"]:
            it["source"] = str(slide.get("source"))
        if slide.get("question"):
            it["question"] = slide.get("question")
        if kind == "answer":
            if slide.get("answer") is not None and not it["answer"]:
                it["answer"] = str(slide.get("answer"))
            exp = (slide.get("explanation") or "").strip()
            if exp:
                it["explanation"] = (it["explanation"] + " " + exp).strip()
    return [items[k] for k in order]


def generate_summary_note(
    bundle_dir,
    *,
    model: Optional[str] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> dict:
    bundle = Path(bundle_dir)
    files = sorted((bundle / "script").glob("*_script.json"))
    if not files:
        raise FileNotFoundError("대본 JSON 이 없습니다. 먼저 레슨/문제집을 저장하세요.")
    data = json.loads(files[0].read_text(encoding="utf-8"))
    title = data.get("title") or ""
    items = _collect_items(data)
    if not items:
        raise ValueError("문제(problem/answer) 항목이 없어 요약노트를 만들 수 없습니다.")

    lines: list[str] = []
    for it in items:
        num = it.get("number")
        head = f"[문제 {num}]" if num is not None else "[문제]"
        q = (it.get("question") or "").strip()
        a = (it.get("answer") or "").strip()
        e = (it.get("explanation") or "").strip()
        lines.append(f"{head} {q}\n- 정답: {a}\n- 해설: {e}")
    body = "\n\n".join(lines)[:6000]

    if on_progress:
        try:
            on_progress(f"요약노트 생성 중… LLM({backend.get_provider()}) 호출")
        except Exception:
            pass
    text = _llm(script_prompt.summary_note_prompt(title, body), model)
    return {"ok": True, "title": title, "text": (text or "").strip(),
            "problem_count": len(items)}
