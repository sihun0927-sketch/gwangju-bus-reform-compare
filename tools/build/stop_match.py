"""4단계 기·종점 정류장 대조 — 두 정류장 목록을 순서를 지키며 한 줄씩 맞댄다 (ADR-0003 결정 1).

최장 공통 부분열로 짝을 짓고 줄마다 유지 / 경유 제외 / 경유 추가를 매긴다. 주어는 노선이다 —
경유 제외는 정류장이 없어진 것이 아니라 이 노선이 더는 안 지난다는 뜻이다.

`match`는 대조 전에 명칭 사전을 적용한다 — `canon`을 주면 그 이름으로 견주고 표에는 CSV 이름을 싣는다.
`lcs_length`는 사전을 안 거친다. 기·종점 정렬(3단계)이 겹침을 잴 때 쓰는데, 그 수치는 §6에 못박혀
있고 이번 티켓의 권한은 `stop_match`의 대조까지다.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# 대조에 쓸 이름으로 바꾸는 함수. 명칭 사전을 쓰려면 `rename_dict.RenameDict.canon`을 준다
Canon = Callable[[str], str]

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


def _keys(names: tuple[str, ...], canon: Canon | None) -> tuple[str, ...]:
    return names if canon is None else tuple(canon(n) for n in names)


def _table(x: tuple[str, ...], y: tuple[str, ...]) -> list[list[int]]:
    n, m = len(x), len(y)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if x[i] == y[j] else max(dp[i + 1][j], dp[i][j + 1])
    return dp


def lcs_length(x: tuple[str, ...], y: tuple[str, ...]) -> int:
    """최장 공통 부분열 길이. 순서를 지키며 겹치는 정류장 수. 이름은 글자 그대로 견준다."""
    return _table(x, y)[0][0]


def match(
    before: tuple[str, ...],
    after: tuple[str, ...],
    canon: Canon | None = None,
) -> list[Line]:
    """정류장 목록 둘 → 줄 목록. 짝이 없는 줄은 개편 전 것을 먼저 낸다(표에서 위에 온다).

    견주는 것은 `canon`을 거친 이름이고, `Line`에 담기는 것은 CSV에 적힌 이름 그대로다 —
    그래서 이름만 바뀐 정류장이 한 줄 「유지」가 되면서도 표에는 옛 이름과 새 이름이 나란히 보인다.
    """
    x, y = _keys(before, canon), _keys(after, canon)
    dp = _table(x, y)
    lines: list[Line] = []
    i = j = 0
    while i < len(before) and j < len(after):
        if x[i] == y[j]:
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
