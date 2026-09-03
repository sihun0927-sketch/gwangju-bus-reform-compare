# data

## source/ — 빌드 스크립트가 읽는 입력 8개

CSV 일곱과 형상 JSON 하나다. 여섯은 시가 공표한 원본(2026-09-02 반입, UTF-8 BOM)이고,
`stops.csv`는 광주 BIS API에서 받아 만든 것이며(2026-09-03, ADR-0007), `route_shapes.json`은
OSRM이 낸 것이다(2026-09-04, ADR-0009 · 아래 절). **손으로 고치지 않는다.** 빌드 스크립트는
읽기만 한다 — 스크립트가 만드는 둘도 `tools/build_stops.py`·`tools/build_shapes.py`가 다시 만든다.

| 파일 | 행 | 열 | 쓰이는 곳 |
|---|---|---|---|
| `광주권역 개편전 노선안.csv` | 111 | 버스번호 · 기점 · 종점 · 상행 정류장수 · 상행 정류장(순서대로) · 하행 정류장수 · 하행 정류장(순서대로) | 노선 개편 목록 표, 노선 변화 표의 개편 전 열, 번들 routes·route_stops |
| `광주권역 개편후 노선안.csv` | 119 | 같은 열 | 노선 변화 표의 개편 후 열, 번들 routes·route_stops |
| `노선개편 전후 비교표.csv` | 103 | 기존 노선 · 신규(대체) 노선 | 노선 개편 목록 표, 방면 선택·대체 노선 선택 버튼, 대체 관계의 유일한 출처 |
| `명칭 변경 정류소.csv` | 102 | 구분 · 현 정류소 · ID · 변경정류소 | 명칭 사전(ADR-0003), 비고 |
| `신설 정류소.csv` | 68 | 구분 · 정류소 | 비고 "신설 정류소", 좌표 채우기 대상(ADR-0004) |
| `통폐합이전정류소.csv` | 16 | 지역 · 구분 · 정류소명 · ID · 통폐합사유 | 비고 "폐지/통폐합/이전 · 사유" |
| `stops.csv` | 4,746 | STATION_NUM · BUSSTOP_NAME · ARS_ID · NEXT_BUSSTOP · BUSSTOP_ID · LONGITUDE · NAME_E · LATITUDE | 노선 지도 좌표, 번들 stops 표. **시 공표 아님** — 광주 BIS API(ADR-0007) |

## 알아 둘 함정

- **정류장 구분자가 파일마다 다르다.** 개편 전은 `▶`, 개편 후는 `>`.
- **번호 표기가 파일마다 다르다.** 개편 후 노선안은 `간선 01`·`급행 03`(등급 + 공백), 비교표는 `1`·`급행03`.
  개편 전 노선안은 방면 접미가 붙는다(`228(구151.화순사평)`), 비교표는 `228`. 잇는 규칙은 ADR-0006 —
  (종류, 번호, 방면)으로 갈라 견주고, 숫자만 적힌 것은 급행 아닌 것, 앞 0은 무시. 비교표 순환01 행만 `1`이다.
- **방면.** 같은 종류+번호가 행 여럿인 것. 개편 전: 228(2) · 두암81(4) · 상무62(2) · 선운101(2) ·
  송정97(2, `송정97`과 `송정97(봉정행)`) · 지원152(2). 개편 후: 지선 97(2, `지선 97`과 `지선 97(빛그린산단출근)`).
  접미 없는 행의 방면 이름은 「기본」.
- **급행 03·05·06과 간선 03·05·06이 따로 있다.** 기·종점이 같고 정류장 수만 다르다. 숫자만 남기면 섞인다.
- **하행 0개.** 개편 전 7행(순환01, 상무62 2행, 두암81 4행), 개편 후 1행(지선 97(빛그린산단출근)).
- **대체 노선 없음.** 비교표 1행(`두암181`, 신규 칸 비어 있음).
- **명칭 변경은 ID 단위**라 같은 옛 이름이 두 줄씩이고, 새 이름이 방향별로 갈라진다(1번출구/2번출구).
  `입암`은 `입암(남구)`·`입암(북구)`로 갈라진다.
- **통폐합의 `A(B)` 표기**는 B를 A로 흡수했다는 뜻. ID 칸도 `1001(1010)`.
  구분이 `통폐합`인 4행이 모두 이 꼴이라 노선안의 정류장 이름과 안 맞는다 — 빌드는 그 줄의 비고를 비우고
  넘어간다(`폐지` 11행·`이전` 1행은 이름이 그대로라 붙는다). 이름 대조 규칙을 넓히는 것은 다음 스펙.
- **월드컵경기장정문**은 명칭 변경(→ 월드컵경기장역)과 폐지(2호선 개통 때 재운영) 양쪽에 있다.
- **좌표가 없다.** 시 공표 여섯 파일 모두. 좌표는 같은 폴더의 `stops.csv`(ADR-0007).

## 정류장 좌표 — 광주 BIS API (ADR-0007)

