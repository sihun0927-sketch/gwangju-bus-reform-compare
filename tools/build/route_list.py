"""노선 개편 목록 표 — 첫 화면에 늘 펼쳐진 표 (CONTEXT 「노선 개편 목록 표」).

비교표 103행이 줄 103개다. 줄 하나가 카드 하나(`route/{번호}.html`)를 가리킨다.

대체 노선 이름은 카드가 이미 비교표 표기를 개편 후 노선안에 이어 둔 것을 그대로 쓴다.
목록이 비교표 표기(「1」)를 다시 잇지 않는 것은 목록과 카드가 같은 노선을 다른 이름으로
적는 일을 아예 없애기 위해서다 — 목록은 「간선01」, 카드는 「1」 같은 어긋남이 생기지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .route_card import Card


@dataclass(frozen=True)
class Row:
    """목록 표 한 줄 — 개편 전 번호 하나와 그 대체 노선 이름들. 대체가 없으면 `replaced`가 빈다."""

    number: str
    replaced: tuple[str, ...]


def rows(cards: list[Card]) -> list[Row]:
    """카드들 → 목록 표 줄들. 순서는 비교표 순서 그대로다."""
    return [
        Row(number=card.before.number, replaced=tuple(r.number for r in card.replaced))
        for card in cards
    ]
