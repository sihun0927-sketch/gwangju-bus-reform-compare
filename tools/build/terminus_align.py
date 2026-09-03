"""3단계 기·종점 정렬 — 개편 전 상행이 대체 노선의 상행·하행 중 어느 쪽과 짝인지 정한다 (ADR-0003 결정 3).

개편 후 노선의 기·종점이 개편 전과 반대인 쌍이 있다(문흥18 장등동→진곡산단 vs 간선18 하남고등학교→장등동).
상행끼리 그대로 맞대면 순서가 거꾸로라 전부 경유 제외·경유 추가가 된다. 그래서 세 단계로 정한다.

  ① 기·종점 이름이 같거나 서로 바뀌어 있음        → 자동
  ② 정류장 목록 겹침(LCS)이 한쪽으로 뚜렷함        → 자동
  ③ 그래도 애매함(겹침 약함·동률)                → data/기종점정렬표.csv 에 사람이 적는다

③에 해당하는 쌍인데 표에 행이 없으면 빌드는 그 목록을 내고 멈춘다. 짐작으로 만든 표는 내보내지 않는다.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from .branches import Pair
from .errors import BuildError
from .load import Route, read_csv
from .stop_match import lcs_length

# ② 판정 기준. 겹침이 개편 전 정류장 수의 15% 미만이거나 두 방향 차이가 1.3배 미만이면 「약함」
WEAK_RATIO = 0.15
WEAK_MARGIN = 1.3

STAGE_NAME = "기·종점 이름"
STAGE_OVERLAP = "겹침"
STAGE_WEAK = "겹침 약함"
STAGE_TIE = "동률"
MANUAL_STAGES = (STAGE_WEAK, STAGE_TIE)

TABLE_CSV = "기종점정렬표.csv"
TABLE_COLUMNS = ("개편전번호", "개편전방면", "대체노선", "개편후방면", "개편전상행이맞닿는쪽", "확인")
UP, DOWN = "상행", "하행"


@dataclass(frozen=True)
class Alignment:
    """쌍 하나의 방향 결정. `flipped`가 True면 개편 전 상행을 대체 노선의 하행과 맞댄다."""

    stage: str
    flipped: bool | None   # ③ 단계에서 사람이 아직 안 적었으면 None
    same: int              # 상행↔상행 + 하행↔하행 겹침
    reverse: int           # 상행↔하행 + 하행↔상행 겹침
    base: int              # 개편 전 정류장 수(상행 + 하행)


def _facing(before: Route) -> tuple[str, ...]:
    """판정에만 쓰는 개편 전 하행. 순환 노선은 하행이 없으니 상행을 뒤집어 견준다(표에는 채우지 않는다)."""
    return before.down or tuple(reversed(before.up))


def decide(before: Route, after: Route) -> Alignment:
    """쌍 하나의 방향을 ①②로 정해 본다. ③이면 flipped는 None이다."""
    same_ends = (after.origin == before.origin) + (after.terminus == before.terminus)
    flipped_ends = (after.origin == before.terminus) + (after.terminus == before.origin)
    if same_ends or flipped_ends:
        # 개편 전 기점과 종점이 같은 순환 노선은 두 신호가 함께 서므로 「그대로」를 먼저 본다
        return Alignment(STAGE_NAME, flipped=not same_ends, same=0, reverse=0, base=0)

    b_up, b_dn = before.up, _facing(before)
    same = lcs_length(b_up, after.up) + lcs_length(b_dn, after.down)
    reverse = lcs_length(b_up, after.down) + lcs_length(b_dn, after.up)
    hi, lo = max(same, reverse), min(same, reverse)
    base = len(b_up) + len(b_dn)

    if hi == lo:
        return Alignment(STAGE_TIE, None, same, reverse, base)
    if hi / base < WEAK_RATIO or hi < lo * WEAK_MARGIN:
        return Alignment(STAGE_WEAK, None, same, reverse, base)
    return Alignment(STAGE_OVERLAP, flipped=reverse > same, same=same, reverse=reverse, base=base)


def read_table(path: Path) -> dict[tuple[str, str, str, str], bool]:
    """사람이 적은 기·종점 정렬표를 읽어 열쇠 → 뒤집었는지로 만든다. 「확인」 열은 사람 몫이라 읽지 않는다."""
    if not path.exists():
        raise BuildError(f"기·종점 정렬표가 없습니다: {path} (목록은 `python tools/measure_direction.py`가 냅니다)")
    table: dict[tuple[str, str, str, str], bool] = {}
    for row in read_csv(path, TABLE_COLUMNS):
        side = row["개편전상행이맞닿는쪽"].strip()
        if side not in (UP, DOWN):
            raise BuildError(
                f"{path.name}의 「개편전상행이맞닿는쪽」은 「{UP}」 또는 「{DOWN}」이어야 합니다: {side!r}"
            )
        key = (
            row["개편전번호"].strip(),
            row["개편전방면"].strip(),
            row["대체노선"].strip(),
            row["개편후방면"].strip(),
        )
        if key in table:
            raise BuildError(f"{path.name}에 같은 쌍이 두 번 적혀 있습니다: {' / '.join(key)}")
        table[key] = side == DOWN
    return table


def align(
    pairs: list[Pair],
    table: dict[tuple[str, str, str, str], bool],
) -> tuple[dict[tuple[str, str, str, str], Alignment], list[Pair]]:
    """쌍 전부의 방향을 정한다. 돌려주는 둘째 값은 ③인데 정렬표에 행이 없는 쌍들이다."""
    decided: dict[tuple[str, str, str, str], Alignment] = {}
    unwritten: list[Pair] = []
    for pair in pairs:
        found = decide(pair.before, pair.after)
        if found.flipped is None:
            written = table.get(pair.key)
            if written is None:
                unwritten.append(pair)
            else:
                found = Alignment(found.stage, written, found.same, found.reverse, found.base)
        if found.flipped and not pair.after.down:
            # 대체 노선에 하행이 없으면(편도) 뒤집어 맞댈 목록 자체가 없다. 그대로 두면 개편 후 칸이
            # 통째로 비어 그 노선이 아무 데도 안 서는 표가 나온다 — 그런 표는 내보내지 않는다.
            raise BuildError(
                f"{pair.label}: 대체 노선에 하행이 없어 뒤집어 맞댈 수 없습니다."
                f" {TABLE_CSV}의 이 쌍은 「{UP}」이어야 합니다."
            )
        decided[pair.key] = found
    return decided, unwritten
