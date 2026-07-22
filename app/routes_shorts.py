"""SQLD 말하는-아바타 쇼츠 — 웹 GUI용 라우트 (1개씩 생성).

/api/mf/shorts/options    : 얼굴/음성 코드 + 테스트용 샘플 목록
/api/mf/shorts/sample/{n} : 샘플 lesson JSON 내용(테스트 편의)
/api/mf/shorts/generate   : {problem, subject, label, face, voice} → 백그라운드 잡
/api/mf/shorts/jobs/{id}  : 진행상황 폴링
/api/mf/shorts/file/{n}   : 결과 mp4 서빙
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .jobs import get_registry

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples" / "sqld_shorts"
VOICES = ROOT / "assets" / "avatar" / "voices"
OUT = ROOT / "out" / "shorts"
ALL_CODES = ["M1", "M2", "M3", "M4", "M5", "F1", "F2", "F3", "F4", "F5"]

router = APIRouter()


class GenReq(BaseModel):
    problem: dict                 # 문제 블록(질문/보기/정답/해설/narration)
    subject: str = "SQLD"
    label: str = "01"             # 출력 파일명 라벨
    face: str = "F2"
    voice: str = "F2"
    min_res: int = 384


@router.get("/shorts/options")
def options() -> dict:
    faces = [c for c in ALL_CODES if (VOICES / f"{c}.png").is_file()]
    samples = sorted(p.name for p in SAMPLES.glob("*.json"))
    return {"faces": faces, "voices": ALL_CODES, "samples": samples}


@router.get("/shorts/sample/{name}")
def sample(name: str) -> dict:
    # 테스트 편의: 샘플 JSON 내용을 그대로 반환(프론트가 첨부파일처럼 사용)
    if not re.fullmatch(r"[\w.\-]+\.json", name):
        raise HTTPException(400, "bad name")
    p = SAMPLES / name
    if not p.is_file():
        raise HTTPException(404, "샘플 없음")
    return json.loads(p.read_text(encoding="utf-8"))


def _run(job, req: GenReq) -> None:
    from mp4maker.talking_shorts import build_talking_short
    reg = get_registry()
    job.status = "running"
    try:
        safe = re.sub(r"[^\w\-]", "_", req.label)[:60] or "short"
        out = OUT / f"{safe}.mp4"          # 예: sqld_0001_F2_F2.mp4
        work = OUT / "_work" / safe
        build_talking_short(req.problem, face_code=req.face, voice_code=req.voice,
                            out_mp4=out, workdir=work, subject=req.subject,
                            min_res=req.min_res,
                            log=lambda m: (job.add_log(m), setattr(job, "stage", m)))
        reg.finish(job, status="done", result={"file": out.name})
    except Exception as exc:  # noqa: BLE001
        job.add_log(f"[오류] {exc}")
        reg.finish(job, status="error", error=str(exc))


@router.post("/shorts/generate")
def generate(req: GenReq) -> dict:
    if req.face not in ALL_CODES or req.voice not in ALL_CODES:
        raise HTTPException(400, "잘못된 얼굴/음성 코드")
    if not isinstance(req.problem, dict) or not req.problem.get("question"):
        raise HTTPException(400, "문제 JSON에 question이 없습니다")
    job = get_registry().create(kind="short", bundle=req.label, total=1)
    threading.Thread(target=_run, args=(job, req), daemon=True).start()
    return {"job_id": job.job_id}


@router.get("/shorts/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = get_registry().get(job_id)
    if not job:
        raise HTTPException(404, "잡 없음")
    return job.to_dict()


@router.get("/shorts/file/{name}")
def serve(name: str):
    f = OUT / name
    if not f.is_file():
        raise HTTPException(404, "파일 없음")
    return FileResponse(str(f), media_type="video/mp4")


class PreviewReq(BaseModel):
    text: str
    voice: str = "F2"


@router.post("/shorts/tts_preview")
def tts_preview(req: PreviewReq):
    """음성+자막 탭: narration 텍스트를 슈퍼토닉으로 미리듣기(wav)."""
    from mp4maker.talking_shorts import tts_supertonic
    import uuid as _uuid
    if req.voice not in ALL_CODES:
        raise HTTPException(400, "잘못된 목소리 코드")
    prev = OUT / "_preview"
    prev.mkdir(parents=True, exist_ok=True)
    wav = prev / f"prev_{_uuid.uuid4().hex[:8]}.wav"
    try:
        tts_supertonic((req.text or "").strip()[:500], req.voice, wav)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"음성 생성 실패: {exc}")
    return FileResponse(str(wav), media_type="audio/wav")


class YtReq(BaseModel):
    problem: dict
    subject: str = "SQLD"


@router.post("/shorts/youtube")
def youtube(req: YtReq) -> dict:
    """최종 탭: 문제로 YouTube 제목/설명/해시태그 자동 생성(템플릿, LLM 불필요)."""
    p = req.problem or {}
    subj = req.subject or "SQLD"
    q = (p.get("question") or "").strip()
    ans = (p.get("answer") or "").strip()
    expl = (p.get("explanation") or "").strip()
    tags = p.get("tags") or []
    num = p.get("number")
    title = f"[{subj}] {q[:30]}{'…' if len(q) > 30 else ''} #shorts"
    hs = " ".join("#" + str(t).replace(" ", "") for t in tags)
    hashtags = (hs + f" #{subj} #자격증 #기출 #shorts #공부").strip()
    desc = (
        f"{subj} 기출 유형{f' · 문제 {num}' if num is not None else ''}\n\n"
        f"Q. {q}\n✅ 정답: {ans}\n\n💡 {expl}\n\n{hashtags}\n\n"
        f"— {subj} 개념을 쇼츠로 빠르게! 구독하면 매일 한 문제 🔔"
    )
    return {"title": title, "description": desc, "hashtags": hashtags}
