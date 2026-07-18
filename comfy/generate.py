"""번들 단위 씬 이미지(+영상 클립) 생성 — FlowGenie import 대체.

대본 JSON 의 씬별 영어 "prompt" 를 ComfyUI txt2img 에 넣어 이미지를 만들고,
img2video 가 가능하면 그 이미지를 클립으로 애니메이션한다(하이브리드).
클립을 못 만들면 이미지만 남기고 mp4maker 가 Ken Burns 로 움직임을 준다.

산출:
    <bundle>/images/chNN_XX_<slug>.png      (항상)
    <bundle>/clips/chNN_XX.mp4              (img2video 성공 시에만)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

from .comfy_client import ComfyClient, ComfyError
from .config import ComfyConfig, load_config
from .workflow import (
    has_video_capability,
    inject_img2video,
    inject_txt2img,
    load_api_workflow,
    load_override_map,
)

ProgressCb = Optional[Callable[[dict], None]]

_ASPECT = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "1:1": (1024, 1024),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
}


def _emit(cb: ProgressCb, ev: dict) -> None:
    if cb:
        try:
            cb(ev)
        except Exception:
            pass


def _chapter_id(bundle: Path) -> str:
    m = re.search(r"(\d{1,3})", bundle.name.replace("_bundle", ""))
    return f"ch{int(m.group(1)):02d}" if m else "ch01"


def _round8(x: int) -> int:
    return max(8, int(round(x / 8)) * 8)


def _resolution(aspect: str, max_dim: int = 0) -> tuple[int, int]:
    w, h = _ASPECT.get((aspect or "16:9").strip(), (1280, 720))
    if max_dim and max(w, h) > max_dim:          # 저사양: 비율 유지하며 축소(8의 배수)
        scale = max_dim / float(max(w, h))
        w, h = _round8(w * scale), _round8(h * scale)
    return w, h


def _seed_for(cfg: ComfyConfig, scene_idx: int) -> int:
    if cfg.fixed_seed is not None:
        return cfg.fixed_seed + scene_idx
    # 재현성 있게 씬 인덱스 기반(무작위 금지 — 재실행 동일 결과)
    return 100000 + scene_idx * 977


def _slug_from_filename(image_filename: str, chapter_id: str, idx: int) -> str:
    stem = Path(image_filename or "").stem
    if stem:
        return stem
    return f"{chapter_id}_{idx:02d}_scene"


def load_scenes(bundle: Path) -> tuple[str, str, list[dict]]:
    """번들 script/*_script.json 에서 (chapter_id, aspect_ratio, scenes) 로드."""
    script_dir = bundle / "script"
    files = sorted(script_dir.glob("*_script.json"))
    if not files:
        raise FileNotFoundError(f"대본 JSON 없음: {script_dir}/*_script.json")
    data = json.loads(files[0].read_text(encoding="utf-8"))
    chap = int(data.get("chapter") or 0)
    chapter_id = f"ch{chap:02d}" if chap else _chapter_id(bundle)
    aspect = data.get("aspect_ratio") or "16:9"
    scenes = data.get("scenes") or []
    return chapter_id, aspect, scenes


def generate_bundle_images(
    bundle_dir: str | Path,
    *,
    cfg: ComfyConfig | None = None,
    only: list[int] | None = None,
    make_video: bool | None = None,
    on_progress: ProgressCb = None,
) -> dict:
    """번들의 모든(또는 only) 씬 이미지를 ComfyUI 로 생성. 하이브리드 클립 포함.

    Returns: {"images": [...], "clips": [...], "video_used": bool, "errors": [...]}
    """
    cfg = cfg or load_config()
    bundle = Path(bundle_dir).resolve()
    chapter_id, aspect, scenes = load_scenes(bundle)
    width, height = _resolution(aspect, cfg.max_dim)

    images_dir = bundle / "images"
    clips_dir = bundle / "clips"
    images_dir.mkdir(parents=True, exist_ok=True)

    client = ComfyClient(cfg)
    # 연결 확인
    try:
        client.ping()
    except ComfyError as exc:
        raise ComfyError(
            f"ComfyUI 서버에 연결할 수 없습니다 ({cfg.base_url}). "
            f"ComfyUI 를 먼저 실행하세요. 원인: {exc}") from exc

    txt2img_wf = load_api_workflow(cfg.txt2img_workflow)
    txt2img_map = load_override_map(cfg.txt2img_workflow)

    # 영상 능력 감지 (하이브리드)
    want_video = cfg.enable_video if make_video is None else make_video
    video_ok = False
    img2video_wf = None
    img2video_map = {}
    if want_video:
        classes = client.available_node_classes()
        video_ok = has_video_capability(classes, cfg.img2video_workflow)
        if video_ok:
            try:
                img2video_wf = load_api_workflow(cfg.img2video_workflow)
                img2video_map = load_override_map(cfg.img2video_workflow)
            except (FileNotFoundError, ValueError) as exc:
                _emit(on_progress, {"type": "log",
                      "line": f"[comfy] img2video 워크플로우 사용 불가 -> Ken Burns 폴백 ({exc})"})
                video_ok = False
    if video_ok:
        clips_dir.mkdir(parents=True, exist_ok=True)

    only_set = set(only) if only else None
    result = {"images": [], "clips": [], "video_used": video_ok, "errors": []}
    total = len(scenes)

    for pos, scene in enumerate(scenes):
        idx = int(scene.get("scene") or scene.get("scene_number") or (pos + 1))
        if only_set is not None and idx not in only_set:
            continue
        prompt = (scene.get("prompt") or "").strip()
        slug = _slug_from_filename(scene.get("image_filename", ""), chapter_id, idx)
        prefix = f"{chapter_id}_{idx:02d}"
        _emit(on_progress, {"type": "progress", "completed": pos, "total": total, "scene": idx})

        if not prompt:
            msg = f"씬{idx}: prompt 비어 있음 — 건너뜀"
            result["errors"].append(msg)
            _emit(on_progress, {"type": "log", "line": f"[comfy] {msg}"})
            continue

        # 1) txt2img -> PNG
        try:
            wf = inject_txt2img(txt2img_wf, prompt=prompt, seed=_seed_for(cfg, idx),
                                width=width, height=height,
                                filename_prefix=prefix, override=txt2img_map)
            rec = client.wait(client.queue_prompt(wf))
            imgs = [f for f in ComfyClient.outputs_of(rec) if f.kind == "images"]
            if not imgs:
                raise ComfyError("이미지 출력이 없습니다(SaveImage 노드 확인).")
            png = images_dir / f"{slug}.png"
            png.write_bytes(client.download(imgs[-1]))
            result["images"].append(png.name)
            _emit(on_progress, {"type": "log", "line": f"[comfy] 씬{idx} 이미지 -> {png.name}"})
        except ComfyError as exc:
            msg = f"씬{idx} 이미지 생성 실패: {exc}"
            result["errors"].append(msg)
            _emit(on_progress, {"type": "log", "line": f"[comfy] {msg}"})
            continue

        # 2) img2video -> 클립 (가능할 때만; 실패해도 이미지로 진행)
        if video_ok and img2video_wf is not None:
            try:
                uploaded = client.upload_image(png.read_bytes(), f"{prefix}_src.png")
                wf2 = inject_img2video(img2video_wf, image_name=uploaded,
                                       seed=_seed_for(cfg, idx),
                                       filename_prefix=prefix, override=img2video_map)
                rec2 = client.wait(client.queue_prompt(wf2))
                vids = [f for f in ComfyClient.outputs_of(rec2)
                        if f.kind in ("videos", "gifs")]
                if vids:
                    chosen = _pick_video(vids)
                    ext = Path(chosen.filename).suffix or ".mp4"
                    clip = clips_dir / f"{prefix}{ext}"
                    clip.write_bytes(client.download(chosen))
                    result["clips"].append(clip.name)
                    _emit(on_progress, {"type": "log",
                          "line": f"[comfy] 씬{idx} 클립 -> {clip.name}"})
            except ComfyError as exc:
                _emit(on_progress, {"type": "log",
                      "line": f"[comfy] 씬{idx} img2video 실패 -> Ken Burns 폴백 ({exc})"})

    _emit(on_progress, {"type": "progress", "completed": total, "total": total, "scene": None})
    return result


def _pick_video(vids) -> object:
    """mp4 를 우선, 없으면 첫 항목(webm/gif)."""
    for f in vids:
        if Path(f.filename).suffix.lower() == ".mp4":
            return f
    return vids[-1]
