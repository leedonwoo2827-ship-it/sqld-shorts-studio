"""ComfyUI 저수준 HTTP/WebSocket 클라이언트.

표준 라이브러리(urllib)만으로 REST 를 호출하고, WebSocket 진행 대기는
websocket-client 가 있으면 사용, 없으면 /history 폴링으로 폴백한다.

엔드포인트:
    POST /prompt               잡 제출 -> {"prompt_id": ...}
    GET  /history/{prompt_id}  실행 결과(노드별 outputs)
    GET  /view?filename&subfolder&type  산출 파일 바이트
    POST /upload/image         입력 이미지 업로드(멀티파트) -> {"name": ...}
    GET  /object_info          설치된 노드 목록(능력 감지용)
    GET  /system_stats         서버 상태(연결 점검용)
    WS   /ws?clientId=<uuid>   진행 스트림
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass

from .config import ComfyConfig


class ComfyError(RuntimeError):
    pass


@dataclass
class OutputFile:
    filename: str
    subfolder: str
    type: str          # "output" | "temp"
    kind: str          # "images" | "gifs" | "videos"


class ComfyClient:
    def __init__(self, cfg: ComfyConfig):
        self.cfg = cfg
        self.client_id = str(uuid.uuid4())

    # ------------------------- 저수준 HTTP -------------------------
    def _get(self, path: str, timeout: float = 15.0) -> bytes:
        url = f"{self.cfg.base_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except urllib.error.URLError as exc:
            raise ComfyError(f"GET {path} 실패: {exc}") from exc

    def _get_json(self, path: str, timeout: float = 15.0) -> dict:
        return json.loads(self._get(path, timeout=timeout).decode("utf-8"))

    def _post_json(self, path: str, body: dict, timeout: float = 30.0) -> dict:
        url = f"{self.cfg.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise ComfyError(f"POST {path} HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ComfyError(f"POST {path} 실패: {exc}") from exc

    # ------------------------- 연결/능력 점검 -------------------------
    def ping(self) -> dict:
        """서버 상태. 실패 시 ComfyError."""
        return self._get_json("/system_stats")

    def object_info(self) -> dict:
        return self._get_json("/object_info", timeout=30.0)

    def available_node_classes(self) -> set[str]:
        try:
            return set(self.object_info().keys())
        except ComfyError:
            return set()

    # ------------------------- 잡 제출/대기 -------------------------
    def queue_prompt(self, workflow: dict) -> str:
        body = {"prompt": workflow, "client_id": self.client_id}
        res = self._post_json("/prompt", body)
        node_errors = res.get("node_errors") or {}
        if node_errors:
            raise ComfyError(f"워크플로우 노드 오류: {json.dumps(node_errors, ensure_ascii=False)}")
        pid = res.get("prompt_id")
        if not pid:
            raise ComfyError(f"prompt_id 없음: {res}")
        return pid

    def history(self, prompt_id: str) -> dict:
        data = self._get_json(f"/history/{prompt_id}")
        return data.get(prompt_id, {})

    def wait(self, prompt_id: str, timeout: float | None = None) -> dict:
        """완료까지 대기하고 history 레코드를 반환. WS 우선, 없으면 폴링."""
        timeout = timeout or self.cfg.timeout
        if _has_websocket():
            try:
                return self._wait_ws(prompt_id, timeout)
            except Exception:
                pass  # WS 실패 -> 폴링 폴백
        return self._wait_poll(prompt_id, timeout)

    def _wait_ws(self, prompt_id: str, timeout: float) -> dict:
        import websocket  # type: ignore
        ws = websocket.WebSocket()
        ws.connect(f"{self.cfg.ws_url}?clientId={self.client_id}", timeout=timeout)
        ws.settimeout(timeout)
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                msg = ws.recv()
                if not isinstance(msg, str):
                    continue  # 바이너리 프레임 = 미리보기 이미지(무시)
                m = json.loads(msg)
                if m.get("type") == "executing":
                    d = m.get("data") or {}
                    if d.get("node") is None and d.get("prompt_id") == prompt_id:
                        break
        finally:
            try:
                ws.close()
            except Exception:
                pass
        rec = self.history(prompt_id)
        if not rec:
            raise ComfyError(f"완료 후 history 비어 있음: {prompt_id}")
        return rec

    def _wait_poll(self, prompt_id: str, timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rec = self.history(prompt_id)
            if rec and rec.get("outputs"):
                status = (rec.get("status") or {}).get("status_str")
                if status == "error":
                    raise ComfyError(f"실행 오류(prompt {prompt_id}): {rec.get('status')}")
                return rec
            time.sleep(1.0)
        raise ComfyError(f"타임아웃({timeout:.0f}s): prompt {prompt_id}")

    # ------------------------- 산출물 -------------------------
    @staticmethod
    def outputs_of(history_record: dict) -> list[OutputFile]:
        files: list[OutputFile] = []
        outputs = (history_record or {}).get("outputs") or {}
        for node_out in outputs.values():
            for kind in ("images", "gifs", "videos"):
                for f in node_out.get(kind, []) or []:
                    files.append(OutputFile(
                        filename=f.get("filename", ""),
                        subfolder=f.get("subfolder", ""),
                        type=f.get("type", "output"),
                        kind=kind,
                    ))
        return files

    def download(self, f: OutputFile) -> bytes:
        qs = urllib.parse.urlencode(
            {"filename": f.filename, "subfolder": f.subfolder, "type": f.type})
        return self._get(f"/view?{qs}", timeout=120.0)

    # ------------------------- 입력 이미지 업로드 -------------------------
    def upload_image(self, data: bytes, filename: str, overwrite: bool = True) -> str:
        """멀티파트로 입력 이미지를 올린다. 저장된 name 반환(LoadImage.image 에 사용)."""
        boundary = f"----comfy{uuid.uuid4().hex}"
        parts: list[bytes] = []

        def field(name: str, value: str) -> None:
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            parts.append(f"{value}\r\n".encode())

        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode())
        parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
        parts.append(data)
        parts.append(b"\r\n")
        field("overwrite", "true" if overwrite else "false")
        parts.append(f"--{boundary}--\r\n".encode())
        payload = b"".join(parts)

        req = urllib.request.Request(
            f"{self.cfg.base_url}/upload/image", data=payload,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(req, timeout=60.0) as r:
                res = json.loads(r.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise ComfyError(f"이미지 업로드 실패: {exc}") from exc
        name = res.get("name") or filename
        sub = res.get("subfolder") or ""
        return f"{sub}/{name}" if sub else name


def _has_websocket() -> bool:
    try:
        import websocket  # noqa: F401  # websocket-client
        return True
    except Exception:
        return False