| 파일 | 무엇 | 만드는 것 |
|---|---|---|
| `back_up/api_stops.json` | API 응답 원본. 고치지 않는다 | `python tools/fetch_stops.py` (키는 `.env`의 `GWANGJU_BUS_KEY`) |
| `source/stops.csv` | 정류장 4,746개 × 8열, 좌표 결측 0. **좌표의 유일한 출처** | `python tools/build_stops.py` |
| `name_canon.json` | 노선안 표기 → API 정식 표기 8개 | `python tools/build_stops.py` |

`source/stops.csv` 열: `STATION_NUM, BUSSTOP_NAME, ARS_ID, NEXT_BUSSTOP, BUSSTOP_ID, LONGITUDE, NAME_E, LATITUDE`

### 알아 둘 함정

- **API 이름 46개에 꼬리 공백이 있다**(`'대산         '`). `build_stops.py`가 떼어 낸다. 다시 넣지 말 것.
- **`ARS_ID`가 1,697개 비어 있다** — 광주 밖(전남 통합분). ID 조인은 광주 정류장에만 된다.
  명칭 변경 CSV의 ID 102개는 모두 `ARS_ID`와 맞는다.
- `NEXT_BUSSTOP` 528개, `NAME_E` 188개가 비어 있다. `LATITUDE`·`LONGITUDE`는 4,746개 **전부** 있다.
- **이름을 대조하기 전에 `name_canon.json`을 통과시킨다.** 값이 `null`이면 좌표 없음이다.
- 개편 전 노선안 정류장 1,499개는 100% 붙는다. 개편 후 1,507개 중 1,369(90.8%).
  못 붙는 138개는 명칭 변경 새 이름 81 · 신설 56 · `광주교대역2번출구` 1이다.

## 노선 형상 — OSRM (ADR-0009)

`source/route_shapes.json`(2.7MB). 지도의 선 둘이 여기 있다. 정류장을 순서대로 이은 것이며
**실제 운행 경로가 아니다** — 시가 공표한 것은 정류장의 순서뿐이다. 화면이 그렇게 적는다
(CONTEXT 「노선 형상」).

**라이선스가 다르다.** 이 파일만 **ODbL**(© OpenStreetMap contributors)이다. 리포의 나머지는 MIT다.

| 열쇠 | 무엇 | 개수 | 키 | 값 |
|---|---|---|---|---|
| `shapes` | 노선 형상 — **차도**(car) | **452** (개편 전 215 + 개편 후 237) | `노선망\|노선 이름\|up 또는 down`, 예 `before\|문흥18\|up` | `points`(`[[위도, 경도], …]`, 소수 6자리) · `straight`(직선으로 남은 구간 수) |
| `walks` | 환승 도보 — **인도**(foot) | **141** | `작은 STATION_NUM\|큰 STATION_NUM`, 예 `1000\|1001` | `[[위도, 경도], …]` |
| `meta` | 반입 날짜 · 엔진 · OSM 판 · 라이선스 · 단순화·튐 판정 값 | | | |

실측: 형상 점 55,791개(형상당 평균 123) · 직선으로 남은 구간 63개(전체 약 21,000구간의 0.3%) ·
도보 점 평균 4.1개.

**환승 도보가 141쌍뿐인 까닭**은 `route_links` 7,250개 중 **6,399개가 같은 정류장에서 갈아타기**
때문이다. 걸을 것이 없으면 열쇠도 없다. 출발·도착 도보는 여기 없다 — 시민이 고른 지점이라 미리
낼 수 없고 화면이 직선으로 잇는다(ADR-0009 결정 7).

### 다시 만드는 절차

OSM 남한 추출본이 갱신되면 형상도 달라지므로 `meta.made`(반입 날짜)를 함께 본다.

```bash
# 1. 도로망 준비 — 한 번만. WSL/리눅스에 도커가 있어야 한다
mkdir -p ~/osrm/car && cd ~/osrm/car
wget -O south-korea.osm.pbf https://download.geofabrik.de/asia/south-korea-latest.osm.pbf
docker run --rm -v ~/osrm/car:/data ghcr.io/project-osrm/osrm-backend \
  osrm-extract -p /opt/car.lua /data/south-korea.osm.pbf
docker run --rm -v ~/osrm/car:/data ghcr.io/project-osrm/osrm-backend \
  osrm-partition /data/south-korea.osrm
docker run --rm -v ~/osrm/car:/data ghcr.io/project-osrm/osrm-backend \
  osrm-customize /data/south-korea.osrm

# 1'. 환승 도보용 foot 프로파일도 같은 PBF로 한 벌 더. 자리를 갈라야 한다 —
#     osrm-extract가 PBF 이름으로 파일을 써서 car와 foot이 부딪친다
mkdir -p ~/osrm/foot && ln ~/osrm/car/south-korea.osm.pbf ~/osrm/foot/
docker run --rm -v ~/osrm/foot:/data ghcr.io/project-osrm/osrm-backend \
  osrm-extract -p /opt/foot.lua /data/south-korea.osm.pbf
# partition·customize는 car와 같다

# 2. 서버 둘 띄우기 — car는 5000, foot은 5001
docker run --rm -d --name osrm-car  -p 5000:5000 -v ~/osrm/car:/data \
  ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/south-korea.osrm
docker run --rm -d --name osrm-foot -p 5001:5000 -v ~/osrm/foot:/data \
  ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/south-korea.osrm

# 3. 뽑기 (약 2분)
python tools/build_shapes.py
```

