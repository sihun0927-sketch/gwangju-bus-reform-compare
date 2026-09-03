# gwangju-bus-reform-compare

2026년 10월 광주 시내버스 노선 개편 전후를 시민이 비교하는 웹 서비스.
탭 둘: **장소로 찾기**(출발·도착 장소를 넣으면 개편 전후 경로를 비교)와
**노선번호로 찾기**(번호를 넣으면 대체 노선과 노선 변화 표를 보여 줌).

구조는 **정적 HTML + htmx 조각**이다. 이유와 부품별 역할은 `docs/architecture.md`에 있다.

## 새로 합류했다면 이 순서로 읽는다

1. `CONTEXT.md` — 용어. 방면·대체 노선·조각·유지/경유 제외/경유 추가 같은 말의 뜻
2. `docs/architecture.md` — 구조와 부품 역할, 두 탭의 정적/동적 분할, 데이터 흐름, 결정 요약
3. `docs/adr/` — 되돌리기 어려운 결정 여덟과 그 이유 (0004는 0007로, 0001의 D1 부분은 0008로 대체됨)
4. `data/README.md` — 원천 CSV 6개의 열과 행 수, 정류장 좌표(`source/stops.csv`), 알아 둘 함정
5. **모듈 지도** (아래 그림) — 탭마다 두 장: 모듈 지도(화면 조각 → 화면 모듈 → 조각 →
   만드는 곳(빌드 스크립트 / Worker) → 데이터, 정적/동적·용어·데이터 있음/없음)와 만드는 곳의
   단계(단계별 입력·출력·테스트 경계). 구현·유지보수 때 보는 것
6. **화면 목업** (아래 그림) — 장소 탭 · 노선번호 탭 · 노선 변화 표 · 조각 출처 a vs b

## 그림

아트보드(`docs/canvas/*.dc.html`)를 헤드리스 크롬으로 찍은 PNG다. 고칠 일이 생기면 아트보드를 고치고
`python tools/render_canvas.py`를 돌린다. 원본이 아직 없는 그림도 있다 — 어느 것인지는
`docs/images/README.md`에 적혀 있다.

### 노선번호로 찾기

![노선번호로 찾기 · 모듈 지도](docs/images/modmap-2-route-map.png)

![노선번호로 찾기 · 빌드 스크립트 단계](docs/images/modmap-2-route-build.png)

![노선번호로 찾기 · 초기 상태 목업](docs/images/mock-2-route-initial.png)

![노선번호로 찾기 · 결과 상태 목업](docs/images/mock-2-route-result.png)

![노선 변화 표 · 문흥18](docs/images/mock-3-stop-diff.png)

### 장소로 찾기

![장소로 찾기 · 모듈 지도](docs/images/modmap-1-place-map.png)

![장소로 찾기 · Worker 단계](docs/images/modmap-1-place-worker.png)

![장소로 찾기 · 초기 상태 목업](docs/images/mock-1-place-initial.png)

![장소로 찾기 · 결과 상태 목업](docs/images/mock-1-place-result.png)

### 조각 출처 a vs b (Q6)

![조각 출처 a vs b](docs/images/mock-4-fragment-source.png)

## 배포 (Cloudflare Workers)

Worker 이름 `gwangju-bus-reform-compare`. Workers Builds가 `main`에 push될 때마다 리포를 받아
`python -m tools.build`로 `out/`을 만들고, `wrangler.jsonc`대로 `out/`을 정적 자산으로 올린다.
Worker 코드(`worker/`)는 장소 탭 세 경로 `/places` · `/compare` · `/journey/…`만 받는다 —
`wrangler.jsonc`의 `run_worker_first`에 적힌 그 셋이다. 노선번호 탭은 정적 파일만으로 돈다(ADR-0002).

대시보드 빌드 설정(리포 밖, 한 번만): 빌드 명령 `python -m tools.build` · 배포 명령 `npx wrangler deploy` · 루트 `/`.
로컬 확인: `python -m tools.build && npx wrangler deploy --dry-run`.

빌드 환경 변수 `KAKAO_JS_KEY`(Kakao JavaScript 키, ADR-0005)가 있으면 껍데기에 지도 SDK 태그가 들어간다.
없으면 빌드는 그대로 성공하고 노선 지도 자리에 「지도를 불러오지 못했습니다」 한 줄만 남는다. **키는 리포에
없다** — Cloudflare 설정에 둔다. 로컬에서 지도를 보려면 `KAKAO_JS_KEY=… python -m tools.build`.

