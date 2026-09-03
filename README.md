# gwangju-bus-reform-compare

2026년 10월 광주 시내버스 노선 개편 전후를 시민이 비교하는 웹 서비스.
탭 둘: **장소로 찾기**(출발·도착 장소를 넣으면 개편 전후 경로를 비교)와
**노선번호로 찾기**(번호를 넣으면 대체 노선과 노선 변화 표를 보여 줌).

구조는 **정적 HTML + htmx 조각**이다. 이유와 부품별 역할은 `docs/architecture.md`에 있다.

## 새로 합류했다면 이 순서로 읽는다

1. `CONTEXT.md` — 용어. 방면·대체 노선·조각·유지/경유 제외/경유 추가 같은 말의 뜻
2. `docs/architecture.md` — 구조와 부품 역할, 두 탭의 정적/동적 분할, 데이터 흐름, 결정 요약
3. `docs/adr/` — 되돌리기 어려운 결정 일곱과 그 이유 (0004는 0007로 대체됨)
4. `data/README.md` — 원천 CSV 6개의 열과 행 수, 정류장 좌표(`stops.csv`), 알아 둘 함정
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

## 상태 (2026-09-03)

설계 결정만 있고 화면 코드는 없다. 번호 잇기 규칙은 ADR-0006으로 닫혔고 `tools/measure_direction.py`가 못 찾는 쌍 0으로 재현한다.
정류장 좌표가 들어왔다 — `data/stops.csv` 4,746개, 결측 0(ADR-0007). 개편 전 노선안 정류장 1,499개가 100% 붙는다.
다음 단계는 `docs/architecture.md` §9 「다음 할 일」.
