"""빌드 스크립트 — CSV를 읽어 노선번호 탭의 정적 조각을 쓴다 (ADR-0002).

배포 전에 한 번 돌린다. 진입점은 `build(source, out)` 하나이고, `out/`을 비우고 다시 쓴다.
노선 변화 표의 규칙(번호 잇기 · 명칭 사전 · 방면 · 기·종점 정렬 · 기·종점 정류장 대조 · 비고)은 전부 여기 산다.

    python -m tools.build                    # data/source → out/
    python -m tools.build data/source out    # 경로를 직접 줄 때

이번 범위는 껍데기 `index.html` 한 장(노선 개편 목록 표 103줄을 품는다)과
노선 변화 표 조각 205개, 노선 변화 카드 103개다. 장소 탭은 자리만 있다.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import (
    branches, load, notes, rename_dict, render, route_card, route_list, shell, stop_match,
    terminus_align,
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


def _align_table_path(source: Path, given: Path | None) -> Path:
    """기·종점 정렬표는 사람이 적는 파일이라 `data/source/`가 아니라 그 위 `data/`에 있다."""
    return given if given is not None else source.parent / terminus_align.TABLE_CSV


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


def build(source: Path, out: Path, *, align_table: Path | None = None) -> Result:
    """`source`의 CSV를 읽어 `out/`에 노선 변화 표 조각을 쓴다.

    번호를 못 잇거나 기·종점 정렬표에 사람이 안 적은 쌍이 있으면 목록을 담은 `BuildError`를 낸다.
    """
    source, out = Path(source).resolve(), Path(out).resolve()
    before = load.read_before(source)
    after = load.read_after(source)
    replacements = load.read_replacements(source)
    renames = rename_dict.from_rows(load.read_renames(source))
    facts = notes.collect(renames, load.read_removals(source), load.read_additions(source))

    pairs, missing = branches.pairs(before, after, replacements)
    if missing:
        raise BuildError(
            "비교표의 번호를 노선안에서 못 찾았습니다 (규칙은 ADR-0006):\n  "
            + "\n  ".join(missing)
        )

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

    if not shell.CSS_SOURCE.exists():
        raise BuildError(f"화면 CSS가 없습니다: {shell.CSS_SOURCE}")

    _clear(out, source)
    stages: dict[str, int] = {}
    tables: dict[tuple[str, str, str, str], str] = {}
    for pair in pairs:
        alignment = alignments[pair.key]
        stages[alignment.stage] = stages.get(alignment.stage, 0) + 1
        tables[pair.key] = _write_table(
            out, pair, alignment, before_siblings, after_siblings, facts
        )

    for card in cards:
        # 카드는 자기 기본 표를 통째로 품는다 — 열자마자 버튼을 누르기 전에도 답이 보인다
        html = render.route_change_card(card, tables[card.default] if card.default else "")
        _write(out / render.card_url(card.before.number), html)

    _write(out / "index.html", render.index_page(route_list.rows(cards)))
    shutil.copyfile(shell.CSS_SOURCE, out / shell.CSS)

    return Result(out=out, tables=len(pairs), cards=len(cards), stages=stages)


def _write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def _write_table(
    out: Path,
    pair: branches.Pair,
    alignment: terminus_align.Alignment,
    before_siblings: dict[str, list[load.Route]],
    after_siblings: dict[str, list[load.Route]],
    facts: notes.Facts,
) -> str:
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
    html = render.route_change_table(
        pair,
        up,
        down,
        stop_match.summary(up),
        stop_match.summary(down),
        flipped=flipped,
        row_notes=notes.for_rows(up, down, facts, table_note=table_note),
    )
    _write(out / render.fragment_url(pair.key), html)
    return html
