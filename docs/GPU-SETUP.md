# 회사 PC(GPU)에서 하기 — 이미지 & 영상화

사무용 PC(Iris Xe/CPU)와 달리 **NVIDIA GPU가 있는 회사 노트북**에서는 고화질 이미지와
**실제 움직이는 영상(img2video)** 이 가능하다. 이 문서는 그 두 부분만 다룬다.

> 앱(compy-ui) 사용법은 동일하다. 바뀌는 건 **ComfyUI 쪽 모델/워크플로우 + `.env` 3줄**뿐이다.

---

## 0. 공통 준비 (한 번)

1. **GPU 확인**: NVIDIA인지 확인 (작업관리자 → 성능 → GPU). NVIDIA면 아래 그대로, 아니면 [COMFYUI.md](COMFYUI.md) 참고.
2. **ComfyUI 설치**: [릴리스](https://github.com/comfyanonymous/ComfyUI/releases)에서
   `ComfyUI_windows_portable_nvidia_cu126.7z` (최신 드라이버) 또는 `..._nvidia.7z` 다운 → 7-Zip 해제
   → **`run_nvidia_gpu.bat`** 더블클릭 → `http://127.0.0.1:8188`
3. **compy-ui**: 이 repo를 그 PC에 clone → `setup.bat` (한 번). 또는 사무용 PC의 compy-ui를 그대로 두고
   **원격 연결**만 할 수도 있음(맨 아래 D).

---

## A. 이미지 (고화질)

### A-1. 모델 선택 (`ComfyUI\models\checkpoints\` 에 단일 `.safetensors`)

| 모델 | 화질 | VRAM | 워크플로우 |
|---|---|---|---|
| **SDXL 파인튜닝** (Juggernaut XL, RealVisXL) ★추천 | 사실적·시네마틱 | 8~12GB | 기본(우리 txt2img) 그대로 |
| **SDXL-Turbo / Lightning** | 좋음·빠름(적은 스텝) | 8GB | steps 4~8, cfg 1~2 |
| **FLUX.1 [schnell/dev]** | 최상급 | 12~24GB | 별도 FLUX 워크플로우 필요(아래 A-3) |
| **SD3.5** | 강력 | 12GB+ | 별도 워크플로우 |

- 다운로드: Hugging Face 또는 Civitai에서 **단일 파일** safetensors (폴더형 diffusers 아님).
  예) Juggernaut XL, RealVisXL V5 등.

### A-2. 워크플로우 설정 (SDXL 파인튜닝 기준 — 가장 쉬움)
`workflows\txt2img_api.json` 만 수정(우리 기본 워크플로우가 SDXL도 그대로 동작):
- `ckpt_name` → 받은 파일명
- `steps` 25~30, `cfg` 5.0~7.0, `sampler_name` `dpmpp_2m`, `scheduler` `karras`
- (SDXL-Turbo/Lightning이면 `steps` 4~8, `cfg` 1.0~2.0, `sampler` `euler`)

`.env`:
```
COMFY_ENABLE_VIDEO=1
COMFY_MAX_DIM=0        # 상한 해제 → 대본 aspect 그대로(16:9=1280x720). GPU면 1024~1536도 가능
```

### A-3. FLUX 를 쓸 경우(선택, 최상급이지만 복잡)
FLUX는 체크포인트 1개가 아니라 여러 파일이 필요:
- `models\unet\flux1-schnell.safetensors` (또는 dev)
- `models\clip\clip_l.safetensors`, `models\clip\t5xxl_fp16.safetensors`
- `models\vae\ae.safetensors`
→ ComfyUI 기본 제공 **FLUX 템플릿** 워크플로우를 로드하고 **Save (API Format)** 으로
`workflows\txt2img_api.json` 교체. 노드 자동탐지가 안 맞으면 `workflows\txt2img_api.map.json` 로
`positive`/`seed`/`save` 노드 id 지정 → [../workflows/README.md](../workflows/README.md).

---

## B. 영상화 (img2video · 실제 움직임)

이미지를 만든 뒤 그 이미지를 **짧은 영상 클립으로 애니메이션**한다. compy-ui가 자동으로
이미지 업로드 → img2video 실행 → 클립 다운로드 → mp4maker가 나레이션 길이에 맞춰 loop.

### B-1. 모델/노드 선택 (`ComfyUI\models\...`)

| 방식 | 화질 | VRAM | 비고 |
|---|---|---|---|
| **WAN 2.2 I2V** ★추천 | 최상 | 24GB(14B) / 8~12GB(경량·GGUF) | 2025~26 최강 오픈 img2video |
| **Stable Video Diffusion (SVD/SVD-XT)** | 무난 | 10~12GB | 가장 단순: 이미지→2~4초 클립 |
| **LTX-Video** | 빠름 | 8~12GB | 실시간급, 가벼움 |
| **CogVideoX-I2V** | 좋음 | 12GB+ | |

필요 모델을 ComfyUI-Manager로 설치하거나 각 폴더에 배치.

### B-2. 워크플로우 만들기
1. ComfyUI에서 img2video 워크플로우 구성(유튜브 튜토리얼 로드 또는 ComfyUI 템플릿)
2. **한 번 실행해 잘 되는지 확인**
3. 설정(⚙) → **Enable Dev mode** → **Save (API Format)** → `workflows\img2video_api.json` 로 저장
4. `.env`: `COMFY_ENABLE_VIDEO=1`

자동 주입: compy-ui가 **LoadImage** 노드에 씬 이미지를, 영상 저장 노드에 파일명을 넣는다.
노드 자동탐지가 틀리면 `workflows\img2video_api.map.json`:
```json
{ "load_image": "10", "seed": "3", "save": "12" }
```

### B-3. 확인
```
.venv\Scripts\python -m comfy.check
```
→ `image->video: ready (real motion)` 나오면 준비 완료. 이후 `[2 이미지] → 🎨 생성` 하면
씬마다 이미지 + 클립이 만들어지고, `clips\chNN_XX.mp4` 가 mp4maker에서 나레이션 길이만큼 loop된다.
(클립이 없거나 실패한 씬은 자동으로 이미지 + Ken Burns 폴백)

---

## C. 요약 — 회사 PC에서 바꾸는 것만

1. `run_nvidia_gpu.bat` 로 ComfyUI 실행
2. `checkpoints\` 에 SDXL 파인튜닝(또는 FLUX) + img2video 모델 배치
3. `workflows\txt2img_api.json`(ckpt/steps/cfg) + `workflows\img2video_api.json`(API export)
4. `.env`: `COMFY_ENABLE_VIDEO=1`, `COMFY_MAX_DIM=0`
5. `python -m comfy.check` 로 둘 다 ready 확인 → `run.bat` → 평소처럼 사용

---

## D. (선택) 사무용 PC에서 회사 PC의 GPU만 빌려 쓰기

compy-ui는 사무용 PC에 두고, 이미지/영상 생성만 회사 PC GPU로:
- 회사 PC ComfyUI를 **`--listen 0.0.0.0`** 로 실행 (외부 접속 허용; 포터블이면 bat에 인자 추가)
- 사무용 PC compy-ui `.env`:
  ```
  COMFY_HOST=<회사 PC의 LAN IP>   # 예: 192.168.0.50
  COMFY_PORT=8188
  COMFY_ENABLE_VIDEO=1
  COMFY_MAX_DIM=0
  ```
- 같은 네트워크(사내 LAN)여야 하고, 방화벽에서 8188 허용 필요.
