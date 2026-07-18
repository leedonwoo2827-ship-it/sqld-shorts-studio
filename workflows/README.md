# workflows/ — ComfyUI API-format 워크플로우

이 폴더의 JSON 은 ComfyUI 에 제출하는 **API-format** 워크플로우다.
FlowGenie(웹) 대신 로컬 ComfyUI 가 씬 이미지를(그리고 가능하면 움직이는 클립을) 만든다.

## 파일

| 파일 | 용도 | 필수 |
|---|---|---|
| `txt2img_api.json` | 씬 프롬프트 → 정지 이미지 | 필수 |
| `img2video_api.json` | 정지 이미지 → 움직이는 클립(img2video) | 선택(있으면 하이브리드) |
| `<name>.map.json` | 노드 자동탐지 실패 시 노드 id 수동 지정 | 선택 |

## API-format 으로 내보내는 법 (중요)

ComfyUI 캔버스의 기본 "Save" 는 **UI 포맷**이라 `/prompt` 에 넣을 수 없다.
1. ComfyUI 설정(⚙) → **Enable Dev mode Options** 켜기
2. 원하는 워크플로우를 캔버스에 구성 (유튜브 튜토리얼의 워크플로우 로드)
3. 메뉴에서 **Save (API Format)** → 나온 JSON 을 이 폴더에 저장
   - 이미지용 → `txt2img_api.json`
   - 영상용 → `img2video_api.json`

## 자동 주입되는 값 (코드가 씬마다 바꿔 넣음)

**txt2img_api.json**
- positive 프롬프트 텍스트 ← 대본 JSON 의 씬별 `"prompt"`
  (KSampler 의 `positive` 링크를 따라 CLIPTextEncode 를 자동 탐지)
- seed ← 씬 인덱스 기반(재현 가능) / `.env` 의 `COMFY_SEED`
- width/height ← 대본 `aspect_ratio` (16:9 → 1280×720)
- `filename_prefix` ← `chNN_XX`

**img2video_api.json**
- LoadImage 의 `image` ← 방금 만든 씬 이미지(업로드됨)
- seed, 저장 노드 `filename_prefix` 자동 주입

## 자동탐지가 틀릴 때: `.map.json`

노드가 특이해 자동탐지가 실패하면(예: positive/negative 구분 불가) 같은 이름의
`.map.json` 을 만들어 노드 id 를 직접 지정한다. 노드 id 는 API-format JSON 의 최상위 키다.

`txt2img_api.map.json`:
```json
{ "positive": "6", "seed": "3", "latent": "5", "save": "9" }
```
`img2video_api.map.json`:
```json
{ "load_image": "10", "seed": "3", "save": "12" }
```

## 점검

```
python -m comfy.check
```
서버 연결, 워크플로우 유효성, 영상 노드 설치 여부, 하이브리드 가능 여부를 출력한다.

## 참고 — 기본 제공 txt2img

`txt2img_api.json` 은 표준 SD 체크포인트용 최소 워크플로우다.
`CheckpointLoaderSimple.ckpt_name` 을 **실제 보유한 체크포인트 파일명**으로 바꿔야 동작한다.
(예: `sd_xl_base_1.0.safetensors`) — 없으면 튜토리얼 워크플로우를 export 해 통째로 교체하라.

## img2video 가 없는/저사양 PC

- 이 PC(Intel Iris Xe 등 전용 GPU 없음)에서는 img2video 가 사실상 불가능하다.
  `img2video_api.json` 을 두지 않거나 영상 노드가 없으면, 코드가 자동으로 이미지만 만들고
  mp4maker 의 **Ken Burns**(확대/이동)로 움직임을 준다.
- 실제 img2video 는 NVIDIA GPU 노트북에서 ComfyUI 를 구동하고 `.env` 의
  `COMFY_HOST` 를 그 PC 로 지정하면 같은 repo 로 사용할 수 있다.
