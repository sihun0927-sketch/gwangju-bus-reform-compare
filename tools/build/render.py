"""6단계 조각 — 결과를 HTML 토막으로 쓴다 (`<!doctype>` 없음, htmx가 자리에 끼운다).

표 규격은 docs/architecture.md §5, 화면 문구는 CONTEXT.md 「노선번호로 찾기」를 따른다.
"""
from __future__ import annotations

import json
from html import escape

from .branches import Pair
from .load import Route
from .notes import Note
from .route_card import Card, Choice, Key, NO_REPLACEMENT
from .route_geometry import Geometry
from .route_list import Row
from .shell import RESULT_ID, page as shell_page
from .stop_match import ADDED, DROPPED, KEPT, Line

COLUMNS = (
    "#",
    "개편 전 상행 정류장",
    "개편 후 상행 정류장",
    "개편 전 하행 정류장",
    "개편 후 하행 정류장",
    "비고",
)
FLIPPED_NOTE = "기점·종점이 반대라 뒤집어 맞댔습니다"
SOURCE_NOTE = (
    "출처: 광주광역시 시내버스 노선개편안 「노선개편 전·후 비교표」 · 「광주권역 개편전/개편후 노선안」"
)
STATE_CLASS = {KEPT: "kept", DROPPED: "dropped", ADDED: "added"}

# 카드 안 노선 변화 표 자리. 버튼의 hx-target이 이것을 가리킨다 — 한 화면에 카드는 하나뿐이다
SLOT_ID = "route-change"
REPLACED_LEAD = "개편 후에는 →"

# 노선 지도 — 자리와 범례는 카드에, 좌표와 「지도에 없습니다」 줄은 표에 있다. 표가 바뀌면 지도도 바뀐다
MAP_LEGEND = (
    "굵은 초록 = 개편 전 · 가는 파랑 = 대체 노선 · 점: 유지 회색 · 경유 제외 빨강 · 경유 추가 파랑"
)
MAP_MISSING = "좌표 없는 정류장 {count}곳은 지도에 없습니다"
GEOMETRY_CLASS = "route-geometry"
UP_STOPS = "개편 전 상행 정류장"
DOWN_STOPS = "개편 전 하행 정류장"

LIST_TITLE = "노선번호 개편안"
LIST_LEAD = (
    "시가 공표한 비교표에 실린 개편 전 노선입니다."
    " 한 줄을 누르면 그 노선의 대체 노선과 노선 변화 표가 아래에 뜹니다."
)
LIST_COLUMNS = ("개편 전 노선", "개편 후 노선")
# 줄을 누르는 것은 마우스만이 아니다 — 탭으로 옮겨 엔터나 스페이스를 쳐도 같은 조각을 부른다
LIST_TRIGGER = "click, keyup[key=='Enter'], keyup[key==' ']"
# 결과 영역은 목록 표 아래에 있다. 그냥 끼우면 긴 목록의 끝을 누른 사람에게는 화면 밖에서 바뀐다
LIST_SWAP = "innerHTML show:top"


def _summary(direction: str, counts: dict[str, int]) -> list[str]:
    return [
        f'<li class="{STATE_CLASS[state]}">'
        f'<span class="label">{direction} · {state}</span> '
        f'<span class="count">{counts[state]}곳</span></li>'
        for state in (KEPT, DROPPED, ADDED)
    ]


def _cells(line: Line | None) -> str:
    """한 방향의 두 칸. 색은 줄이 아니라 이 두 칸에 붙는다 — 상행과 하행이 한 줄에서 상태가 다르다."""
    if line is None:
        return "<td></td><td></td>"
    cls = STATE_CLASS[line.state]
    return f'<td class="{cls}">{escape(line.before)}</td><td class="{cls}">{escape(line.after)}</td>'


def _note_cell(note: Note) -> str:
    """비고 칸. 사유 문장은 `title`이라 마우스를 올렸을 때만 보인다(ADR-0003 개정)."""
    title = f' title="{escape(note.title)}"' if note.title else ""
    return f'<td class="note"{title}>{escape(note.text)}</td>'


def _geometry_script(geometry: Geometry) -> str:
    """지도 좌표를 조각 안에 싣는다. 브라우저 `map.js`가 htmx 뒤에 읽어 그린다 (§7-3 Q6).

    `</` 를 막는 것은 JSON 안의 정류장 이름이 `<script>`를 먼저 닫아 버리는 일을 없애기 위해서다.
    """
    body = json.dumps(geometry.data, ensure_ascii=False, separators=(",", ":"))
    return (
        f'<script type="application/json" class="{GEOMETRY_CLASS}">'
        + body.replace("</", "<\\/")
        + "</script>"
    )


