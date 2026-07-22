# SQLD 쇼츠 · 말하는 아바타 설치·연동 가이드 (초보자용)

> 목표: **세로 9:16 SQLD 문제 쇼츠**에 **좌측에서 말하는(립싱크) 아바타** 넣기.

### 제작 기준 PC (가명: **STUDIO-4070**)
| 항목 | 사양 |
|---|---|
| CPU | AMD Ryzen 9 7945HX (16코어 / 32스레드) |
| GPU | NVIDIA GeForce **RTX 4070 Laptop · VRAM 8GB** |
| RAM | 32GB |
| OS | Windows 11 |
| 드라이버 | **610.62 이상**(NVIDIA Studio, ComfyUI PyTorch가 580+ 요구) |

→ 판정: **얼굴 크롭 립싱크 쇼츠 제작에 충분.** 아바타가 화면 좌측에 작게 들어가므로
저해상도로 돌려도 되고, 립싱크 VRAM 사용도 8GB 안에서 감당 가능.
⚠️ 드라이버가 580 미만이면 ComfyUI 첫 실행이 `0xC0000005`로 크래시함 → 드라이버 먼저 업데이트.

전체 그림:
```
문제 JSON ─▶ 슬라이드(9:16, 해설상단/정답하단, 좌측 아바타 자리) ─┐
TTS 음성 ────────────────────────────────────────────────────────┤─▶ ffmpeg 합성 ─▶ 9:16 MP4
아바타 사진(ComfyUI 생성) + 음성 ─▶ [ComfyUI 립싱크] ─▶ 말하는 얼굴 클립 ─┘  (좌하단 오버레이)
```

---

## 0. 큰 그림: 무엇을 왜 까는가
이 앱(compy-ui)은 **이미지·립싱크 같은 무거운 AI는 “ComfyUI”라는 별도 프로그램에 맡기고**,
HTTP로 불러 쓰는 구조입니다. 그래서 3개만 준비하면 됩니다.

| # | 준비물 | 용도 | 상태 |
|---|---|---|---|
| 1 | **Python 3.12** | 앱·TTS·슬라이드 | ✅ 이미 설치됨 |
| 2 | **FFmpeg** | 영상 합성 | ✅ 이미 설치됨 (`winget install Gyan.FFmpeg`) |
| 3 | **ComfyUI Desktop** + 립싱크 노드/모델 | 아바타 얼굴 생성 + 립싱크 | ⬜ 이번에 설치 |

> 3번이 없어도 **정지 아바타 + 음성 쇼츠**는 바로 됩니다. 3번을 추가하면 **입이 움직입니다.**

---

## 1. 앱 준비 (setup.bat)
프로젝트 폴더에서 **`setup.bat` 더블클릭** (최초 1회).
→ 가상환경 생성 + 의존성 설치 + **TTS 모델 다운로드** + ffmpeg/ComfyUI 연결 점검.

---

## 2. ComfyUI 설치 — **두 가지 방법 중 택1**

