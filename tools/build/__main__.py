"""명령줄 진입점 — `python -m tools.build [source] [out] [bundle]`."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import BuildError, build
from .bundle import DEFAULT_PATH as DEFAULT_BUNDLE
from .shell import KAKAO_JS_KEY_ENV
from .terminus_align import MANUAL_STAGES, STAGE_NAME, STAGE_OVERLAP

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SOURCE = ROOT / "data" / "source"
DEFAULT_OUT = ROOT / "out"


def main(argv: list[str]) -> int:
    if len(argv) > 3:
        print("사용법: python -m tools.build [source] [out] [bundle]", file=sys.stderr)
        return 2
    source = Path(argv[0]) if argv else DEFAULT_SOURCE
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    bundle = Path(argv[2]) if len(argv) > 2 else DEFAULT_BUNDLE
    # Kakao JS 키는 리포에 없다 — Pages 환경 변수로 들어오고 빌드가 껍데기에 박는다(ADR-0005).
    # 없으면 지도만 안 뜨고 나머지는 그대로다. 읽는 곳은 환경 변수 하나뿐이라(`.env` 파일을 읽는
    # 코드는 없다) 로컬에서는 명령 앞에 `KAKAO_JS_KEY=…`를 붙인다
    try:
        result = build(source, out, bundle, kakao_js_key=os.environ.get(KAKAO_JS_KEY_ENV, ""))
    except BuildError as e:
        print(f"빌드를 멈춥니다.\n{e}", file=sys.stderr)
        return 1
    manual = sum(result.stages.get(s, 0) for s in MANUAL_STAGES)
    print(
        f"껍데기 index.html(노선 개편 목록 표 {result.cards}줄)과"
        f" 노선 변화 표 {result.tables}개, 노선 변화 카드 {result.cards}개를"
        f" {result.out}에 썼습니다."
    )
    print(
        f"기·종점 정렬 — ① 기·종점 이름 {result.stages.get(STAGE_NAME, 0)}"
        f" · ② 겹침 {result.stages.get(STAGE_OVERLAP, 0)}"
        f" · ③ 사람이 적음 {manual}"
    )
    번들 = result.bundle_counts
    print(
        f"번들 JSON — 정류장 {번들.stops}줄(추정 좌표 {번들.estimated})"
        f" · 노선 {번들.routes} · 노선별 정류장 {번들.route_stops}줄"
        f" · 환승 쌍 {번들.transfers}줄 · 노선 쌍 환승 지점 {번들.route_links}줄"
        f" · {result.bundle_bytes / 1024 / 1024:.2f}MB를 {result.bundle}에 썼습니다."
    )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
