"""5단계 비고 — 표의 여섯째 열 (ADR-0003 결정 5·6, 2026-09-03 개정).

비고에는 CSV 사실 넷만 적는다 — 명칭 변경 · 통폐합 · 이전 · 신설. 상태(유지·경유 제외·경유 추가)는
줄 색과 요약 칸이 말하므로 여기 적지 않는다. 구분 값만 보이고 사유 문장은 마우스를 올렸을 때(`title`)
나온다. 표가 어수선해지지 않게 하려는 것이다.

정류장을 잇는 열쇠는 이름뿐이다(노선안 CSV에 ID가 없다). 통폐합 CSV의 「A(B)」 표기처럼 이름이
노선안과 안 맞는 줄은 비고를 비우고 넘어간다 — 이름 대조 규칙을 넓히는 것은 다음 스펙이다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .branches import Pair
from .load import Removal, Route
from .rename_dict import RenameDict
from .stop_match import ADDED, DROPPED, KEPT, Line

CIRCULAR = "순환 노선 · 하행 없음"
ONE_WAY = "편도 운행 · 하행 없음"
RENAMED = "명칭 변경"
ADDITION = "신설 정류소"
JOIN = " · "


@dataclass(frozen=True)
class Note:
    """비고 칸 하나. `text`는 화면에 보이고 `title`은 마우스를 올렸을 때만 보인다."""

    text: str = ""
    title: str = ""


@dataclass(frozen=True)
class Sources:
    """비고가 읽는 CSV 셋에서 뽑은 사실. 열쇠는 정류장 이름이다."""

    renames: RenameDict
    removals: dict[str, Removal]   # 개편 전에만 있는 정류장에 붙는다
    additions: frozenset[str]      # 개편 후에만 있는 정류장에 붙는다


def sources(renames: RenameDict, removals: list[Removal], additions: list[str]) -> Sources:
    """CSV 행들 → 이름으로 찾는 사실. 같은 이름이 두 행이면(ID가 둘) 먼저 것을 쓴다."""
    by_name: dict[str, Removal] = {}
    for row in removals:
        by_name.setdefault(row.stop, row)
    return Sources(renames=renames, removals=by_name, additions=frozenset(additions))


def for_line(line: Line, found: Sources) -> Note:
    """줄 하나의 비고. 해당하는 사실이 없으면 빈 비고다."""
    if line.state == KEPT and found.renames.renamed(line.before, line.after):
        return Note(f"{RENAMED}: {line.before} → {line.after}")
    if line.state == DROPPED:
        removal = found.removals.get(line.before)
        if removal:
            return Note(removal.kind, removal.reason)
    if line.state == ADDED and line.after in found.additions:
        return Note(ADDITION)
    return Note()


def _merge(notes: list[Note]) -> Note:
    """한 줄에 상행·하행 두 사실이 겹칠 수 있다. 같은 말은 한 번만 적는다."""
    texts = list(dict.fromkeys(n.text for n in notes if n.text))
    titles = list(dict.fromkeys(n.title for n in notes if n.title))
    return Note(JOIN.join(texts), JOIN.join(titles))


def for_rows(
    up: list[Line],
    down: list[Line],
    found: Sources,
    *,
    table_note: str = "",
) -> list[Note]:
    """표의 줄 수만큼 비고를 만든다.

    한 줄에는 상행 칸과 하행 칸이 같이 있으므로 두 방향의 사실을 " · "로 잇는다. `table_note`는
    표 전체에 걸린 말(하행 없음)이라 줄에 속하지 않지만, 적을 자리가 비고뿐이라 첫 줄에 붙인다.
    """
    rows: list[Note] = []
    for i in range(max(len(up), len(down))):
        found_notes = [
            for_line(line[i], found)
            for line in (up, down)
            if i < len(line)
        ]
        if i == 0 and table_note:
            found_notes.insert(0, Note(table_note))
        rows.append(_merge(found_notes))
    return rows


def is_circular(siblings: list[Route]) -> bool:
    """순환인지는 방면이 아니라 번호로 본다.

    상무62(시청경유상무역행)은 종점 표기가 「상무지구종점」이라 기점과 글자가 다르지만, 같은 번호의
    다른 방면이 상무지구 → 상무지구다. 두암81(각화초교.장등마을)도 마찬가지다(장등마을 → 장동마을).
    한 방면이라도 기점과 종점이 같으면 그 번호는 순환 노선이고, 아니면 편도다(지선97(빛그린산단출근)).
    """
    return any(s.origin == s.terminus for s in siblings)


def down_missing(
    pair: Pair,
    before_siblings: list[Route],
    after_siblings: list[Route],
) -> str:
    """하행 칸을 비우는 이유. 하행이 양쪽 다 있으면 빈 문자열이다."""
    texts: list[str] = []
    if not pair.before.down:
        texts.append(CIRCULAR if is_circular(before_siblings) else ONE_WAY)
    if not pair.after.down:
        texts.append(CIRCULAR if is_circular(after_siblings) else ONE_WAY)
    return JOIN.join(dict.fromkeys(texts))
