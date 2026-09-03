"""환승 표 실측 (ADR-0008 결정 1·3의 근거).

번들에 들어가는 표 다섯 가운데 환승에 쓰는 둘 — 환승 도보 안 정류장 쌍(transfers)과 노선 쌍당
최단 환승 지점(route_links) — 이 얼마나 되는지, 그래서 번들 한 장이 몇 MB인지 잰다.
「D1 없이 번들 하나로 간다」는 결정이 이 수치 위에 서 있으므로, 한 번 잰 값을 단정해 쓰지 않고
스크립트를 다시 돌려 확인한다.

실행:  python tools/measure_transfers.py
입력:  data/source/*.csv (고치지 않는다)
출력:  줄 수 · 크기 · 거리 분포. 값은 docs/architecture.md §6 에 옮긴다.

**만드는 규칙은 빌드 스크립트(`tools/build/bundle.py`)에서 가져다 쓴다.** 여기서 따로 세면 실측과
배포본이 조용히 갈린다 — 그래서 이 파일에는 재는 코드만 있고 만드는 코드가 없다.
"""
from __future__ import annotations

import gzip
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.build import bundle as bundle_json  # noqa: E402
from tools.build import load, rename_dict  # noqa: E402

SOURCE = Path(__file__).resolve().parent.parent / "data" / "source"

# 무료 요금제의 번들 상한. wrangler가 재는 것은 **압축 뒤** 크기다(ADR-0008 결정 3)
FREE_PLAN_LIMIT_MB = 3.0


def main() -> None:
    made = bundle_json.make(
        load.read_before(SOURCE),
        load.read_after(SOURCE),
        load.read_stops(SOURCE),
        load.read_name_canon(SOURCE.parent / load.NAME_CANON_JSON),
        rename_dict.from_rows(load.read_renames(SOURCE)),
        load.read_additions(SOURCE),
    )
    counts = made.counts
    data = made.data

    with tempfile.TemporaryDirectory() as 임시:
        자리 = Path(임시) / "data.json"
        크기 = bundle_json.write(자리, made)
        # wrangler가 재는 것은 압축 뒤 크기다. 상한과 견줄 값이라 여기서 같이 잰다
        눌린 = len(gzip.compress(자리.read_bytes(), 9))

    MB = 1024 * 1024
    print(
        f"번들 한 장 압축 전 {크기 / MB:.2f}MB · gzip {눌린 / MB:.2f}MB"
        f" — 무료 요금제 상한 {FREE_PLAN_LIMIT_MB}MB(압축 뒤)의 {눌린 / MB / FREE_PLAN_LIMIT_MB:.0%}"
    )
    print(f"  stops {counts.stops:,}줄 (추정 좌표 {counts.estimated})")
    print(f"  routes {counts.routes} · route_stops {counts.route_stops:,}줄")
    print(f"  transfers {counts.transfers:,}줄 · route_links {counts.route_links:,}줄")

    거리 = sorted(m for _, _, m in data["transfers"])
    print(f"\n환승 도보 상한 {bundle_json.TRANSFER_WALK_M}m")
    print(f"  거리 최소 {거리[0]}m · 중앙값 {거리[len(거리) // 2]}m · 최대 {거리[-1]}m")
    print(f"  0m(좌표가 같은 다른 줄) {sum(1 for m in 거리 if m == 0)}줄")

    노선망 = data["routes"]
    묶음: dict[str, list[int]] = {}
    for a, _b, _here, _there, m in data["route_links"]:
        묶음.setdefault(노선망[a]["network"], []).append(m)
    print("\n노선 쌍당 최단 환승 지점")
    for 이름, 값 in 묶음.items():
        노선_수 = sum(1 for v in 노선망.values() if v["network"] == 이름)
        print(
            f"  {이름}: 노선 {노선_수} → 쌍 {len(값):,}줄"
            f" (가능한 쌍 {노선_수 * (노선_수 - 1) // 2:,}의 {len(값) / (노선_수 * (노선_수 - 1) / 2):.0%})"
            f" · 걸어서 갈아타는 쌍 {sum(1 for m in 값 if m > 0):,}"
        )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
