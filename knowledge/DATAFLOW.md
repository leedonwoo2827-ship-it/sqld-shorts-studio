# 데이터 흐름 (DATAFLOW)

## 4단계 → ⚡ 한 번에
```
[1] 대본 JSON      Claude/scriptforge      →  script/chNN_script.json   (사람)
[2] 이미지         FlowGenie(크롬) → Downloads → images/                (사람 + 📥)
─────────────────────────  여기부터 ⚡ 한 번에  ─────────────────────────
[3] 음성/자막      voicewright TTS         →  audio/*.wav, subtitles/*.srt  (자동)
[4] MP4 합성       mp4maker(ffmpeg)        →  draft/chNN_final.mp4          (자동)
```

## ⚡ "한 번에 만들기" 순서 (app/routes_pipeline.py)
```
1. 이미지 가져오기 (Downloads → images/, 씬당 최신 1장)
     └ 누락 씬 있으면 STOP → "씬N 이미지 없음, Flow에서 받아오세요"
2. 음성/자막 일괄 생성 (오디오 없는 씬이 있을 때만; 이미 있으면 건너뜀)
3. MP4 합성 (mp4maker subprocess, 진행률 태그 파싱)
4. 완료 → 결과 탭, 미리보기 + 다운로드
```
- 끝난 단계는 건너뛰어 재실행해도 안전.
- 어느 단계든 실패하면 거기서 멈추고 무엇을·왜 안내.

## 시작점은 어디든 가능
- 이미지를 **이미 다 만들어 뒀다면** `images/` 에 직접 넣고 [2]를 건너뛰어도 된다.
- 음성만, 렌더만 따로 돌려도 된다(탭/CLI).

## 사람이 하는 것은 둘뿐
ⓐ 대본 JSON 넣기  ⓑ 이미지 받기(또는 미리 만든 이미지 넣기). 나머지는 ⚡.
