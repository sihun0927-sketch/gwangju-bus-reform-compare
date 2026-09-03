"""5단계 비고 — 표의 여섯째 열 (ADR-0003 결정 5·6).

이번 티켓은 하행이 없는 노선의 한 줄만 붙인다. 명칭 변경·통폐합·이전·신설은 다음 티켓이다.
"""
from __future__ import annotations

from .branches import Pair
from .load import Route

CIRCULAR = "순환 노선 · 하행 없음"
ONE_WAY = "편도 운행 · 하행 없음"


def is_circular(siblings: list[Route]) -> bool:
    """순환인지는 방면이 아니라 번호로 본다.

    상무62(시청경유상무역행)은 종점 표기가 「상무지구종점」이라 기점과 글자가 다르지만, 같은 번호의
    다른 방면이 상무지구 → 상무지구다. 두암81(각화초교.장등마을)도 마찬가지다(장등마을 → 장동마을).
    한 방면이라도 기점과 종점이 같으면 그 번호는 순환 노선이고, 아니면 편도다(지선97(빛그린산단출근)).
    """
    return any(s.origin == s.terminus for s in siblings)


def down_missing(
    pair: Pair,
    before_siblings: list[Route],
    after_siblings: list[Route],
) -> str:
    """하행 칸을 비우는 이유. 하행이 양쪽 다 있으면 빈 문자열이다."""
    texts: list[str] = []
    if not pair.before.down:
        texts.append(CIRCULAR if is_circular(before_siblings) else ONE_WAY)
    if not pair.after.down:
        texts.append(CIRCULAR if is_circular(after_siblings) else ONE_WAY)
    return " · ".join(dict.fromkeys(texts))
