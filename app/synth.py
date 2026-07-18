"""voicewright 어댑터 — 번들 폴더 하나를 받아 음성/자막을 만든다.

voicewright는 원래 workspace/ch{NN}/audio 레이아웃으로 출력하지만, mp4maker는
번들 직속 audio/·subtitles/ 를 읽는다. 여기서 run_batch(flat_layout=True)로
번들에 직접 쓰도록 맞춘다.

공개 함수:
    synthesize(bundle_dir, only=None, ...)  → 전체 또는 특정 씬만 합성
    rebuild_chapter_srt(bundle_dir)         → 디스크의 per-scene SRT/WAV로 통합 SRT 재생성
"""
from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

import soundfile as sf

from voicewright import settings as settings_module
from voicewright.audio_io import write_wav
from voicewright.batch import parse_script, run_batch
from voicewright.engine import Engine
from voicewright.paths import narration_filename, normalize_chapter_id, srt_filename
from voicewright.srt import (
    Cue,
    auto_time_cues,
    make_multi_srt,
    merge_scene_cues,
    parse_srt_cues,
    split_into_cues,
)
from voicewright.voices import ALL_VOICE_CODES, load_voice_map

_PER_SCENE_SRT_RE = re.compile(r"^ch[^_]+_(\d+)_narration\.srt$")


def _bundle_chapter_id(bundle_dir: Path) -> str | None:
    """번들 폴더 이름(ch90_bundle)에서 챕터 id('90')를 추출."""
    return normalize_chapter_id(bundle_dir.name.replace("_bundle", ""))


def find_script(bundle_dir: Path) -> Path:
    script_dir = bundle_dir / "script"
    hits = sorted(script_dir.glob("*_script.json"))
    if not hits:
        raise FileNotFoundError(f"대본 JSON이 없습니다: {script_dir}\\*_script.json")
    return hits[0]


async def synthesize(
    bundle_dir: str | Path,
    *,
    only: list[int] | None = None,
    voice_override: str | None = None,
    speed: float | None = None,
    total_step: int | None = None,
    on_progress=None,
) -> dict:
    """번들의 대본으로 음성(wav)+자막(srt)을 생성한다.

    only=None  → 전체 씬 배치
    only=[2,5] → 2,5번 씬만 재생성 (나머지는 디스크에 있던 것 유지)

    발음 교정은 config/pronunciation_map.yaml(웹 UI에서 편집) 를 합성 직전에
    자동 적용한다(engine 내부, 핫리로드). 단어 추가 후 그 씬만 재생성하면 반영됨.
    """
    bundle = Path(bundle_dir).resolve()
    script_path = find_script(bundle)
    script = parse_script(script_path.read_bytes())

    if only:
        wanted = set(int(n) for n in only)
        filtered = deepcopy(script)
        filtered.scenes = [sc for sc in script.scenes if sc.scene in wanted]
        if not filtered.scenes:
            raise ValueError(f"--only {sorted(wanted)} 에 해당하는 씬이 대본에 없습니다.")
        run_script = filtered
    else:
        run_script = script

    engine = await Engine.get()
    result = await run_batch(
        engine=engine,
        script=run_script,
        chapter_id_explicit=_bundle_chapter_id(bundle),
        filename_hint=script_path.name,
        output_root=bundle,
        voice_override=voice_override,
        speed=speed,
        total_step=total_step,
        on_progress=on_progress,
        flat_layout=True,
    )

    # 통합 SRT는 항상 디스크의 모든 per-scene SRT/WAV 기준으로 다시 만든다.
    # (부분 재생성 시 run_batch는 그 씬들만으로 통합 SRT를 만들기 때문에 보정 필요.
    #  사용자가 검수 탭에서 손본 per-scene SRT 타임코드도 이때 반영된다.)
    chapter_srt = rebuild_chapter_srt(bundle)

    return {
        "chapter": result.chapter_id,
        "bundle": str(bundle),
        "audio_dir": str(bundle / "audio"),
        "subtitles_dir": str(bundle / "subtitles"),
        "files": result.files,
        "chapter_srt": str(chapter_srt) if chapter_srt else None,
        "warnings": result.warnings,
        "scenes_done": [sc.scene for sc in run_script.scenes],
    }


def _wav_duration(path: Path) -> float:
    info = sf.info(str(path))
    return info.frames / float(info.samplerate)


def rebuild_chapter_srt(bundle_dir: str | Path) -> Path | None:
    """번들의 audio/*.wav + subtitles/*_narration.srt 를 모아 통합 chNN.srt 재생성.

    per-scene SRT(멀티큐)를 실측 오디오 길이만큼 누적 offset으로 병합한다.
    audio가 없는 씬은 통합 SRT에 넣지 못하므로 건너뛴다.
    """
    bundle = Path(bundle_dir).resolve()
    sub_dir = bundle / "subtitles"
    audio_dir = bundle / "audio"
    chapter_id = _bundle_chapter_id(bundle)
    if not sub_dir.exists() or chapter_id is None:
        return None

    scene_data: list[tuple[int, list, float]] = []
    for srt_p in sorted(sub_dir.glob("*_narration.srt")):
        m = _PER_SCENE_SRT_RE.match(srt_p.name)
        if not m:
            continue
        scene_num = int(m.group(1))
        wav_p = audio_dir / narration_filename(chapter_id, scene_num)
        if not wav_p.exists():
            continue
        cues = parse_srt_cues(srt_p.read_text(encoding="utf-8"))
        scene_data.append((scene_num, cues, _wav_duration(wav_p)))

    if not scene_data:
        return None

    scene_data.sort(key=lambda t: t[0])
    text = merge_scene_cues([(cues, dur) for _, cues, dur in scene_data])
    out = sub_dir / f"ch{chapter_id}.srt"
    out.write_text(text, encoding="utf-8")
    return out


