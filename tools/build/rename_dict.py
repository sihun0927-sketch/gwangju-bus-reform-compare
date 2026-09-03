"""1단계 명칭 사전 — 「명칭 변경 정류소.csv」로 옛 이름과 새 이름을 잇는다 (ADR-0003 결정 2).

이름이 바뀐 정류장은 같은 정류장이다. 사전을 안 거치면 문흥고가와 문화육교가 두 줄(경유 제외 +
경유 추가)로 갈라져 개편을 실제보다 나쁘게 보여 준다.

CSV는 정류장 ID 단위라 같은 옛 이름이 여러 줄이고, 새 이름이 방향별로 갈라진다
(법원입구 → 광주법원검찰역1번출구 / 2번출구). 노선안 CSV에는 ID가 없어 이름이 유일한 열쇠다.

`stop_match`는 대조 전에 `canon`으로 이름을 옛 이름 쪽에 모은다 — 새 이름 하나에 옛 이름이
하나뿐이라 그 방향이 함수가 된다. 어느 새 이름과 만나도 같은 정류장으로 잡히는 것이 이 때문이다.

`bundle`은 이름 대신 **CSV의 ID**를 쓴다(`new_to_ars`). 옛 이름의 표기가 `stops.csv`와 어긋나는
행이 있고(「도로교통공단.대신파크」 대 「도로교통공단 대신파크」), 무엇보다 옛 이름 하나가 새 이름
둘로 갈릴 때(법원입구 → 1번출구 / 2번출구) 이름으로는 어느 줄이 어느 쪽인지 가릴 수 없다.
ID는 `stops.csv`의 ARS_ID와 102/102로 이어진다(ADR-0007).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .errors import BuildError
from .load import Rename


@dataclass(frozen=True)
class RenameDict:
    """옛 이름 → 새 이름 집합. 대조는 반대 방향(`canon`)을 쓴다."""

    old_to_new: dict[str, frozenset[str]] = field(default_factory=dict)
    new_to_old: dict[str, str] = field(default_factory=dict)
    new_to_ars: dict[str, frozenset[str]] = field(default_factory=dict)

    def canon(self, stop: str) -> str:
        """대조에 쓸 이름. 새 이름이면 옛 이름으로, 아니면 그대로."""
        return self.new_to_old.get(stop, stop)

    def renamed(self, old: str, new: str) -> bool:
        """이 둘이 같은 정류장의 옛 이름과 새 이름인가."""
        return new in self.old_to_new.get(old, ())


def from_rows(rows: list[Rename]) -> RenameDict:
    """CSV 행들 → 명칭 사전. 한 새 이름에 옛 이름이 둘이면 어느 쪽으로 모을지 알 수 없어 멈춘다."""
    old_to_new: dict[str, set[str]] = {}
    new_to_old: dict[str, str] = {}
    new_to_ars: dict[str, set[str]] = {}
    for row in rows:
        if not row.old or not row.new:
            continue
        old_to_new.setdefault(row.old, set()).add(row.new)
        if row.ars_id:
            new_to_ars.setdefault(row.new, set()).add(row.ars_id)
        seen = new_to_old.setdefault(row.new, row.old)
        if seen != row.old:
            raise BuildError(
                f"명칭 변경 CSV에서 새 이름 하나에 옛 이름이 둘입니다: "
                f"{row.new} ← {seen} / {row.old}"
            )
    return RenameDict(
        old_to_new={k: frozenset(v) for k, v in old_to_new.items()},
        new_to_old=new_to_old,
        new_to_ars={k: frozenset(v) for k, v in new_to_ars.items()},
    )