### 알아 둘 함정

- **정류장 자리는 `route_geometry.chain`이 고른다.** 여기서 다시 고르면 지도의 점과 선이 다른
  자리를 가리킨다. 같은 이름이 여러 고을에 있는 문제(「금곡마을」 6줄, 55km)를 그 함수가 푼다.
- **진행 방향(`bearings`)을 안 주면 반대 차선에 붙는다.** 길 양쪽 정류장은 20m 차이라 직선에서는
  안 보이지만 도로 경로에서는 유턴이 된다.
- **`approaches=curb`는 쓰지 않는다.** 정류장 좌표가 도로 어느 쪽에 찍혔는지 `stops.csv`가
  보장하지 않아, 반대편에 찍혀 있으면 유턴을 되레 만들어 낸다(ADR-0009 결정 6).
- **`straight`가 0이 아닌 형상**은 그 구간을 직선으로 두었다는 뜻이다(직선 대비 5배 & 2km 초과).
  갑자기 늘었으면 도로망이나 좌표가 나빠진 것이다.

## 배차간격 — 개편 전만 (2026-09-04 반입)

`source/route_headways_with_stops.csv` 110행. 장소 탭 카드의 경로 줄이 「배차간격 12분」이라 적는 값이다
(CONTEXT 「경로 줄」). 빌드는 `route_name`과 `headway_minutes` **두 열만** 읽는다 — 뒤 두 열의 정류장
목록은 노선안 CSV와 겹치는 값이라 쓰지 않고, 이 파일이 어느 노선을 말하는지 눈으로 대조할 때만 쓴다.

| 무엇 | 값 |
|---|---|
| 노선 이름 | 개편 전 노선안의 버스번호와 **같은 표기**다. 잇는 규칙(ADR-0006)이 필요 없고 공백만 뗀다 |
| 값 | 분. 5 ~ 250, 중앙값 20 |
| 붙는 범위 | 개편 전 111행 중 **110개**. 개편 후는 0개 |

### 알아 둘 함정

- **개편 후에는 공표된 값이 없다.** 이름으로만 찾으면 두 노선망에 다 있는 `228`·`419`·`518`·`1187`이
  개편 후 카드에서 개편 전 값을 제 것처럼 적는다. `bundle.make`가 노선망을 가려 붙인다.
- **순환01 한 행이 이 파일에 없다.** 개편 전인데도 「정보 없음」인 유일한 노선이다.
- **다시 받을 절차가 없다.** 출처는 공공데이터 API라고 들었으나(2026-09-04 사용자 확인) **어느 서비스의
  어느 응답인지 확인되지 않았고**, `stops.csv`와 달리 응답 원본이 `back_up/`에 없다. 값이 낡으면
  이 파일을 통째로 다시 받아 갈아 끼우는 수밖에 없다.
- 배차간격은 **예상 시간 계산에 쓰지 않는다.** 배차 대기를 넣지 않는다는 결정은 그대로다
  (CONTEXT 「추정 소요 시간」). 화면 각주가 그렇게 적는다.


## 기종점정렬표.csv — 사람이 적는 기·종점 정렬

`data/기종점정렬표.csv`(18행). 기·종점 이름과 정류장 겹침으로 방향을 못 정한 쌍만 여기 온다.
`data/source/`가 아니라 `data/`에 있다 — 시 공표 자료가 아니라 우리가 적는 파일이기 때문이다.
행이 하나라도 없으면 빌드가 그 쌍 이름을 내고 멈춘다(`python -m tools.build`).

열: `개편전번호, 개편전방면, 대체노선, 개편후방면, 개편전상행이맞닿는쪽, 확인`. 앞 네 열은 조각 경로
네 단계와 같고, `개편전상행이맞닿는쪽`은 `상행`(그대로) 또는 `하행`(뒤집어 맞댐)이다.
지금 값은 실측의 겹침이 큰 쪽으로 채워 둔 것이고 **`확인` 열은 비어 있다** — 사람이 검토할 자리다.
대체 노선에 하행이 없으면(편도, 지선97(빛그린산단출근)) 뒤집어 맞댈 목록이 없으므로 `상행`만 쓸 수 있다.
선운101 두 방면이 그렇다 — 실측은 겹침이 개편 전 하행 쪽에서 더 크다고 나오지만, 그 배치는 하행 두 칸을
비우라는 ADR-0003 결정 6·ADR-0006 결정 7과 어긋난다. 표 모양을 바꿀지는 ADR을 고칠 때 정한다.
목록은 `python tools/measure_direction.py`가 낸다.
