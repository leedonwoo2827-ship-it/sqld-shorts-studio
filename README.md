# compy-ui-mujejip — 문제집 → 강의/복습 영상 도구

**문제집(JSON) → 텍스트 슬라이드(요소 순차 등장 모션) → 음성/자막 → MP4**, 그리고
여러 회차의 해설을 모아 **공식 출제기준 순서의 통합 요약노트**까지 — 웹 화면 하나에서
버튼 몇 개로. 클라우드 없이, API 키 없이, 이 폴더 하나로 로컬 실행됩니다. (SQLD 예시로
만들었지만 `subject`/`theme`만 바꾸면 어떤 과목·자격증에도 적용됩니다.)

- **슬라이드**: 문제·보기·정답·해설을 로컬에서 렌더(Pillow+ffmpeg) — ComfyUI 불필요
- **음성/자막**: **Supertonic3** 로컬 TTS(문제집 기본 강의체 F2) · 합성 **ffmpeg** · 자막 없음(기본)
- **AI 발음**: 숫자·영어를 소리 나는 대로 한글로(CREATE→크리에이트) 자동 변환
- **요약노트**: 회차별 요약 → 과목→주요항목→세부항목 순 한 권 통합(+기출 회차·번호 출처)
- 원본 **다큐 경로**(대본→ComfyUI 이미지→영상)도 그대로 공존

