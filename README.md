# gwangju-bus-reform-compare

2026년 10월 광주 시내버스 노선 개편 전후를 시민이 비교하는 웹 서비스.
탭 둘: **장소로 찾기**(출발·도착 장소를 넣으면 개편 전후 경로를 비교)와
**노선번호로 찾기**(번호를 넣으면 대체 노선과 노선 변화 표를 보여 줌).

구조는 **정적 HTML + htmx 조각**이다. 이유와 부품별 역할은 `docs/architecture.md`에 있다.

## 새로 합류했다면 이 순서로 읽는다

1. `CONTEXT.md` — 용어. 방면·대체 노선·조각·유지/경유 제외/경유 추가 같은 말의 뜻
2. `docs/architecture.md` — 구조와 부품 역할, 두 탭의 정적/동적 분할, 데이터 흐름, 결정 요약
3. `docs/adr/` — 되돌리기 어려운 결정 열과 그 이유 (0004는 0007로, 0001의 D1 부분은 0008로 대체됨)
4. `data/README.md` — 원천 CSV 8개의 열과 행 수, 정류장 좌표(`source/stops.csv`), 배차간격(`source/route_headways.csv`), 알아 둘 함정
5. **모듈 지도** — https://claude.ai/code/artifact/6977a9d4-929e-40d8-a252-9620cb46f86b
   탭마다 두 장: 모듈 지도(화면 조각 → 화면 모듈 → 조각 → 만드는 곳(빌드 스크립트 / Worker) → 데이터, 정적/동적·용어·데이터 있음/예정)와
   만드는 곳의 단계(단계별 입력·출력·테스트 경계). 구현·유지보수 때 보는 것. 같은 그림이 `docs/images/`에 PNG로 있다(아래)
6. 화면 목업 — https://claude.ai/code/artifact/fbf89d71-17a6-4f49-b963-aa3eb506b539
   (페이지 4장: 장소 탭 분할 · 노선번호 탭 분할 · 노선 변화 표 · 조각 출처 a vs b. 용어는 2026-09-03 확정본). PNG는 아래

## 그림 (캔버스 없이 볼 때)

캔버스에서 렌더링한 PNG. 캔버스가 바뀌면 다시 뽑는다(`docs/images/README.md`).

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
Worker 코드는 아직 없다(노선번호 탭은 정적 파일만으로 돈다, ADR-0002).

대시보드 빌드 설정(리포 밖, 한 번만): 빌드 명령 `python -m tools.build` · 배포 명령 `npx wrangler deploy` · 루트 `/`.
로컬 확인: `python -m tools.build && npx wrangler deploy --dry-run`.

빌드 환경 변수 `KAKAO_JS_KEY`(Kakao JavaScript 키, ADR-0005)가 있으면 껍데기에 지도 SDK 태그가 들어간다.
없으면 빌드는 그대로 성공하고 노선 지도 자리에 「지도를 불러오지 못했습니다」 한 줄만 남는다. **키는 리포에
없다** — Cloudflare 설정에 둔다. 로컬에서 지도를 보려면 `KAKAO_JS_KEY=… python -m tools.build`.

## 빌드와 테스트

```
python -m tools.build            # data/source → out/ (정적 조각) + worker/data.json (번들 JSON) + worker/headway.json (배차간격 표)
python -m pytest                 # 빌드 검사 — out/의 조각과 번들 JSON을 본다
npm test                         # Worker 검사 — 빌드를 한 번 돌린 뒤 node --test
npm run deploy:dry               # wrangler deploy --dry-run
python tools/measure_direction.py    # 실측 — 기·종점 정렬 단계별 개수 (§6-1)
python tools/measure_transfers.py    # 실측 — 번들 크기와 환승 표 줄 수 (§6-2)
node tools/measure_search.mjs        # 실측 — 상태 분포와 요청 시간 (§6-3, 빌드가 먼저다)
python tools/measure_headway.py      # 실측 — 배차간격 추정과 차량 수지 (§6-4)
node tools/check_key.mjs             # `.dev.vars`에 어느 제공자 키가 들어왔는지만 본다 (키는 안 찍는다)
node tools/check_key.mjs --live      # 그 키가 살아 있는지 물어본다 (모형 목록 — 공짜다)
node tools/measure_infer.mjs         # 실측 — 추론의 흩어짐과 돈 (§6-5). **진짜로 부른다, 돈이 든다**
```

`out/`과 `worker/data.json`·`worker/headway.json`은 빌드 산출물이라 저장소에 없다. **배포도 테스트도 빌드가 먼저다.**

## 상태 (2026-09-04)

