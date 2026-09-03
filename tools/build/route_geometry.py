"""노선 지도 좌표 — 표 조각 하나에 실리는 선 둘과 점들 (architecture §7-3 Q5~Q7).

노선 변화 표 하나가 지도 하나다. 표가 답하는 것은 **상행**이므로 그리는 것도 상행뿐이다.
대체 노선 쪽은 기·종점 정렬이 뒤집었으면 하행 목록을 쓴다 — 표의 「개편 후 상행 정류장」 칸에
들어간 바로 그 목록이라 지도와 표가 같은 것을 말한다.

이름을 `stops.csv`의 줄에 잇는 것은 `bundle`의 `StopIndex`를 그대로 쓴다. 못 잇는 이름(신설
정류소와 `name_canon.json`이 `null`이라 적은 것)은 **건너뛰고 앞뒤를 잇고 개수를 센다**.
`bundle`의 추정 좌표(앞뒤 중점)는 여기 오지 않는다 — 그것은 장소 탭 경로 계산 전용이고,
지도에 찍으면 시민이 실제 정류장 자리로 읽는다(ADR-0007).

**같은 이름이 여러 곳에 있다.** `stops.csv`는 광주와 전남을 함께 담고 있어 「금곡마을」이 여섯 줄,
서로 55km 떨어져 있기도 하다. 줄을 다 평균 내면 아무 정류장도 없는 들판에 점이 찍히고 선이
왕복 50km를 튄다(고치기 전 205개 표 중 130개에 3km 넘는 튐이 있었다). 그래서 이름 하나가
가리킬 수 있는 **자리**를 먼저 모으고(길 양쪽 두 줄은 한 자리), 노선을 따라가며 앞뒤 정류장에
가장 가까운 자리를 고른다. 고르는 것은 늘 `stops.csv`에 실제로 있는 줄이다 — 좌표를 짓지 않는다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .bundle import StopIndex
from .load import Stop
from .stop_match import ADDED, KEPT, Line

# 좌표를 소수 여섯 자리로 끊는다 — 위도 11cm쯤이라 지도에서 구분되지 않고, 조각 205개가 가벼워진다
DIGITS = 6

# 이 안에 있는 줄들은 한 정류장의 양쪽(또는 같은 자리의 여러 승강장)으로 보고 한 자리로 묶는다.
# 광주 정류장 사이 거리는 보통 300~500m라, 이보다 멀면 같은 이름이라도 다른 곳이다
SAME_PLACE_M = 200.0

Point = tuple[float, float]


@dataclass(frozen=True)
class Dot:
    """지도의 점 하나. 색은 상태가 정하고 이름은 마우스를 올렸을 때 보인다."""

    lat: float
    lng: float
    name: str
    state: str


@dataclass(frozen=True)
class Geometry:
    """표 하나의 지도. `undrawn`은 좌표가 없어 점이 되지 못한 정류장 **이름**들이다."""

    before: tuple[Point, ...]
    after: tuple[Point, ...]
    stops: tuple[Dot, ...]
    undrawn: frozenset[str]

    @property
    def missing(self) -> int:
        """지도에 없는 정류장 수. 화면 문구가 「정류장 N곳」이라 줄이 아니라 이름을 센다 —
        한 노선이 같은 정류장을 두 번 지나도(지선92의 왕동저수지) 한 곳이다."""
        return len(self.undrawn)

    @property
    def data(self) -> dict:
        """조각에 실리는 모양. 키 이름은 `out/map.js`가 읽는 이름과 같아야 한다."""
        return {
            "before": [list(p) for p in self.before],
            "after": [list(p) for p in self.after],
            "stops": [
                {"lat": d.lat, "lng": d.lng, "name": d.name, "state": d.state} for d in self.stops
            ],
            "missing": self.missing,
        }


def metres(a: Point, b: Point) -> float:
    """두 좌표 사이 거리. 광주 한 도시 안이라 위경도를 평면으로 놓고 재도 충분하다."""
    dy = (a[0] - b[0]) * 111_000
    dx = (a[1] - b[1]) * 111_000 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def _centre(rows: list[Stop]) -> Point:
    """한 자리에 모인 줄들의 한가운데. 길 양쪽 둘이면 도로 한복판이 나온다."""
    return (
        round(sum(r.lat for r in rows) / len(rows), DIGITS),
        round(sum(r.lng for r in rows) / len(rows), DIGITS),
    )


def places(index: StopIndex, name: str) -> tuple[Point, ...]:
    """이름 하나가 가리킬 수 있는 자리들. 대개 하나뿐이고, 못 이으면 빈 목록이다.

    가까운 줄끼리 이어 붙여 묶는다(단일 연결) — 길 양쪽 두 줄은 한 자리, 다른 고을의 같은 이름은
    다른 자리다. 자리의 차례는 `stops.csv`의 줄 차례라 같은 입력이면 늘 같은 답이 나온다.
    """
    rows = index.resolve(name)
    if not rows:
        return ()
    groups: list[list[Stop]] = []
    for row in rows:
        at = (row.lat, row.lng)
        near = [g for g in groups if any(metres(at, (o.lat, o.lng)) <= SAME_PLACE_M for o in g)]
        if not near:
            groups.append([row])
            continue
        # 두 무리를 한꺼번에 잇는 줄이면 셋을 하나로 합친다
        first = near[0]
        first.append(row)
        for other in near[1:]:
            first.extend(other)
            groups.remove(other)
    return tuple(_centre(g) for g in groups)


def chain(index: StopIndex, names: tuple[str, ...]) -> list[Point | None]:
    """정류장 이름 차례 → 자리 차례. 같은 이름이 여러 곳이면 노선이 가장 짧아지는 곳을 고른다.

    앞에서부터 하나씩 가까운 것을 고르면 첫 선택이 어긋났을 때 노선 전체가 끌려간다. 그래서 자리
    전체를 놓고 이어진 거리의 합이 가장 작은 조합을 고른다(층마다 후보 몇 개뿐이라 값이 싸다).
    좌표를 못 이은 이름은 None으로 두고 앞뒤를 잇는다.
    """
    options = [places(index, name) for name in names]
    known = [i for i, o in enumerate(options) if o]
    if not known:
        return [None] * len(options)

    # cost[b] = 여기까지 오는 가장 짧은 거리, back[층][b] = 그때 앞 층에서 고른 자리
    cost = dict.fromkeys(range(len(options[known[0]])), 0.0)
    back: list[dict[int, int]] = []
    for prev, cur in zip(known, known[1:]):
        step: dict[int, float] = {}
        chosen: dict[int, int] = {}
        for b, point in enumerate(options[cur]):
            chosen[b], step[b] = min(
                ((a, spent + metres(options[prev][a], point)) for a, spent in cost.items()),
                key=lambda pair: pair[1],
            )
        back.append(chosen)
        cost = step
    picks = [min(cost, key=cost.__getitem__)]
    for chosen in reversed(back):
        picks.append(chosen[picks[-1]])
    picks.reverse()

    found: list[Point | None] = [None] * len(options)
    for i, pick in zip(known, picks):
        found[i] = options[i][pick]
    return found


def geometry(
    index: StopIndex,
    before_up: tuple[str, ...],
    after_up: tuple[str, ...],
    up: list[Line],
) -> Geometry:
    """개편 전 상행 · 대체 노선 상행 · 그 둘을 맞댄 줄들 → 지도 하나.

    점은 표의 줄에서 나온다 — 유지·경유 제외는 개편 전 정류장, 경유 추가는 개편 후 정류장의
    자리다. 그래서 점 수 + `missing` = 상행 줄 수이고, 표에 보이는 것과 지도에 보이는 것이
    어긋나지 않는다. 점은 선이 고른 바로 그 자리를 쓴다 — 따로 고르면 점이 선을 벗어난다.
    """
    before = chain(index, before_up)
    after = chain(index, after_up)

    stops: list[Dot] = []
    undrawn: set[str] = set()
    # `stop_match.match`가 두 목록을 훑은 차례를 그대로 되짚는다 — 유지는 양쪽, 경유 제외는 개편
    # 전, 경유 추가는 개편 후에서 하나씩 가져갔다
    i = j = 0
    for line in up:
        if line.state == ADDED:
            name, found = line.after, after[j]
            j += 1
        else:
            name, found = line.before, before[i]
            i += 1
            if line.state == KEPT:
                j += 1
        if found is None:
            undrawn.add(name)
            continue
        stops.append(Dot(lat=found[0], lng=found[1], name=name, state=line.state))

    return Geometry(
        before=tuple(p for p in before if p is not None),
        after=tuple(p for p in after if p is not None),
        stops=tuple(stops),
        undrawn=frozenset(undrawn),
    )
