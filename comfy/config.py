"""ComfyUI 연동 환경설정.

.env 또는 환경변수로 제어한다. 같은 repo 를 사무용 PC(Iris Xe)와 GPU 노트북에서
모두 쓰기 위해, ComfyUI 서버 위치(host:port)를 바꿔가며 연결한다.

주요 변수:
    COMFY_HOST            ComfyUI 서버 호스트 (기본 127.0.0.1)
    COMFY_PORT            포트 (기본 8188)
    COMFY_ENABLE_VIDEO    img2video 사용 여부 (1/0, 기본 1=하이브리드)
    COMFY_TXT2IMG_WORKFLOW  txt2img API json 경로 (기본 workflows/txt2img_api.json)
    COMFY_IMG2VIDEO_WORKFLOW img2video API json 경로 (기본 workflows/img2video_api.json)
    COMFY_TIMEOUT         한 씬 생성 최대 대기(초) (기본 600)
    COMFY_SEED            고정 시드(정수) 지정 시 재현 가능. 미지정이면 씬 인덱스 기반.
    COMFY_MAX_DIM         해상도 긴 변 상한(px). 저사양(CPU)에서 속도용(예: 768).
                          0=제한 없음(기본). aspect_ratio 비율은 유지하고 8의 배수로 맞춤.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv_once() -> None:
    """python-dotenv 가 있으면 .env 를 읽어 os.environ 에 채운다(있을 때만)."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    env_path = ROOT / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def _as_bool(v: str | None, default: bool) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on", "y")


@dataclass
class ComfyConfig:
    host: str = "127.0.0.1"
    port: int = 8188
    enable_video: bool = True
    txt2img_workflow: Path = ROOT / "workflows" / "txt2img_api.json"
    img2video_workflow: Path = ROOT / "workflows" / "img2video_api.json"
    timeout: float = 600.0
    fixed_seed: int | None = None
    max_dim: int = 0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws"


def load_config() -> ComfyConfig:
    _load_dotenv_once()
    seed_env = os.environ.get("COMFY_SEED", "").strip()
    return ComfyConfig(
        host=os.environ.get("COMFY_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=int(os.environ.get("COMFY_PORT", "8188") or "8188"),
        enable_video=_as_bool(os.environ.get("COMFY_ENABLE_VIDEO"), True),
        txt2img_workflow=Path(os.environ.get(
            "COMFY_TXT2IMG_WORKFLOW", str(ROOT / "workflows" / "txt2img_api.json"))),
        img2video_workflow=Path(os.environ.get(
            "COMFY_IMG2VIDEO_WORKFLOW", str(ROOT / "workflows" / "img2video_api.json"))),
        timeout=float(os.environ.get("COMFY_TIMEOUT", "600") or "600"),
        fixed_seed=int(seed_env) if seed_env.lstrip("-").isdigit() else None,
        max_dim=int(os.environ.get("COMFY_MAX_DIM", "0") or "0"),
    )
