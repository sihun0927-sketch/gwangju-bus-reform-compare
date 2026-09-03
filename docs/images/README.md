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
