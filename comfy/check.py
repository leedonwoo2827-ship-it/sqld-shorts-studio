"""ComfyUI 연결/능력 점검 CLI.

    python -m comfy.check

서버 상태, txt2img/img2video 워크플로우 존재, 영상 노드 설치 여부를 출력한다.
"""
from __future__ import annotations

import sys

from .comfy_client import ComfyClient, ComfyError
from .config import load_config
from .workflow import has_video_capability, load_api_workflow


def _utf8_stdout() -> None:
    """Windows 콘솔(cp949)에서 유니코드 출력이 깨지거나 죽지 않도록 UTF-8 로 전환."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def main() -> int:
    _utf8_stdout()
    cfg = load_config()
    print(f"[comfy] server   : {cfg.base_url}")
    print(f"[comfy] video    : {'on' if cfg.enable_video else 'off'} (COMFY_ENABLE_VIDEO)")
    print(f"[comfy] txt2img  : {cfg.txt2img_workflow}")
    print(f"[comfy] img2video: {cfg.img2video_workflow}")

    client = ComfyClient(cfg)
    try:
        stats = client.ping()
    except ComfyError as exc:
        print(f"\n[FAIL] 연결 불가 — ComfyUI 를 먼저 실행하세요.\n       {exc}")
        return 1

    devs = stats.get("devices") or []
    if devs:
        d = devs[0]
        vram = d.get("vram_total")
        gb = f"{vram / (1024**3):.1f}GB" if isinstance(vram, (int, float)) else "?"
        print(f"[ OK ] connected. device: {d.get('name', '?')} (VRAM {gb})")
    else:
        print("[ OK ] connected.")

    classes = client.available_node_classes()
    print(f"[comfy] installed node classes: {len(classes)}")

    for label, path in (("txt2img", cfg.txt2img_workflow),
                        ("img2video", cfg.img2video_workflow)):
        try:
            wf = load_api_workflow(path)
            needed = {n.get("class_type") for n in wf.values()
                      if isinstance(n, dict) and n.get("class_type")}
            missing = sorted(needed - classes) if classes else []
            status = "ready" if not missing else f"missing nodes: {missing}"
            print(f"[comfy] {label} workflow: {len(wf)} nodes — {status}")
        except FileNotFoundError:
            print(f"[comfy] {label} workflow: NOT FOUND ({path})")
        except ValueError as exc:
            print(f"[comfy] {label} workflow: INVALID — {exc}")

    video_ok = has_video_capability(classes, cfg.img2video_workflow)
    print(f"\n[result] image generation: ready")
    print(f"[result] image->video   : {'ready (real motion)' if video_ok else 'unavailable -> Ken Burns fallback'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
