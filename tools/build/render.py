"""6단계 조각 — 결과를 HTML 토막으로 쓴다 (`<!doctype>` 없음, htmx가 자리에 끼운다).

표 규격은 docs/architecture.md §5, 화면 문구는 CONTEXT.md 「노선번호로 찾기」를 따른다.
"""
from __future__ import annotations

from html import escape

from .branches import Pair
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
