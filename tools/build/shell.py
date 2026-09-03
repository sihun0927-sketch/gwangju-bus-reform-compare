"""껍데기 — 두 탭 공용 `index.html` 한 장 (CONTEXT 「껍데기」).

데이터와 무관한 부분만 여기 산다. 제목·탭 둘·입력칸·안내문·빈 결과 영역, htmx와 CSS·브라우저 조각 스크립트 부르기.
노선 개편 목록 표는 데이터에서 나오므로 밖에서 받아 자리에 끼운다.

탭 전환은 숨긴 라디오 단추와 CSS만으로 한다. 장소 탭 입력칸은 htmx로 Worker의 자동완성 조각을 받고,
브라우저 스크립트가 고른 출발·도착 좌표를 `/compare`에 보낸다(ADR-0001).
번호로 좁히기(자동완성·표 필터)는 architecture §8에서 아직 미결이다.
"""
from __future__ import annotations

from pathlib import Path

TITLE = "버스개편 비교"
LEAD = "2026년 10월 광주 시내버스 노선 개편 전후로 내 경로가 어떻게 달라지는지 비교합니다."

PLACE_TAB = "장소로 찾기"
ROUTE_TAB = "노선번호로 찾기"
PLACE_PLACEHOLDER = "장소나 주소 입력 (예: 전남대)"
PLACE_FIELDS = (("from", "출발"), ("to", "도착"))
ROUTE_PLACEHOLDER = "노선번호 입력 (예: 지원152)"
ROUTE_FIELD = ("number", "노선번호")
ROUTE_HINT = "번호로 좁히기는 아직 준비 중입니다. 아래 목록에서 노선을 고르세요."

# 카드가 끼워지는 자리. 목록 표의 줄마다 hx-target이 이것을 가리킨다 — 한 화면에 카드는 하나뿐이다
RESULT_ID = "result"
RESULT_EMPTY = "한 줄을 누르면 대체 노선과 정류장 변화가 여기에 나옵니다."

CSS = "site.css"
CSS_SOURCE = Path(__file__).resolve().parent / CSS
PLACE_JS = "place.js"
PLACE_JS_SOURCE = Path(__file__).resolve().parent / PLACE_JS
# CDN 스크립트 태그 하나. 우리가 쓰는 것은 hx-get · hx-target · hx-swap · hx-trigger 넷뿐이다(ADR-0001)
HTMX = "https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js"
# CDN이 다른 파일을 내주면 브라우저가 아예 싣지 않는다. 위 주소를 받아 sha384로 잰 값이다
HTMX_SRI = "sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+"


def _field(field_id: str, label: str, placeholder: str, *, places: bool = False) -> list[str]:
    field = [
        '<div class="field">',
        f'<input id="{field_id}" type="text" placeholder="{placeholder}"',
        f'<label for="{field_id}">{label}</label>',
        "</div>",
    ]
    if places:
        field[1] = (
            f'<input id="{field_id}" name="q" type="text" placeholder="{placeholder}"'
            f' hx-get="/places" hx-trigger="keyup changed delay:250ms"'
            f' hx-target="#{field_id}-candidates" autocomplete="off">'
        )
        field.append(f'<div class="place-candidate-list" id="{field_id}-candidates"></div>')
    return field


def _place_panel() -> list[str]:
    return [
        '<section class="panel place">',
        '<div class="card">',
        *[c for f, l in PLACE_FIELDS for c in _field(f, l, PLACE_PLACEHOLDER, places=True)],
        "</div>",
        '<div class="result" id="place-result"></div>',
        "</section>",
    ]


def _route_panel(route_list: str) -> list[str]:
    return [
        '<section class="panel route">',
        '<div class="card">',
        *_field(*ROUTE_FIELD, ROUTE_PLACEHOLDER),
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


def page(route_list: str) -> str:
    """껍데기 한 장. `route_list`는 노선 개편 목록 표 HTML이고 노선번호 탭 안에 통째로 들어간다."""
    return "\n".join([
        "<!doctype html>",
        '<html lang="ko">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{TITLE}</title>",
        f'<link rel="stylesheet" href="{CSS}">',
        f'<script src="{HTMX}" integrity="{HTMX_SRI}" crossorigin="anonymous" defer></script>',
        f'<script src="{PLACE_JS}" defer></script>',
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
        *_route_panel(route_list),
        "</div>",
        "</main>",
        "</body>",
        "</html>",
        "",
    ])
