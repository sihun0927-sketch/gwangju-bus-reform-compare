"""6단계 조각 — 결과를 HTML 토막으로 쓴다 (`<!doctype>` 없음, htmx가 자리에 끼운다).

표 규격은 docs/architecture.md §5, 화면 문구는 CONTEXT.md 「노선번호로 찾기」를 따른다.
"""
from __future__ import annotations

from html import escape

from .branches import Pair
from .load import Route
from .route_card import Card, Choice, Key, NO_REPLACEMENT
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
UP_STOPS = "개편 전 상행 정류장"
DOWN_STOPS = "개편 전 하행 정류장"


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


def route_change_table(
    pair: Pair,
    up: list[Line],
    down: list[Line],
    up_counts: dict[str, int],
    down_counts: dict[str, int],
    *,
    flipped: bool,
    note: str = "",
) -> str:
    """노선 변화 표 조각 하나. 제목은 「<번호(방면)> 노선 변화」."""
    out = [
        f'<section class="route-change" data-before="{escape(pair.before.name)}"'
        f' data-after="{escape(pair.after.name)}">',
        f"<h3>{escape(pair.before.name)} 노선 변화</h3>",
        '<ul class="summary">',
        *_summary("상행", up_counts),
        *_summary("하행", down_counts),
        "</ul>",
        '<table class="stop-diff">',
        "<thead><tr>" + "".join(f"<th>{escape(c)}</th>" for c in COLUMNS) + "</tr></thead>",
        "<tbody>",
    ]
    for i in range(max(len(up), len(down))):
        cell_note = note if i == 0 else ""
        out.append(
            f'<tr><td class="index">{i + 1}</td>'
            + _cells(up[i] if i < len(up) else None)
            + _cells(down[i] if i < len(down) else None)
            + f'<td class="note">{escape(cell_note)}</td></tr>'
        )
    out += ["</tbody>", "</table>"]
    if flipped:
        out.append(f'<p class="flipped">{FLIPPED_NOTE}</p>')
    out += [f'<p class="source">{SOURCE_NOTE}</p>', "</section>", ""]
    return "\n".join(out)


def fragment_url(key: Key) -> str:
    """표 조각 주소. 껍데기(`index.html`) 기준 상대 경로라 카드가 어디 있든 같다 (ADR-0006)."""
    number, branch, replacement, after_branch = key
    return f"route/{number}/{branch}/{replacement}/{after_branch}.html"


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
    out += [f'<div class="route-change-slot" id="{SLOT_ID}">', table.rstrip("\n"), "</div>",
            "</section>", ""]
    return "\n".join(out)
