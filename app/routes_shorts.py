"""SQLD 말하는-아바타 쇼츠 — 웹 GUI용 라우트 (1개씩 생성).

/api/mf/shorts/options   : 문제 목록 + 얼굴/음성 코드
/api/mf/shorts/generate  : {problem, face, voice} → 백그라운드 잡 시작
/api/mf/shorts/jobs/{id} : 진행상황 폴링
/api/mf/shorts/file/{n}  : 결과 mp4 서빙
"""
from __future__ import annotations

import json
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
    problem: int
    face: str = "F2"
    voice: str = "F2"
    min_res: int = 384


def _load_problem(no: int) -> tuple[dict, str]:
    p = SAMPLES / f"sqld_{no:02d}.json"
    if not p.is_file():
        raise HTTPException(404, f"문제 {no} JSON 없음")
    data = json.loads(p.read_text(encoding="utf-8"))
    prob = data["blocks"][0]
    prob["chapter"] = data.get("chapter")
    return prob, data.get("subject") or "SQLD"


@router.get("/shorts/options")
def options() -> dict:
    problems = []
    for p in sorted(SAMPLES.glob("sqld_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        b = d["blocks"][0]
        problems.append({"no": b.get("number"), "question": b.get("question", "")[:40]})
    faces = [c for c in ALL_CODES if (VOICES / f"{c}.png").is_file()]
    return {"problems": problems, "faces": faces, "voices": ALL_CODES}


def _run(job, req: GenReq) -> None:
    from mp4maker.talking_shorts import build_talking_short
    reg = get_registry()
    job.status = "running"
    try:
        prob, subject = _load_problem(req.problem)
        out = OUT / f"sqld_short_{req.problem:02d}.mp4"
        work = OUT / "_work" / f"{req.problem:02d}"
        build_talking_short(prob, face_code=req.face, voice_code=req.voice,
                            out_mp4=out, workdir=work, subject=subject,
                            min_res=req.min_res, log=lambda m: (job.add_log(m), setattr(job, "stage", m)))
        reg.finish(job, status="done", result={"file": out.name})
    except Exception as exc:  # noqa: BLE001
        job.add_log(f"[오류] {exc}")
        reg.finish(job, status="error", error=str(exc))


@router.post("/shorts/generate")
def generate(req: GenReq) -> dict:
    if req.face not in ALL_CODES or req.voice not in ALL_CODES:
        raise HTTPException(400, "잘못된 얼굴/음성 코드")
    job = get_registry().create(kind="short", bundle=f"문제{req.problem}", total=1)
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