## 빌드와 테스트

```
python -m tools.build            # data/source → out/ (정적 조각) + worker/data.json (번들 JSON)
python -m pytest                 # 빌드 검사 — out/의 조각과 번들 JSON을 본다
npm test                         # Worker 검사 — 빌드를 한 번 돌린 뒤 node --test
npm run deploy:dry               # wrangler deploy --dry-run
python tools/measure_direction.py    # 실측 — 기·종점 정렬 단계별 개수 (§6-1)
python tools/measure_transfers.py    # 실측 — 번들 크기와 환승 표 줄 수 (§6-2)
node tools/measure_search.mjs        # 실측 — 상태 분포와 요청 시간 (§6-3, 빌드가 먼저다)
node tools/measure_cpu.mjs           # 실측 — /compare 요청당 CPU (§6-4, `npm ci`와 빌드가 먼저다)
```

`out/`과 `worker/data.json`은 빌드 산출물이라 저장소에 없다. **배포도 테스트도 빌드가 먼저다.**
`measure_cpu`만 `node_modules`가 필요하다 — `wrangler dev`를 직접 띄워 그 안 workerd에서 재기 때문이다.

## 상태 (2026-09-04)

**노선번호 탭이 정적 파일로 돈다.** `python -m tools.build`가 `out/`에 껍데기 `index.html` 한 장(노선 개편 목록 표 103줄)과
노선 변화 카드 103개 · 노선 변화 표 205개를 쓴다. `out/`을 정적 서버로 열면 목록의 한 줄을 눌러 카드를,
카드의 버튼을 눌러 표를 새로고침 없이 바꿀 수 있다 — Worker도 D1도 없이(ADR-0001·0002).
표 조각마다 상행 좌표가 실려 있어 카드 위 노선 지도가 개편 전(굵은 초록)과 대체 노선(가는 파랑)을 겹쳐 그린다 —
그리는 브라우저 코드는 `out/map.js` 하나뿐이고, Kakao JS 키가 있는 환경에서만 뜬다(ADR-0005).

**장소 탭도 브라우저에서 끝까지 돈다.** 출발·도착 칸에 두 글자를 치면 `GET /places?q=`가 Kakao로
자동완성 후보를 띄우고, 둘을 고르면 `GET /compare?from=lat,lng&to=lat,lng`가 개편 전 카드와 개편 후
카드를 한 쌍으로 돌려준다. 카드 머리에는 판정 문장이 아니라 상태가 선다 —
「직행 · 환승 1회 · 환승 2회 · 경로 없음」. 환승 줄에는 내리는 곳 → 타는 곳과 환승 도보가 있고,
「다른 경로 더 보기」는 `GET /journey/{경로 키}`로 노선 조합이 다른 경로를 둘까지 펼친다.
카드마다 실린 좌표를 `out/map.js`가 받아 경로 지도를 그린다(노선 지도와 같은 코드).
껍데기의 입력칸 둘은 활성화됐고 「아직 준비 중」 안내는 없다. 다만 **후보 고름 → 카드 한 쌍을
브라우저에서 찍은 그림은 아직 없다** — Kakao REST 키가 있는 환경에서 찍어 `docs/images/checks/`에
더한다(#26의 마지막 AC).
데이터는 같은 빌드가 쓴 `worker/data.json` 하나뿐이고 **D1은 없다**(ADR-0008) —
정류장 4,803줄(`stops.csv` 4,746 + 추정 좌표 57) · 노선 230(개편 전 111 + 개편 후 119) ·
노선별 정류장 42,390줄 · 환승 쌍 6,566줄 · 노선 쌍별 환승 지점 7,250줄, 압축 전 2.02MB(gzip 0.28MB).

**하나 남았다 — 요청당 CPU가 무료 요금제 상한을 넘는다.** workerd에서 재니 `/compare` 한 번이
중앙값 20~21ms로 상한 10ms의 두 배이고, 120개 중 110개 안팎이 넘는다. `walkableStops`와 `갈아탄다`
둘이 80%를 쓴다 — 줄일 곳은 `docs/architecture.md` §6-4 · §8에 적어 두었다.
설계는 2026-09-03에 닫혔다 — `docs/architecture.md` §7 표와 ADR-0008.

번호 잇기 규칙은 ADR-0006으로 닫혔고 못 찾는 쌍 0이다. 정류장 좌표도 들어왔다 —
`data/source/stops.csv` 4,746개, 결측 0(ADR-0007). 다음 단계는 `docs/architecture.md` §9 「다음 할 일」.
