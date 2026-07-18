# ComfyUI 상세 가이드 (설치 · 연결 · 고급)

compy-ui 는 이미지/영상 생성을 **로컬 ComfyUI 서버**에 맡긴다. ComfyUI 는 사용자가 직접
설치·구동하고, 이 앱은 HTTP(기본 `127.0.0.1:8188`)로 연결만 한다. ComfyUI 자체는 이 저장소에
포함되지 않는다.

README 의 3줄 요약으로 대부분 끝나지만, 아래는 그 배경/고급/문제해결이다.

---

## 1. 어떤 포터블을 받나 (GPU별)

[github.com/comfyanonymous/ComfyUI/releases](https://github.com/comfyanonymous/ComfyUI/releases)
최신 릴리스 Assets 에서 **내 PC GPU에 맞는 것 하나**:

| 파일 | 대상 | 비고 |
|---|---|---|
| `ComfyUI_windows_portable_intel.7z` | **Intel GPU/iGPU** (Iris Xe, Arc) | 이 사무용 PC → **이걸로**. iGPU 가속(순수 CPU보다 빠름) |
| `ComfyUI_windows_portable_nvidia.7z` | NVIDIA GPU | GPU 노트북용. img2video 실동작 |
| `ComfyUI_windows_portable_nvidia_cu126.7z` | NVIDIA (CUDA 12.6) | 최신 드라이버면 이쪽 |
| `ComfyUI_windows_portable_amd.7z` | AMD GPU | |

압축 해제는 **7-Zip** 필요(일반 압축기로 안 풀림). 경로는 **한글·공백 없이 얕게**(예: `D:\ComfyUI_windows_portable\`),
OneDrive/동기화 폴더는 피한다.

실행: 폴더 안 `.bat` 중 내 GPU용(Intel/NVIDIA)이 있으면 그걸, 없거나 오류면 `run_cpu.bat`.
성공하면 콘솔에 `To see the GUI go to: http://127.0.0.1:8188`.

### Intel 포터블 예시 (이 사무용 PC)

압축을 풀면 폴더 구성은 이렇다:

```
D:\ComfyUI_windows_portable\ComfyUI_windows_portable_intel\
├── ComfyUI\            ← 본체 (models\checkpoints\ 에 모델 넣는 곳)
├── python_embeded\     ← 내장 파이썬 (건드리지 않음)
├── update\             ← 업데이트 스크립트
└── run_intel_gpu.bat   ← ★ 이 파일을 더블클릭 (Iris Xe/Arc 로 실행)
```

<!-- 실제 폴더 스크린샷을 쓰려면 docs/img/comfyui-intel-folder.png 로 저장하세요. 아래 줄이 자동 표시됩니다. -->
![Intel 포터블 폴더](img/comfyui-intel-folder.png)

- **`run_intel_gpu.bat` 더블클릭** → 검은 콘솔 창이 뜨고 초기화(첫 실행은 조금 오래) →
  `To see the GUI go to: http://127.0.0.1:8188` 이 보이면 성공. 브라우저에서 열린다.
- ⚠️ 이 시점엔 **모델이 아직 없어** ComfyUI 화면이 "checkpoint 없음" 이라고 한다 →
  아래 2번에서 `ComfyUI\models\checkpoints\` 에 모델을 넣어야 한다.
- 콘솔 창은 **켜둔 채로** 둔다(닫으면 서버 종료). compy-ui 는 이 서버에 연결한다.

---

## 2. 모델(체크포인트) — CPU/iGPU는 "적은 스텝"이 핵심

`ComfyUI\models\checkpoints\` 에 `.safetensors` 를 넣는다.

- **저사양(이 PC) 추천: Turbo 계열** — 1~4스텝으로 생성해 느린 하드웨어에 최적
  - **SD-Turbo**: [huggingface.co/stabilityai/sd-turbo](https://huggingface.co/stabilityai/sd-turbo) → `sd_turbo.safetensors` (SD1.5 크기, 가장 가벼움)
  - **SDXL-Turbo**: [huggingface.co/stabilityai/sdxl-turbo](https://huggingface.co/stabilityai/sdxl-turbo) → 더 고화질, 더 무거움
- **GPU 노트북 추천: 일반 SDXL 또는 WAN(영상)** — 화질 우선

Turbo 는 `cfg≈1.0`, `steps 1~4`, `sampler euler_ancestral` 가 정석이다(일반 모델의 cfg 7 / 25스텝과 다름).

### 사무용 노트북(CPU/Iris Xe) 현재 권장 모델 — 확정

전용 GPU가 없는 이 PC에서는 **`sd_turbo.safetensors`(SD-Turbo 단일 파일)** 가 현실적 최선이다.
- 이유: 1~4스텝이라 CPU에서도 장면당 ~1분 내외. 실제로 이 PC에서 768×432 생성이 검증됨.
- 세팅(이미 기본값): `workflows\txt2img_api.json` → ckpt `sd_turbo.safetensors`, `steps 4`, `cfg 1.0`,
  `sampler euler_ancestral`; `.env` → `COMFY_ENABLE_VIDEO=0`, `COMFY_MAX_DIM=768`.
- 화질을 조금 더 올리고 싶으면 **SDXL-Turbo**(`sd_xl_turbo_1.0_fp16.safetensors`, steps 4~6/cfg 1.0)로
  교체 가능하나 CPU에선 2~4배 느리다. 그 이상(SDXL 파인튜닝·FLUX)은 GPU 필요 → [GPU-SETUP.md](GPU-SETUP.md).
- ⚠️ 이 PC에서 **img2video(실제 움직임)는 불가** — 이미지만 만들고 합성 때 Ken Burns.

---

## 3. compy-ui 연결

이 저장소의 `workflows/txt2img_api.json` 은 **ComfyUI 기본 노드만** 쓰는 표준 워크플로우라
커스텀 노드 없이 바로 동작한다. UI 를 안 만져도 두 값만 맞추면 된다:

- `"ckpt_name"` → 받은 체크포인트 파일명
- Turbo 모델이면 `"steps": 4`, `"cfg": 1.0` (그 외 모델은 기본값 유지)

그다음 **ComfyUI 켜둔 상태**로 compy-ui `run.bat` → 웹 `[2 이미지]` 탭 배지가 🟢 연결됨.
연결/능력만 콘솔로 확인하려면:

```
.venv\Scripts\python -m comfy.check
```

`.env` 로 서버 위치·옵션을 바꾼다:
```
COMFY_HOST=127.0.0.1      # 다른 PC의 ComfyUI면 그 IP
COMFY_PORT=8188
COMFY_ENABLE_VIDEO=0      # 저사양은 0(이미지만 → Ken Burns) 권장
```

---

## 4. 능력 매트릭스 (머신별)

| 머신 | 이미지 | 움직임 |
|---|---|---|
| 이 사무용 PC(Iris Xe) | Intel 포터블로 생성(느림, Turbo 권장) | **Ken Burns 폴백** (img2video 사실상 불가) |
| GPU 노트북(NVIDIA) | SDXL 등 | **img2video 실동작** |

같은 repo 로 두 머신 모두 쓰려면, GPU 노트북에서 ComfyUI 를 켜고 사무용 PC 의 `.env`
`COMFY_HOST` 를 그 노트북 IP 로 지정한다(같은 LAN). ComfyUI 는 `--listen 0.0.0.0` 으로 실행해야
외부 접속을 받는다.

---

## 5. img2video (실제 움직임)

GPU 노트북에서만 현실적이다. ComfyUI 에 img2video 워크플로우(SVD/WAN/LTX 등)를 구성한 뒤
**Save (API Format)** 으로 내보내 `workflows/img2video_api.json` 에 둔다. 노드 자동탐지/수동 매핑은
[../workflows/README.md](../workflows/README.md) 참고. 클립이 생기면 mp4maker 가 나레이션 길이만큼
loop 하고, 없으면 이미지 + Ken Burns 로 폴백한다.

---

## 6. 튜토리얼 워크플로우 그대로 쓰기

유튜브 등에서 받은 워크플로우를 쓰려면:
1. ComfyUI 설정(⚙) → **Enable Dev mode Options** 켜기
2. 캔버스에 워크플로우 로드 → **Save (API Format)**
3. 이미지용 → `workflows/txt2img_api.json`, 영상용 → `workflows/img2video_api.json` 로 저장
4. 노드 자동탐지가 틀리면 `workflows/<name>.map.json` 으로 노드 id 지정 → [../workflows/README.md](../workflows/README.md)

---

## 7. 문제해결

| 증상 | 원인/해결 |
|---|---|
| Intel 포터블: `pti.dll ... zetMetricGroupCalculateMultipleMetricValuesExp 찾을 수 없음` + `assuming Nvidia` | **Intel 그래픽 드라이버가 오래됨**(Level Zero 함수 누락). ① 팝업 [확인] 후 콘솔이 8188까지 가면 무시 가능 ② 안 되면 **Intel Driver & Support Assistant**로 Iris Xe 드라이버 최신(32.x) 업데이트 + 재부팅 ③ 드라이버 못 올리면 nvidia 포터블의 **`run_cpu.bat`**(CPU 모드)로 우회 |
| `comfy.check` [FAIL] 연결 불가 | ComfyUI 가 안 켜짐 → 먼저 실행. 포트가 다르면 `.env` `COMFY_PORT` |
| 배지 🟡 "이미지만 → Ken Burns" | img2video 노드/워크플로우 없음 → 정상(저사양). 영상 원하면 5번 |
| 이미지 생성 매우 느림 | CPU/iGPU 한계 → Turbo 모델 + 스텝↓ + 해상도↓(`EmptyLatentImage` width/height) |
| "이미지 출력이 없습니다" | 워크플로우에 `SaveImage` 노드 없음, 또는 ckpt_name 오타 |
| 노드 오류(node_errors) | 커스텀 노드 미설치 → ComfyUI-Manager 로 설치하거나 기본 노드 워크플로우 사용 |
| 실존 인물/브랜드 프롬프트 거부 | 대본 프롬프트 규칙이 이미 일반 묘사로 유도(실명·브랜드·흡연 금지) |

해상도는 대본 `aspect_ratio` 로 정해진다(16:9→1280×720). 더 낮추려면 워크플로우의
`EmptyLatentImage` 를 직접 줄인다(예: 768×432).