def route_change_table(
    pair: Pair,
    up: list[Line],
    down: list[Line],
    up_counts: dict[str, int],
    down_counts: dict[str, int],
    *,
    flipped: bool,
    row_notes: list[Note],
    geometry: Geometry,
) -> str:
    """노선 변화 표 조각 하나. 제목은 「<번호(방면)> 노선 변화」.

    지도 좌표도 여기 실린다 — 표 하나가 지도 하나이므로 카드가 아니라 표에 둔다(§7-3 Q6).
    좌표 없는 정류장을 알리는 줄도 표마다 값이 달라 여기 있다. 카드는 기본 표를 품으므로
    카드 조각에도 함께 나오고, 버튼을 눌러 표가 바뀌면 그 줄도 같이 바뀐다.
    """
    out = [
        f'<section class="route-change" data-before="{escape(pair.before.name)}"'
        f' data-after="{escape(pair.after.name)}">',
        *(
            [f'<p class="map-missing">{MAP_MISSING.format(count=geometry.missing)}</p>']
            if geometry.missing
            else []
        ),
        f"<h3>{escape(pair.before.name)} 노선 변화</h3>",
        '<ul class="summary">',
        *_summary("상행", up_counts),
        *_summary("하행", down_counts),
        "</ul>",
        '<table class="stop-diff">',
        "<thead><tr>" + "".join(f"<th>{escape(c)}</th>" for c in COLUMNS) + "</tr></thead>",
        "<tbody>",
    ]
    # 줄 수는 비고 목록이 정한다 — `notes.for_rows`가 이미 max(상행, 하행)으로 세어 두었다
    for i, note in enumerate(row_notes):
        out.append(
            f'<tr><td class="index">{i + 1}</td>'
            + _cells(up[i] if i < len(up) else None)
            + _cells(down[i] if i < len(down) else None)
            + _note_cell(note)
            + "</tr>"
        )
    out += ["</tbody>", "</table>"]
    if flipped:
        out.append(f'<p class="flipped">{FLIPPED_NOTE}</p>')
    out += [
        f'<p class="source">{SOURCE_NOTE}</p>',
        _geometry_script(geometry),
        "</section>",
        "",
    ]
    return "\n".join(out)


def fragment_url(key: Key) -> str:
    """표 조각 주소. 껍데기(`index.html`) 기준 상대 경로라 카드가 어디 있든 같다 (ADR-0006)."""
    number, branch, replacement, after_branch = key
    return f"route/{number}/{branch}/{replacement}/{after_branch}.html"


def card_url(number: str) -> str:
    """카드 조각 주소. 표 조각과 마찬가지로 껍데기(`index.html`) 기준 상대 경로다 (ADR-0006)."""
    return f"route/{number}.html"


def _list_row(row: Row) -> str:
    """줄 하나. 줄 전체가 단추다 — 눈으로 못 보는 사람에게도 그렇게 읽히도록 이름과 role을 적는다."""
    after = (
        " ".join(f'<span class="name">{escape(n)}</span>' for n in row.replaced)
        if row.replaced
        else f'<span class="none">{NO_REPLACEMENT}</span>'
    )
    # role="button"을 붙이면 칸 둘은 따로 읽히지 않는다. 그래서 이름에 대체 노선까지 함께 적는다
    label = f"{row.number} — " + (", ".join(row.replaced) if row.replaced else NO_REPLACEMENT)
    return (
        f'<tr hx-get="{escape(card_url(row.number))}" hx-target="#{RESULT_ID}"'
        f' hx-swap="{LIST_SWAP}" hx-trigger="{LIST_TRIGGER}"'
        f' role="button" tabindex="0" aria-label="{escape(label)}">'
        f'<td class="before">{escape(row.number)}</td>'
        f'<td class="after">{after}</td></tr>'
    )


def route_reform_list(rows: list[Row]) -> str:
    """노선 개편 목록 표. 껍데기 안에 통째로 들어간다 — 첫 화면에 늘 펼쳐져 있다."""
    return "\n".join([
        '<section class="route-list">',
        f"<h2>{LIST_TITLE}</h2>",
        f'<p class="lead">{LIST_LEAD}</p>',
        f'<p class="count">{len(rows)}개 노선</p>',
        '<table class="reform-list">',
        "<thead><tr>" + "".join(f"<th>{escape(c)}</th>" for c in LIST_COLUMNS) + "</tr></thead>",
        '<tbody class="reform">',
        *[_list_row(r) for r in rows],
        "</tbody>",
        "</table>",
        "</section>",
        "",
    ])


