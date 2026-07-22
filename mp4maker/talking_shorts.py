"""SQLD 말하는-아바타 쇼츠 파이프라인 (한 문제 = 한 쇼츠).

단계: 보드 렌더(9:16 흰 배경, 문제/보기/정답/해설) → Supertonic TTS →
      ComfyUI Sonic 립싱크(얼굴+음성→말하는 얼굴) → 배경제거·밝기·원형 프레이밍 →
      ffmpeg 합성(보드 + 우하단 원형 말하는 아바타 + 음성) → 9:16 mp4.

의존: Pillow, numpy, cv2, rembg, onnxruntime, soundfile, ffmpeg, 그리고
      ComfyUI(Sonic 노드+모델) 실행 중 + Supertonic assets(VOICEWRIGHT_ASSETS_DIR).
웹 route(app)와 CLI(scripts) 양쪽에서 재사용한다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
SHARED = Path(os.environ.get("COMFY_SHARED",
              r"C:\Users\ubion\AppData\Local\Comfy-Desktop\ComfyUI-Shared"))
VOICES_DIR = ROOT / "assets" / "avatar" / "voices"
Log = Callable[[str], None]

# ---- 보드/원 지오메트리 (make_boards2 와 동일) ----
W, H = 1080, 1920
PAD = 56
D = 450                       # 아바타 원 지름
NUDGE = {"F1": 46, "F3": 46, "F5": 46}
FILL = {"M3", "M5"}           # 하단 흰여백 방지: 채우기 모드
TARGET_FH = D * 0.35
FACE_CY = D * 0.40


def _log(cb: Log | None, msg: str) -> None:
    if cb:
        cb(msg)


# ============================ 1) 보드 렌더 ============================
def render_board(problem: dict, subject: str = "SQLD") -> "object":
    """문제 보드(아바타 자리=옅은 원 링만) PIL RGB 이미지 반환."""
    from PIL import Image, ImageDraw
    from slides.fonts import load_font
    from slides.layout import fit_text, wrap_text, draw_lines, _line_h, _measure, _circled
    pal = {"accent": (37, 99, 214), "answer": (22, 158, 74), "text": (23, 42, 71),
           "sky": (56, 148, 222), "ring": (205, 219, 240)}
    ai = problem.get("answer_index")
    av_cx = W - PAD - D // 2
    av_cy = H - 50 - D // 2
    base = Image.new("RGB", (W, H), (255, 255, 255)); px = base.load()
    for y in range(520):
        t = 1 - y / 520
        c = (int(255 - (255 - 236) * t), int(255 - (255 - 243) * t), int(255 - (255 - 252) * t))
        for x in range(W):
            px[x, y] = c
    d = ImageDraw.Draw(base)
    d.text((PAD, 60), subject, font=load_font(40, bold=True), fill=pal["text"])
    lw = int(_measure(subject, load_font(40, bold=True)))
    d.rounded_rectangle((PAD, 116, PAD + lw, 122), radius=3, fill=pal["accent"])
    y = 165
    cf = load_font(32, bold=True); ct = f"문제 {problem.get('number')}"; cw = int(_measure(ct, cf))
    d.rounded_rectangle((PAD, y, PAD + cw + 40, y + 56), radius=15, fill=pal["accent"])
    d.text((PAD + 20, y + 10), ct, font=cf, fill=(255, 255, 255)); y += 78
    qf, ql, qlh = fit_text(problem.get("question", ""), 48, 34, W - 2 * PAD, 300, bold=True)
    y = draw_lines(d, ql, PAD, y, qf, pal["text"], qlh) + 24
    choices = [str(c) for c in (problem.get("choices") or [])]
    cfont, _, _ = fit_text("\n".join(choices), 40, 28, W - 2 * PAD - 150, 560)
    clh = _line_h(cfont, 0.3)
    for i, ch in enumerate(choices):
        lines = wrap_text(ch, cfont, W - 2 * PAD - 150); bh = clh * len(lines) + 20
        if i == ai:
            d.rounded_rectangle((PAD, y - 6, W - PAD, y + bh - 2), radius=14,
                                fill=(224, 246, 231), outline=pal["answer"], width=4)
        nc = pal["answer"] if i == ai else pal["accent"]
        d.text((PAD + 16, y), _circled(i), font=load_font(cfont.size, bold=True), fill=nc)
        draw_lines(d, lines, PAD + 72, y, cfont, pal["text"], clh); y += bh + 12
    y += 10
    if isinstance(ai, int):
        d.text((PAD, y), f"정답  {_circled(ai)}", font=load_font(38, bold=True), fill=pal["answer"]); y += 64
    ew = (av_cx - D // 2 - 30) - PAD
    d.text((PAD, y), "해설", font=load_font(30, bold=True), fill=pal["sky"]); y += 46
    ef, el, elh = fit_text(problem.get("explanation", ""), 30, 22, ew, H - 56 - y)
    draw_lines(d, el, PAD, y, ef, pal["sky"], elh)
    base = base.convert("RGBA")
    ImageDraw.Draw(base).ellipse((av_cx - D // 2, av_cy - D // 2, av_cx + D // 2, av_cy + D // 2),
                                 outline=pal["ring"] + (255,), width=5)
    return base.convert("RGB")


# ============================ 2) Supertonic TTS ============================
def tts_supertonic(text: str, voice: str, out_wav: Path, log: Log | None = None) -> Path:
    """CLI(typer) 대신 엔진을 인프로세스로 직접 호출(빠르고 의존성 적음)."""
    import asyncio
    os.environ.setdefault("VOICEWRIGHT_ASSETS_DIR", str(ROOT / "assets_supertonic"))
    from voicewright.engine import Engine
    from voicewright.audio_io import write_wav
    _log(log, f"[TTS] Supertonic {voice} 합성…")

    async def _synth():
        eng = await Engine.get()
        wav = await eng.synth(text, voice_code=voice, lang="ko", total_step=8, speed=1.0)
        write_wav(out_wav, wav, eng.sample_rate)

    asyncio.run(_synth())
    if not out_wav.exists():
        raise RuntimeError("TTS 산출 파일이 없습니다")
    return out_wav


# ============================ 3) ComfyUI Sonic 립싱크 ============================
def sonic_lipsync(face_png: Path, audio: Path, out_dir: Path, *, min_res: int = 384,
                  steps: int = 20, log: Log | None = None) -> Path:
    inp = SHARED / "input"; outp = SHARED / "output"; inp.mkdir(parents=True, exist_ok=True)
    import shutil
    fn_img = f"ts_{uuid.uuid4().hex[:6]}.png"; fn_aud = f"ts_{uuid.uuid4().hex[:6]}{audio.suffix}"
    shutil.copy(face_png, inp / fn_img); shutil.copy(audio, inp / fn_aud)
    try:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=nw=1:nk=1", str(audio)], capture_output=True, text=True).stdout) + 0.6
    except Exception:
        dur = 30.0
    g = {
        "ck": {"class_type": "ImageOnlyCheckpointLoader", "inputs": {"ckpt_name": "svd.safetensors"}},
        "ld": {"class_type": "SONICTLoader", "inputs": {"model": ["ck", 0], "sonic_unet": "unet.pth",
               "ip_audio_scale": 1.0, "use_interframe": True, "dtype": "fp16"}},
        "img": {"class_type": "LoadImage", "inputs": {"image": fn_img}},
        "aud": {"class_type": "LoadAudio", "inputs": {"audio": fn_aud}},
        "pre": {"class_type": "SONIC_PreData", "inputs": {"clip_vision": ["ck", 1], "vae": ["ck", 2],
                "audio": ["aud", 0], "image": ["img", 0], "weight_dtype": ["ld", 1],
                "min_resolution": min_res, "duration": dur, "expand_ratio": 0.5}},
        "smp": {"class_type": "SONICSampler", "inputs": {"model": ["ld", 0], "data_dict": ["pre", 0],
                "seed": 0, "inference_steps": steps, "dynamic_scale": 1.0, "fps": 25.0}},
        "cv": {"class_type": "CreateVideo", "inputs": {"images": ["smp", 0], "fps": ["smp", 1]}},
        "sv": {"class_type": "SaveVideo", "inputs": {"video": ["cv", 0],
               "filename_prefix": "ts_lip", "format": "mp4", "codec": "h264"}},
    }
    before = set((outp).glob("ts_lip*.mp4"))
    req = urllib.request.Request(COMFY + "/prompt",
        data=json.dumps({"prompt": g, "client_id": uuid.uuid4().hex}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        pid = json.load(urllib.request.urlopen(req, timeout=30))["prompt_id"]
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"ComfyUI에 연결할 수 없습니다 ({COMFY}). ComfyUI Desktop의 'shorts' 인스턴스를 "
            f"실행한 뒤 다시 시도하세요. (Sonic 립싱크는 ComfyUI가 켜져 있어야 동작)") from e
    _log(log, f"[립싱크] Sonic 생성 시작(해상도 {min_res}, ~수분)…")
    for _ in range(1600):
        time.sleep(3)
        new = set((outp).glob("ts_lip*.mp4")) - before
        if new:
            clip = max(new, key=lambda p: p.stat().st_mtime)
            # ComfyUI가 아직 파일을 쓰는 중일 수 있으니 크기가 안정될 때까지 대기
            last = -1
            for _ in range(40):
                sz = clip.stat().st_size
                if sz > 0 and sz == last:
                    break
                last = sz
                time.sleep(1)
            return clip
        try:
            h = json.load(urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=10))
            if pid in h and h[pid].get("status", {}).get("status_str") == "error":
                raise RuntimeError("Sonic 실행 오류(ComfyUI history). VRAM/모델 확인.")
        except urllib.error.URLError:
            pass
    raise RuntimeError("립싱크 타임아웃")


# ============================ 4) 아바타→원형 클립 + 합성 ============================
def _face_scale_offset(f_rgb, cut, code):
    import numpy as np, cv2
    from PIL import Image
    haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if code in FILL:
        bb = cut.getbbox(); ph = bb[3] - bb[1]; pw = bb[2] - bb[0]
        sc = (D - 6) / ph
        return sc, (D / 2 - (bb[0] + pw / 2) * sc, D - bb[3] * sc)
    g = cv2.cvtColor(np.array(f_rgb), cv2.COLOR_RGB2GRAY)
    faces = haar.detectMultiScale(g, 1.1, 5, minSize=(60, 60))
    if len(faces):
        fx, fy, fw, fh = max(faces, key=lambda r: r[2] * r[3])
    else:
        bb = cut.getbbox(); fx, fy, fw, fh = bb[0], bb[1], bb[2] - bb[0], int((bb[3] - bb[1]) * 0.4)
    sc = TARGET_FH / fh
    return sc, (D / 2 - (fx + fw / 2) * sc, FACE_CY - (fy + fh / 2) * sc + NUDGE.get(code, 0))


def build_talking_short(problem: dict, *, face_code: str, voice_code: str,
                        out_mp4: Path, workdir: Path, subject: str = "SQLD",
                        min_res: int = 384, log: Log | None = None) -> Path:
    """한 문제 → 말하는 아바타 쇼츠 mp4. (ComfyUI 실행 중이어야 함)"""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageChops
    from rembg import remove, new_session
    workdir.mkdir(parents=True, exist_ok=True); out_mp4.parent.mkdir(parents=True, exist_ok=True)
    face_png = VOICES_DIR / f"{face_code}.png"
    if not face_png.is_file():
        raise RuntimeError(f"얼굴 없음: {face_png}")

    # 1) 보드
    _log(log, "[보드] 슬라이드 렌더")
    board = render_board(problem, subject); board.save(workdir / "board.png")

    # 2) 음성
    text = problem.get("narration") or problem.get("explanation_speech") or problem.get("explanation", "")
    wav = tts_supertonic(text, voice_code, workdir / "voice.wav", log)

    # 3) 립싱크
    clip = sonic_lipsync(face_png, wav, workdir, min_res=min_res, log=log)

    # 4) 프레임 추출 → 배경제거·글로우·원형 프레이밍
    _log(log, "[합성] 배경제거·프레이밍")
    fr = workdir / "frames"; fr.mkdir(exist_ok=True)
    for p in fr.glob("*.png"):
        p.unlink()
    ex = subprocess.run(["ffmpeg", "-y", "-i", str(clip), "-r", "25", str(fr / "f_%04d.png")],
                        capture_output=True, text=True)
    if not sorted(fr.glob("f_*.png")):
        raise RuntimeError(f"립싱크 프레임 추출 실패(0장). clip={clip}\nffmpeg: {(ex.stderr or '')[-500:]}")
    sess = new_session("u2net_human_seg")
    cm = Image.new("L", (D * 3, D * 3), 0); ImageDraw.Draw(cm).ellipse((0, 0, D * 3, D * 3), fill=255)
    cm = cm.resize((D, D), Image.LANCZOS)
    av_cx = W - PAD - D // 2; av_cy = H - 50 - D // 2; cx0 = av_cx - D // 2; cy0 = av_cy - D // 2
    ring = (205, 219, 240)
    of = workdir / "final_frames"; of.mkdir(exist_ok=True)
    for p in of.glob("*.png"):
        p.unlink()
    frames = sorted(fr.glob("f_*.png"))
    sc = off = None
    for i, fp in enumerate(frames):
        im = Image.open(fp).convert("RGBA"); cut = remove(im, session=sess)
        w = Image.new("RGBA", cut.size, (255, 255, 255, 255)); w.alpha_composite(cut); f = w.convert("RGB")
        f = ImageEnhance.Brightness(f).enhance(1.11); f = ImageEnhance.Color(f).enhance(1.05)
        bl = f.filter(ImageFilter.GaussianBlur(5)); f = ImageChops.screen(f, bl.point(lambda p: int(p * 0.4)))
        if sc is None:
            sc, off = _face_scale_offset(f, cut, face_code)
        nf = f.resize((int(f.width * sc), int(f.height * sc)))
        tile = Image.new("RGB", (D, D), (255, 255, 255)); tile.paste(nf, (int(off[0]), int(off[1])))
        frame = board.copy(); frame.paste(tile, (cx0, cy0), cm)
        ImageDraw.Draw(frame).ellipse((cx0, cy0, cx0 + D, cy0 + D), outline=ring, width=5)
        frame.save(of / f"F_{i:04d}.png")

    # 5) 조립(+음성)
    _log(log, "[합성] 인코딩")
    r = subprocess.run(["ffmpeg", "-y", "-framerate", "25", "-i", str(of / "F_%04d.png"),
                        "-i", str(wav), "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", str(out_mp4)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not out_mp4.exists():
        raise RuntimeError(f"ffmpeg 합성 실패: {r.stderr[-400:]}")
    _log(log, f"[완료] {out_mp4}")
    return out_mp4
