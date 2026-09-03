"""2단계 방면 — 같은 번호의 행을 방면으로 나누고, 표 하나의 단위인 쌍 205개를 만든다.

노선 변화 표 하나 = 개편 전 방면 × 대체 노선 × 개편 후 방면. 비교표는 번호 하나로만 적으므로
방면은 노선안 CSV에서 나온다 — 개편 전 6개 번호 14행, 개편 후 지선97 하나.
"""
from __future__ import annotations

from dataclasses import dataclass

from .load import Route, Replacement, find_after


@dataclass(frozen=True)
class Pair:
    """노선 변화 표 하나가 답하는 쌍. 조각 파일 하나가 쌍 하나다."""

    before: Route
    after: Route

    @property
    def key(self) -> tuple[str, str, str, str]:
        """조각 경로 네 단계와 같은 열쇠 — (번호, 개편 전 방면, 대체 노선, 개편 후 방면)."""
        return (self.before.number, self.before.branch, self.after.number, self.after.branch)

    @property
    def label(self) -> str:
        return f"{self.before.name} ↔ {self.after.name}"


def by_number(routes: list[Route]) -> dict[str, list[Route]]:
    """번호 → 방면 행들. CSV 순서를 지키며, 방면이 하나뿐이면 목록 길이가 1이다."""
    grouped: dict[str, list[Route]] = {}
    for r in routes:
        grouped.setdefault(r.number, []).append(r)
    return grouped


def pairs(
    before: list[Route],
    after: list[Route],
    replacements: list[Replacement],
) -> tuple[list[Pair], list[str]]:
    """비교표를 따라 쌍을 편다. 돌려주는 둘째 값은 번호를 못 이은 표기 목록이다.

    대체 노선이 비어 있는 행(두암181)은 쌍을 내지 않는다 — 못 찾은 것이 아니라 없는 것이다.
    """
    grouped = by_number(before)
    made: list[Pair] = []
    missing: list[str] = []
    for row in replacements:
        branches = grouped.get(row.before, [])
        for spelled in row.spelled:
            hits = find_after(after, spelled)
            if not branches or not hits:
                missing.append(f"{row.before} ↔ {spelled}")
                continue
            for b in branches:
                for a in hits:
                    made.append(Pair(before=b, after=a))
    return made, missing