def index_page(rows: list[Row], kakao_js_key: str = "") -> str:
    """껍데기 + 노선 개편 목록 표 = `out/index.html` 한 장.

    `kakao_js_key`는 껍데기가 지도 SDK에 박는 값이다 — 리포에 없고 빌드가 환경 변수로 받는다.
    """
    return shell_page(route_reform_list(rows), rows, kakao_js_key)


def _ends(origin: str, terminus: str) -> str:
    return f"{escape(origin)} → {escape(terminus)}"


def _counts(route: Route) -> str:
    """기·종점과 정류장 수 한 줄. 하행이 없는 노선은 하행을 적지 않는다."""
    parts = [_ends(route.origin, route.terminus), f"상행 {len(route.up)}곳"]
    if route.down:
        parts.append(f"하행 {len(route.down)}곳")
    return " · ".join(parts)


def _choice(choice: Choice) -> list[str]:
    prompt = escape(choice.prompt)
    if choice.of:
        prompt += f' <span class="of">{escape(choice.of)}</span>'
    return [
        f'<div class="choice {choice.kind}">',
        f'<p class="prompt">{prompt}</p>',
        *(
            f'<button type="button" hx-get="{fragment_url(b.key)}"'
            f' hx-target="#{SLOT_ID}">{escape(b.label)}</button>'
            for b in choice.buttons
        ),
        "</div>",
    ]


def _stop_list(title: str, stops: tuple[str, ...]) -> list[str]:
    return [
        f"<h3>{escape(title)}</h3>",
        "<ol>" + "".join(f"<li>{escape(s)}</li>" for s in stops) + "</ol>",
    ]


def route_change_card(card: Card, table: str) -> str:
    """노선 변화 카드 조각 하나. 표 자리에는 기본 방면·첫 대체 노선의 표가 미리 들어간다.

    제목은 번호만 적는다 — 지금 보고 있는 방면은 표 자리의 제목(「<번호(방면)> 노선 변화」)이 말하고,
    버튼을 눌러 표가 바뀌면 그 제목도 함께 바뀐다.
    """
    number = card.before.number
    out = [
        f'<section class="route-card" data-number="{escape(number)}">',
        f"<h2>{escape(number)}</h2>",
        f'<p class="ends">{_counts(card.before)}</p>',
    ]
    if not card.replaced:
        # 대체 노선이 없는 번호(두암181). 고를 것이 없으니 개편 전 정류장만 적는다
        out.append(f'<p class="none">{NO_REPLACEMENT}</p>')
        out += ['<div class="stops">', *_stop_list(UP_STOPS, card.before.up)]
        if card.before.down:
            out += _stop_list(DOWN_STOPS, card.before.down)
        out += ["</div>", "</section>", ""]
        return "\n".join(out)

    out.append(f'<p class="lead">{REPLACED_LEAD}</p>')
    out.append('<ul class="replaced">')
    out += [
        f'<li><span class="name">{escape(r.number)}</span>'
        f' <span class="ends">({_ends(r.origin, r.terminus)})</span></li>'
        for r in card.replaced
    ]
    out.append("</ul>")
    for choice in card.choices:
        out += _choice(choice)
    # 지도 자리는 카드에 하나뿐이다 — 표가 바뀌어도 같은 지도 위에 다시 그린다. 자리는 비워 둔다:
    # 카드 자체가 htmx로 오므로 이 자리를 보는 사람에게는 이미 스크립트가 돈다. 채우는 것은 `map.js`다.
    #
    # 지도와 범례를 한 자리에 묶어 읽어 주는 기계에는 통째로 감춘다. 그림이 말하는 것은 표가 이미
    # 말하고, 선과 점의 색만 적은 범례는 지도를 못 보는 사람에게는 쓸모가 없다. 다만 좌표 없는
    # 정류장을 알리는 줄은 표 안에 있어 감춰지지 않는다 — 그것은 그림이 아니라 사실이다.
    out += [
        '<div class="route-map-area" aria-hidden="true">',
        '<div class="route-map"></div>',
        f'<p class="map-legend">{MAP_LEGEND}</p>',
        "</div>",
        f'<div class="route-change-slot" id="{SLOT_ID}">', table.rstrip("\n"), "</div>",
        "</section>", "",
    ]
    return "\n".join(out)
