"""빌드를 멈추는 예외 하나."""
from __future__ import annotations


class BuildError(Exception):
    """입력이 규칙에 안 맞아 빌드를 멈춘다. 조용히 건너뛰지 않는다(ADR-0002)."""