> 이 저장소는 [gemma-chodangimunjejib-maker](https://github.com/leedonwoo2827-ship-it/gemma-chodangimunjejib-maker)
> 완성을 위한 PC 프로토타입입니다. **문제집 사용법 상세 → [docs/LESSON.md](docs/LESSON.md)**

## 문제집 빠른 시작
1. `setup.bat` (최초 1회) → `run.bat` → 브라우저 `http://localhost:8831`
2. **[+ 새 번들]** `ch01` → **[1 대본]** 탭에서 `samples/lesson_1.json` 불러와 **[🧩 레슨 저장]**
3. **[2 이미지]** → **[🖼 슬라이드 생성]** → 헤더 **[⚡ 한 번에 만들기]**
4. **[4 결과]** 미리보기/다운로드, **[5 요약노트]** 에서 전체 통합 요약노트

문제집 JSON은 `samples/lesson_{1,5,10}.json`(문제 1/5/15개) 형식을 복사해 채우면 됩니다.
문제만 있으면 4지선다 자동, `include_lecture:false`면 영상은 문제만, `round`/`source_no`로 기출 출처 표기.

---

## 📱 SQLD 쇼츠(세로 9:16) + 말하는 아바타

유튜브 쇼츠용 **세로 영상**을 **좌측 말하는 아바타 / 해설 상단·정답 하단** 레이아웃으로 생성.
쇼츠는 **한 문제 = 한 파일 = 한 영상**. SQLD 실전 샘플: `samples/sqld_shorts/sqld_0001_F2_F2.json … sqld_0010_F2_F2.json`.

- 지금 바로(정지 아바타·무음, 폴더 일괄): `python scripts/make_shorts.py samples/sqld_shorts -o out/shorts`
- **설치·연동 방법(ComfyUI Desktop + 립싱크): 👉 [docs/SHORTS_AVATAR.md](docs/SHORTS_AVATAR.md)**

---

## (참고) 원본 다큐 경로: 대본 → ComfyUI 이미지 → 영상

아래는 원본 compy-ui 의 다큐 영상 경로입니다. 문제집 영상엔 **ComfyUI가 필요 없습니다.**

- 이미지: 내 PC의 **ComfyUI** (움직임 가능하면 영상까지, 아니면 Ken Burns)
- 음성/자막: **Supertonic3** (로컬 TTS) · 합성: **ffmpeg**
- 대본: **codex/agy** CLI로 자동 생성하거나 직접 붙여넣기

---

## 빠른 시작 (3단계)

### 0) 준비물
- **Python 3.11~3.13** (설치 시 "Add to PATH" 체크) · **ffmpeg** (`winget install Gyan.FFmpeg`) · **git + git-lfs**

### 1) 설치 — `setup.bat` 더블클릭
가상환경 + 라이브러리 + TTS 모델 자동 설치. **한 번만** 하면 됩니다.
(끝에 "ComfyUI 연결 불가" 메시지는 ComfyUI가 아직 안 켜져서 뜨는 **정상** 안내 — 무시)

### 2) 실행 — `run.bat` 더블클릭
브라우저가 `http://localhost:8831` 로 자동으로 열립니다.

### 3) 만들기
`[1 대본]`에서 대본 생성/붙여넣기 → `[2 이미지]`에서 생성 → **⚡ 한 번에 만들기**로
음성·자막·MP4까지 자동. `[4 결과]`에서 미리보기·다운로드.

### 매번 실행 순서 (중요)
1. **ComfyUI 먼저 켜기** (`run_...gpu.bat` 또는 `run_cpu.bat`) → 콘솔에 `http://127.0.0.1:8188` 뜰 때까지 대기
2. **compy-ui `run.bat`** → 브라우저 `http://localhost:8831`
3. 웹에서 대본 → 이미지 → 음성 → MP4

> `run.bat`은 아무 때나 눌러도 됩니다. **대본·음성·렌더(Ken Burns)** 는 ComfyUI 없이도 되고,
> **이미지 생성만** ComfyUI가 켜져 있어야 합니다. ComfyUI 콘솔 창은 **마우스로 클릭하지 마세요**
> (클릭 시 QuickEdit 모드로 멈춤 — 멈추면 창 안에서 `Esc`).

---

## ComfyUI 붙이기 (이미지 생성용)

ComfyUI는 **별도 프로그램**입니다. 한 번 설치해 **켜두기만** 하면 compy-ui가 알아서 연결합니다.
(설치 후 `setup.bat`을 다시 누를 필요 없습니다.)

1. **받기**: [ComfyUI 릴리스](https://github.com/comfyanonymous/ComfyUI/releases)에서 **내 PC GPU에 맞는 포터블**
   - Intel(Iris Xe/Arc) → `..._intel.7z` · NVIDIA → `..._nvidia.7z` · AMD → `..._amd.7z`
2. **풀기**: 7-Zip으로 압축 해제 (경로는 한글·공백 없이, 예: `D:\ComfyUI_windows_portable\`)
3. **켜기**: 폴더 안 `run_...gpu.bat` 더블클릭 → `http://127.0.0.1:8188`
   - GPU 가속이 드라이버 문제로 안 뜨면(예: Iris Xe에서 `pti.dll` 오류) → **CPU로 실행**:
     같은 폴더에 `run_cpu.bat`을 만들어 아래 한 줄로 실행 (느리지만 확실)
     ```
     .\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --cpu
     ```
4. **모델 넣기** (단일 `.safetensors` 파일이어야 함 — 폴더형 diffusers는 안 됨):
   - 저사양 추천: **SD-Turbo 단일 파일** — [sd-turbo/tree/main](https://huggingface.co/stabilityai/sd-turbo/tree/main) 맨 아래
     **`sd_turbo.safetensors`**(~5GB) 다운로드 → `ComfyUI\models\checkpoints\` 에 복사
   - 넣은 뒤 **ComfyUI 재시작**(콘솔 닫고 다시 실행)해야 인식됩니다
5. **`.env` 설정** (저사양 PC): `COMFY_ENABLE_VIDEO=0`, `COMFY_MAX_DIM=768`
   (워크플로우 `workflows\txt2img_api.json` 은 이미 SD-Turbo 기준: ckpt `sd_turbo.safetensors`, steps 4, cfg 1.0)
6. **연결 확인**: `.venv\Scripts\python -m comfy.check` → `image generation: ready`
   → ComfyUI 켠 채로 `run.bat` → `[2 이미지]` 탭 배지 🟢 → **🎨 씬 이미지/영상 생성**

> ⚠️ **전용 GPU가 없는 PC(예: Iris Xe)**: 이미지 생성은 CPU로 **가능**하지만 씬당 1~수 분 느립니다
> (768×432·SD-Turbo 기준, 첫 테스트는 2~3씬 대본 권장). **실제 움직임(img2video)은 어려워**
> 이미지만 만들고 합성 때 **Ken Burns**로 움직입니다. 실제 영상화는 **GPU 노트북**에서 ComfyUI를
> 돌리고 `.env`의 `COMFY_HOST`를 그 노트북 IP로 지정하세요.

**자세한 설치·연결·문제해결 → [docs/COMFYUI.md](docs/COMFYUI.md)**

---

## 샘플로 먼저 (ComfyUI 없이)
```powershell
Copy-Item -Recurse sample\ch01_bundle _assets\ch01_bundle
run.bat   # 번들 ch01_bundle 선택 → [3 음성] → [4 풀 렌더]
```

## 폴더(번들) 규약
```
_assets/ch90_bundle/
  script/      ch90_script.json          ← 대본 (자동 생성/붙여넣기)
  images/      ch90_01_*.png             ← ComfyUI 이미지 (자동)
  clips/       ch90_01.mp4               ← ComfyUI 영상 (자동, 가능할 때만)
  audio/       ch90_01_narration.wav     ← Supertonic3 (자동)
  subtitles/   ch90_01_narration.srt     ← 자동
  draft/       ch90_final.mp4            ← ffmpeg (자동)
```

## 더 읽기
- **ComfyUI 상세**: [docs/COMFYUI.md](docs/COMFYUI.md)
- **회사 PC(GPU) 세팅 — 고화질 이미지 + 영상화(img2video)**: [docs/GPU-SETUP.md](docs/GPU-SETUP.md)
- 워크플로우/노드 매핑: [workflows/README.md](workflows/README.md)
- 운영/문제해결: [docs/](docs/) (RUN · BUNDLE · CLI · TROUBLESHOOTING)

## 구성
voicewright(로컬 TTS, Supertone Supertonic) + mp4maker(ffmpeg 합성)를 포함하고,
이미지 조달을 로컬 ComfyUI 연동으로 구현. ComfyUI는 외부 프로세스로 연결만 하며 저장소에 포함되지 않습니다.
