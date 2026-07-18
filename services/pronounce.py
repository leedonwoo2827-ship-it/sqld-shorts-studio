"""AI 발음 변환 — 숫자·영어를 소리 나는 대로 한글로 바꾼 '읽기용' 텍스트 생성.

TTS 가 영어를 글자 단위로 읽는(CREATE→씨알이에이티이) 문제를 피하려고, 낭독 텍스트를
LLM 으로 한 줄 한글 읽기(크리에이트, 얼터…)로 바꾼다. 세부 예외는 발음사전으로 보완.
"""
from __future__ import annotations

from typing import Optional

from . import script_prompt
from .script_gen import _llm


def to_reading(text: str, model: Optional[str] = None) -> str:
    """낭독 텍스트 → 한 줄 한글 읽기. 실패/빈값이면 원문 반환."""
    t = (text or "").strip()
    if not t:
        return ""
    try:
        out = (_llm(script_prompt.pronounce_prompt(t), model) or "").strip()
    except Exception:
        return t
    if not out:
        return t
    # 여러 줄로 오면 첫 비어있지 않은 줄만
    for line in out.splitlines():
        if line.strip():
            return line.strip()
    return t