def _resolve_voice(bundle: Path, scene: int, voice: str | None) -> str:
    """씬 보이스 결정: 명시값 → 대본의 voice_style → 기본."""
    s = settings_module.load()
    vmap = load_voice_map(s.voice_map_path)
    if voice:
        code = voice.upper()
        if code not in ALL_VOICE_CODES:
            raise ValueError(f"알 수 없는 보이스: {voice}")
        return code
    style = None
    sp = find_script(bundle)
    if sp:
        try:
            sc = parse_script(sp.read_bytes())
            for x in sc.scenes:
                if x.scene == int(scene):
                    style = x.voice_style
                    break
        except Exception:
            pass
    code, _ = vmap.resolve(style)
    return code


async def synth_scene_text(
    bundle_dir: str | Path,
    scene: int,
    text: str,
    *,
    srt_text: str | None = None,
    voice: str | None = None,
    speed: float | None = None,
    total_step: int | None = None,
    reset_subtitle: bool = False,
) -> dict:
    """한 씬만, 주어진 텍스트로 음성을 다시 만든다 (번들에 직접 기록).

    - 음성(TTS)에는 발음 사전이 자동 적용된다(엔진 내부).
    - 자막 타이밍은 **실측 음성 길이**에 맞춰 자동 재계산 → 발음변환/괄호제거로 인한
      싱크 어긋남을 보정한다.
    - reset_subtitle=False(기본): 이미 편집해 둔 per-scene 자막의 **줄 나눔(텍스트)을 유지**하고
      시간만 새 음성 길이에 맞춰 재배분 → 사용자의 자막 편집이 보존된다.
    - reset_subtitle=True: 자막을 srt_text(없으면 text)로 처음부터 새로 만든다.
    """
    bundle = Path(bundle_dir).resolve()
    chap = _bundle_chapter_id(bundle)
    if chap is None:
        raise ValueError(f"번들 이름에서 챕터를 찾지 못함: {bundle.name}")
    if not text.strip():
        raise ValueError("빈 텍스트입니다.")

    engine = await Engine.get()
    code = _resolve_voice(bundle, scene, voice)
    wav = await engine.synth(text, voice_code=code, total_step=total_step, speed=speed)

    audio_dir = bundle / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    wav_path = audio_dir / narration_filename(chap, int(scene))
    write_wav(wav_path, wav, engine.sample_rate)

    dur = float(len(wav)) / float(engine.sample_rate)
    sub_dir = bundle / "subtitles"
    sub_dir.mkdir(parents=True, exist_ok=True)
    srt_p = sub_dir / srt_filename(chap, int(scene))

    # 기존 편집 자막의 줄 나눔(텍스트) 유지 — 시간만 새 길이에 재배분
    existing_texts: list[str] = []
    if not reset_subtitle and srt_p.exists():
        existing_texts = [c.text for c in parse_srt_cues(srt_p.read_text(encoding="utf-8")) if c.text.strip()]
    if existing_texts:
        cues = auto_time_cues(existing_texts, dur)
    else:
        body = (srt_text or text).strip()
        cues = auto_time_cues(split_into_cues(body), dur)
    srt_p.write_text(make_multi_srt(cues), encoding="utf-8")
    rebuild_chapter_srt(bundle)

    return {
        "scene": int(scene),
        "voice": code,
        "duration": round(dur, 3),
        "audio_file": wav_path.name,
        "subtitle_file": srt_filename(chap, int(scene)),
        "cues": [{"text": c.text, "start": c.start, "end": c.end} for c in cues],
    }


def save_scene_cues(bundle_dir: str | Path, scene: int, cues_data: list[dict]) -> dict:
    """사용자가 편집한 자막 큐(시작/끝/텍스트)를 per-scene SRT로 저장 + 통합 SRT 갱신."""
    bundle = Path(bundle_dir).resolve()
    chap = _bundle_chapter_id(bundle)
    if chap is None:
        raise ValueError(f"번들 이름에서 챕터를 찾지 못함: {bundle.name}")
    cues: list[Cue] = []
    prev = -1.0
    for i, c in enumerate(cues_data):
        t = str(c.get("text", "")).strip()
        if not t:
            continue
        start = round(float(c.get("start", 0.0)), 3)
        end = round(float(c.get("end", 0.0)), 3)
        if start < 0 or end < start:
            raise ValueError(f"{i+1}번 자막 시간이 잘못됨 (start={start}, end={end})")
        if start < prev - 1e-3:
            raise ValueError(f"{i+1}번 자막이 앞 자막과 겹침")
        prev = end
        cues.append(Cue(text=t, start=start, end=end))
    if not cues:
        raise ValueError("저장할 자막이 없습니다.")

    sub_dir = bundle / "subtitles"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / srt_filename(chap, int(scene))).write_text(make_multi_srt(cues), encoding="utf-8")
    rebuild_chapter_srt(bundle)
    return {"scene": int(scene), "cue_count": len(cues)}
