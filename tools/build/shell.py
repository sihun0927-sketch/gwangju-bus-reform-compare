"""껍데기 — 두 탭 공용 `index.html` 한 장 (CONTEXT 「껍데기」).

데이터와 무관한 부분만 여기 산다. 제목·탭 둘·입력칸·안내문·빈 결과 영역, htmx와 CSS·브라우저 조각 스크립트 부르기.
노선 개편 목록 표는 데이터에서 나오므로 밖에서 받아 자리에 끼운다.

탭 전환은 숨긴 라디오 단추와 CSS만으로 한다. 장소 탭 입력칸은 htmx로 Worker의 자동완성 조각을 받고,
브라우저 스크립트가 고른 출발·도착 좌표를 `/compare`에 보낸다(ADR-0001).

노선번호 탭은 Worker 없이 돈다. 입력칸의 자동완성 후보(CONTEXT)는 `<datalist>`다 — 비교표 번호 103개를
껍데기에 통째로 싣고 좁히는 것은 브라우저가 한다. 고르면 htmx의 `path-params` 확장이
`route/{number}.html`의 `{number}`를 입력값으로 바꿔 카드 조각을 부른다(architecture §7-3 Q1·Q2).
표 필터는 없다 — 목록 표는 늘 103행이다.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

from .route_list import Row

TITLE = "버스개편 비교"
LEAD = "2026년 10월 광주 시내버스 노선 개편 전후로 내 경로가 어떻게 달라지는지 비교합니다."

PLACE_TAB = "장소로 찾기"
ROUTE_TAB = "노선번호로 찾기"
PLACE_PLACEHOLDER = "장소나 주소 입력 (예: 전남대)"
PLACE_FIELDS = (("from", "출발"), ("to", "도착"))
ROUTE_PLACEHOLDER = "노선번호 입력 (예: 지원152)"
ROUTE_FIELD = ("number", "노선번호")
ROUTE_HINT = "번호를 치면 후보가 뜹니다. 목록에 있는 번호를 골라야 카드가 열립니다."
# 후보 목록의 id. 입력칸의 `list=`가 이것을 가리킨다
CANDIDATES_ID = "route-numbers"
CANDIDATE_NONE = "대체 노선 없음"

# 카드가 끼워지는 자리. 목록 표의 줄마다 hx-target이 이것을 가리킨다 — 한 화면에 카드는 하나뿐이다
RESULT_ID = "result"
RESULT_EMPTY = "한 줄을 누르면 대체 노선과 정류장 변화가 여기에 나옵니다."

CSS = "site.css"
CSS_SOURCE = Path(__file__).resolve().parent / CSS
PLACE_JS = "place.js"
PLACE_JS_SOURCE = Path(__file__).resolve().parent / PLACE_JS
MAP_JS = "map.js"
MAP_JS_SOURCE = Path(__file__).resolve().parent / MAP_JS
# 브라우저 조각 스크립트 둘. 순서는 상관없다 — 둘 다 자기 자리만 본다
BROWSER_SCRIPTS = (PLACE_JS, MAP_JS)

# Kakao 지도 SDK. JS 키는 리포에 없고 빌드 때 환경 변수에서 받아 여기에 박는다(ADR-0005).
# 키가 없으면 태그를 아예 안 단다 — 그때는 `map`이 지도 자리를 감춘다. 로컬 빌드가 그 자리다.
KAKAO_SDK = "https://dapi.kakao.com/v2/maps/sdk.js"
KAKAO_JS_KEY_ENV = "KAKAO_JS_KEY"
# CDN 스크립트 태그 둘(htmx + 공식 확장 하나)과 우리 스크립트 둘(place.js · map.js),
# 그리고 JS 키가 있을 때만 붙는 Kakao 지도 SDK.
# 우리가 쓰는 htmx 속성은 hx-get · hx-target · hx-swap · hx-trigger · hx-ext 다섯뿐이다(ADR-0001)
HTMX = "https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js"
# CDN이 다른 파일을 내주면 브라우저가 아예 싣지 않는다. 위 주소를 받아 sha384로 잰 값이다
HTMX_SRI = "sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+"
# htmx 공식 확장. `hx-get`의 `{number}`를 입력값(URL 인코딩)으로 바꾼다 — 열두 줄짜리 파일이라
# 우리 스크립트를 쓰지 않고도 입력값에서 정적 조각 주소를 만든다. htmx 뒤에 실려야 켜진다
PATH_PARAMS = "https://unpkg.com/htmx-ext-path-params@2.0.2/path-params.js"
PATH_PARAMS_SRI = "sha384-+0JRT1scVqIpEs6pL27kzkwjQiKfufPTrqIby57YbBrMMkYvVqHev8WykHtNFTIj"


def _field(
    field_id: str, label: str, placeholder: str, attrs: str = " disabled", *, places: bool = False
) -> list[str]:
    field = [
        '<div class="field">',
        f'<input id="{field_id}" type="text" placeholder="{placeholder}"{attrs}>',
        f'<label for="{field_id}">{label}</label>',
        "</div>",
    ]
    if places:
        field.append(f'<div class="place-candidate-list" id="{field_id}-candidates"></div>')
    return field


def _route_field() -> list[str]:
    """노선번호 입력칸. 값이 굳으면(후보를 고르거나 엔터) 그 번호의 카드 조각을 결과 자리에 끼운다.

    목록에 없는 값이면 조각 파일이 없어 404가 오고 htmx는 아무것도 끼우지 않는다 — 안내문이 그대로 남는다.
    """
    field_id, label = ROUTE_FIELD
    attrs = (
        f' name="{field_id}" list="{CANDIDATES_ID}" autocomplete="off"'
        ' hx-ext="path-params"'
        f' hx-get="route/{{{field_id}}}.html" hx-target="#{RESULT_ID}"'
        ' hx-trigger="change" hx-swap="innerHTML show:top"'
    )
    return _field(field_id, label, ROUTE_PLACEHOLDER, attrs)


def _candidate_label(row: Row) -> str:
    return " · ".join(row.replaced) or CANDIDATE_NONE


def candidates(rows: list[Row]) -> str:
    """자동완성 후보 — 값은 번호, 설명은 대체 노선 이름들 「지원152 — 급행1003 · 228」(CONTEXT).

    줄 순서는 목록 표 그대로다. 좁히는 것은 브라우저가 한다.
    """
    return "\n".join([
        f'<datalist id="{CANDIDATES_ID}">',
        *[
            f'<option value="{escape(r.number)}" label="{escape(_candidate_label(r))}">'
            for r in rows
        ],
        "</datalist>",
    ])


def _place_panel() -> list[str]:
    return [
        '<section class="panel place">',
        '<div class="card">',
        *[
            c
            for f, l in PLACE_FIELDS
            for c in _field(
                f, l, PLACE_PLACEHOLDER,
                f' name="q" hx-get="/places" hx-trigger="keyup changed delay:250ms"'
                f' hx-target="#{f}-candidates" autocomplete="off"',
                places=True,
            )
        ],
        "</div>",
        '<div class="result" id="place-result"></div>',
        "</section>",
    ]


def _route_panel(route_list: str, rows: list[Row]) -> list[str]:
    return [
        '<section class="panel route">',
        '<div class="card">',
        *_route_field(),
        candidates(rows),
        f'<p class="hint">{ROUTE_HINT}</p>',
        "</div>",
        '<div class="card">',
        route_list.rstrip("\n"),
        "</div>",
        f'<div class="result" id="{RESULT_ID}">',
        f'<p class="empty">{RESULT_EMPTY}</p>',
        "</div>",
        "</section>",
    ]


def _map_scripts(kakao_js_key: str) -> list[str]:
    """지도를 그리는 SDK 태그. 키가 없으면 아무것도 안 단다(ADR-0005).

    `autoload=false`로 받고 `map`이 `kakao.maps.load()`로 기다린다 — 스크립트를 `defer`로 싣기
    때문에 자동으로 켜지는 쪽은 언제 준비되는지가 정해지지 않는다.
    """
    if not kakao_js_key:
        return []
    src = f"{KAKAO_SDK}?appkey={quote(kakao_js_key, safe='')}&autoload=false"
    return [f'<script src="{src}" defer></script>']


def page(route_list: str, rows: list[Row], kakao_js_key: str = "") -> str:
    """껍데기 한 장. `route_list`는 노선 개편 목록 표 HTML이고 노선번호 탭 안에 통째로 들어간다.

    `rows`는 그 표의 줄들이다 — 후보를 같은 자리에서 만들어야 목록과 후보가 같은 번호를 적는다.
    `kakao_js_key`는 지도 SDK에 박는 값이고, 빈 값이면 지도를 안 싣는다(ADR-0005).
    """
    return "\n".join([
        "<!doctype html>",
        '<html lang="ko">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{TITLE}</title>",
        f'<link rel="stylesheet" href="{CSS}">',
        f'<script src="{HTMX}" integrity="{HTMX_SRI}" crossorigin="anonymous" defer></script>',
        f'<script src="{PATH_PARAMS}" integrity="{PATH_PARAMS_SRI}"'
        ' crossorigin="anonymous" defer></script>',
        *_map_scripts(kakao_js_key),
        *[f'<script src="{js}" defer></script>' for js in BROWSER_SCRIPTS],
        "</head>",
        "<body>",
        '<main class="page">',
        f"<h1>{TITLE}</h1>",
        f'<p class="lead">{LEAD}</p>',
        '<div class="tabbed">',
        # 라디오 단추가 패널보다 앞에 있어야 CSS가 형제 선택자로 켜고 끌 수 있다
        '<input type="radio" name="tab" id="tab-place" class="tab-toggle">',
        '<input type="radio" name="tab" id="tab-route" class="tab-toggle" checked>',
        '<nav class="tabs">',
        f'<label for="tab-place">{PLACE_TAB}</label>',
        f'<label for="tab-route">{ROUTE_TAB}</label>',
        "</nav>",
        *_place_panel(),
        *_route_panel(route_list, rows),
        "</div>",
        "</main>",
        "</body>",
        "</html>",
        "",
    ])
