"""data/back_up/api_stops.json에서 data/source/stops.csv와 data/name_canon.json을 만든다.

    python tools/build_stops.py

- source/stops.csv: API 응답을 그대로, 이름의 앞뒤 공백만 떼서 8열로.
  source/의 다른 CSV 6개와 달리 이 파일만 스크립트가 쓴다 — 원본은 back_up/api_stops.json이다.
- name_canon.json: 노선안 CSV의 정류장 표기 → API 정식 표기 (공백 4건 + 예외 3건)
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLUMNS = ("STATION_NUM", "BUSSTOP_NAME", "ARS_ID", "NEXT_BUSSTOP",
           "BUSSTOP_ID", "LONGITUDE", "NAME_E", "LATITUDE")

# 공백 규칙으로 안 붙는 것. 값이 None이면 API에 없는 정류장(좌표 없음).
EXCEPTIONS = {
    "압촌마을종점": "압촌마을",                                  # 종점 접미
    "절골입구": "절골입구(북)",                                  # (북)·(서) 약 40m — (북)을 쓴다
    "살레시오살레시오고/교통문화연수원": "살레시오고/교통문화연수원",   # 노선안 오타
    "광주교대역2번출구": None,                                   # 2호선 신설. API에 없다
}

norm = lambda s: re.sub(r"\s+", "", s)


def stations() -> list[dict]:
    raw = json.loads((ROOT / "data" / "back_up" / "api_stops.json").read_text(encoding="utf-8"))
    out = []
    for x in raw["STATION_LIST"]:
        x = dict(x)
        for k in ("BUSSTOP_NAME", "NEXT_BUSSTOP", "NAME_E"):
            if isinstance(x.get(k), str):
                x[k] = x[k].strip()
        out.append(x)
    return out


def route_stops(fname: str, sep: str) -> set[str]:
    out = set()
    with open(ROOT / "data" / "source" / fname, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            for v in row.values():
                if v and sep in v:
                    out |= {s.strip() for s in v.split(sep) if s.strip()}
    return out


def main() -> None:
    S = stations()

    dst = ROOT / "data" / "source" / "stops.csv"
    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(S)
    print(f"{dst.name}: {len(S)}행")

    names = {x["BUSSTOP_NAME"] for x in S}
    groups = defaultdict(set)
    for n in names:
        groups[norm(n)].add(n)
    canon = {k: min(v, key=lambda s: (len(s), s)) for k, v in groups.items()}

    used = route_stops("광주권역 개편전 노선안.csv", "▶") | route_stops("광주권역 개편후 노선안.csv", ">")
    fix = {s: canon[norm(s)] for s in used if norm(s) in canon and canon[norm(s)] != s}
    fix.update(EXCEPTIONS)

    out = ROOT / "data" / "name_canon.json"
    out.write_text(json.dumps(fix, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{out.name}: {len(fix)}개 (공백 {len(fix) - len(EXCEPTIONS)} + 예외 {len(EXCEPTIONS)})")

    resolve = lambda s: fix.get(s, s) if fix.get(s, s) is not None else None
    for lbl, fn, sep in (("개편전", "광주권역 개편전 노선안.csv", "▶"),
                         ("개편후", "광주권역 개편후 노선안.csv", ">")):
        st = route_stops(fn, sep)
        hit = sum(1 for s in st if (r := resolve(s)) is not None and r in names)
        print(f"  {lbl} {len(st)}개 — 매칭 {hit} ({hit / len(st):.1%})")


if __name__ == "__main__":
    main()
