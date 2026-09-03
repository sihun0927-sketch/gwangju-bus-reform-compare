"""0단계 번호 잇기 — CSV를 읽고 노선 표기를 (종류, 번호, 방면)으로 가른다 (ADR-0006).

시가 공표한 CSV는 파일마다 노선을 다르게 적는다. 개편 후 노선안은 「간선 01」, 비교표는 「1」,
개편 전 노선안은 방면 접미가 붙은 「두암81(각화초교.장등동)」이다. 셋을 잇는 규칙이 여기 있고,
못 잇는 쌍은 `branches.pairs`가 모아 빌드를 멈춘다.

정류장 구분자도 파일마다 다르다 — 개편 전 `▶`, 개편 후 `>`. 읽을 때 목록으로 통일한다.
"""
from __future__ import annotations

import csv
import io
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

BEFORE_CSV = "광주권역 개편전 노선안.csv"
AFTER_CSV = "광주권역 개편후 노선안.csv"
TABLE_CSV = "노선개편 전후 비교표.csv"

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
