"""명령줄 진입점 — `python -m tools.build [source] [out]`."""
from __future__ import annotations

import sys
from pathlib import Path

from . import BuildError, build
from .terminus_align import MANUAL_STAGES, STAGE_NAME, STAGE_OVERLAP

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SOURCE = ROOT / "data" / "source"
DEFAULT_OUT = ROOT / "out"


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("사용법: python -m tools.build [source] [out]", file=sys.stderr)
        return 2
    source = Path(argv[0]) if argv else DEFAULT_SOURCE
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    try:
        result = build(source, out)
    except BuildError as e:
        print(f"빌드를 멈춥니다.\n{e}", file=sys.stderr)
        return 1
    manual = sum(result.stages.get(s, 0) for s in MANUAL_STAGES)
    print(f"노선 변화 표 {result.tables}개를 {result.out}에 썼습니다.")
    print(
        f"기·종점 정렬 — ① 기·종점 이름 {result.stages.get(STAGE_NAME, 0)}"
        f" · ② 겹침 {result.stages.get(STAGE_OVERLAP, 0)}"
        f" · ③ 사람이 적음 {manual}"
    )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
