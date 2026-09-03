"""기·종점 정렬 실측 (ADR-0003 결정 3의 근거).

비교표의 「개편 전 노선 ↔ 대체 노선」 쌍마다, 개편 전 상행을 대체 노선의 상행과 맞댈지 하행과
맞댈지를 세 단계로 정해 보고 단계별 개수를 센다.

  1) 기·종점 이름이 같거나 서로 바뀌어 있음        → 자동
  2) 정류장 목록 겹침(LCS)이 한쪽으로 뚜렷함         → 자동
  3) 그래도 애매함(겹침 약함·동률)                 → data/기종점정렬표.csv 에 사람이 적는다

실행:  python tools/measure_direction.py
입력:  data/source/*.csv (고치지 않는다)
출력:  단계별 개수와 3)에 해당하는 쌍 목록. 값은 docs/architecture.md §6 에 옮긴다.

번호를 잇는 규칙은 ADR-0006. 개편 후 노선은 종류+번호(+방면)로 구별하고, 비교표의 숫자만 있는
표기는 급행 아닌 것으로 읽으며, 앞자리 0은 무시한다. 쌍은 「개편 전 방면 × 대체 노선 × 개편 후 방면」
단위로 센다 — 노선 변화 표 파일 하나가 쌍 하나다.
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "data" / "source"

# 2단계 판정 기준. 겹침이 전체의 15% 미만이거나 두 방향의 차이가 1.3배 미만이면 "약함"
WEAK_RATIO = 0.15
WEAK_MARGIN = 1.3

# '지선 97(빛그린산단출근)' → kind=지선 num=97 branch=빛그린산단출근. '228' → kind 없음
ROUTE_RE = re.compile(r"^(?P<kind>[^\d\s(]+)?\s*(?P<num>\d+(?:-\d+)?)\s*(?:\((?P<branch>[^)]*)\))?$")


def load(name: str) -> list[dict[str, str]]:
    with io.open(SOURCE / name, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def split_stops(text: str, sep: str) -> list[str]:
    return [s.strip() for s in text.split(sep) if s.strip()]


def parse(name: str) -> tuple[str, str, str]:
    """노선 표기 → (종류, 번호, 방면). 번호는 앞자리 0을 뗀다('01' → '1'), 방면 없으면 '기본'."""
    m = ROUTE_RE.match(name.strip())
    if not m:
        raise ValueError(name)
    main, _, tail = m.group("num").partition("-")
    num = str(int(main)) + ("-" + tail if tail else "")
    return m.group("kind") or "", num, m.group("branch") or "기본"


def find_after(rows: list[dict[str, str]], spelled: str) -> list[dict[str, str]]:
    """비교표 표기 하나 → 개편 후 행들(방면마다 하나). 종류가 적혀 있으면 그 종류, 없으면 급행 아닌 것."""
    kind, num, _ = parse(spelled)
    hits = [r for r in rows if parse(r["버스번호"])[1] == num]
    if kind:
        hits = [r for r in hits if parse(r["버스번호"])[0] == kind]
    elif len({parse(r["버스번호"])[0] for r in hits}) > 1:
        hits = [r for r in hits if parse(r["버스번호"])[0] != "급행"]
    return hits


def lcs(x: list[str], y: list[str]) -> int:
    """최장 공통 부분열 길이. 순서를 지키며 겹치는 정류장 수."""
    n, m = len(x), len(y)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if x[i] == y[j] else max(dp[i + 1][j], dp[i][j + 1])
    return dp[0][0]


def main() -> None:
    after_rows = load("광주권역 개편후 노선안.csv")
    table = load("노선개편 전후 비교표.csv")

    before: dict[str, list[dict[str, str]]] = {}  # 번호(방면 뗀 것) → 방면 행들
    for r in load("광주권역 개편전 노선안.csv"):
        key = re.sub(r"\(.*\)$", "", re.sub(r"\s+", "", r["버스번호"]))
        before.setdefault(key, []).append(r)

    counts = {"1) 기·종점 이름 자동": 0, "2) 겹침 자동(뚜렷)": 0, "3) 겹침 약함": 0, "3) 동률": 0, "번호 못 찾음": 0}
    manual: list[str] = []
    missing: list[str] = []

    pairs: list[tuple[str, dict[str, str], dict[str, str]]] = []
    number_pairs = 0
    for row in table:
        branches = before.get(re.sub(r"\s+", "", row["기존 노선"]), [])
        for number in split_stops(row["신규(대체) 노선"], ","):
            number_pairs += 1
            hits = find_after(after_rows, number)
            if not branches or not hits:
                counts["번호 못 찾음"] += 1
                missing.append(f"{row['기존 노선']} ↔ {number}")
                continue
            for b in branches:
                for a in hits:
                    pairs.append((f"{b['버스번호']} ↔ {a['버스번호']}", b, a))

    for pair, b, a in pairs:
        bs, be, as_, ae = b["기점"], b["종점"], a["기점"], a["종점"]
        if as_ == bs or ae == be or as_ == be or ae == bs:
            counts["1) 기·종점 이름 자동"] += 1
            continue

        b_up, b_dn = split_stops(b["상행 정류장(순서대로)"], "▶"), split_stops(b["하행 정류장(순서대로)"], "▶")
        a_up, a_dn = split_stops(a["상행 정류장(순서대로)"], ">"), split_stops(a["하행 정류장(순서대로)"], ">")
        if not b_dn:  # 순환(하행 0개)은 상행을 뒤집어 견준다 — 표에 채우는 것이 아니라 판정에만 쓴다
            b_dn = list(reversed(b_up))

        same = lcs(b_up, a_up) + lcs(b_dn, a_dn)
        reverse = lcs(b_up, a_dn) + lcs(b_dn, a_up)
        hi, lo = max(same, reverse), min(same, reverse)
        base = len(b_up) + len(b_dn)

        if hi == lo:
            counts["3) 동률"] += 1
            manual.append(f"{pair}  같은 {same} : 반대 {reverse}")
        elif hi / base < WEAK_RATIO or hi < lo * WEAK_MARGIN:
            counts["3) 겹침 약함"] += 1
            manual.append(f"{pair}  같은 {same} : 반대 {reverse}  / 개편 전 정류장 {base}")
        else:
            counts["2) 겹침 자동(뚜렷)"] += 1

    print(f"비교표 번호 쌍 {number_pairs} → 방면까지 가른 쌍(표 파일 수) {len(pairs)}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print("\n3) 사람이 적을 쌍:")
    for line in manual:
        print("  " + line)
    print("\n번호 못 찾음 (ADR-0006 규칙으로 0이어야 한다):")
    for line in missing:
        print("  " + line)


if __name__ == "__main__":
    main()
