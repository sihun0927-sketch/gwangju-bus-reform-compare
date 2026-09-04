"""빌드 스크립트 — CSV를 읽어 노선번호 탭의 정적 조각을 쓴다 (ADR-0002).

배포 전에 한 번 돌린다. 진입점은 `build(source, out, bundle)` 하나이고, `out/`을 비우고 다시 쓴다.
노선 변화 표의 규칙(번호 잇기 · 명칭 사전 · 방면 · 기·종점 정렬 · 기·종점 정류장 대조 · 비고)은 전부 여기 산다.

    python -m tools.build                                   # data/source → out/ + worker/data.json
    python -m tools.build data/source out worker/data.json  # 경로를 직접 줄 때

산출물은 둘이다 — `out/`의 정적 조각(껍데기 `index.html` 한 장, 노선 변화 카드 103개,
노선 변화 표 205개)과 장소 탭 Worker가 import하는 번들 JSON 한 장(ADR-0008).
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

# `build`의 셋째 인자 이름이 `bundle`이라 모듈은 별칭으로 받는다(진입점 모양은 이슈 #23이 정했다)
from . import (
    branches, bundle as bundle_json, headway, load, notes, rename_dict, render, route_card,
    route_geometry, route_list, shell, stop_match, terminus_align,
)
from .errors import BuildError

__all__ = ["build", "BuildError", "Result"]


@dataclass(frozen=True)
class Result:
    """빌드가 무엇을 얼마나 썼는지. 명령줄이 그대로 찍고, 실측 수치(architecture §6)와 견준다."""

    out: Path
    tables: int
    cards: int
    stages: dict[str, int]
    bundle: Path
    bundle_bytes: int
    bundle_counts: bundle_json.Counts
    map_stops: int      # 노선 지도에 찍은 점(표마다 세어 더한 것)
    map_missing: int    # 좌표가 없어 못 찍은 정류장 — 사이트 전체에서 **이름 몇 개**인지
    estimate: headway.Estimate   # 개편 후 배차간격 추정(ADR-0010). 명령줄이 수치를 찍는다


def _align_table_path(source: Path, given: Path | None) -> Path:
    """기·종점 정렬표는 사람이 적는 파일이라 `data/source/`가 아니라 그 위 `data/`에 있다."""
    return given if given is not None else source.parent / terminus_align.TABLE_CSV


def _canon_path(source: Path) -> Path:
    """이름 잇기 표도 사람이 아니라 `tools/build_stops.py`가 쓰는 파일이라 `data/` 바로 아래에 있다."""
    return source.parent / load.NAME_CANON_JSON


def _clear(out: Path, source: Path) -> None:
    if out == source or source.is_relative_to(out):
        raise BuildError(f"입력을 담은 자리는 지우지 않습니다: {out}")
    if out.exists():
        if not out.is_dir():
            raise BuildError(f"출력 자리가 폴더가 아닙니다: {out}")
        if (out / ".git").exists():
            raise BuildError(f"출력 자리에 저장소가 있습니다. 지우지 않습니다: {out}")
        shutil.rmtree(out)
    out.mkdir(parents=True)


def build(
    source: Path,
    out: Path,
    bundle: Path,
    *,
    align_table: Path | None = None,
    kakao_js_key: str = "",
) -> Result:
    """`source`의 CSV를 읽어 `out/`에 정적 조각을, `bundle`에 번들 JSON을 쓴다.

    번들 자리에 기본값을 두지 않는다 — 기본값(`worker/data.json`)은 명령줄의 것이고, 여기에
    두면 자리를 안 준 호출이 작업 트리의 배포 산출물을 조용히 덮어쓴다.

    `kakao_js_key`는 껍데기의 지도 SDK 태그에 박는다. 리포에 없는 값이라 기본은 빈 값이고,
    그때는 태그를 안 달아 지도가 안 뜬다(ADR-0005) — 나머지 화면은 그대로 돈다.

    번호를 못 잇거나, 기·종점 정렬표에 사람이 안 적은 쌍이 있거나, 노선안 정류장 이름을
    `stops.csv`의 줄에 못 이으면 목록을 담은 `BuildError`를 낸다.
    """
    source, out = Path(source).resolve(), Path(out).resolve()
    bundle_path = Path(bundle).resolve()
    before = load.read_before(source)
    after = load.read_after(source)
    replacements = load.read_replacements(source)
    renames = rename_dict.from_rows(load.read_renames(source))
    additions = load.read_additions(source)
    facts = notes.collect(renames, load.read_removals(source), additions)
    stops = load.read_stops(source)
    canon = load.read_name_canon(_canon_path(source))
    headways = load.read_headways(source)
    # 배차간격 원천이 지금 **둘**이다. `load.read_headways`가 읽는 것은 개편 전 110행이라
    # 순환01이 없고(그 노선은 화면에 「정보 없음」), 추정은 111행을 다 알아야 유효 운행시간을
    # 풀 수 있어 순환01A·B가 든 `route_headways.csv`(120행)를 따로 읽는다.
    # **하나로 합치는 것이 맞다** — 뒤엣것이 앞엣것을 덮으므로 옮기면 순환01 구멍도 메워진다.
    # 다만 그것은 화면의 「정보 없음」 한 줄을 바꾸는 일이라 이 PR에서 하지 않는다(ADR-0010 남은 일)
    headways_full = headway.read_headways(source)

    pairs, missing = branches.pairs(before, after, replacements)
    if missing:
        raise BuildError(
            "비교표의 번호를 노선안에서 못 찾았습니다 (규칙은 ADR-0006):\n  "
            + "\n  ".join(missing)
        )

    # 번들은 `out/`을 지우기 전에 만들어 본다 — 이름을 못 이으면 지난번 조각을 남긴 채 멈춘다
    made = bundle_json.make(before, after, stops, canon, renames, additions, headways)
    # 노선 지도는 번들과 같은 이름 잇기를 쓴다. 다만 추정 좌표는 안 받는다(ADR-0007, `route_geometry`)
    index = bundle_json.stop_index(stops, canon, renames)
    # 지도의 선은 정류장 직선이 아니라 차도 경로다(ADR-0009). 없으면 빈 표이고 직선으로 돌아간다
    shapes = load.read_shapes(source)
    # 배차간격 추정도 `out/`을 지우기 전에 끝내 둔다 — 원천이 어긋나면 지난번 조각을 남긴 채 멈춘다
    estimated = headway.estimate(before, after, replacements, headways_full, index, renames)

    table = terminus_align.read_table(_align_table_path(source, align_table))
    alignments, unwritten = terminus_align.align(pairs, table)
    if unwritten:
        raise BuildError(
            f"기·종점 정렬표({terminus_align.TABLE_CSV})에 사람이 아직 안 적은 쌍이 있습니다:\n  "
            + "\n  ".join(p.label for p in unwritten)
        )

    before_siblings = branches.by_number(before)
    after_siblings = branches.by_number(after)
    # 카드는 `out/`을 지우기 전에 다 만들어 본다 — 입력이 틀리면 반쯤 쓰다 만 자리를 남기지 않는다
    cards = [route_card.card(row, before_siblings.get(row.before, []), after) for row in replacements]

    assets = (shell.CSS_SOURCE, shell.PLACE_JS_SOURCE, shell.MAP_JS_SOURCE)
    for asset in assets:
        if not asset.exists():
            raise BuildError(f"화면 자산이 없습니다: {asset}")

    _clear(out, source)
    stages: dict[str, int] = {}
    tables: dict[tuple[str, str, str, str], str] = {}
    map_stops = 0
    # 못 찍은 정류장은 표마다 더하면 같은 이름을 여러 번 센다. 사이트 전체에서 몇 곳인지를 낸다
    map_undrawn: set[str] = set()
    for pair in pairs:
        alignment = alignments[pair.key]
        stages[alignment.stage] = stages.get(alignment.stage, 0) + 1
        tables[pair.key], drawn = _write_table(
            out, pair, alignment, before_siblings, after_siblings, facts, index, shapes
        )
        map_stops += len(drawn.stops)
        map_undrawn |= drawn.undrawn

    for card in cards:
        # 카드는 자기 기본 표를 통째로 품는다 — 열자마자 버튼을 누르기 전에도 답이 보인다
        html = render.route_change_card(card, tables[card.default] if card.default else "")
        _write(out / render.card_url(card.before.number), html)

    _write(out / "index.html", render.index_page(route_list.rows(cards), kakao_js_key))
    for asset in assets:
        shutil.copyfile(asset, out / asset.name)
    _write_shapes(out, shapes)

    written = bundle_json.write(bundle_path, made)
    # 배차간격 표는 번들과 따로 둔다 — 2MB짜리 번들과 달리 100KB가 안 되고, 정적 자산으로도
    # 나가야 LLM이 주소 하나로 통째로 받아 갈 수 있다(ADR-0010 결정 4)
    headway_text = headway.write(bundle_path.parent / headway.JSON_NAME, estimated)
    (out / headway.JSON_NAME).write_text(headway_text, encoding="utf-8")

    return Result(
        out=out, tables=len(pairs), cards=len(cards), stages=stages,
        bundle=bundle_path, bundle_bytes=written, bundle_counts=made.counts,
        map_stops=map_stops, map_missing=len(map_undrawn), estimate=estimated,
    )


def _write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


# 노선 형상을 파일 하나씩 내놓는 자리. 장소 탭은 조각에 좌표를 싣지 않고 여기서 받아 자른다
# (ADR-0009 결정 4) — 경로 하나에 노선이 셋까지라 카드마다 33KB쯤이다
SHAPE_DIR = "shape"
# 파일 이름에서 `|`를 대신하는 글자. `map.js`의 `형상_받기`와 같아야 한다
SHAPE_SEP = "~"


def _write_shapes(out: Path, shapes: dict[str, tuple[tuple[float, float], ...]]) -> int:
    """형상 452개를 `out/shape/`에 한 줄짜리 JSON으로 쓴다. 파일 이름은 키를 URL 인코딩한 것이다.

    키의 `|`만 `~`로 바꾼다 — 윈도우에서 파일 이름이 못 되는 글자가 그것 하나이고, `~`는 주소에서
    그대로 나가는 글자라 자산 서버가 다시 인코딩하지 않는다. 한글은 브라우저가 알아서 인코딩하고
    자산 서버가 되돌린다. `map.js`가 같은 규칙으로 주소를 만든다 — 두 곳에 한 줄씩이다.
    """
    if not shapes:
        return 0
    folder = out / SHAPE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    for key, points in shapes.items():
        body = json.dumps([[lat, lng] for lat, lng in points], separators=(",", ":"))
        (folder / f"{key.replace('|', SHAPE_SEP)}.json").write_text(body, encoding="utf-8")
    return len(shapes)


def _write_table(
    out: Path,
    pair: branches.Pair,
    alignment: terminus_align.Alignment,
    before_siblings: dict[str, list[load.Route]],
    after_siblings: dict[str, list[load.Route]],
    facts: notes.Facts,
    index: bundle_json.StopIndex,
    shapes: dict[str, tuple[tuple[float, float], ...]],
) -> tuple[str, route_geometry.Geometry]:
    flipped = bool(alignment.flipped)
    # 뒤집어 맞댄 표의 「개편 후 상행」 칸에는 CSV의 하행이 들어간다 — 개편 전 상행과 같은 방향이다
    after_up = pair.after.down if flipped else pair.after.up
    after_down = pair.after.up if flipped else pair.after.down

    up = stop_match.match(pair.before.up, after_up, facts.renames.canon)
    # 하행 칸을 채울지는 뒤집은 뒤의 목록으로 본다. 한쪽이 비면 두 칸을 비우고 비고가 까닭을 말한다
    has_down = bool(pair.before.down) and bool(after_down)
    down = stop_match.match(pair.before.down, after_down, facts.renames.canon) if has_down else []

    table_note = notes.down_missing(
        pair,
        before_siblings.get(pair.before.number, []),
        after_siblings.get(pair.after.number, []),
    )
    # 지도는 상행만 그린다 — 표의 「개편 후 상행 정류장」 칸에 들어간 바로 그 목록을 쓴다(§7-3 Q7)
    # 선도 「개편 후 상행」 칸과 같은 방향이어야 한다 — 뒤집어 맞댔으면 대체 노선의 하행 형상이다
    lines = (
        shapes.get(load.shape_key("before", pair.before.name, "up")),
        shapes.get(load.shape_key("after", pair.after.name, "down" if flipped else "up")),
    )
    drawn = route_geometry.geometry(index, pair.before.up, after_up, up, lines)
    html = render.route_change_table(
        pair,
        up,
        down,
        stop_match.summary(up),
        stop_match.summary(down),
        flipped=flipped,
        row_notes=notes.for_rows(up, down, facts, table_note=table_note),
        geometry=drawn,
    )
    _write(out / render.fragment_url(pair.key), html)
    return html, drawn
