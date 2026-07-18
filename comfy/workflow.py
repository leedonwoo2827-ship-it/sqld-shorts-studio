"""API-format 워크플로우 로드 + 노드 주입.

ComfyUI 의 "Save (API Format)" 로 내보낸 JSON 은 노드 id 를 키로 갖는 flat dict 이며,
각 엔트리는 {"class_type": ..., "inputs": {...}} 구조다. inputs 값은 리터럴이거나
["<source_node_id>", <output_index>] 형태의 링크다.

노드 id 는 워크플로우마다 다르므로, 클래스와 그래프 링크를 따라 자동 탐지한다.
자동 탐지가 틀리면 workflows/<name>.map.json 으로 노드 id 를 직접 지정할 수 있다:

    txt2img_api.map.json:
        {"positive": "6", "seed": "3", "latent": "5", "save": "9"}
    img2video_api.map.json:
        {"load_image": "10", "seed": "3", "save": "12"}
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

_KSAMPLER_CLASSES = {"KSampler", "KSamplerAdvanced", "SamplerCustom", "SamplerCustomAdvanced"}
_LATENT_CLASSES = {"EmptyLatentImage", "EmptySD3LatentImage", "EmptyLatentImageAdvanced"}
_TEXT_ENCODE_CLASSES = {"CLIPTextEncode", "CLIPTextEncodeSDXL", "CLIPTextEncodeFlux"}
_SAVE_IMAGE_CLASSES = {"SaveImage", "SaveImageWebsocket"}
_LOAD_IMAGE_CLASSES = {"LoadImage", "LoadImageOutput"}
_VIDEO_SAVE_CLASSES = {
    "VHS_VideoCombine", "SaveWEBM", "SaveAnimatedWEBP", "SaveAnimatedPNG",
    "SaveVideo", "CreateVideo",
}
_SEED_KEYS = ("seed", "noise_seed")


def load_api_workflow(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(
            f"워크플로우 JSON 없음: {p}\n"
            f"ComfyUI 에서 'Save (API Format)' 로 내보내 이 경로에 두세요.")
    data = json.loads(p.read_text(encoding="utf-8"))
    # UI 포맷(nodes[] 키)이 잘못 저장된 경우 방어
    if "nodes" in data and "prompt" not in data and not _looks_like_api(data):
        raise ValueError(
            f"{p.name} 은 UI 포맷 같습니다. ComfyUI 설정에서 Dev Mode 를 켜고 "
            f"'Save (API Format)' 로 다시 내보내세요.")
    if "prompt" in data and isinstance(data["prompt"], dict):
        data = data["prompt"]           # 일부 export 는 {"prompt": {...}} 로 감쌈
    return data


def _looks_like_api(data: dict) -> bool:
    return any(isinstance(v, dict) and "class_type" in v for v in data.values())


def load_override_map(workflow_path: str | Path) -> dict:
    p = Path(workflow_path)
    mp = p.with_suffix(".map.json")
    if mp.is_file():
        try:
            return json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _nodes_by_class(wf: dict, classes: set[str]) -> list[str]:
    return [nid for nid, node in wf.items()
            if isinstance(node, dict) and node.get("class_type") in classes]


def _first_by_class(wf: dict, classes: set[str]) -> str | None:
    ids = _nodes_by_class(wf, classes)
    return ids[0] if ids else None


def _link_target(value) -> str | None:
    """inputs 값이 ["node_id", idx] 링크면 node_id 를 반환."""
    if isinstance(value, list) and value and isinstance(value[0], (str, int)):
        return str(value[0])
    return None


def _find_positive_encode(wf: dict) -> str | None:
    """KSampler.positive 링크를 따라 positive CLIPTextEncode 노드 id 를 찾는다."""
    for sid in _nodes_by_class(wf, _KSAMPLER_CLASSES):
        pos = (wf[sid].get("inputs") or {}).get("positive")
        tgt = _link_target(pos)
        if tgt and tgt in wf and wf[tgt].get("class_type") in _TEXT_ENCODE_CLASSES:
            return tgt
    # 폴백: text 위젯이 있는 첫 인코더
    for nid in _nodes_by_class(wf, _TEXT_ENCODE_CLASSES):
        if "text" in (wf[nid].get("inputs") or {}):
            return nid
    return None


def _set_seed(wf: dict, node_id: str, seed: int) -> bool:
    inputs = wf[node_id].get("inputs") or {}
    for k in _SEED_KEYS:
        if k in inputs:
            inputs[k] = int(seed)
            return True
    return False


def inject_txt2img(wf: dict, *, prompt: str, seed: int,
                   width: int, height: int, filename_prefix: str,
                   override: dict | None = None) -> dict:
    """positive 프롬프트/시드/해상도/파일명 접두사를 주입한 새 워크플로우 dict 반환."""
    wf = copy.deepcopy(wf)
    override = override or {}

    pos_id = override.get("positive") or _find_positive_encode(wf)
    if not pos_id or pos_id not in wf:
        raise ValueError("positive 프롬프트 노드를 찾지 못함. .map.json 으로 'positive' 지정 필요.")
    wf[pos_id].setdefault("inputs", {})["text"] = prompt

    seed_id = override.get("seed") or _first_by_class(wf, _KSAMPLER_CLASSES)
    if seed_id and seed_id in wf:
        _set_seed(wf, seed_id, seed)

    latent_id = override.get("latent") or _first_by_class(wf, _LATENT_CLASSES)
    if latent_id and latent_id in wf:
        li = wf[latent_id].setdefault("inputs", {})
        if "width" in li:
            li["width"] = int(width)
        if "height" in li:
            li["height"] = int(height)

    save_id = override.get("save") or _first_by_class(wf, _SAVE_IMAGE_CLASSES)
    if save_id and save_id in wf:
        si = wf[save_id].setdefault("inputs", {})
        if "filename_prefix" in si or True:
            si["filename_prefix"] = filename_prefix
    return wf


def inject_img2video(wf: dict, *, image_name: str, seed: int,
                     filename_prefix: str, override: dict | None = None) -> dict:
    """LoadImage 에 업로드 이미지명을, 영상 저장 노드에 파일명 접두사를 주입."""
    wf = copy.deepcopy(wf)
    override = override or {}

    load_id = override.get("load_image") or _first_by_class(wf, _LOAD_IMAGE_CLASSES)
    if not load_id or load_id not in wf:
        raise ValueError("LoadImage 노드를 찾지 못함. .map.json 으로 'load_image' 지정 필요.")
    wf[load_id].setdefault("inputs", {})["image"] = image_name

    seed_id = override.get("seed") or _first_by_class(wf, _KSAMPLER_CLASSES)
    if seed_id and seed_id in wf:
        _set_seed(wf, seed_id, seed)

    save_id = override.get("save") or _first_by_class(wf, _VIDEO_SAVE_CLASSES)
    if save_id and save_id in wf:
        si = wf[save_id].setdefault("inputs", {})
        # VHS_VideoCombine 은 filename_prefix, 일부 노드는 filename 사용
        for key in ("filename_prefix", "filename"):
            if key in si:
                si[key] = filename_prefix
                break
        else:
            si["filename_prefix"] = filename_prefix
    return wf


def has_video_capability(available_classes: set[str],
                         img2video_workflow: str | Path | None = None) -> bool:
    """서버에 img2video 워크플로우가 요구하는 노드가 설치돼 있는지."""
    if img2video_workflow and Path(img2video_workflow).is_file():
        try:
            wf = load_api_workflow(img2video_workflow)
        except Exception:
            wf = {}
        needed = {n.get("class_type") for n in wf.values()
                  if isinstance(n, dict) and n.get("class_type")}
        if needed:
            return needed.issubset(available_classes)
    # 워크플로우가 없으면 대표적인 영상 노드 존재로 추정
    video_markers = _VIDEO_SAVE_CLASSES | {
        "SVD_img2vid_Conditioning", "WanImageToVideo", "LTXVImgToVideo",
        "CogVideoImageEncode",
    }
    return bool(video_markers & available_classes)
