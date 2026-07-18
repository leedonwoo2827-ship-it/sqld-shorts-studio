"""통합 요약노트(책 합본) — 여러 번들의 chNN_summary.md 를 공식 출제기준(taxonomy)
뼈대로 한 권으로 재정리한다.

흐름: 수집 → (맵) 배치마다 세부항목으로 분류·통합 → (리듀스) 세부항목별 최종 정리 →
taxonomy 순서(과목→주요항목→세부항목)로 조립 + 기출 색인(출처 회차·번호) 부록 → Markdown/HTML.

LLM 은 활성 공급자(codex/agy)를 summary._llm 로 호출한다. 100개 번들도 배치로 처리한다.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from app import bundles
from . import script_prompt, taxonomy
from .summary import _llm, generate_summary_note

BATCH_CHARS = 12000
BOOK_DIR = bundles.ASSETS_DIR / "_book"


# ----------------------------- 수집 -----------------------------
def _summary_path(name: str) -> Path | None:
    root = bundles.bundle_path(name)
    chap = bundles._chap(root)
    if not chap:
        return None
    p = root / "draft" / f"ch{chap}_summary.md"
    return p if p.exists() else None


def _read_bundle(name: str) -> dict:
    """번들 하나의 (subject, chapter, title, summary_text, problems[]) 로드."""
    root = bundles.bundle_path(name)
    sp = bundles.find_script(root)
    subject = title = ""
    chapter = 0
    problems: list[dict] = []
    if sp:
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
            subject = data.get("subject") or ""
            title = data.get("title") or ""
            chapter = int(data.get("chapter") or 0)
            for sc in data.get("scenes") or []:
                sl = sc.get("slide") or {}
                if sl.get("kind") == "answer":
                    problems.append({
                        "source": str(sl.get("source") or "").strip(),
                        "question": (sl.get("question") or "").strip(),
                        "explanation": (sl.get("explanation") or "").strip(),
                    })
        except Exception:
            pass
    smp = _summary_path(name)
    summary_text = smp.read_text(encoding="utf-8") if smp else ""
    return {"bundle": name, "subject": subject, "chapter": chapter,
            "title": title, "summary": summary_text, "problems": problems}


def collect_overview() -> dict:
    """전체 번들 개요(과목/챕터/요약 유무) — [5 요약노트] 탭 진입 시 목록용."""
    rows = []
    for name in bundles.list_bundles():
        d = _read_bundle(name)
        rows.append({"bundle": name, "subject": d["subject"] or "(미지정)",
                     "chapter": d["chapter"], "title": d["title"],
                     "has_summary": bool(d["summary"]),
                     "problem_count": len(d["problems"])})
    rows.sort(key=lambda r: (r["subject"], r["chapter"]))
    subjects = sorted({r["subject"] for r in rows})
    return {"bundles": rows, "total": len(rows), "subjects": subjects,
            "with_summary": sum(1 for r in rows if r["has_summary"])}


# ----------------------------- 분류/파싱 -----------------------------
def _batch(items: list[dict], max_chars: int) -> list[list[dict]]:
    out, cur, cur_len = [], [], 0
    for it in items:
        t = it.get("summary") or ""
        if cur and cur_len + len(t) > max_chars:
            out.append(cur)
            cur, cur_len = [], 0
        cur.append(it)
        cur_len += len(t)
    if cur:
        out.append(cur)
    return out


def _batch_text(items: list[dict]) -> str:
    parts = []
    for it in items:
        head = f"[챕터 {it['chapter']} · {it['title']}]".strip()
        parts.append(f"{head}\n{it['summary']}")
    return "\n\n".join(parts)


def _parse_topic_sections(md: str, topics: list[str]) -> dict[str, str]:
    """LLM 출력의 '### <세부항목>' 섹션을 topic→본문 dict 로 파싱. 매칭 안되면 '기타'."""
    out: dict[str, list[str]] = defaultdict(list)
    cur = None
    tmap = {t.lower(): t for t in topics}
    for line in (md or "").splitlines():
        m = re.match(r"^#{2,4}\s+(.*)$", line.strip())
        if m:
            head = m.group(1).strip()
            cur = tmap.get(head.lower())
            if cur is None:  # 부분일치 폴백
                for t in topics:
                    if t.lower() in head.lower() or head.lower() in t.lower():
                        cur = t
                        break
            if cur is None:
                cur = "기타"
            continue
        if cur is not None and line.strip():
            out[cur].append(line.rstrip())
    return {k: "\n".join(v).strip() for k, v in out.items() if "".join(v).strip()}


# ----------------------------- 출처(기출) 색인 -----------------------------
def _topic_core(topic: str) -> str:
    """세부항목에서 매칭용 핵심어 추출: 괄호·꼬리표(절/문/의 이해) 제거."""
    t = re.sub(r"\(.*?\)", "", topic)
    t = re.sub(r"(절|문|의 이해)\s*$", "", t).strip()
    return t


def _match_sources(data: list[dict], topics: list[str]) -> dict[str, list[str]]:
    """세부항목별 관련 기출(출처) — 문제 질문/해설에 핵심어가 있으면 매칭(best-effort)."""
    res: dict[str, list[str]] = defaultdict(list)
    cores = [(t, _topic_core(t)) for t in topics]
    for d in data:
        for p in d["problems"]:
            src = p.get("source") or ""
            if not src:
                continue
            hay = (p.get("question", "") + " " + p.get("explanation", ""))
            for t, core in cores:
                if core and core in hay and src not in res[t]:
                    res[t].append(src)
    return res


def _source_index(data: list[dict]) -> str:
    """기출 색인 부록: 과목→챕터별로 각 문제의 출처·질문을 그대로 나열(정확)."""
    by_subject: dict[str, list[dict]] = defaultdict(list)
    for d in data:
        by_subject[d["subject"] or "(미지정)"].append(d)
    lines = ["## 부록 · 기출 색인 (출처)"]
    for subj in sorted(by_subject):
        lines.append(f"\n### {subj}")
        for d in sorted(by_subject[subj], key=lambda x: x["chapter"]):
            if not d["problems"]:
                continue
            lines.append(f"\n**{d['title'] or ('챕터 ' + str(d['chapter']))}**")
            for p in d["problems"]:
                src = p.get("source") or "-"
                q = (p.get("question") or "").strip()
                q = (q[:60] + "…") if len(q) > 60 else q
                lines.append(f"- {src} — {q}")
    return "\n".join(lines)


# ----------------------------- 조립 -----------------------------
def _assemble_md(title: str, tax: dict | None, topic_final: dict[str, str],
                 topic_sources: dict[str, list[str]], data: list[dict],
                 stamp: str) -> str:
    lines = [f"# {title}", f"_{stamp} · 통합 요약노트_", ""]
    used = set()
    if tax:
        # 목차
        lines.append("## 목차")
        for subj in tax.get("subjects") or []:
            lines.append(f"- {subj.get('name')}")
            for cat in subj.get("categories") or []:
                lines.append(f"  - {cat.get('name')}")
        lines.append("")
        # 본문 (과목→주요항목→세부항목 순)
        for subj in tax.get("subjects") or []:
            lines.append(f"\n# {subj.get('name')}")
            for cat in subj.get("categories") or []:
                lines.append(f"\n## {cat.get('name')}")
                for topic in cat.get("topics") or []:
                    body = topic_final.get(topic)
                    lines.append(f"\n### {topic}")
                    if body:
                        lines.append(body)
                        used.add(topic)
                    else:
                        lines.append("_(해당 문제 없음)_")
                    srcs = topic_sources.get(topic) or []
                    if srcs:
                        lines.append(f"\n> 관련 기출: {', '.join(srcs[:12])}")
    else:
        # taxonomy 없으면 세부항목 키 순서대로
        for topic, body in topic_final.items():
            lines.append(f"\n## {topic}")
            lines.append(body)
            used.add(topic)
    # 기타(분류 안 된 개념)
    etc = topic_final.get("기타")
    if etc and "기타" not in used:
        lines.append("\n# 기타")
        lines.append(etc)
    # 기출 색인 부록
    lines.append("\n\n" + _source_index(data))
    return "\n".join(lines)


# ----------------------------- MD → HTML -----------------------------
def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(s: str) -> str:
    s = _esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def _md_to_html(md: str, title: str) -> str:
    body: list[str] = []
    in_ul = False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            body.append("</ul>")
            in_ul = False

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            close_ul()
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            close_ul()
            lv = len(m.group(1))
            body.append(f"<h{lv}>{_inline(m.group(2))}</h{lv}>")
            continue
        if line.lstrip().startswith(("- ", "* ")):
            if not in_ul:
                body.append("<ul>")
                in_ul = True
            body.append(f"<li>{_inline(line.lstrip()[2:])}</li>")
            continue
        if line.lstrip().startswith("> "):
            close_ul()
            body.append(f"<blockquote>{_inline(line.lstrip()[2:])}</blockquote>")
            continue
        close_ul()
        body.append(f"<p>{_inline(line)}</p>")
    close_ul()
    css = (
        "body{font-family:'Malgun Gothic',Pretendard,system-ui,sans-serif;max-width:820px;"
        "margin:40px auto;padding:0 20px;line-height:1.7;color:#1a1a2e}"
        "h1{border-bottom:3px solid #213183;padding-bottom:6px;margin-top:1.6em;color:#213183}"
        "h2{border-bottom:1px solid #ccd;padding-bottom:4px;margin-top:1.4em;color:#0075de}"
        "h3{margin-top:1.2em;color:#333}"
        "ul{margin:.4em 0 .9em}li{margin:.2em 0}"
        "blockquote{margin:.4em 0;padding:.3em .8em;border-left:3px solid #0075de;"
        "background:#eef4fc;color:#555;font-size:.92em}"
        "code{background:#eef4fc;color:#0075de;padding:1px 5px;border-radius:4px}"
        "@media print{body{max-width:none;margin:0}}"
    )
    return (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            f"<title>{_esc(title)}</title><style>{css}</style></head>"
            f"<body>{''.join(body)}</body></html>")


# ----------------------------- 메인 -----------------------------
def build_summary_book(
    *,
    model: Optional[str] = None,
    auto_generate_missing: bool = False,
    on_progress: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    def p(msg: str) -> None:
        if on_progress:
            try:
                on_progress(msg)
            except Exception:
                pass

    names = bundles.list_bundles()
    if auto_generate_missing:
        for name in names:
            if _summary_path(name) is None and bundles.find_script(bundles.bundle_path(name)):
                p(f"요약 없는 번들 생성: {name}")
                try:
                    res = generate_summary_note(bundles.bundle_path(name), model=model)
                    root = bundles.bundle_path(name)
                    chap = bundles._chap(root)
                    (root / "draft").mkdir(parents=True, exist_ok=True)
                    (root / "draft" / f"ch{chap}_summary.md").write_text(res.get("text", ""), encoding="utf-8")
                except Exception as exc:  # noqa: BLE001
                    p(f"  건너뜀({name}): {exc}")

    data = [d for d in (_read_bundle(n) for n in names) if d["summary"]]
    skipped = [n for n in names if _read_bundle(n)["summary"] == ""]
    if not data:
        raise ValueError("요약노트가 있는 번들이 없습니다. 먼저 번들별 요약노트를 만드세요.")
    data.sort(key=lambda d: (d["subject"], d["chapter"]))

    subject = data[0]["subject"]
    tax = taxonomy.load_taxonomy(subject)
    topics = taxonomy.topic_names(tax) if tax else []

    # MAP: 배치마다 세부항목 분류·통합
    batches = _batch(data, BATCH_CHARS)
    topic_frag: dict[str, list[str]] = defaultdict(list)
    for i, batch in enumerate(batches):
        p(f"배치 {i + 1}/{len(batches)} 분류·통합 중… ({len(batch)}챕터)")
        try:
            out = _llm(script_prompt.classify_merge_prompt(topics or ["기타"], _batch_text(batch)), model)
        except Exception as exc:  # noqa: BLE001
            p(f"  배치 {i + 1} 실패 — 건너뜀 ({exc})")
            continue
        for topic, body in _parse_topic_sections(out, topics or []).items():
            topic_frag[topic].append(body)

    # REDUCE: 세부항목별 최종 정리(조각 많/길면 재통합)
    topic_final: dict[str, str] = {}
    keys = list(topic_frag.keys())
    for j, topic in enumerate(keys):
        merged = "\n".join(topic_frag[topic]).strip()
        if len(topic_frag[topic]) > 1 and len(merged) > 1500:
            p(f"세부항목 정리 {j + 1}/{len(keys)}: {topic}")
            try:
                merged = _llm(script_prompt.topic_polish_prompt(topic, merged), model).strip() or merged
            except Exception:
                pass
        topic_final[topic] = merged

    topic_sources = _match_sources(data, topics)
    title = f"{subject or '학습'} 통합 요약노트"
    stamp = datetime.now().strftime("%Y-%m-%d")
    md = _assemble_md(title, tax, topic_final, topic_sources, data, stamp)
    html = _md_to_html(md, title)

    BOOK_DIR.mkdir(parents=True, exist_ok=True)
    md_path = BOOK_DIR / "요약노트_통합.md"
    html_path = BOOK_DIR / "요약노트_통합.html"
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    p("완료")

    return {
        "ok": True, "text": md,
        "saved_md": md_path.name, "saved_html": html_path.name,
        "dir": str(BOOK_DIR),
        "subjects": sorted({d["subject"] for d in data}),
        "chapters_included": len(data),
        "chapters_skipped": len(skipped),
    }
