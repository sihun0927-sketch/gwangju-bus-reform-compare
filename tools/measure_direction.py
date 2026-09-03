"""기·종점 정렬 실측 (ADR-0003 결정 3의 근거).

비교표의 「개편 전 방면 × 대체 노선 × 개편 후 방면」 쌍마다, 개편 전 상행을 대체 노선의 상행과
맞댈지 하행과 맞댈지를 세 단계로 정해 보고 단계별 개수를 센다.

  1) 기·종점 이름이 같거나 서로 바뀌어 있음        → 자동
  2) 정류장 목록 겹침(LCS)이 한쪽으로 뚜렷함        → 자동
  3) 그래도 애매함(겹침 약함·동률)                → data/기종점정렬표.csv 에 사람이 적는다

실행:  python tools/measure_direction.py
입력:  data/source/*.csv (고치지 않는다)
출력:  단계별 개수와 3)에 해당하는 쌍 목록. 값은 docs/architecture.md §6 에 옮긴다.

규칙은 빌드 스크립트(`tools/build`)에서 가져다 쓴다 — 번호 잇기는 `load`, 방면은 `branches`,
세 단계 판정은 `terminus_align`. 실측과 빌드가 같은 코드를 보므로 두 곳의 수치가 어긋나지 않는다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.build import branches, load  # noqa: E402
from tools.build import terminus_align as align  # noqa: E402

SOURCE = Path(__file__).resolve().parent.parent / "data" / "source"

LABELS = {
    align.STAGE_NAME: "1) 기·종점 이름 자동",
    align.STAGE_OVERLAP: "2) 겹침 자동(뚜렷)",
    align.STAGE_WEAK: "3) 겹침 약함",
    align.STAGE_TIE: "3) 동률",
}


def main() -> None:
    before = load.read_before(SOURCE)
    after = load.read_after(SOURCE)
    replacements = load.read_replacements(SOURCE)

    pairs, missing = branches.pairs(before, after, replacements)
    number_pairs = sum(len(r.spelled) for r in replacements)

    counts = dict.fromkeys(LABELS.values(), 0)
    manual: list[str] = []
    for pair in pairs:
        found = align.decide(pair.before, pair.after)
        counts[LABELS[found.stage]] += 1
        if found.stage in align.MANUAL_STAGES:
            line = f"{pair.label}  같은 {found.same} : 반대 {found.reverse}"
            if found.stage == align.STAGE_WEAK:
                line += f"  / 개편 전 정류장 {found.base}"
            manual.append(line)

    print(f"비교표 번호 쌍 {number_pairs} → 방면까지 가른 쌍(표 파일 수) {len(pairs)}")
    for label, value in counts.items():
        print(f"  {label}: {value}")
    print(f"  번호 못 찾음: {len(missing)}")
    print("\n3) 사람이 적을 쌍:")
    for line in manual:
        print("  " + line)
    print("\n번호 못 찾음 (ADR-0006 규칙으로 0이어야 한다):")
    for line in missing:
        print("  " + line)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
