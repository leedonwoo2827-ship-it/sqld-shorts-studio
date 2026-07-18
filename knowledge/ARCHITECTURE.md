# 구조 (ARCHITECTURE) — 왜 이렇게 만들었나

## 한 줄
**voicewright(로컬 TTS) + mp4maker(ffmpeg 합성)** 를 한 레포로 합치고, 단일 FastAPI
웹앱으로 `이미지 가져오기 → 음성/자막 → MP4` 를 굴린다. AI 런타임 호출 0, 전부 CPU.

## 왜 FastAPI 베이스 + mp4maker는 subprocess
- voicewright는 이미 **FastAPI 웹 UI**(발음사전 편집·씬카드·배치·씬별 재생성·백그라운드 잡)를
  갖추고 있었다. 이걸 다시 만드는 건 낭비라 **베이스로 채택**.
- mp4maker는 **CLI로 호출**되고 stdout으로 파싱 가능한 진행률 태그를 낸다.
  voicewright 잡 패턴 위에 **subprocess로 얹으면** 렌더 진행률까지 자연스럽게 처리된다.
- 결과: **단일 서버·단일 포트·단일 UI** → "단계 줄이기 / ⚡ 한 번에" 목표에 부합.

## 구성 요소
```
app/main.py            FastAPI 앱 (voicewright API/발음사전 재사용 + /api/mf)
app/routes_pipeline.py 번들·가져오기·음성·렌더·⚡한번에 + 작업 폴링
app/synth.py           voicewright 어댑터: synthesize(bundle, only=...) (flat 출력)
app/render.py          mp4maker subprocess 러너 + 진행률 태그 파싱
app/bundles.py         번들 탐색/생성/상태
ingest/import_images.py  Downloads → 번들 images/ (씬당 최신 1장)
voicewright/           벤더 (TTS 코어)
mp4maker/              벤더 (합성, subprocess로 호출)
```

## 데이터 인터페이스 = 번들 폴더
세 단계는 서로를 직접 부르지 않고 **번들 폴더 규약**으로 파일을 주고받는다.
([../docs/BUNDLE.md](../docs/BUNDLE.md))

## 어댑터 핵심
voicewright는 원래 `workspace/ch{NN}/audio` 로 출력하지만 mp4maker는 `bundle/audio` 를
읽는다. `run_batch(flat_layout=True)` 로 번들에 직접 쓰게 맞췄다.
([../docs/CUSTOMIZATIONS.md](../docs/CUSTOMIZATIONS.md))
