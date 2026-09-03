"""OSRM으로 노선 형상과 환승 도보를 낸다 (ADR-0009).

    python tools/build_shapes.py     # car가 5000에, foot이 5001에 떠 있어야 한다

내는 것은 `data/source/route_shapes.json` 하나다. 둘이 들어 있고 빌드는 **읽기만** 한다 —
라우팅은 여기서 한 번만 돈다.

- `shapes`: 노선 형상 452개(개편 전 215 + 개편 후 237, 상행·하행 각각). **차도** 경로다.
- `walks`: 환승 도보 선. 걸을 자리는 `route_links`가 정하고, 그 대부분은 같은 정류장이라
  실제로 선이 필요한 쌍은 얼마 안 된다. **인도** 경로다.

한 파일에 둘을 담는 까닭은 반입이 한 번이기 때문이다 — 같은 날 같은 OSM 판에서 나왔고 같은
라이선스(ODbL)를 지며 다시 만드는 절차도 하나다. 갈라 두면 판이 어긋나도 모른다.

선은 **추정이다.** 시가 공표한 것은 정류장의 순서뿐이라 버스가 실제로 이 길로 다니는지는
아무도 모른다. 그래서 화면이 그렇다고 적고(CONTEXT 「노선 형상」), 여기서는 정확한 척하지 않는다.

세 가지를 한다.

1. **진행 방향을 알려 준다.** 길 양쪽 정류장은 20m 차이라 직선에서는 안 보이지만, 반대 차선에
   붙으면 OSRM이 유턴 경로를 낸다. 앞뒤 정류장으로 방향을 재어 `bearings`로 넘긴다.
2. **구간마다 따로 묻는다.** 노선 하나를 통째로 묻는 대신 정류장 A→B씩 묻는다. 튄 구간 하나만
   골라내 직선으로 바꿀 수 있고, 로컬 OSRM은 이 정도 호출을 몇 분에 끝낸다.
3. **점을 줄인다.** Douglas-Peucker 10m. 지도 축척에서 안 보이는 차이이고 파일이 4분의 1이 된다.

정류장 자리를 고르는 일은 `tools.build.route_geometry`가 이미 푼 것을 그대로 쓴다 — 같은 이름이
여러 고을에 있는 문제(「금곡마을」 6줄, 55km)를 그 `chain`이 푼다. 여기서 다시 풀면 지도의 점과
선이 다른 자리를 가리키게 된다.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 진행 상황에 노선 이름이 섞이는데 Windows 콘솔 기본이 cp949라 그대로 두면 도중에 죽는다
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from tools.build import load, rename_dict                      # noqa: E402
from tools.build.bundle import stop_index                      # noqa: E402
from tools.build.route_geometry import DIGITS, chain, metres    # noqa: E402

OSRM = "http://127.0.0.1:5000"      # car — 노선 형상
FOOT = "http://127.0.0.1:5001"      # foot — 환승 도보
OUT = ROOT / "data" / "source" / "route_shapes.json"

# 점을 줄이는 자. 위도 10m는 지도에서 한 픽셀도 안 되고, 이보다 크게 잡으면 좁은 골목이 펴진다
SIMPLIFY_M = 10.0
# 튐 판정 — 직선 대비 이 배수를 넘고 차이가 이 미터를 넘으면 그 구간만 직선으로 잇는다.
# 배수만 쓰면 도심에서 오탐이 잦고(강·철도를 돌면 3배는 정상), 미터만 쓰면 시외를 못 잡는다
DETOUR_TIMES = 5.0
DETOUR_M = 2_000.0
# 진행 방향에서 이만큼 벗어난 도로에는 안 붙는다. 좁히면 정류장이 도로에서 먼 곳에서 길을 못 찾는다
BEARING_RANGE = 60


def bearing(a: tuple[float, float], b: tuple[float, float]) -> int:
    """a에서 b를 볼 때의 방위각(도, 북쪽 0, 시계 방향). OSRM의 `bearings`가 받는 값이다."""
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlng = math.radians(b[1] - a[1])
    y = math.sin(dlng) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlng)
    return int(math.degrees(math.atan2(y, x))) % 360


def headings(points: list[tuple[float, float]]) -> list[int]:
    """정류장마다 버스가 지나는 방향. 앞뒤 정류장을 이은 방향이라 그 정류장에서 **꺾이는** 각이
    아니라 **지나가는** 각이다 — 반대 차선을 후보에서 빼는 데 필요한 것이 이쪽이다.
    양 끝은 이웃이 하나뿐이라 그 하나로 잰다."""
    if len(points) < 2:
        return [0] * len(points)
    return [
        bearing(points[max(i - 1, 0)], points[min(i + 1, len(points) - 1)])
        for i in range(len(points))
    ]


def ask(
    url: str,
    a: tuple[float, float],
    b: tuple[float, float],
    ba: int | None = None,
    bb: int | None = None,
) -> list | None:
    """정류장 둘 사이 차도 경로. 못 찾으면 None — 부르는 쪽이 직선으로 잇는다.

    방향을 안 주면(`ba`가 None) OSRM이 가장 가까운 도로에 그냥 붙인다. 방향을 준 답이 터무니없이
    돌아갈 때 한 번 더 묻는 데 쓴다.
    """
    # 주소의 `driving`은 OSRM이 안 읽는다 — 프로파일은 서버를 띄울 때 정해진다(car와 foot이 각각 뜬다)
    query = (
        f"{url}/route/v1/driving/{a[1]:.6f},{a[0]:.6f};{b[1]:.6f},{b[0]:.6f}"
        f"?overview=full&geometries=geojson&steps=false&alternatives=false"
    )
    if ba is not None and bb is not None:
        query += f"&bearings={ba},{BEARING_RANGE};{bb},{BEARING_RANGE}"
    try:
        with urllib.request.urlopen(query, timeout=30) as answer:
            body = json.load(answer)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    if body.get("code") != "Ok" or not body.get("routes"):
        return None
    route = body["routes"][0]
    # GeoJSON은 [경도, 위도]이고 우리는 [위도, 경도]로 적는다
    return [[point[1], point[0]] for point in route["geometry"]["coordinates"]]


def simplify(points: list[list[float]], tolerance: float) -> list[list[float]]:
    """Douglas-Peucker. 두 끝을 이은 선에서 가장 먼 점이 `tolerance`보다 가까우면 사이를 다 버린다."""
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    far, gap = 0, -1.0
    for i in range(1, len(points) - 1):
        away = _off_line(points[i], start, end)
        if away > gap:
            far, gap = i, away
    if gap <= tolerance:
        return [start, end]
    return simplify(points[: far + 1], tolerance)[:-1] + simplify(points[far:], tolerance)


def _off_line(point: list[float], start: list[float], end: list[float]) -> float:
    """점에서 선분까지의 거리(m). 광주 한 도시 안이라 평면으로 놓고 재도 충분하다."""
    span = metres((start[0], start[1]), (end[0], end[1]))
    if span == 0:
        return metres((point[0], point[1]), (start[0], start[1]))
    # 선분 위로 내린 발의 위치를 0~1로 재고, 밖으로 나가면 끝점까지의 거리다
    scale = 111_000 * math.cos(math.radians(point[0]))
    px, py = (point[1] - start[1]) * scale, (point[0] - start[0]) * 111_000
    ex, ey = (end[1] - start[1]) * scale, (end[0] - start[0]) * 111_000
    t = max(0.0, min(1.0, (px * ex + py * ey) / (ex * ex + ey * ey)))
    return math.hypot(px - ex * t, py - ey * t)


def shape(url: str, points: list[tuple[float, float]]) -> tuple[list[list[float]], int]:
    """정류장 자리 차례 → 차도 경로와 직선으로 남은 구간 수.

    구간마다 따로 묻고 이어 붙인다. 못 찾았거나 터무니없이 돌아가는 구간은 직선으로 둔다 —
    노선 전체를 버리지 않으므로 나머지는 도로를 따라간다(ADR-0009 결정 8).
    """
    if len(points) < 2:
        return [[p[0], p[1]] for p in points], 0

    angles = headings(points)

    def leg_at(i: int) -> list | None:
        """구간 하나. 방향을 주고 묻되, 그 답이 튀면 방향 없이 한 번 더 묻는다.

        방향은 앞뒤 정류장으로 잰 것이라, 정류장에서 길이 크게 꺾이면 실제 차선과 안 맞는다.
        그때 `bearings`는 멀쩡한 400m 구간을 3km로 돌려 놓는다(임곡역 → 임곡정수장). 다시 물어
        나아지면 그것을 쓰고, 그래도 튀면 진짜 우회이거나 좌표가 나쁜 것이라 부르는 쪽이 직선으로 둔다.
        """
        line = metres(points[i], points[i + 1])
        found = ask(url, points[i], points[i + 1], angles[i], angles[i + 1])
        if found is not None and not _too_far(found, line):
            return found
        plain = ask(url, points[i], points[i + 1])
        return plain if plain is not None and not _too_far(plain, line) else found

    with ThreadPoolExecutor(max_workers=8) as pool:
        legs = list(pool.map(leg_at, range(len(points) - 1)))

    path: list[list[float]] = [[points[0][0], points[0][1]]]
    straight = 0
    for i, leg in enumerate(legs):
        a, b = points[i], points[i + 1]
        line = metres(a, b)
        if leg is None or _too_far(leg, line):
            straight += 1
            path.append([b[0], b[1]])
            continue
        # 구간의 첫 점은 앞 구간의 끝과 같은 자리다
        path.extend(simplify(leg, SIMPLIFY_M)[1:])
    return [[round(p[0], DIGITS), round(p[1], DIGITS)] for p in path], straight


def _too_far(leg: list[list[float]], line: float) -> bool:
    """구간이 터무니없이 돌아가는가. 두 자를 함께 넘겨야 튐으로 본다."""
    walked = sum(
        metres((leg[i][0], leg[i][1]), (leg[i + 1][0], leg[i + 1][1]))
        for i in range(len(leg) - 1)
    )
    return walked > line * DETOUR_TIMES and walked - line > DETOUR_M


def walks(url: str, source: Path) -> dict[str, list[list[float]]]:
    """환승 도보 선들. 키는 `작은 STATION_NUM|큰 STATION_NUM`이라 어느 쪽에서 걸어도 같은 선이다.

    걸을 자리는 `route_links`가 정한다 — 노선 쌍마다 환승 지점 하나다(ADR-0008). 그 7,250개 중
    6,399개는 **같은 정류장**에서 갈아타므로 걸을 것이 없고, 서로 다른 자리는 141쌍뿐이다.
    출발·도착 도보는 여기 없다 — 시민이 고른 지점이라 미리 낼 수 없다(ADR-0009 결정 7).
    """
    from tools.build import bundle as bundle_json          # 무거워서 쓸 때만 들인다

    made = bundle_json.make(
        load.read_before(source), load.read_after(source), load.read_stops(source),
        load.read_name_canon(ROOT / "data" / "name_canon.json"),
        rename_dict.from_rows(load.read_renames(source)), load.read_additions(source),
    ).data
    where = {num: (row["lat"], row["lng"]) for num, row in made["stops"].items()}
    pairs = sorted({tuple(sorted((a, b))) for _, _, a, b, _ in made["route_links"] if a != b})

    lines: dict[str, list[list[float]]] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        found = list(pool.map(lambda p: ask(url, where[p[0]], where[p[1]]), pairs))
    for (a, b), leg in zip(pairs, found):
        line = metres(where[a], where[b])
        if leg is None or _too_far(leg, line):
            continue                                        # 못 찾으면 열쇠를 안 남긴다 — 화면이 직선으로 잇는다
        lines[f"{a}|{b}"] = [
            [round(p[0], DIGITS), round(p[1], DIGITS)] for p in simplify(leg, SIMPLIFY_M)
        ]
    print(f"환승 도보 {len(lines)}/{len(pairs)}쌍", file=sys.stderr)
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="노선 형상과 환승 도보를 OSRM으로 낸다 (ADR-0009)")
    parser.add_argument("--url", default=OSRM, help=f"OSRM car 자리 (기본 {OSRM})")
    parser.add_argument("--foot-url", default=FOOT, help=f"OSRM foot 자리 (기본 {FOOT})")
    parser.add_argument("--out", type=Path, default=OUT, help=f"낼 파일 (기본 {OUT})")
    args = parser.parse_args()

    source = ROOT / "data" / "source"
    index = stop_index(
        load.read_stops(source),
        load.read_name_canon(ROOT / "data" / "name_canon.json"),
        rename_dict.from_rows(load.read_renames(source)),
    )

    shapes: dict[str, dict] = {}
    straight_total = skipped_total = 0
    networks = (("before", load.read_before(source)), ("after", load.read_after(source)))
    for network, routes in networks:
        for route in routes:
            for way, names in (("up", route.up), ("down", route.down)):
                if not names:
                    continue                       # 순환·편도는 하행이 없다
                found = chain(index, names)
                points = [p for p in found if p is not None]
                skipped_total += sum(1 for p in found if p is None)
                if len(points) < 2:
                    continue
                path, straight = shape(args.url, points)
                straight_total += straight
                shapes[f"{network}|{route.name}|{way}"] = {
                    "points": path,
                    "straight": straight,
                }
                print(f"  {network} {route.name} {way}: 점 {len(path)} · 직선 {straight}",
                      file=sys.stderr)

    walk_lines = walks(args.foot_url, source)

    args.out.write_text(json.dumps({
        "meta": {
            "made": date.today().isoformat(),
            "engine": "OSRM · car(노선 형상) · foot(환승 도보)",
            "osm": "Geofabrik south-korea-latest.osm.pbf",
            "license": "ODbL · © OpenStreetMap contributors",
            "simplify_m": SIMPLIFY_M,
            "detour": [DETOUR_TIMES, DETOUR_M],
            "bearing_range": BEARING_RANGE,
            "note": "선은 정류장을 순서대로 이은 차도 경로이며 실제 운행 경로가 아니다 (ADR-0009)",
        },
        "shapes": shapes,
        "walks": walk_lines,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    points_total = sum(len(s["points"]) for s in shapes.values())
    print(
        f"\n형상 {len(shapes)}개 · 점 {points_total:,}개 · 직선으로 남은 구간 {straight_total}개"
        f" · 좌표 못 이은 정류장 {skipped_total}개\n{args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
