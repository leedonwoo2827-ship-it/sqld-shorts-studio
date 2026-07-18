# 샘플 (sample)

처음 실행해 보는 사람을 위한 **바로 써보는 예제**입니다. 대본 JSON + 이미지 3장이 들어 있어,
음성/자막 → MP4 합성까지 한 번에 돌려볼 수 있습니다. (이미지는 직접 만들 필요 없이 포함됨)

```
sample/ch01_bundle/
├── script/  ch01_script.json        ← 3씬 한국어 대본
└── images/  ch01_01_opening.png, ch01_02_body.png, ch01_03_closing.png
```

## 써보는 법

### 방법 A — 폴더째 복사 (가장 쉬움)
`sample/ch01_bundle` 을 `_assets/` 안으로 복사한 뒤 웹앱에서 고릅니다.

PowerShell:
```powershell
Copy-Item -Recurse sample\ch01_bundle _assets\ch01_bundle
run.bat
```
브라우저(자동 열림)에서 번들 `ch01_bundle` 선택 → **⚡ 한 번에 만들기**.
→ 음성/자막 생성 후 MP4가 `_assets\ch01_bundle\draft\ch01_final.mp4` 에 만들어집니다.

### 방법 B — CLI 로만
```powershell
.venv\Scripts\activate
Copy-Item -Recurse sample\ch01_bundle _assets\ch01_bundle
python -c "import asyncio; from app.synth import synthesize; asyncio.run(synthesize('_assets/ch01_bundle'))"
python -m mp4maker _assets\ch01_bundle
```

> 이미지를 이미 갖고 있다면 이렇게 `images/` 에 `chNN_XX_*` 이름으로 넣어두기만 하면
> Flow/가져오기 단계를 건너뛰고 바로 합성할 수 있습니다 (이 샘플이 그 예시).
>
> 샘플 이미지는 ffmpeg로 만든 단색 그라데이션 placeholder 입니다. 실제로는 FlowGenie로
> 만든 이미지를 같은 이름으로 넣으면 됩니다.
