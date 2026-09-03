"""5단계 비고 — 표의 여섯째 열 (ADR-0003 결정 5·6, 2026-09-03 개정).

비고에는 CSV 사실만 적는다. 상태(유지·경유 제외·경유 추가)는 줄 색과 요약 칸이 말하므로 여기
적지 않는다. 표 하나의 줄에는 상행 칸과 하행 칸이 같이 있어서 비고도 한 칸에 모인다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .branches import Pair
from .errors import BuildError
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
class Facts:
    """비고가 읽는 CSV에서 뽑은 사실. 열쇠는 정류장 이름이다 — 노선안 CSV에 ID가 없다."""

    renames: RenameDict
    removals: dict[str, Removal]   # 개편 전에만 있는 정류장에 붙는다
    additions: frozenset[str]      # 개편 후에만 있는 정류장에 붙는다

    def note_for(self, line: Line) -> Note:
        """줄 하나의 비고. 해당하는 사실이 없으면 빈 비고다."""
        if line.state == KEPT and self.renames.renamed(line.before, line.after):
            return Note(f"{RENAMED}: {line.before} → {line.after}")
        if line.state == DROPPED:
            removal = self.removals.get(line.before)
            if removal:
                return Note(removal.kind, removal.reason)
        if line.state == ADDED and line.after in self.additions:
            return Note(ADDITION)
        return Note()


def collect(
    renames: RenameDict,
    removals: list[Removal],
    additions: list[str],
) -> Facts:
    """CSV 행들 → 이름으로 찾는 사실.

    같은 정류장이 여러 행인 것은 정상이다(ID 단위라 계림사거리가 두 행이다). 다만 그 행들이 서로
    다른 말을 하면 어느 쪽을 적을지 우리가 고를 수 없으므로 멈춘다 — `rename_dict`와 같은 태도다.
    """
    by_name: dict[str, Removal] = {}
    for row in removals:
        seen = by_name.setdefault(row.stop, row)
        if (seen.kind, seen.reason) != (row.kind, row.reason):
            raise BuildError(
                f"통폐합이전 CSV의 같은 정류장이 다른 말을 합니다: {row.stop}"
                f" — 「{seen.kind}」 / 「{row.kind}」"
            )
    return Facts(renames=renames, removals=by_name, additions=frozenset(additions))


def _join(values: list[str]) -> str:
    """같은 말은 한 번만, 나온 차례대로 이어 붙인다."""
    return JOIN.join(dict.fromkeys(v for v in values if v))


def _merge(cells: list[Note]) -> Note:
    """한 줄에 상행·하행 두 사실이 겹칠 수 있다."""
    return Note(_join([n.text for n in cells]), _join([n.title for n in cells]))


def for_rows(
    up: list[Line],
    down: list[Line],
    facts: Facts,
    *,
    table_note: str = "",
) -> list[Note]:
    """표의 줄 수만큼 비고를 만든다.

    `table_note`는 표 전체에 걸린 말(하행 없음)이라 줄에 속하지 않지만, 적을 자리가 비고뿐이라
    첫 줄에 붙인다.
    """
    rows: list[Note] = []
    for i in range(max(len(up), len(down))):
        cells = [facts.note_for(lines[i]) for lines in (up, down) if i < len(lines)]
        if i == 0 and table_note:
            cells.insert(0, Note(table_note))
        rows.append(_merge(cells))
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
    return _join(texts)
