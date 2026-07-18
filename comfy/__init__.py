"""ComfyUI 연동 패키지 (FlowGenie 대체).

로컬(또는 LAN) ComfyUI 서버에 API-format 워크플로우를 제출해 씬 이미지를 생성하고,
선택적으로 이미지→영상(img2video) 클립을 생성한다. 서버는 사용자가 직접 구동하며,
이 패키지는 HTTP/WebSocket API 로 연결만 한다.

핵심 모듈:
- config      : COMFY_HOST/PORT 등 환경설정
- comfy_client: /prompt, /history, /view, /upload/image, /ws 저수준 클라이언트
- workflow    : API-format 워크플로우 로드 + 노드 주입(프롬프트/시드/해상도/파일명)
- generate    : 번들 단위로 씬 이미지(+클립) 생성 (하이브리드 폴백 포함)
- check       : 연결/능력 점검 CLI (python -m comfy.check)
"""
from __future__ import annotations

from .config import ComfyConfig, load_config

__all__ = ["ComfyConfig", "load_config"]
