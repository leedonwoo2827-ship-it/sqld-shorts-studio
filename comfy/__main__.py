"""번들 이미지 생성 CLI.

    python -m comfy <bundle_dir> [--only 1,2,3] [--no-video]

대본 JSON 의 씬별 prompt 로 ComfyUI 이미지를(+가능하면 클립을) 생성한다.
"""
from __future__ import annotations

import argparse
import sys

from .comfy_client import ComfyError
from .generate import generate_bundle_images


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="ComfyUI 로 번들 씬 이미지/클립 생성")
    ap.add_argument("bundle", help="번들 폴더 (예: _assets/ch01_bundle 또는 sample/ch01_bundle)")
    ap.add_argument("--only", default="", help="쉼표로 구분한 씬 번호만 생성 (예: 1,2,5)")
    ap.add_argument("--no-video", action="store_true", help="img2video 끄기(이미지만)")
    args = ap.parse_args(argv)

    only = [int(x) for x in args.only.split(",") if x.strip().isdigit()] or None

    def cb(ev: dict) -> None:
        if ev.get("type") == "log":
            print(ev["line"])
        elif ev.get("type") == "progress" and ev.get("scene"):
            print(f"  ... 씬{ev['scene']} ({ev['completed']}/{ev['total']})")

    try:
        res = generate_bundle_images(
            args.bundle, only=only,
            make_video=False if args.no_video else None, on_progress=cb)
    except (ComfyError, FileNotFoundError, ValueError) as exc:
        print(f"[error] {exc}")
        return 1

    print(f"\n[done] images={len(res['images'])} clips={len(res['clips'])} "
          f"video_used={res['video_used']}")
    if res["errors"]:
        print("[warn] " + "; ".join(res["errors"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
