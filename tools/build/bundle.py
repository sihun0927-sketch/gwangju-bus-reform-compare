"""번들 만들기 — 장소 탭 Worker가 import하는 `worker/data.json` 한 장 (ADR-0008).

노선번호 탭이 정적 파일로 끝나는 것과 같은 논리다. 장소 탭의 **입력**(좌표 쌍)은 무한이지만
계산의 **재료**(정류장 · 노선 · 노선별 정류장 순서)는 시 공표 CSV로 고정이므로 빌드가 미리 만든다.
D1은 만들지 않는다.

이 단계가 하는 일은 노선안 CSV의 **이름**을 `stops.csv`의 **줄**(STATION_NUM)에 잇는 것이다.

- 이름 하나에 그 이름의 줄 **전부**를 붙인다. 보통 길 양쪽 둘이라, 어느 쪽에서 타는지는 경로 계산이 고른다.
- 개편 후 노선안이 쓰는 새 이름은 명칭 사전의 **ID**로 옛 이름의 줄에 붙는다 — 문화육교는 문흥고가의
  두 줄이다. 이름이 아니라 ID인 까닭은 `rename_dict`에 적어 두었다.
- 이도 저도 아닌 이름이 하나라도 있으면 목록을 내고 멈춘다. 조용히 건너뛰면 그 정류장은 지도에서만
  사라지는 것이 아니라 경로 탐색에서 통째로 없는 것이 된다.

좌표가 아직 없는 57개(신설 56 + 광주교대역2번출구)는 예외다. 같은 노선 앞뒤 정류장의 중점을
**추정 좌표**로 받고 추정 여부 플래그가 켜진다(ADR-0007 개정). `stops.csv`에는 쓰지 않는다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import BuildError
from .load import Route, Stop
from .rename_dict import RenameDict

# 번들의 기본 자리. Worker 코드 옆이라 `wrangler deploy`가 그대로 싣는다
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "worker" / "data.json"

BEFORE = "before"
AFTER = "after"
UP = "up"
DOWN = "down"

# 추정 좌표 정류장의 STATION_NUM. `stops.csv`의 값은 전부 숫자라 겹칠 수 없다
ESTIMATED_PREFIX = "est:"

# 중점을 소수 8자리로 끊는다 — 위도 1mm 아래라 도보 거리에 무해하고, 실수 계산의 꼬리를 안 남긴다
ESTIMATED_DIGITS = 8


# 노선 → 방향 → 정류장 이름 차례. 노선안 CSV가 준 것 그대로이고, 이름을 줄에 잇기 전 모습이다
Plans = dict[str, dict[str, tuple[str, ...]]]


@dataclass(frozen=True)
class Counts:
    """명령줄이 찍고 실측 수치(architecture §6)와 견줄 숫자들."""

    stops: int          # stops 줄 수 — `stops.csv` 4,746 + 추정 57
    estimated: int      # 그중 추정 좌표
    routes: int         # 개편 전 111 + 개편 후 119
    route_stops: int    # 노선 × 방향 × 순번 × STATION_NUM 줄 수


@dataclass(frozen=True)
class Bundle:
    """번들 한 장과 그 숫자들."""

    data: dict
    counts: Counts


@dataclass(frozen=True)
class StopIndex:
    """이름 하나를 `stops.csv`의 줄로 바꾸는 데 드는 것 전부.

    넷이 늘 같이 다녀서 한 타입으로 묶었다. 잇는 길이 늘면(개편 후 BIS가 열려 신설 정류장에
    진짜 좌표가 오면) 여기만 는다.
    """

    by_name: dict[str, list[Stop]]
    by_ars: dict[str, list[Stop]]
    canon: dict[str, str | None]
    renames: RenameDict

    def resolve(self, name: str) -> list[Stop]:
        """노선안 이름 하나 → 그 이름의 `stops.csv` 줄 전부. 못 이으면 빈 목록.

        잇는 길은 둘이다.

        1. 이름 그대로. 표기가 어긋나면 `name_canon.json`이 맞춘다(ADR-0007).
        2. 개편 후 새 이름이면 명칭 변경 CSV가 적어 둔 **ID**의 줄. 이름으로 되돌리지 않는 까닭은
           옛 이름 하나가 새 이름 둘로 갈릴 때 어느 줄이 어느 쪽인지 이름으로는 못 가리기 때문이다.
        """
        fixed = self.canon.get(name, name)
        if fixed and fixed in self.by_name:
            return self.by_name[fixed]
        return [
            row
            for ars in sorted(self.renames.new_to_ars.get(fixed or name, ()))
            for row in self.by_ars.get(ars, ())
        ]

    def coordinateless(self, name: str, additions: set[str]) -> bool:
        """좌표가 없는 것이 **확인된** 이름인가 — 신설 정류소이거나 `name_canon.json`이 `null`이라 적었거나."""
        return name in additions or self.canon.get(name, name) is None


def route_id(network: str, name: str) -> str:
    """번들에서 노선 하나를 부르는 이름. 노선망이 다르면 같은 번호라도 다른 노선이다."""
    return f"{network}:{name}"


def make(
    before: list[Route],
    after: list[Route],
    stops: list[Stop],
    canon: dict[str, str | None],
    renames: RenameDict,
    additions: list[str],
) -> Bundle:
    """노선안·`stops.csv`·명칭 사전·신설 정류소 → 번들 한 장.

    STATION_NUM에 못 잇는 이름이 있으면 그 목록을 담은 `BuildError`를 낸다.
    """
    order = {s.station_num: i for i, s in enumerate(stops)}
    by_name: dict[str, list[Stop]] = {}
    by_ars: dict[str, list[Stop]] = {}
    for s in stops:
        by_name.setdefault(s.name, []).append(s)
        if s.ars_id:
            by_ars.setdefault(s.ars_id, []).append(s)
    index = StopIndex(by_name=by_name, by_ars=by_ars, canon=canon, renames=renames)

    routes: dict[str, dict] = {}
    plans: Plans = {}
    for network, rows in ((BEFORE, before), (AFTER, after)):
        for r in rows:
            rid = route_id(network, r.name)
            if rid in routes:
                raise BuildError(f"노선안에 같은 노선 이름이 두 번 있습니다: {rid}")
            # 배차는 자리만 둔다 — 개편 전 자료가 아직 없다(스펙 Out of Scope)
            routes[rid] = {"network": network, "name": r.name, "headway": None}
            plans[rid] = {UP: r.up, DOWN: r.down}

    linked, unlinked = _link(plans, routes, index, set(additions), order)
    if unlinked:
        raise BuildError(
            "노선안 정류장 이름을 stops.csv의 줄에 못 이었습니다"
            " (신설 정류소도 명칭 변경도 아닙니다):\n  "
            + "\n  ".join(f"{route} — {name}" for name, route in unlinked.items())
        )

    estimated = _estimate(plans, linked, {s.station_num: s for s in stops})
    out_stops = {
        s.station_num: {
            "ars": s.ars_id, "name": s.name, "lat": s.lat, "lng": s.lng, "estimated": False,
        }
        for s in stops
    }
    for name, (lat, lng) in estimated.items():
        sid = ESTIMATED_PREFIX + name
        out_stops[sid] = {"ars": "", "name": name, "lat": lat, "lng": lng, "estimated": True}
        linked[name] = (sid,)

    route_stops = {
        rid: {
            side: [{"name": name, "stops": list(linked[name])} for name in names]
            for side, names in sides.items()
        }
        for rid, sides in plans.items()
    }
    used = {sid for ids in linked.values() for sid in ids}
    data = {
        "bbox": _bbox(used, out_stops),
        "stops": out_stops,
        "routes": routes,
        "route_stops": route_stops,
    }
    return Bundle(
        data=data,
        counts=Counts(
            stops=len(out_stops),
            estimated=len(estimated),
            routes=len(routes),
            route_stops=sum(
                len(x["stops"]) for sides in route_stops.values() for side in sides.values()
                for x in side
            ),
        ),
    )


def write(path: Path, bundle: Bundle) -> int:
    """번들을 한 줄 JSON으로 쓰고 바이트 수를 돌려준다. 사람이 아니라 Worker가 읽는 파일이다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(bundle.data, ensure_ascii=False, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def _link(
    plans: Plans,
    routes: dict[str, dict],
    index: StopIndex,
    additions: set[str],
    order: dict[str, int],
) -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
    """노선안에 나오는 이름마다 STATION_NUM들을 붙인다.

    돌려주는 둘째 값은 못 이은 이름 → 그 이름이 처음 나온 노선이다. 좌표가 아직 없어 추정할 이름은
    빈 튜플로 남겨 두고, `_estimate`가 채운다.
    """
    linked: dict[str, tuple[str, ...]] = {}
    unlinked: dict[str, str] = {}
    for rid, sides in plans.items():
        for names in sides.values():
            for name in names:
                if name in linked or name in unlinked:
                    continue
                hit = index.resolve(name)
                if hit:
                    # `stops.csv`의 줄 차례로 둔다 — 이름으로 이었든 ID로 이었든 같은 순서가 나온다
                    linked[name] = tuple(
                        sorted((s.station_num for s in hit), key=order.__getitem__)
                    )
                elif index.coordinateless(name, additions):
                    # 여기서만 비워 두고 `_estimate`가 앞뒤 중점을 채운다
                    linked[name] = ()
                else:
                    unlinked[name] = routes[rid]["name"]
    return linked, unlinked


def _centre(ids: tuple[str, ...], by_num: dict[str, Stop]) -> tuple[float, float]:
    """이름 하나가 붙은 줄들의 한가운데. 길 양쪽 둘이면 도로 한복판이라 앞뒤 정류장을 대표한다."""
    rows = [by_num[i] for i in ids]
    return sum(r.lat for r in rows) / len(rows), sum(r.lng for r in rows) / len(rows)


def _estimate(
    plans: Plans,
    linked: dict[str, tuple[str, ...]],
    by_num: dict[str, Stop],
) -> dict[str, tuple[float, float]]:
    """좌표 없는 이름에 같은 노선 앞뒤 정류장의 중점을 준다 (ADR-0007 개정 · ADR-0008 결정 4).

    앞이나 뒤가 없으면(기점·종점) 있는 쪽 하나를 그대로 쓴다. 앞뒤가 둘 다 아직 좌표가 없으면
    (신설 정류장이 잇달아 놓인 자리) 이번 바퀴는 건너뛰고, 채워진 값으로 다음 바퀴에 다시 본다.
    한 바퀴에 하나도 못 채우면 멈춘다 — 지어낸 좌표를 넣지 않는다.
    """
    coords = {name: _centre(ids, by_num) for name, ids in linked.items() if ids}
    pending = {name for name, ids in linked.items() if not ids}
    estimated: dict[str, tuple[float, float]] = {}
    while pending:
        # 한 바퀴 동안 `coords`를 얼지 않게 두면 노선을 도는 순서가 값을 바꾼다. 바퀴 끝에 한꺼번에 넣는다
        found: dict[str, tuple[float, float]] = {}
        for sides in plans.values():
            for names in sides.values():
                for i, name in enumerate(names):
                    if name not in pending or name in found:
                        continue
                    around = [
                        coords[n]
                        for n in (names[i - 1] if i else None,
                                  names[i + 1] if i + 1 < len(names) else None)
                        if n in coords
                    ]
                    if around:
                        found[name] = (
                            round(sum(c[0] for c in around) / len(around), ESTIMATED_DIGITS),
                            round(sum(c[1] for c in around) / len(around), ESTIMATED_DIGITS),
                        )
        if not found:
            raise BuildError(
                "좌표 없는 정류장의 앞뒤에도 좌표가 없어 추정할 수 없습니다:\n  "
                + "\n  ".join(sorted(pending))
            )
        coords.update(found)
        estimated.update(found)
        pending -= found.keys()
    return estimated


def _bbox(used: set[str], stops: dict[str, dict]) -> dict[str, float]:
    """노선안에 나오는 정류장의 좌표 범위. `places`가 Kakao 검색을 이 안으로 좁히는 데 쓴다.

    `stops.csv` 전체가 아니라 **노선안이 지나는 줄**의 범위다 — 광주 노선망이 닿지 않는 전남
    정류장까지 넣으면 상자가 순천·여수까지 넓어진다.
    """
    if not used:
        raise BuildError("노선안 정류장이 하나도 없습니다.")
    lat = [stops[i]["lat"] for i in used]
    lng = [stops[i]["lng"] for i in used]
    return {"min_lat": min(lat), "min_lng": min(lng), "max_lat": max(lat), "max_lng": max(lng)}
