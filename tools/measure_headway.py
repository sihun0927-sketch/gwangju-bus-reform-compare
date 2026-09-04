"""실측 — 개편 후 배차간격 추정과 차량 수지 (architecture §6-4, ADR-0010).

    python tools/measure_headway.py            # 수치를 다 찍는다. 문서 §6-4가 이 출력이다
    python tools/measure_headway.py --gate G7  # 게이트 하나만. 통과하면 표식 한 줄, 아니면 0이 아닌 값

빌드를 안 거치고 `data/source`를 곧장 읽는다 — 이 수치는 산출물이 아니라 입력에서 나오는 것이라
`out/`이 없어도 잰다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.build import bundle, headway as hw, load, rename_dict  # noqa: E402

SOURCE = ROOT / "data" / "source"
ARCH = ROOT / "docs" / "architecture.md"
ADR = ROOT / "docs" / "adr" / "0010-headway-estimate.md"
ADR_INFER = ROOT / "docs" / "adr" / "0011-headway-inference.md"
CONTEXT = ROOT / "CONTEXT.md"
DATA_README = ROOT / "data" / "README.md"

# 게이트 문턱. 모형을 고치면 여기가 아니라 모형이 바뀌어야 한다
SELF_R_MIN = 0.80          # G4 자기일관성 로그 상관
VARIANT_SPREAD_MAX = 3.0   # G7 갈래 넷의 상승률 폭(%p)
IMPOSSIBLE_KMH = 40.0      # G8 시내버스로 불가능하다고 볼 표정속도


def load_all() -> tuple[hw.Estimate, dict[str, float]]:
    before = load.read_before(SOURCE)
    after = load.read_after(SOURCE)
    replacements = load.read_replacements(SOURCE)
    stops = load.read_stops(SOURCE)
    canon = load.read_name_canon(SOURCE.parent / load.NAME_CANON_JSON)
    renames = rename_dict.from_rows(load.read_renames(SOURCE))
    index = bundle.stop_index(stops, canon, renames)
    headways = hw.read_headways(SOURCE)
    return hw.estimate(before, after, replacements, headways, index, renames), headways


def report(result: hw.Estimate, headways: dict[str, float]) -> None:
    """문서 §6-4에 그대로 옮기는 출력. 사람이 읽는 쪽이라 표식은 안 찍는다."""
    n = result.network
    heads = sorted(e.headway for e in result.routes)
    print(f"원천 배차간격 {len(headways)}행 · 개편 전 노선 {n.before_routes} · 개편 후 노선 {n.after_routes}")
    print(f"유효 운행시간 E = {n.span_min:.1f}분 ({n.span_min / 60:.2f}시간)")
    print(f"운행횟수 {n.before_trips:.0f} → {n.after_trips:.0f}회")
    print(f"노선 중앙 배차 {n.before_headway:.1f} → {n.after_headway:.1f}분")
    print(f"개편 후 배차 범위 {heads[0]:.1f} ~ {heads[-1]:.1f}분 (개편 전 관측 {hw.HEADWAY_FLOOR:.0f}~{hw.HEADWAY_CEILING:.0f}분)")
    print(f"정류장 승계 연산자 자기일관성 로그 상관 r = {n.self_r:.3f}")
    print(f"주행거리 {n.before_bus_km:,.0f} → {n.after_bus_km:,.0f} bus-km/일 (비 {n.demand_ratio:.4f})")
    print(f"증차 없이 필요한 표정속도 상승 {n.speed_gain:.1f}%  ·  갈래 넷 {min(n.variant_gain):.1f}~{max(n.variant_gain):.1f}%")
    print(f"시가 발표한 통행시간 단축을 같은 눈금으로 옮기면 {n.claimed_gain:.1f}%")
    print(f"첨두 소요 차량 {n.before_buses:.0f} → {n.after_buses:.0f}대 (표정속도 {hw.CRUISE_KMH}km/h · 회차여유 {hw.LAYOVER:.0%} 가정)")
    print(f"운행횟수 가중 평균 편도 {n.weighted_km:.2f}km ÷ 발표 {hw.BEFORE_TRAVEL_MIN}분 = {n.weighted_km / (hw.BEFORE_TRAVEL_MIN / 60):.1f}km/h")
    print("종류별 배차간격(분) — 개수 · 중앙 · 최소 · 최대")
    for kind in ("직행", "급행", "간선", "지선", ""):
        rows = [e for e in result.routes if e.kind == kind]
        if not rows:
            continue
        hs = sorted(e.headway for e in rows)
        print(f"  {kind or '번호만':4s} {len(rows):3d}개  중앙 {hs[len(hs) // 2]:6.1f}  {hs[0]:6.1f} ~ {hs[-1]:6.1f}")
    print(
        f"적합 배차간격(제곱근 법칙, 차량 총량 고정) 중앙 {n.fit_headway:.1f}분"
        f"  ·  배차 편차 개편안 {n.plan_spread:.1f}배 → 적합 {n.fit_spread:.1f}배"
    )
    print("등급 — 개수")
    for verdict in hw.VERDICTS:
        print(f"  {verdict:8s} {sum(1 for e in result.routes if e.verdict == verdict):3d}개")


# ── 게이트 ────────────────────────────────────────────────────────────────────
# 게이트 하나가 함수 하나다. 통과하면 아무것도 안 내고, 어긋나면 까닭을 문자열로 돌려준다


def g1(result: hw.Estimate, headways: dict[str, float]) -> str:
    rows = load.read_csv(SOURCE / hw.HEADWAY_CSV, hw.HEADWAY_COLUMNS)
    if len(rows) != 120:
        return f"{hw.HEADWAY_CSV}가 120행이 아닙니다: {len(rows)}행"
    if len(headways) != 120:
        return f"읽은 노선이 120개가 아닙니다: {len(headways)}개"
    return ""


def g2(result: hw.Estimate, headways: dict[str, float]) -> str:
    """운행횟수 → 배차간격 변환이 가역인가. 방면이 하나인 노선은 원천 값과 똑같아야 한다."""
    before = load.read_before(SOURCE)
    singles = [r for r in before if sum(1 for x in before if x.number == r.number) == 1]
    if len(singles) < 90:
        return f"방면이 하나인 노선이 너무 적습니다: {len(singles)}개"
    worst, where = 0.0, ""
    for r in singles:
        gap = abs(result.before_headways[r.number] - hw.headway_of(r.name, headways))
        if gap > worst:
            worst, where = gap, r.name
    if worst > 1e-3:
        return f"역산 오차가 큽니다: {where} {worst:.6f}분"
    return ""


def g3(result: hw.Estimate, headways: dict[str, float]) -> str:
    gap = abs(result.network.before_trips - hw.BEFORE_TRIPS)
    if gap > 1e-3:
        return f"개편 전 운행횟수가 {hw.BEFORE_TRIPS:.0f}이 아닙니다: {result.network.before_trips} (차 {gap})"
    return ""


def g4(result: hw.Estimate, headways: dict[str, float]) -> str:
    r = result.network.self_r
    if r < SELF_R_MIN:
        return f"정류장 승계 연산자의 자기일관성이 낮습니다: 로그 상관 {r:.3f} < {SELF_R_MIN}"
    return ""


def g5(result: hw.Estimate, headways: dict[str, float]) -> str:
    routes = result.routes
    if len(routes) != 118:
        return f"개편 후 노선이 118개가 아닙니다: {len(routes)}개"
    if len({e.name for e in routes}) != 118:
        return "노선 이름이 겹칩니다"
    blank = [e.name for e in routes if not (e.headway > 0) or not (e.trips > 0)]
    if blank:
        return f"배차간격이 없는 노선: {', '.join(blank)}"
    gap = abs(result.network.after_trips - hw.AFTER_TRIPS)
    if gap > 1e-3:
        return f"개편 후 운행횟수가 {hw.AFTER_TRIPS:.0f}이 아닙니다: {result.network.after_trips} (차 {gap})"
    return ""


def g6(result: hw.Estimate, headways: dict[str, float]) -> str:
    out = [
        f"{e.name} {e.headway:.1f}분"
        for e in result.routes
        if e.headway < hw.HEADWAY_FLOOR - 1e-6 or e.headway > hw.HEADWAY_CEILING + 1e-6
    ]
    if out:
        return f"관측 범위 {hw.HEADWAY_FLOOR:.0f}~{hw.HEADWAY_CEILING:.0f}분을 벗어난 노선: {', '.join(out)}"
    observed = sorted(headways.values())
    if observed[0] != hw.HEADWAY_FLOOR or observed[-1] != hw.HEADWAY_CEILING:
        return (
            f"울타리가 원천의 관측 범위와 다릅니다: 원천 {observed[0]:.0f}~{observed[-1]:.0f}분,"
            f" 울타리 {hw.HEADWAY_FLOOR:.0f}~{hw.HEADWAY_CEILING:.0f}분"
        )
    return ""


def g7(result: hw.Estimate, headways: dict[str, float]) -> str:
    gains = result.network.variant_gain
    spread = max(gains) - min(gains)
    if spread > VARIANT_SPREAD_MAX:
        return f"갈래마다 결론이 다릅니다: 상승률 {min(gains):.1f}~{max(gains):.1f}% (폭 {spread:.1f}%p)"
    if result.network.speed_gain <= 0:
        return f"차량 수지가 남습니다: 상승률 {result.network.speed_gain:.1f}% — 증차 이야기가 성립하지 않습니다"
    return ""


def g8(result: hw.Estimate, headways: dict[str, float]) -> str:
    implied = result.network.weighted_km / (hw.BEFORE_TRAVEL_MIN / 60)
    if implied <= IMPOSSIBLE_KMH:
        return (
            f"발표 통행시간 {hw.BEFORE_TRAVEL_MIN}분이 차량 운행시간일 수도 있습니다:"
            f" 그때 표정속도 {implied:.1f}km/h ≤ {IMPOSSIBLE_KMH:.0f}km/h"
        )
    return ""


def g18(result: hw.Estimate, headways: dict[str, float]) -> str:
    """적합 배차가 다 있고, 그 배차가 쓰는 차량이 개편안과 같은가 — 증차 없이 다시 나눈 것이다."""
    빈칸 = [e.name for e in result.routes if not e.fit > 0 or not e.fit_buses > 0]
    if 빈칸:
        return f"적합 배차간격이 없는 노선: {', '.join(빈칸)}"
    지금 = sum(e.buses for e in result.routes)
    적합 = sum(e.fit_buses for e in result.routes)
    if abs(지금 - 적합) > 0.5:
        return f"적합 배차가 차량을 더(또는 덜) 씁니다: 개편안 {지금:.1f}대 → 적합 {적합:.1f}대"
    밖 = [
        f"{e.name} {e.fit:.1f}분"
        for e in result.routes
        if e.fit < hw.HEADWAY_FLOOR - 1e-6 or e.fit > hw.HEADWAY_CEILING + 1e-6
    ]
    if 밖:
        return f"적합 배차가 관측 범위 밖입니다: {', '.join(밖)}"
    return ""


def g19(result: hw.Estimate, headways: dict[str, float]) -> str:
    """제곱근 법칙은 배차 편차가 **좁아진다**고 예측한다. 그 예측이 실제로 나오는지 본다.

    수요에 비례해 배차를 벌리는 대신 √수요만큼만 벌리는 것이 대기시간 총합을 줄이므로,
    적합 배차의 최대÷최소는 개편안의 그것보다 작아야 한다. 안 그러면 셈이 어딘가 틀렸다.
    """
    n = result.network
    if n.fit_spread >= n.plan_spread:
        return (
            f"적합 배차의 편차가 안 좁아졌습니다: 개편안 {n.plan_spread:.1f}배 →"
            f" 적합 {n.fit_spread:.1f}배 (제곱근 법칙의 예측과 어긋납니다)"
        )
    if n.fit_spread < 1.5:
        return f"적합 배차가 지나치게 고릅니다: 편차 {n.fit_spread:.1f}배 — 수요 차이가 사라졌습니다"
    return ""


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def g16(result: hw.Estimate, headways: dict[str, float]) -> str:
    """문서에 적은 수치가 지금 계산한 값과 같은가. 문서가 코드보다 낡는 것을 잡는다.

    문서마다 말하는 것이 달라 대조할 수치도 다르다 — 추정 모형은 ADR-0010, 추론 층은 ADR-0011,
    실측 절(`architecture` §6-4)은 둘 다다.
    """
    n = result.network
    추정 = {
        "유효 운행시간": f"{n.span_min:.1f}",
        "개편 후 노선 수": f"{n.after_routes}",
        "개편 후 중앙 배차": f"{n.after_headway:.1f}",
        "자기일관성": f"{n.self_r:.3f}",
        "차량 소요 비": f"{n.demand_ratio:.4f}",
        "필요 표정속도 상승": f"{n.speed_gain:.1f}",
        "가중 평균 편도": f"{n.weighted_km:.2f}",
    }
    추론 = {
        "개편안 배차 편차": f"{n.plan_spread:.1f}",
        "적합 배차 편차": f"{n.fit_spread:.1f}",
    }
    문서 = {ARCH: {**추정, **추론, "적합 중앙 배차": f"{n.fit_headway:.1f}"},
            ADR: 추정, ADR_INFER: 추론}
    missing = []
    for path, facts in 문서.items():
        if not path.exists():
            return f"문서가 없습니다: {path.relative_to(ROOT)}"
        found = _numbers(path.read_text(encoding="utf-8"))
        missing += [f"{path.name}:{k}={v}" for k, v in facts.items() if v not in found]
    if missing:
        return "문서에 없는(또는 낡은) 수치: " + ", ".join(missing)
    return ""


def g17(result: hw.Estimate, headways: dict[str, float]) -> str:
    context = CONTEXT.read_text(encoding="utf-8")
    terms = [t for t in ("**배차간격", "**운행횟수", "**유효 운행시간") if t not in context]
    if terms:
        return "CONTEXT에 없는 용어: " + ", ".join(t.strip("*") for t in terms)
    if hw.HEADWAY_CSV not in DATA_README.read_text(encoding="utf-8"):
        return f"data/README.md의 원천 표에 {hw.HEADWAY_CSV} 줄이 없습니다"
    return ""


GATES = {"G1": g1, "G2": g2, "G3": g3, "G4": g4, "G5": g5, "G6": g6, "G7": g7, "G8": g8,
         "G16": g16, "G17": g17, "G18": g18, "G19": g19}


def main(argv: list[str]) -> int:
    gate = ""
    if argv:
        if len(argv) != 2 or argv[0] != "--gate" or argv[1] not in GATES:
            print(f"사용법: python tools/measure_headway.py [--gate {'|'.join(GATES)}]", file=sys.stderr)
            return 2
        gate = argv[1]
    result, headways = load_all()
    if not gate:
        report(result, headways)
        return 0
    reason = GATES[gate](result, headways)
    if reason:
        print(f"{gate} 어긋남 — {reason}", file=sys.stderr)
        return 1
    print(f"GATE-{gate} OK")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
