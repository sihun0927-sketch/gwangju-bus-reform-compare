"""0단계 번호 잇기 — CSV를 읽고 노선 표기를 (종류, 번호, 방면)으로 가른다 (ADR-0006).

시가 공표한 CSV는 파일마다 노선을 다르게 적는다. 개편 후 노선안은 「간선 01」, 비교표는 「1」,
개편 전 노선안은 방면 접미가 붙은 「두암81(각화초교.장등동)」이다. 셋을 잇는 규칙이 여기 있고,
못 잇는 쌍은 `branches.pairs`가 모아 빌드를 멈춘다.

정류장 구분자도 파일마다 다르다 — 개편 전 `▶`, 개편 후 `>`. 읽을 때 목록으로 통일한다.
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import BuildError

BEFORE_SEP = "▶"
AFTER_SEP = ">"
DEFAULT_BRANCH = "기본"

ROUTE_COLUMNS = (
    "버스번호", "기점", "종점",
    "상행 정류장수", "상행 정류장(순서대로)",
    "하행 정류장수", "하행 정류장(순서대로)",
)
TABLE_COLUMNS = ("기존 노선", "신규(대체) 노선")

# 명칭 사전이 읽는 CSV. 노선안 CSV에는 정류장 ID가 없어 노선 변화 표는 이름으로만 견주지만,
# 이 CSV의 「ID」는 `stops.csv`의 ARS_ID와 102/102로 이어진다(ADR-0007) — 번들이 그쪽을 쓴다
RENAME_COLUMNS = ("현 정류소", "ID", "변경정류소")
REMOVAL_COLUMNS = ("구분", "정류소명", "통폐합사유")
ADDITION_COLUMNS = ("정류소",)

# 정류장 좌표 — 시 공표 CSV가 아니라 광주 BIS API에서 받아 둔 것이다(ADR-0007). 읽기만 한다
STOPS_COLUMNS = ("STATION_NUM", "BUSSTOP_NAME", "ARS_ID", "LATITUDE", "LONGITUDE")

# 개편 전 배차간격. 파일에는 정류장 목록 두 열도 있지만 노선안과 겹치는 값이라 읽지 않는다
HEADWAY_COLUMNS = ("route_name", "headway_minutes")

RENAME_CSV = "명칭 변경 정류소.csv"
REMOVAL_CSV = "통폐합이전정류소.csv"
ADDITION_CSV = "신설 정류소.csv"
BEFORE_CSV = "광주권역 개편전 노선안.csv"
AFTER_CSV = "광주권역 개편후 노선안.csv"
TABLE_CSV = "노선개편 전후 비교표.csv"
STOPS_CSV = "stops.csv"
HEADWAY_CSV = "route_headways_with_stops.csv"
NAME_CANON_JSON = "name_canon.json"
# 노선 형상 — OSRM이 낸 차도 경로(ADR-0009). 빌드는 읽기만 한다
ROUTE_SHAPES_JSON = "route_shapes.json"

# 「지선 97(빛그린산단출근)」 → 종류 지선 · 번호 97 · 방면 빛그린산단출근. 「228」은 종류 없음
ROUTE_RE = re.compile(r"^(?P<kind>[^\d\s(]+)?\s*(?P<num>\d+(?:-\d+)?)\s*(?:\((?P<branch>[^)]*)\))?$")
BRANCH_RE = re.compile(r"^(?P<number>.*?)\((?P<branch>[^)]*)\)$")


@dataclass(frozen=True)
class Route:
    """노선안 CSV 한 행. 방면 하나가 행 하나다."""

    name: str          # 노선 이름 — 띄어쓰기 없는 CSV 표기 「문흥18」「지선97(빛그린산단출근)」
    number: str        # 방면을 뗀 번호 「문흥18」「두암81」「지선97」 — 조각 경로의 한 단계
    branch: str        # 방면 「기본」「각화초교.장등동」
    kind: str          # 종류 — 개편 후만 있다 「간선」「급행」, 228·419·518·1187과 개편 전은 빈 문자열
    digits: str        # 앞 0을 뗀 숫자 「18」「1」「70-1」 — 비교표와 잇는 데만 쓴다
    origin: str        # 기점
    terminus: str      # 종점
    up: tuple[str, ...]    # 상행 정류장(순서대로)
    down: tuple[str, ...]  # 하행 정류장(순서대로). 순환·편도는 비어 있다


@dataclass(frozen=True)
class Rename:
    """명칭 변경 CSV 한 행 — 정류장 ID 하나가 행 하나라 같은 옛 이름이 여러 행에 나온다."""

    old: str      # 현 정류소 — 개편 전 노선안이 쓰는 이름. `stops.csv`의 표기와 다를 수 있다
    new: str      # 변경정류소 — 개편 후 노선안이 쓰는 이름
    ars_id: str   # ID — `stops.csv`의 ARS_ID. 이름이 아니라 이것이 정류장을 가리킨다


@dataclass(frozen=True)
class Removal:
    """통폐합·이전·폐지 CSV 한 행. 비고에는 구분만 적고 사유는 마우스를 올렸을 때 보인다."""

    kind: str    # 구분 — 통폐합 / 폐지 / 이전
    stop: str    # 정류소명. 「A(B)」는 B를 A로 흡수했다는 뜻이라 노선안의 이름과 안 맞는다
    reason: str  # 통폐합사유 — 화면에는 `title`로만 나온다


@dataclass(frozen=True)
class Stop:
    """`stops.csv` 한 줄. 정류장의 정체성이 이 줄이고 키는 STATION_NUM이다(ADR-0008 결정 2).

    같은 이름이 보통 두 줄이다 — 길 양쪽이 따로다. 이름은 노선안과 잇는 데만 쓰는 열쇠이지
    정체성이 아니다.
    """

    station_num: str   # STATION_NUM — 번들 stops의 키
    name: str          # BUSSTOP_NAME. 꼬리 공백을 뗀 값(ADR-0007)
    ars_id: str        # ARS_ID. 전남 정류장은 비어 있어 키가 될 수 없다
    lat: float         # LATITUDE
    lng: float         # LONGITUDE


@dataclass(frozen=True)
class Replacement:
    """비교표 한 행 — 개편 전 번호 하나와 그것이 적어 둔 대체 노선 표기들."""

    before: str          # 개편 전 번호(공백 없는 표기)
    spelled: tuple[str, ...]   # 비교표가 적은 대체 노선 표기 「1」「급행03」. 빈 행도 있다(두암181)


def read_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    """UTF-8 BOM CSV를 읽는다. 열 이름이 다르면 빌드를 멈춘다."""
    if not path.exists():
        raise BuildError(f"입력 CSV가 없습니다: {path}")
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = tuple(reader.fieldnames or ())
        missing = [c for c in columns if c not in header]
        if missing:
            raise BuildError(f"{path.name}의 열 이름이 다릅니다. 없는 열: {', '.join(missing)} / 읽은 열: {', '.join(header)}")
        return list(reader)


def split_stops(text: str, sep: str) -> tuple[str, ...]:
    return tuple(s.strip() for s in text.split(sep) if s.strip())


def parse(name: str) -> tuple[str, str, str]:
    """노선 표기 → (종류, 번호, 방면). 번호는 앞자리 0을 뗀다(「01」 → 「1」), 방면 없으면 「기본」."""
    m = ROUTE_RE.match(name.strip())
    if not m:
        raise BuildError(f"노선 표기를 가를 수 없습니다: {name!r} (규칙은 ADR-0006)")
    main, _, tail = m.group("num").partition("-")
    digits = str(int(main)) + ("-" + tail if tail else "")
    return m.group("kind") or "", digits, m.group("branch") or DEFAULT_BRANCH


def split_branch(name: str) -> tuple[str, str]:
    """띄어쓰기 없는 노선 이름 → (방면 뗀 번호, 방면). 「두암81(각화초교.장등동)」 → (두암81, 각화초교.장등동)."""
    m = BRANCH_RE.match(name)
    if m:
        return m.group("number"), m.group("branch")
    return name, DEFAULT_BRANCH


def _route(row: dict[str, str], sep: str, *, split_kind: bool) -> Route:
    name = re.sub(r"\s+", "", row["버스번호"])
    number, branch = split_branch(name)
    kind, digits, _ = parse(name) if split_kind else ("", "", "")
    return Route(
        name=name,
        number=number,
        branch=branch,
        kind=kind,
        digits=digits,
        origin=row["기점"].strip(),
        terminus=row["종점"].strip(),
        up=split_stops(row["상행 정류장(순서대로)"], sep),
        down=split_stops(row["하행 정류장(순서대로)"], sep),
    )


def read_before(source: Path) -> list[Route]:
    """개편 전 노선안 111행. 앞말(순환·문흥·두암…)은 종류가 아니라 번호의 일부다."""
    rows = read_csv(source / BEFORE_CSV, ROUTE_COLUMNS)
    return [_route(r, BEFORE_SEP, split_kind=False) for r in rows]


def read_after(source: Path) -> list[Route]:
    """개편 후 노선안 119행. 노선의 신원은 종류 + 번호다(급행03 ≠ 간선03)."""
    rows = read_csv(source / AFTER_CSV, ROUTE_COLUMNS)
    return [_route(r, AFTER_SEP, split_kind=True) for r in rows]


def read_replacements(source: Path) -> list[Replacement]:
    """비교표 103행. 대체 관계의 유일한 출처이며 우리가 계산하지 않는다."""
    rows = read_csv(source / TABLE_CSV, TABLE_COLUMNS)
    return [
        Replacement(
            before=re.sub(r"\s+", "", r["기존 노선"]),
            spelled=tuple(s.strip() for s in r["신규(대체) 노선"].split(",") if s.strip()),
        )
        for r in rows
    ]


def read_renames(source: Path) -> list[Rename]:
    """명칭 변경 정류소 102행. 사전으로 만드는 것은 `rename_dict`가 한다."""
    rows = read_csv(source / RENAME_CSV, RENAME_COLUMNS)
    return [
        Rename(old=r["현 정류소"].strip(), new=r["변경정류소"].strip(), ars_id=r["ID"].strip())
        for r in rows
    ]


def read_removals(source: Path) -> list[Removal]:
    """통폐합이전정류소 16행. 폐지도 이 파일에 있다."""
    rows = read_csv(source / REMOVAL_CSV, REMOVAL_COLUMNS)
    return [
        Removal(kind=r["구분"].strip(), stop=r["정류소명"].strip(), reason=r["통폐합사유"].strip())
        for r in rows
    ]


def read_additions(source: Path) -> list[str]:
    """신설 정류소 68행 — 이름만 쓴다."""
    return [r["정류소"].strip() for r in read_csv(source / ADDITION_CSV, ADDITION_COLUMNS)]


def read_headways(source: Path) -> dict[str, int]:
    """개편 전 배차간격 110행 — 노선 이름 → 분.

    **개편 전만 있다.** 개편 후는 시가 공표한 값이 없어 카드가 「정보 없음」이라 적는다
    (CONTEXT 「경로 줄」). 개편 전 111행 중 순환01 한 행도 이 파일에 없어 그 노선도 「정보 없음」이다.

    이름은 노선안의 버스번호와 같은 표기라 잇는 규칙(ADR-0006)이 필요 없다 — 공백만 뗀다.
    분이 아닌 값이 오면 멈춘다. 조용히 건너뛰면 그 노선만 「정보 없음」이 되어, 자료가 깨진 것인지
    원래 없는 것인지를 화면에서 가릴 수 없다.
    """
    out: dict[str, int] = {}
    for r in read_csv(source / HEADWAY_CSV, HEADWAY_COLUMNS):
        name = re.sub(r"\s+", "", r["route_name"])
        raw = r["headway_minutes"].strip()
        if not raw.isdigit() or int(raw) <= 0:
            raise BuildError(f"{HEADWAY_CSV}의 배차간격이 분이 아닙니다: {name} — {raw!r}")
        if name in out:
            raise BuildError(f"{HEADWAY_CSV}에 같은 노선이 두 번 있습니다: {name}")
        out[name] = int(raw)
    return out


def read_shapes(source: Path) -> dict[str, tuple[tuple[float, float], ...]]:
    """노선 형상 452개 — 「망|노선이름|방향」 → 차도 경로의 점들 (ADR-0009).

    키의 노선 이름은 노선안 CSV 표기 그대로다(방면까지, 「두암81(각화초교.장등마을)」). 방향은
    `up`·`down`이다. 값은 OSRM이 낸 차도 경로를 10m로 단순화한 것이라 **정류장 좌표가 아니다** —
    정류장 점은 지금도 `stops.csv`에서 온다(ADR-0009 결정 1: 점은 사실, 선은 추정).

    파일이 없으면 빈 표를 돌려준다. 그때 지도는 지난날처럼 정류장을 직선으로 잇는다 — 형상은
    도커로 한 번 내는 것이라(ADR-0009 결정 2) 없는 곳에서도 빌드는 돌아야 한다.
    """
    path = source / ROUTE_SHAPES_JSON
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    shapes = data.get("shapes", {})
    out: dict[str, tuple[tuple[float, float], ...]] = {}
    for key, shape in shapes.items():
        points = shape.get("points") or []
        if len(points) < 2:
            continue
        out[key] = tuple((float(p[0]), float(p[1])) for p in points)
    return out


def shape_key(network: str, route_name: str, way: str) -> str:
    """`read_shapes`의 키. 만드는 쪽(`tools/build_shapes.py`)과 이 한 줄로만 맞춘다."""
    return f"{network}|{route_name}|{way}"


def read_stops(source: Path) -> list[Stop]:
    """`stops.csv` 4,746줄 — 좌표의 유일한 출처(ADR-0007). 이 빌드는 이 파일을 읽기만 한다.

    이름의 꼬리 공백은 뗀다(API 자료의 함정, ADR-0007). 같은 STATION_NUM이 두 줄이면 멈춘다 —
    번들 stops의 키라 겹치면 한 줄이 조용히 사라진다.
    """
    rows = read_csv(source / STOPS_CSV, STOPS_COLUMNS)
    stops: list[Stop] = []
    seen: set[str] = set()
    for r in rows:
        num = r["STATION_NUM"].strip()
        if num in seen:
            raise BuildError(f"{STOPS_CSV}의 STATION_NUM이 겹칩니다: {num}")
        seen.add(num)
        try:
            lat, lng = float(r["LATITUDE"]), float(r["LONGITUDE"])
        except ValueError:
            raise BuildError(
                f"{STOPS_CSV}의 좌표를 읽을 수 없습니다: STATION_NUM {num} "
                f"({r['LATITUDE']!r}, {r['LONGITUDE']!r})"
            ) from None
        stops.append(
            Stop(station_num=num, name=r["BUSSTOP_NAME"].strip(), ars_id=r["ARS_ID"].strip(),
                 lat=lat, lng=lng)
        )
    return stops


def read_name_canon(path: Path) -> dict[str, str | None]:
    """노선안 표기 → `stops.csv` 정식 표기(ADR-0007). 값이 `None`이면 좌표가 없다는 뜻이다.

    사람이 손대는 파일이 아니라 `tools/build_stops.py`가 쓰는 파일이라 `data/source/`가 아니라
    그 위 `data/`에 있다 — 기·종점 정렬표와 같은 자리다.
    """
    if not path.exists():
        raise BuildError(f"이름 잇기 표가 없습니다: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise BuildError(f"{path.name}은 객체 하나여야 합니다.")
    return {str(k): (None if v is None else str(v)) for k, v in raw.items()}


def find_after(routes: list[Route], spelled: str) -> list[Route]:
    """비교표 표기 하나 → 개편 후 노선 행들(방면마다 하나).

    종류가 적혀 있으면(「급행03」) 그 종류, 숫자만이면(「03」) 그 번호를 가진 노선 중 급행 아닌 것.
    앞자리 0은 무시한다 — 비교표 순환01 행만 「1」이고 나머지는 「01」이다(ADR-0006 결정 2).
    """
    kind, digits, _ = parse(spelled)
    hits = [r for r in routes if r.digits == digits]
    if kind:
        return [r for r in hits if r.kind == kind]
    if len({r.kind for r in hits}) > 1:
        return [r for r in hits if r.kind != "급행"]
    return hits
