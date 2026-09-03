"""4단계 기·종점 정류장 대조 — 두 정류장 목록을 순서를 지키며 한 줄씩 맞댄다 (ADR-0003 결정 1).

최장 공통 부분열로 짝을 짓고 줄마다 유지 / 경유 제외 / 경유 추가를 매긴다. 주어는 노선이다 —
경유 제외는 정류장이 없어진 것이 아니라 이 노선이 더는 안 지난다는 뜻이다.

명칭 사전은 아직 쓰지 않는다(다음 티켓). 지금은 이름이 글자 그대로 같아야 유지다.
"""
from __future__ import annotations

from dataclasses import dataclass

KEPT = "유지"
DROPPED = "경유 제외"
ADDED = "경유 추가"
STATES = (KEPT, DROPPED, ADDED)


@dataclass(frozen=True)
class Line:
    """표의 줄 하나. 유지면 둘 다, 경유 제외면 개편 전만, 경유 추가면 개편 후만 채워진다."""

    before: str
    after: str
    state: str


def _table(x: tuple[str, ...], y: tuple[str, ...]) -> list[list[int]]:
    n, m = len(x), len(y)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if x[i] == y[j] else max(dp[i + 1][j], dp[i][j + 1])
    return dp


def lcs_length(x: tuple[str, ...], y: tuple[str, ...]) -> int:
    """최장 공통 부분열 길이. 순서를 지키며 겹치는 정류장 수."""
    return _table(x, y)[0][0]


def match(before: tuple[str, ...], after: tuple[str, ...]) -> list[Line]:
    """정류장 목록 둘 → 줄 목록. 짝이 없는 줄은 개편 전 것을 먼저 낸다(표에서 위에 온다)."""
    dp = _table(before, after)
    lines: list[Line] = []
    i = j = 0
    while i < len(before) and j < len(after):
        if before[i] == after[j]:
            lines.append(Line(before[i], after[j], KEPT))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            lines.append(Line(before[i], "", DROPPED))
            i += 1
        else:
            lines.append(Line("", after[j], ADDED))
            j += 1
    lines.extend(Line(s, "", DROPPED) for s in before[i:])
    lines.extend(Line("", s, ADDED) for s in after[j:])
    return lines


def summary(lines: list[Line]) -> dict[str, int]:
    """상행·하행 요약 칸에 들어갈 개수 셋."""
    counts = dict.fromkeys(STATES, 0)
    for line in lines:
        counts[line.state] += 1
    return counts
