# docs/images

캔버스 두 개의 아트보드를 헤드리스 Chrome으로 렌더링한 PNG. 캔버스 없이 문서만 읽을 때를 위한 것이다.

| 파일 | 출처 캔버스 · 페이지 |
|---|---|
| `modmap-1-place-map.png` · `modmap-1-place-worker.png` | 모듈 지도 · 장소로 찾기 |
| `modmap-2-route-map.png` · `modmap-2-route-build.png` | 모듈 지도 · 노선번호로 찾기 |
| `mock-1-place-initial.png` · `mock-1-place-result.png` | 화면 목업 · 장소로 찾기 |
| `mock-2-route-initial.png` · `mock-2-route-result.png` | 화면 목업 · 노선번호로 찾기 |
| `mock-3-stop-diff.png` | 화면 목업 · 노선 변화 표 |
| `mock-4-fragment-source.png` | 화면 목업 · Q6 조각 출처 a vs b |

다시 뽑는 법: 아트보드의 `.dc.html`을 파일로 열어
`chrome --headless=new --hide-scrollbars --window-size=<w>,<h> --screenshot=<out>.png <file>`.
크기는 캔버스 `canvas.json`의 w·h. 아트보드 원본은 캔버스에서 내려받거나 세션 작업 파일에 있다.

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
