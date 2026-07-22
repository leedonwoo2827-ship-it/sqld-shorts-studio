"""세로(9:16) SQLD 문제 쇼츠 조립기.

한 문제 = 한 쇼츠. 구성(씬):
    1) 문제 슬라이드(문제+보기)         — problem_sec
    2) 정답+해설 슬라이드(해설상단/정답하단) — answer_sec
슬라이드는 slides.layout_shorts 로 렌더(좌측 아바타 컬럼 포함)하고,
ffmpeg 로 1080x1920 세그먼트를 만든 뒤 concat 한다.

옵션:
    avatar_clip : 립싱크 말하는 얼굴 클립(mp4/mov, 배경 크로마키/알파). 좌측에 오버레이.
    audio_map   : {"problem": wav|None, "answer": wav} 씬별 TTS. 있으면 길이 자동 동기 + 믹스.

지금은 avatar_clip/audio 없이도 (자리표시자 아바타가 슬라이드에 baked, 무음) 완결 동작한다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from slides import layout_shorts as L
from slides.theme import get_palette

from .ffmpeg_runner import ffprobe_duration, probe_binary, run_ffmpeg

FPS = 30
CHROMA_DEFAULT = "0x00FF00"     # 아바타 클립 배경(초록) 키컬러 기본값


def _render_slides(problem: dict, subject: str, pal: dict, avatar_img: str | None,
                   out_dir: Path) -> tuple[Path, Path]:
    """문제/정답 슬라이드 PNG(1080x1920)를 렌더해 경로를 돌려준다."""
    pslide = {
        "kind": "problem", "number": problem.get("number"), "subject": subject,
        "question": problem.get("question"), "choices": problem.get("choices"),
        "meta": {"difficulty": problem.get("difficulty")},
    }
    aslide = {
        "kind": "answer", "number": problem.get("number"), "subject": subject,
        "choices": problem.get("choices"), "answer": problem.get("answer"),
        "answer_index": problem.get("answer_index"),
        "explanation": problem.get("explanation"),
        "source": problem.get("source") or "",
    }
    pb, pe = L.build(pslide, pal, avatar_img)
    ab, ae = L.build(aslide, pal, avatar_img)
    p_png = out_dir / "seg_problem.png"
    a_png = out_dir / "seg_answer.png"
    L.compose_static(pb, pe).save(p_png)
    L.compose_static(ab, ae).save(a_png)
    return p_png, a_png


def _segment(png: Path, seconds: float, out: Path, *, avatar_clip: str | None,
             audio: str | None, chroma: str, log: Path) -> None:
    """정지 PNG(배경) + (선택)아바타 클립 오버레이 + (선택)오디오 → 세그먼트 mp4."""
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(png)]
    fil1 = f"[0:v]scale={L.W}:{L.H},setsar=1,fps={FPS}[bg]"
    has_avatar = bool(avatar_clip and Path(avatar_clip).is_file())
    has_audio = bool(audio and Path(audio).is_file())

    if has_avatar:
        cmd += ["-i", str(avatar_clip)]
    if has_audio:
        cmd += ["-i", str(audio)]

    if has_avatar:
        # 아바타 클립을 아바타 컬럼 폭에 맞춰 스케일 → 크로마키 → 좌하단 오버레이
        av_idx = 1
        chain = (
            f"{fil1};"
            f"[{av_idx}:v]scale={L.AV_W + 8}:-1,chromakey={chroma}:0.10:0.08[av];"
            f"[bg][av]overlay=0:H-h:shortest=0[vout]"
        )
        cmd += ["-filter_complex", chain, "-map", "[vout]"]
    else:
        cmd += ["-vf", fil1.replace("[0:v]", "").replace("[bg]", ""), "-map", "0:v"]

    if has_audio:
        aud_idx = 2 if has_avatar else 1
        cmd += ["-map", f"{aud_idx}:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        cmd += ["-an"]

    cmd += ["-t", f"{seconds:.3f}", "-r", str(FPS),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
            "-movflags", "+faststart", str(out)]
    run_ffmpeg(cmd, log)


def _concat(segments: list[Path], out: Path, log: Path) -> None:
    lst = out.parent / "concat_list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-c", "copy", "-movflags", "+faststart", str(out)]
    run_ffmpeg(cmd, log)


def _seg_seconds(default: float, audio: str | None) -> float:
    if audio and Path(audio).is_file():
        try:
            return max(default, ffprobe_duration(Path(audio)) + 0.6)
        except Exception:
            pass
    return default


def build_short(
    problem: dict,
    *,
    subject: str,
    theme: str,
    out_path: Path,
    tmp_dir: Path,
    avatar_img: str | None = None,
    avatar_clip_problem: str | None = None,
    avatar_clip_answer: str | None = None,
    audio_problem: str | None = None,
    audio_answer: str | None = None,
    problem_sec: float = 4.0,
    answer_sec: float = 9.0,
    chroma: str = CHROMA_DEFAULT,
) -> Path:
    """문제 하나로 9:16 쇼츠 mp4 하나를 만든다. 반환 = out_path."""
    if probe_binary("ffmpeg") is None:
        raise RuntimeError("ffmpeg 가 PATH 에 없습니다. winget install Gyan.FFmpeg")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pal = get_palette(theme, subject, int(problem.get("chapter") or 1))

    p_png, a_png = _render_slides(problem, subject, pal, avatar_img, tmp_dir)
    log = tmp_dir / "ffmpeg_error.log"

    p_sec = _seg_seconds(problem_sec, audio_problem)
    a_sec = _seg_seconds(answer_sec, audio_answer)

    seg_p = tmp_dir / "seg_problem.mp4"
    seg_a = tmp_dir / "seg_answer.mp4"
    _segment(p_png, p_sec, seg_p, avatar_clip=avatar_clip_problem,
             audio=audio_problem, chroma=chroma, log=log)
    _segment(a_png, a_sec, seg_a, avatar_clip=avatar_clip_answer,
             audio=audio_answer, chroma=chroma, log=log)
    _concat([seg_p, seg_a], out_path, log)
    return out_path


def build_from_lesson(lesson_json: str | Path, out_dir: str | Path,
                      *, avatar_img: str | None = None,
                      only: list[int] | None = None) -> list[Path]:
    """lesson JSON 의 각 problem 을 개별 쇼츠 mp4 로 만든다(무음/자리표시자 기본)."""
    data = json.loads(Path(lesson_json).read_text(encoding="utf-8"))
    subject = data.get("subject") or "SQLD"
    theme = data.get("theme") or "sqld"
    out_dir = Path(out_dir)
    made: list[Path] = []
    for b in data.get("blocks", []):
        if b.get("kind") != "problem":
            continue
        n = b.get("number")
        if only and n not in only:
            continue
        b = dict(b, chapter=data.get("chapter"),
                 source=f"{data.get('round','')} {n}번".strip())
        out = out_dir / f"sqld_short_{n:02d}.mp4"
        tmp = out_dir / "_tmp" / f"{n:02d}"
        build_short(b, subject=subject, theme=theme, out_path=out, tmp_dir=tmp,
                    avatar_img=avatar_img)
        made.append(out)
    return made