### 방법 A) 설치기(추천, 가장 쉬움)
1. **https://comfy.org/download/** 접속 → Windows용 **ComfyUI Desktop** 설치기(.exe) 다운로드·실행.
   - (같은 것: [Comfy-Org/Comfy-Desktop 릴리스](https://github.com/Comfy-Org/Comfy-Desktop))
2. 설치 후 실행하면 ComfyUI가 자체 GPU 환경으로 뜹니다(기본 주소 `http://127.0.0.1:8188`).
3. 최신 Desktop 은 **ComfyUI Manager**가 기본 포함. 없으면 방법 B의 Manager 설치만 따라 하세요.

### 방법 B) 폴더에 직접 배치(포터블/수동 — 예전에 하시던 방식)
> “어디 폴더 만들어서 거기에 배치” 하고 싶을 때. HuggingFace에서 모델을 받아 폴더에 넣습니다.

1. 원하는 드라이브에 폴더 생성(예: `D:\ComfyUI`).
2. **ComfyUI 포터블** 받기: [Comfy-Org/ComfyUI 릴리스](https://github.com/comfy-org/comfyui) 의
   `ComfyUI_windows_portable` 압축을 `D:\ComfyUI` 에 풀기 → `run_nvidia_gpu.bat` 로 실행.
3. **ComfyUI Manager** 설치: `D:\ComfyUI\ComfyUI\custom_nodes` 에서
   ```
   git clone https://github.com/Comfy-Org/ComfyUI-Manager
   ```
   ComfyUI 재시작하면 화면에 **Manager** 버튼이 생깁니다.

---

## 3. 립싱크 엔진 설치 (ComfyUI 확장 프로그램 관리자로 점-클릭)

ComfyUI 노드 화면 우측 상단 **[확장 프로그램 관리]** 클릭 → **커스텀 노드 관리자** 가 열림.
상단 검색창에 **`lip`** 입력 → 립싱크 관련 노드 목록이 뜬다.

> 참고: `SadTalker` 는 이 레지스트리에 **미등록**이라 검색해도 안 나온다(정상). `lip` 으로 찾을 것.

### ✅ 설치할 것: **ComfyUI Sonic** (첫 성공용 · 권장)
검색 결과 중 **`ComfyUI Sonic`**(제작자 sbcode, 다운로드 1위) 카드의 **[설치]** → 설치 후 **[Restart]**.
- 설명: *"오디오 mp3 + 이미지 → 립싱크 영상 생성"* — 우리가 원하는 **사진 1장 + 음성 → 말하는 얼굴** 그대로.
- 사진 1장이면 되어 초보자에 최적. 첫 사용 시 모델 몇 GB 자동 다운로드(정상).
- 아바타가 좌측에 작게 들어가므로 **저해상도로 돌려 8GB 안에서 처리**.

### ⛔ 고르면 안 되는 것 (같은 `lip` 검색 결과)
| 노드 | 이유 |
|---|---|
| ComfyUI LatentSync Enhanced | **24GB VRAM** 요구 → 8GB 초과 |
| comfyui-sync-lipsync-node / Replicate API NM / X-Dub | **유료 클라우드 API** (로컬 아님) |
| InfiniteTalk-Native / OmniAvatar | WAN 등 무거움 → 8GB 빠듯 |
| Wav2Lip Node | 사진 1장 불가(**영상 입력 필요**) — Sonic 실패 시 예비 |

### (예비) Sonic이 VRAM 부족(OOM)이면
- 해상도/프레임 낮춰 재시도, 또는 **Wav2Lip Node** + 아바타 정지영상(루프) 조합으로 폴백.

---

## 4. 아바타 얼굴 만들기 (ComfyUI에서 1장)
같은 ComfyUI에서 **한국인 강사 얼굴/상반신** 1장을 생성:
- 세로 구도(예 832×1216), 정면, 단색/초록 배경(합성 쉬움), 실사 SDXL 체크포인트.
- 프롬프트 예: `korean female instructor, professional, upper body, front facing, plain studio background, neutral expression, high detail`
- 결과를 `assets/avatar/instructor.png` 로 저장. (배경 제거 노드로 투명 PNG면 더 깔끔)
> 사진을 직접 준비해도 됩니다(Sonic은 사진 1장이면 충분).

---

## 5. 앱과 ComfyUI 연결
`.env` 파일(없으면 `.env.example` 복사)에서 주소만 맞으면 끝:
```
COMFY_HOST=127.0.0.1
COMFY_PORT=8188
```
연결 확인: `.venv\Scripts\python -m comfy.check`

---

## 6. 실행 순서 (요약 — 이대로 클릭)
```
① setup.bat            (최초 1회: 앱 + TTS)
② ComfyUI 실행          (Desktop 앱 또는 run_nvidia_gpu.bat)
③ 확장 프로그램 관리 → `lip` 검색 → ComfyUI Sonic 설치 + Restart  (최초 1회)
④ run.bat              (브라우저 http://localhost:8830 자동 열림)
```
- 아바타/음성 없이 **지금 결과 먼저 보기**(한 문제=한 영상, 폴더 일괄):
  `python scripts/make_shorts.py samples/sqld_shorts -o out/shorts`

---

## 7. 립싱크 클립을 영상에 넣는 지점 (개발 메모)
립싱크 결과 클립(배경 초록 크로마키 `0x00FF00` 또는 알파)은 이미 파이프라인이 받습니다:
```python
from mp4maker.shorts import build_short  # avatar_clip_* / audio_* 인자
```
- 세그먼트 길이는 음성 길이에 **자동 동기**.
- 아바타 클립은 좌측 컬럼 폭으로 스케일 후 **좌하단** 오버레이.
- 낭독 텍스트: 문제 씬=문제/보기, 정답 씬=각 문항 `explanation_speech`(발음 변환 반영).

> ComfyUI 립싱크 **워크플로 JSON + 앱 자동호출 배선**은 다음 작업으로 붙입니다(그러면 버튼 한 번에
> 10편 자동 생성). 현재는 정지 아바타까지 완성·검증됨.

---

## 출처
- [Comfy Desktop 다운로드](https://comfy.org/download/) · [Comfy-Org/Comfy-Desktop](https://github.com/Comfy-Org/Comfy-Desktop)
- [ComfyUI-Manager](https://github.com/Comfy-Org/ComfyUI-Manager)
- [MuseTalk (GitHub)](https://github.com/TMElyralab/MuseTalk) · [MuseTalk 모델(HuggingFace)](https://huggingface.co/TMElyralab/MuseTalk)
- [ComfyUI-MuseTalk_FSH](https://github.com/AIFSH/ComfyUI-MuseTalk_FSH) · [chaojie/ComfyUI-MuseTalk](https://github.com/chaojie/ComfyUI-MuseTalk)
- ComfyUI Sonic (커스텀 노드 관리자에서 `lip` 검색, 제작자 sbcode) · [SadTalker(참고)](https://github.com/OpenTalker/SadTalker)
- [오픈소스 립싱크 비교 2026](https://lipsync.com/blog/open-source-lip-sync) · [비교(crazyrouter)](https://crazyrouter.com/en/blog/ai-lip-sync-tools-comparison-2026)
