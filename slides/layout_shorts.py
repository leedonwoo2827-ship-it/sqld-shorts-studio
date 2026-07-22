"""세로(9:16) 쇼츠 레이아웃 — SQLD 문제 쇼츠용.

layout.py(가로 1920x1080)와 동일한 (base, elements) 계약을 따르되:
    - 캔버스: 1080x1920 (YouTube Shorts 9:16)
    - 좌측에 아바타 컬럼(사람 얼굴/상반신)을 예약
    - 우측에 콘텐츠(문제·보기 / 해설·정답)
    - 정답 공개 슬라이드는 요청대로 **해설을 상단, 정답을 최하단**에 배치

layout.py 의 저수준 헬퍼(wrap_text/fit_text/draw_lines/_line_h/_measure/_circled)
는 캔버스 크기에 의존하지 않으므로 그대로 재사용한다.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .fonts import load_font
from .layout import (  # 크기 비의존 헬퍼 재사용
    _circled,
    _line_h,
    _measure,
    draw_lines,
    fit_text,
    wrap_text,
)

# ----------------------------- 세로 캔버스 지오메트리 -----------------------------
W, H = 1080, 1920
PAD = 56

# 좌측 아바타 컬럼
AV_W = 420                       # 아바타 컬럼 폭
AV_GAP = 28                      # 아바타↔콘텐츠 간격

# 우측 콘텐츠 컬럼
CX0 = AV_W + AV_GAP              # 콘텐츠 좌측 x
CW = W - CX0 - PAD               # 콘텐츠 폭 (≈ 576)

TOP_Y = 70
SAFE_BOTTOM = H - 96            # 이 아래는 자막/여백 안전영역

APPEAR_START = 0.4
APPEAR_STEP = 0.5


# ----------------------------- 저수준(세로 전용) -----------------------------
def _blank() -> Image.Image:
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _gradient(pal: dict) -> Image.Image:
    top, bot = pal["bg_top"], pal["bg_bottom"]
    base = Image.new("RGBA", (W, H))
    px = base.load()
    for y in range(H):
        t = y / (H - 1)
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        row = (r, g, b, 255)
        for x in range(W):
            px[x, y] = row
    return base


def _appear(i: int) -> float:
    return APPEAR_START + i * APPEAR_STEP


def _chip(base: Image.Image, text: str, pal: dict, x: int, y: int,
          bg=None, fg=(255, 255, 255)) -> tuple[int, int]:
    """라운드 칩. 반환 = (칩 오른쪽 x, 칩 아래 y)."""
    d = ImageDraw.Draw(base)
    font = load_font(34, bold=True)
    tw = int(_measure(text, font))
    pad = 22
    bg = bg or pal["accent"]
    right = x + tw + pad * 2
    d.rounded_rectangle((x, y, right, y + 60), radius=16,
                        fill=(bg + (255,)) if len(bg) == 3 else bg)
    d.text((x + pad, y + 11), text, font=font, fill=fg)
    return right, y + 60


# ----------------------------- 아바타 컬럼 -----------------------------
def _paste_avatar(base: Image.Image, pal: dict, avatar_path: str | None,
                  live: bool = False) -> None:
    """좌측 컬럼에 아바타를 하단 정렬로 합성한다.

    live=True  : 패널만 그린다(그 위에 '말하는 영상'을 ffmpeg 로 오버레이할 자리).
    avatar_path: RGBA 이미지를 컬럼 폭에 맞춰 스케일 후 하단 기준으로 붙인다(정지 아바타).
    둘 다 아니면 자리표시자(실루엣 + '아바타' 라벨)를 그린다.
    """
    # 좌측 컬럼 은은한 패널(콘텐츠와 시각 분리) — 반투명은 별도 레이어로 합성해야
    # convert("RGB") 시 알파가 유지된다(base 에 직접 그리면 알파가 소실됨).
    panel = _blank()
    pd = ImageDraw.Draw(panel)
    panel_top = int(H * 0.30)
    pd.rounded_rectangle((PAD - 20, panel_top, AV_W, H), radius=40,
                         fill=(255, 255, 255, 14))
    base.alpha_composite(panel)

    if live:                       # 영상 오버레이 자리 — 패널만 남기고 종료
        return

    if avatar_path and Path(avatar_path).is_file():
        try:
            av = Image.open(avatar_path).convert("RGBA")
            col_w = AV_W + 8
            scale = col_w / av.width
            new_h = int(av.height * scale)
            av = av.resize((col_w, new_h), Image.LANCZOS)
            # 하단 정렬(상반신/얼굴이 아래쪽에 오도록)
            y = H - new_h
            base.alpha_composite(av, (0, max(0, y)))
            return
        except Exception:
            pass

    # ---- 자리표시자 실루엣 (반투명 → 레이어로 합성) ----
    ph = _blank()
    pd2 = ImageDraw.Draw(ph)
    cx = AV_W // 2
    accent = pal["accent"]
    body_top = int(H * 0.72)
    pd2.rounded_rectangle((cx - 190, body_top, cx + 190, H), radius=120,
                          fill=accent + (110,))
    hr = 130
    hy = body_top - hr - 10
    pd2.ellipse((cx - hr, hy - hr, cx + hr, hy + hr), fill=accent + (150,))
    lab = load_font(40, bold=True)
    t = "아바타"
    tw = int(_measure(t, lab))
    pd2.text((cx - tw // 2, hy - 26), t, font=lab, fill=(255, 255, 255, 255))
    hint = load_font(24, bold=False)
    h2 = "(ComfyUI 생성 + 립싱크)"
    hw = int(_measure(h2, hint))
    pd2.text((cx - hw // 2, hy + 30), h2, font=hint, fill=(255, 255, 255, 220))
    base.alpha_composite(ph)


# ----------------------------- 헤더 -----------------------------
def _header(base: Image.Image, pal: dict, subject: str, tag: str = "") -> None:
    d = ImageDraw.Draw(base)
    f = load_font(40, bold=True)
    label = subject or "SQLD"
    d.text((PAD, TOP_Y), label, font=f, fill=pal["text"] + (255,))
    lw = int(_measure(label, f))
    # accent 밑줄
    d.rounded_rectangle((PAD, TOP_Y + 56, PAD + lw, TOP_Y + 62), radius=3,
                        fill=pal["accent"] + (255,))
    if tag:
        tf = load_font(28, bold=True)
        tw = int(_measure(tag, tf))
        rx = W - PAD - tw - 36
        d.rounded_rectangle((rx, TOP_Y + 2, rx + tw + 36, TOP_Y + 52), radius=14,
                            fill=(255, 255, 255, 26))
        d.text((rx + 18, TOP_Y + 10), tag, font=tf, fill=pal["sub"] + (255,))


# ----------------------------- 문제 슬라이드 -----------------------------
def build_problem(slide: dict, pal: dict, avatar_path: str | None = None,
                  avatar_live: bool = False):
    base = _gradient(pal)
    _paste_avatar(base, pal, avatar_path, live=avatar_live)
    meta = slide.get("meta") or {}
    num = slide.get("number")
    subject = slide.get("subject") or "SQLD"
    tag = f"난이도 {meta['difficulty']}" if meta.get("difficulty") else ""
    _header(base, pal, subject, tag)

    d = ImageDraw.Draw(base)
    y = TOP_Y + 100

    # 문제 번호 칩
    chip = f"문제 {num}" if num is not None else "문제"
    _, y = _chip(base, chip, pal, x=CX0, y=y)
    y += 22

    # 질문(Q) — 우측 컬럼
    question = slide.get("question") or ""
    qfont, qlines, qlh = fit_text(question, 52, 34, CW, 420, bold=True)
    y = draw_lines(d, qlines, CX0, y, qfont, pal["text"] + (255,), qlh)
    y += 30

    # 보기 ①②③④ — 순차 등장
    choices = [str(c) for c in (slide.get("choices") or [])]
    elements = []
    if choices:
        avail = SAFE_BOTTOM - y
        cfont, _, _ = fit_text("\n".join(choices), 42, 28, CW - 58, avail)
        clh = _line_h(cfont, 0.32)
        cy = y
        for i, ch in enumerate(choices):
            layer = _blank()
            ld = ImageDraw.Draw(layer)
            ld.text((CX0, cy), _circled(i), font=load_font(cfont.size, bold=True),
                    fill=pal["accent"] + (255,))
            lines = wrap_text(ch, cfont, CW - 58)
            draw_lines(ld, lines, CX0 + 56, cy, cfont, pal["text"] + (255,), clh)
            elements.append((layer, _appear(i)))
            cy += clh * len(lines) + 20
    return base, elements


# ----------------------------- 정답+해설 슬라이드 (해설 상단 / 정답 하단) -----------------------------
def build_answer(slide: dict, pal: dict, avatar_path: str | None = None,
                 avatar_live: bool = False):
    base = _gradient(pal)
    _paste_avatar(base, pal, avatar_path, live=avatar_live)
    num = slide.get("number")
    subject = slide.get("subject") or "SQLD"
    src = str(slide.get("source") or "").strip()
    _header(base, pal, subject, f"출처 · {src}" if src else "")

    d = ImageDraw.Draw(base)
    choices = [str(c) for c in (slide.get("choices") or [])]
    ai = slide.get("answer_index")
    ans = str(slide.get("answer") or "").strip()

    elements = []

    # ===== 하단: 정답 박스 (프레임 최하단에 pin) =====
    if choices and isinstance(ai, int) and 0 <= ai < len(choices):
        correct = f"{_circled(ai)}  {choices[ai]}"
    elif ans:
        correct = f"정답: {ans}"
    else:
        correct = "정답"
    afont, alines, alh = fit_text(correct, 48, 30, CW - 56, 220, bold=True)
    ans_box_h = len(alines) * alh + 40
    ans_label_h = 52
    ans_top = SAFE_BOTTOM - ans_box_h
    ans_block_top = ans_top - ans_label_h

    # '정답' 라벨(항상 보임)
    d.text((CX0, ans_block_top), "정답", font=load_font(34, bold=True),
           fill=pal["answer"] + (255,))
    # 정답 박스는 팝으로 등장
    ans_layer = _blank()
    ald = ImageDraw.Draw(ans_layer)
    ald.rounded_rectangle((CX0, ans_top, CX0 + CW, ans_top + ans_box_h), radius=18,
                          fill=pal["answer"] + (52,), outline=pal["answer"] + (255,), width=5)
    draw_lines(ald, alines, CX0 + 28, ans_top + 20, afont, pal["text"] + (255,), alh)

    # ===== 상단: 해설 블록 =====
    y = TOP_Y + 100
    # accent 막대 + '해설' 라벨 (이모지는 malgun.ttf 미지원 → 텍스트만)
    d.rounded_rectangle((CX0, y + 6, CX0 + 10, y + 44), radius=4, fill=pal["accent"] + (255,))
    d.text((CX0 + 26, y), "해설", font=load_font(38, bold=True), fill=pal["accent"] + (255,))
    y += 64
    explanation = (slide.get("explanation") or "").strip()
    if explanation:
        avail = ans_block_top - 30 - y        # 정답 블록 위까지만 사용
        efont, elines, elh = fit_text(explanation, 42, 28, CW, max(120, avail))
        exp_layer = _blank()
        eld = ImageDraw.Draw(exp_layer)
        draw_lines(eld, elines, CX0, y, efont, pal["text"] + (255,), elh)
        elements.append((exp_layer, APPEAR_START))

    # 정답은 해설 뒤에 등장
    elements.append((ans_layer, APPEAR_START + 0.6))
    return base, elements


# ----------------------------- 정적 합성 -----------------------------
def compose_static(base: Image.Image, elements) -> Image.Image:
    out = base.copy()
    for layer, _t in elements:
        out = Image.alpha_composite(out, layer)
    return out.convert("RGB")


_BUILDERS = {
    "problem": build_problem,
    "answer": build_answer,
}


def build(slide: dict, pal: dict, avatar_path: str | None = None,
          avatar_live: bool = False):
    kind = (slide or {}).get("kind") or "problem"
    builder = _BUILDERS.get(kind, build_problem)
    return builder(slide or {}, pal, avatar_path, avatar_live)
