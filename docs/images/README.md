# docs/images

아트보드를 헤드리스 크롬으로 렌더링한 PNG. 캔버스 없이 문서만 읽을 때를 위한 것이다.

## 다시 뽑는 법

```
python tools/render_canvas.py                      # 아트보드 원본이 리포에 있는 것 전부
python tools/render_canvas.py mock-1-place-result.dc.html   # 하나만
```

크기는 `docs/canvas/canvas.json`의 `w`·`h`다. 내용이 창보다 길면 **찍기 전에 멈추고** 얼마로 고치라고
알려 준다 — 잘린 PNG는 눈으로 봐야만 알 수 있고, 그러면 아무도 안 본다.

## 아트보드 원본이 있는 것

| 파일 | 아트보드 원본 |
|---|---|
| `modmap-1-place-map.png` | `docs/canvas/modmap-1-place-map.dc.html` |
| `modmap-1-place-worker.png` | `docs/canvas/modmap-1-place-worker.dc.html` |
| `modmap-2-route-map.png` | `docs/canvas/modmap-2-route-map.dc.html` |
| `mock-1-place-result.png` | `docs/canvas/mock-1-place-result.dc.html` |

이 넷은 2026-09-04에 **리포 안에서 다시 지었다**(#28). 그 전 그림에는 D1 표와 판정 줄이 남아 있었는데,
원본 아트보드가 세션 작업 파일에만 있어 고칠 수가 없었다 — 원본을 리포에 넣은 까닭이 그것이다.
고칠 일이 생기면 `.dc.html`을 고치고 위 명령을 돌린다. 모양은 `docs/canvas/canvas.css` 한 곳에 있다.

## 아트보드 원본이 없는 것

아래는 옛 캔버스에서 뽑은 그림이고 원본이 남아 있지 않다. **고치려면 `docs/canvas/`에 아트보드부터
다시 지어야 한다.** 지금 내용에 틀린 것은 없다.

| 파일 | 무엇 |
|---|---|
| `modmap-2-route-build.png` | 노선번호로 찾기 · 빌드 스크립트 단계 |
| `mock-1-place-initial.png` | 화면 목업 · 장소로 찾기 (첫 화면) |
| `mock-2-route-initial.png` · `mock-2-route-result.png` | 화면 목업 · 노선번호로 찾기 |
| `mock-3-stop-diff.png` | 화면 목업 · 노선 변화 표 |
| `mock-4-fragment-source.png` | 화면 목업 · Q6 조각 출처 a vs b |

## checks/

캔버스가 아니라 **실제 화면**을 찍은 것. 티켓의 「수동 확인」 증거이고, 이슈 코멘트가 여기를 가리킨다.
저장소가 비공개라 이슈에 그림이 바로 뜨지 않으므로 링크로 남긴다.

| 파일 | 무엇 |
|---|---|
| `check-5-1-route-tab-initial.jpg` | #5 · 노선번호 탭 첫 화면(목록 표 103줄) |
| `check-5-2-card-default-table.jpg` | #5 · 문흥18 줄 → 카드와 간선18 표(47·11·5 / 50·12·6) |
| `check-5-3-table-swapped.jpg` | #5 · 「지선10」 → 표가 17·41·39 / 15·47·38로 |
| `check-5-4-place-tab.jpg` | #5 · 장소 탭(입력칸 자리만) |
| `check-5-5-swap-shows-result.jpg` | #5 · 목록 끝의 두암181을 눌러도 카드가 화면 안에 뜬다 |
| `check-36-1-map-slot-without-key.jpg` | #36 · 키 없이 찍은 노선 지도 자리 |

괄호 안 수치는 **찍을 당시**의 것이다. 그 뒤 명칭 사전(#3)이 들어가 같은 화면이
문흥18 ↔ 간선18은 49·9·3 / 52·10·4, ↔ 지선10은 18·40·38 / 16·46·37로 나온다.
그림은 #5의 화면 배치 증거로 그대로 두고, 수치의 정본은 `docs/architecture.md` §6이다.
