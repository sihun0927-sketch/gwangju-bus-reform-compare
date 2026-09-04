"""노선 변화 카드 — 번호 하나가 카드 하나다 (⑥, ADR-0002·0006).

비교표 103행이 카드 103개다. 카드는 번호를 확정했을 때 뜨는 영역이고, 그 안의 버튼을 누르면
노선 변화 표 조각 하나가 표 자리에 끼워진다. 카드는 정적 파일이라 버튼이 가리키는 주소를
빌드 때 다 적어 둔다 — 늘 네 단계 `route/{번호}/{개편 전 방면}/{대체 노선}/{개편 후 방면}.html`.

버튼 줄은 셋이고 축이 다르다. 있는 것만 넣는다(CONTEXT 「버튼 줄」).

  개편 전 방면 선택 — 개편 전 방면이 여럿인 6개 번호에만
  대체 노선 선택   — 대체 노선이 있는 모든 카드에
  개편 후 방면 선택 — 방면이 여럿인 대체 노선마다 (지금은 지선97 하나뿐)

**아래 두 줄은 개편 전 방면마다 따로 낸다.** 버튼 하나가 든 주소는 하나뿐인데 표는 축의 곱만큼
있기 때문이다 — 두암81은 버튼이 방면 4 + 대체 2 = 6개인데 표는 4 × 2 = 8개다. 줄을 하나씩만 두면
방면 줄은 첫 대체 노선 열만, 대체 노선 줄은 첫 방면 행만 가리켜 세 칸이 어떤 버튼으로도 안 열린다
(사이트 전체로는 205개 중 9개). 정적 파일이라 클릭한 방면을 기억해 둘 곳이 없으므로, 조합마다
주소를 미리 적어 두는 것으로 채운다. 줄에는 어느 방면의 것인지 적는다.

카드를 열자마자 답이 보이도록 기본 방면 · 첫 대체 노선 · 그 노선의 첫 개편 후 방면의 표를 미리 품는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import BuildError
from .load import Replacement, Route, find_after

BEFORE_BRANCH_PROMPT = "개편 전 방면을 고르세요"
REPLACEMENT_PROMPT = "대체 노선을 고르세요"
AFTER_BRANCH_PROMPT = "개편 후 방면을 고르세요"
# 대체 노선이 하나도 없는 노선에 적는 말. 두암181 하나뿐이다 — 「대체 노선 없음」이라 적으면
# 「대체가 없을 뿐 노선은 남는다」로 읽힌다. 이 노선은 개편 후 노선안에 아예 없다(2026-09-04)
NO_REPLACEMENT = "노선 사라짐"

BEFORE_BRANCH = "before-branch"
REPLACEMENT = "replacement"
AFTER_BRANCH = "after-branch"

Key = tuple[str, str, str, str]


@dataclass(frozen=True)
class Button:
    """버튼 하나 — 적히는 이름과, 눌렀을 때 끼울 노선 변화 표의 열쇠."""

    label: str
    key: Key


@dataclass(frozen=True)
class Choice:
    """버튼 줄 하나. 줄마다 축이 다르므로 합쳐 부르지 않는다."""

    kind: str            # 줄의 축 — 화면에서는 class 이름이 된다
    prompt: str          # 안내문
    of: str              # 이 줄이 딸린 대체 노선 이름. 개편 후 방면 줄에만 있다
    buttons: tuple[Button, ...]


@dataclass(frozen=True)
class Replaced:
    """대체 노선 하나 — 개편 후 번호 하나와 그 방면 행들. 기·종점은 첫 방면의 것."""

    number: str
    routes: tuple[Route, ...]

    @property
    def origin(self) -> str:
        return self.routes[0].origin

    @property
    def terminus(self) -> str:
        return self.routes[0].terminus


@dataclass(frozen=True)
class Card:
    """카드 하나가 아는 것 전부. 대체 노선이 없으면 `replaced`가 비고 `default`가 None이다."""

    before: Route                    # 기본 방면 행 — 제목·기·종점·정류장 수의 출처
    branches: tuple[Route, ...]      # 개편 전 방면 행 전부(CSV 순서)
    replaced: tuple[Replaced, ...]   # 대체 노선(비교표 순서)
    choices: tuple[Choice, ...]
    default: Key | None              # 미리 품는 표


def _replaced(after: list[Route], row: Replacement) -> list[Replaced]:
    """비교표가 적은 표기들 → 대체 노선 목록. 표기 순서를 지키고 같은 번호는 한 번만 담는다."""
    found: dict[str, list[Route]] = {}
    for spelled in row.spelled:
        hits = find_after(after, spelled)
        if not hits:
            # `branches.pairs`가 이미 걸러 빌드를 멈추므로 여기까지 오면 부른 쪽이 잘못이다
            raise BuildError(f"{row.before}의 대체 노선 표기를 못 찾았습니다: {spelled!r}")
        for r in hits:
            rows = found.setdefault(r.number, [])
            if r not in rows:   # 같은 노선을 두 번 적은 행(「18, 간선18」)이 와도 버튼은 하나다
                rows.append(r)
    return [Replaced(number=n, routes=tuple(rs)) for n, rs in found.items()]


def _choices(number: str, branches: list[Route], replaced: list[Replaced]) -> list[Choice]:
    """버튼 줄을 만든다. 고를 것이 하나뿐인 축은 줄 자체를 넣지 않는다."""
    first = replaced[0]
    many = len(branches) > 1
    lines: list[Choice] = []
    if many:
        lines.append(Choice(BEFORE_BRANCH, BEFORE_BRANCH_PROMPT, "", tuple(
            Button(b.branch, (number, b.branch, first.number, first.routes[0].branch))
            for b in branches
        )))
    for b in branches:
        lines.append(Choice(REPLACEMENT, REPLACEMENT_PROMPT, b.branch if many else "", tuple(
            Button(r.number, (number, b.branch, r.number, r.routes[0].branch))
            for r in replaced
        )))
        # 개편 후 방면은 대체 노선마다 다르다. 방면이 하나뿐인 대체 노선에는 줄이 붙지 않는다
        lines += [
            Choice(
                AFTER_BRANCH,
                AFTER_BRANCH_PROMPT,
                f"{b.branch} · {r.number}" if many else r.number,
                tuple(Button(a.branch, (number, b.branch, r.number, a.branch)) for a in r.routes),
            )
            for r in replaced
            if len(r.routes) > 1
        ]
    return lines


def card(row: Replacement, branches: list[Route], after: list[Route]) -> Card:
    """비교표 한 행 → 카드 하나. `branches`는 그 번호의 개편 전 방면 행들(CSV 순서)."""
    if not branches:
        raise BuildError(f"비교표의 번호가 개편 전 노선안에 없습니다: {row.before}")
    replaced = _replaced(after, row)
    if not replaced:
        # 대체 노선이 없는 번호(두암181). 고를 것이 없으니 버튼도 표도 없다
        return Card(branches[0], tuple(branches), (), (), None)
    choices = _choices(row.before, branches, replaced)
    first = replaced[0]
    default = (row.before, branches[0].branch, first.number, first.routes[0].branch)
    return Card(branches[0], tuple(branches), tuple(replaced), tuple(choices), default)