**노선번호 탭이 정적 파일로 돈다.** `python -m tools.build`가 `out/`에 껍데기 `index.html` 한 장(노선 개편 목록 표 103줄)과
노선 변화 카드 103개 · 노선 변화 표 205개를 쓴다. `out/`을 정적 서버로 열면 목록의 한 줄을 눌러 카드를,
카드의 버튼을 눌러 표를 새로고침 없이 바꿀 수 있다 — Worker도 D1도 없이(ADR-0001·0002).
표 조각마다 상행 좌표가 실려 있어 카드 위 노선 지도가 개편 전(굵은 초록)과 대체 노선(가는 파랑)을 겹쳐 그린다 —
그리는 브라우저 코드는 `out/map.js` 하나뿐이고, Kakao JS 키가 있는 환경에서만 뜬다(ADR-0005).

**장소 탭의 `/compare`가 직행과 환승 1~2회까지 답한다.** 같은 빌드가 `worker/data.json`도 쓴다 —
ADR-0008이 정한 표 **다섯이 다 들어갔다**: 정류장 4,803줄(`stops.csv` 4,746 + 추정 좌표 57) ·
노선 230(개편 전 111 + 개편 후 119) · 노선별 정류장 42,390줄 · 환승 쌍 6,566줄 ·
노선 쌍별 환승 지점 7,250줄, 압축 전 2.02MB(gzip 0.28MB). 좌표 둘을 주면
`GET /compare?from=lat,lng&to=lat,lng`가 개편 전 카드와 개편 후 카드 한 쌍을 돌려주고, 머리에
「직행 · 환승 1회 · 환승 2회 · 경로 없음」이 선다. 환승 줄에는 내리는 곳 → 타는 곳과 환승 도보가 있다.
**개편 후 노선 118개의 배차간격 추정이 `/headway`로 나간다.** 시가 공표한 것은 총량뿐이라(운행횟수
8394 → 9355회, 노선 103 → 118개, 증차 없음) 노선별 값은 개편 전 배차간격을 정류장에 실어 두고
개편 후 노선이 물려받게 해 나눈다(ADR-0009). `GET /headway?route=간선18`이 배차간격 추정 · 밴드 ·
등급 넷 중 하나 · **답변 뼈대**를 JSON으로 준다 — 이 리포에서 유일하게 조각이 아닌 경로다.
같은 물음이면 늘 같은 답이 나오고(빌드가 미리 계산한다), 「간선18」「간선 18」「18」「018」과 개편 전
번호 「문흥18」이 다 한 기록으로 모인다. 결론 하나는 이렇다 — **증차 없이 9355회를 돌리려면 표정속도가
10.2% 올라야 하고, 시가 밝힌 통행시간 단축(21.7%)이 이뤄지면 증차 없이 가능하다**(`docs/architecture.md` §6-4).

**노선 변화 카드의 대체 노선 줄마다 배차간격이 뜬다.** 카드는 정적 파일이라 자리와 「계산중…」만
적어 두고, htmx가 `GET /headway/{노선}`을 불러 그 칸을 바꾼다. 그 자리에 오는 수는 표에서 꺼낸
고정값이 아니라 **부를 때마다 모형이 다시 판단한 추론값**이다(ADR-0010, OpenAI). 매번 다르되
한곳으로 모이게 하는 장치가 넷이다 — 구조화 출력 · 표본 셋의 중앙값 · 계산값 밴드 안에 가두기 ·
낮은 온도. 옆의 「?」를 누르면 왜 그 값인지,
몇 번 물어 무엇이 나왔는지, 그리고 시가 발표한 값이 아니라는 것이 나온다.
**키(`OPENAI_API_KEY`)는 리포에 없다** — 없으면 추론 없이 계산값을 그대로 보이고 화면은 그대로 돈다.
로컬에서 켜려면 `.dev.vars`(커밋 안 됨, 틀은 `.dev.vars.example`)의 알맞은 줄 오른쪽에 키를 붙여 넣고,
배포에는 `npx wrangler secret put <이름>`으로 넣는다(ADR-0005·0010). 자리만 잡힌 값
(`sk-ant-여기에_…`)은 **키 없음으로 본다** — 헛요청을 안 던진다. 어느 제공자 키가 들어왔는지는
`node tools/check_key.mjs`가 **앞머리 여덟 글자와 길이만** 내어 알려 준다 — 키를 로그나 채팅에
붙이지 않기 위해서다.

아직 「준비 중」인 것은 `/places`와 `/journey/…`이고, 화면의 입력칸도 아직 자리뿐이다.
남은 실측 하나는 요청당 CPU다 — 지금은 중앙값 32~36ms로 무료 요금제 상한 10ms를 크게 넘는다
(`docs/architecture.md` §6-3 · §8).
설계는 2026-09-03에 닫혔다 — `docs/architecture.md` §7 표와 ADR-0008.

번호 잇기 규칙은 ADR-0006으로 닫혔고 못 찾는 쌍 0이다. 정류장 좌표도 들어왔다 —
`data/source/stops.csv` 4,746개, 결측 0(ADR-0007). 다음 단계는 `docs/architecture.md` §9 「다음 할 일」.
