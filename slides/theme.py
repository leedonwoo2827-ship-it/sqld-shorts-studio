"""슬라이드 색상 팔레트 — 과목별/회차별로 다르게.

모든 팔레트는 '어두운 배경 + 밝은 텍스트' 계열이다(하단 흰색 자막이 항상 번인되므로
대비를 보장하기 위함). theme 키로 직접 고르거나, subject/chapter 로 자동 배정한다.
theme 에 hex(예: "#1b3a5b") 를 직접 주면 그 색을 배경 상단으로 쓰는 커스텀 팔레트가 된다.
"""
from __future__ import annotations

# 각 팔레트: (r,g,b) 튜플. bg_top→bg_bottom 세로 그라디언트.
PALETTES: dict[str, dict] = {
    "sqld":    {"bg_top": (33, 49, 131),  "bg_bottom": (12, 20, 58),   "accent": (77, 155, 255),  "answer": (26, 174, 57),  "text": (245, 247, 252), "sub": (183, 196, 224), "card": (255, 255, 255)},
    "default": {"bg_top": (30, 41, 59),   "bg_bottom": (12, 18, 32),   "accent": (96, 165, 250),  "answer": (34, 197, 94),  "text": (244, 246, 250), "sub": (170, 182, 202), "card": (255, 255, 255)},
    "math":    {"bg_top": (6, 78, 59),    "bg_bottom": (3, 34, 27),    "accent": (52, 211, 153),  "answer": (250, 204, 21),  "text": (240, 253, 244), "sub": (167, 208, 190), "card": (255, 255, 255)},
    "eng":     {"bg_top": (91, 33, 60),   "bg_bottom": (43, 12, 30),   "accent": (244, 114, 182), "answer": (250, 204, 21),  "text": (253, 242, 248), "sub": (216, 180, 200), "card": (255, 255, 255)},
    "science": {"bg_top": (76, 29, 149),  "bg_bottom": (35, 14, 78),   "accent": (167, 139, 250), "answer": (52, 211, 153),  "text": (245, 243, 255), "sub": (200, 190, 230), "card": (255, 255, 255)},
    "amber":   {"bg_top": (120, 53, 15),  "bg_bottom": (60, 26, 7),    "accent": (251, 191, 36),  "answer": (52, 211, 153),  "text": (255, 251, 235), "sub": (224, 205, 170), "card": (255, 255, 255)},
    "slate":   {"bg_top": (51, 65, 85),   "bg_bottom": (20, 28, 40),   "accent": (148, 163, 184), "answer": (34, 197, 94),  "text": (248, 250, 252), "sub": (190, 200, 214), "card": (255, 255, 255)},
    "teal":    {"bg_top": (19, 78, 74),   "bg_bottom": (8, 38, 36),    "accent": (45, 212, 191),  "answer": (250, 204, 21),  "text": (240, 253, 250), "sub": (170, 210, 205), "card": (255, 255, 255)},
}

# 회차별 자동 순환에 쓸 순서(테마 미지정 시 chapter 로 색을 돌린다).
_CYCLE = ["sqld", "math", "eng", "science", "amber", "teal", "slate", "default"]

# subject 힌트 → 팔레트
_SUBJECT_HINT = {
    "sqld": "sqld", "sql": "sqld", "데이터": "sqld",
    "수학": "math", "math": "math",
    "영어": "eng", "english": "eng", "eng": "eng",
    "과학": "science", "science": "science", "물리": "science", "화학": "science",
}


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _darken(rgb: tuple[int, int, int], f: float = 0.4) -> tuple[int, int, int]:
    return tuple(max(0, int(c * f)) for c in rgb)  # type: ignore[return-value]


def get_palette(theme: str = "", subject: str = "", chapter: int = 0) -> dict:
    """theme > subject > chapter 순으로 팔레트를 결정한다."""
    t = (theme or "").strip()
    if t.startswith("#"):
        try:
            top = _hex_to_rgb(t)
            base = dict(PALETTES["default"])
            base["bg_top"], base["bg_bottom"] = top, _darken(top, 0.38)
            return base
        except Exception:
            pass
    if t and t.lower() in PALETTES:
        return dict(PALETTES[t.lower()])
    subj = (subject or "").strip().lower()
    for key, pal in _SUBJECT_HINT.items():
        if key in subj:
            return dict(PALETTES[pal])
    if chapter:
        return dict(PALETTES[_CYCLE[(int(chapter) - 1) % len(_CYCLE)]])
    return dict(PALETTES["default"])
