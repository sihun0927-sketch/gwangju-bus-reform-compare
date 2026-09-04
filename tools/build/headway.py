"""개편 후 배차간격 추정 — 발표 수치 넷을 노선 118개에 나눈다 (ADR-0009).

시가 내놓은 것은 총량뿐이다 — 운행횟수 8394 → 9355, 노선 103 → 118, 차량 증차 없음,
평균 통행시간 25.2분 → 20.7분. 노선 하나하나의 배차간격은 공표되지 않았다. 여기서 하는 일은
그 총량을 **개편 전 배차간격 원천**(`route_headways.csv`)과 **노선안의 정류장 목록**에 기대어
노선별로 나누는 것이다.

## 되돌릴 수 있는 변환 하나

배차간격과 운행횟수는 유효 운행시간 `E` 하나로 이어진다.

    운행횟수 = 방향수 × E / 배차간격        배차간격 = 방향수 × E / 운행횟수

`E`는 시간표가 아니라 **보정 상수**다. 공표된 배차간격은 첫차~막차 내내가 아니라 배차가 촘촘한
때의 값이라, 하루를 그 배차로 채웠다 치면 몇 시간어치인지를 8394에서 거꾸로 푼 것이다
(10.1시간쯤 나온다). 그래서 「8394를 재현한다」는 것은 모형이 맞다는 뜻이 아니라 산술이
맞다는 뜻뿐이다 — 모형을 검사하는 것은 아래 `self_consistency`다.

## 수요를 나누는 연산자 둘

개편 후 노선에는 아직 승객이 없다. 그래서 **개편 전의 서비스 수준을 정류장에 실어 두고**
개편 후 노선이 지나가며 물려받게 한다.

- **정류장 승계** — 정류장마다 개편 전에 그곳을 지나던 일 운행횟수를 더해 두고(`V`), 개편 후
  그 정류장을 지나는 노선 수로 나눠 노선을 따라 평균 낸다. 비교표를 안 보므로 **신설 노선
  셋**(간선24 · 지선71 · 지선82, 비교표가 아무 데도 안 적어 둔 것)에도 값이 나온다.
- **비교표 승계** — 비교표가 적어 둔 대체 관계를 따라 개편 전 노선의 운행횟수를 나눠 준다.
  나누는 몫은 정류장 겹침(최장 공통 부분열)이다. 시가 공표한 유일한 대체 관계라 무시하지 않는다.

둘의 기하평균을 중심값으로 쓰고, 둘과 정책 배수를 끈 것까지 **네 갈래**의 최솟값·최댓값을
노선마다 밴드로 싣는다. 밴드는 「모형을 달리 골랐으면 어디까지 갔겠는가」이지 통계적 신뢰구간이
아니다.

## 안 쓰는 수치 하나

발표된 평균 통행시간 25.2분은 **차량 운행시간이 아니다.** 운행횟수로 가중한 평균 편도 노선
길이가 21.2km인데 그것을 25.2분에 달리면 표정속도 50km/h가 되어 시내버스로 불가능하다
(`measure_headway.py`가 잰다). 승객 한 사람의 평균 통행시간으로 읽고, 배차 추정에는 넣지 않는다.
대신 **차량 수지**를 따로 재서 발표 넷이 서로 맞는지 본다 — 증차 없이 9355회를 돌리려면
표정속도가 몇 % 올라야 하는지가 그 답이다.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .errors import BuildError
from .load import Replacement, Route, find_after, read_csv
from .rename_dict import RenameDict
from .route_geometry import chain, metres
from .stop_match import lcs_length

HEADWAY_CSV = "route_headways.csv"
JSON_NAME = "headway.json"
HEADWAY_COLUMNS = ("route_name", "headway_minutes")

# 시가 공표한 총량. 이 넷이 이 모듈의 유일한 외부 수치다
BEFORE_TRIPS = 8394.0     # 개편 전 1일 편도 운행횟수
AFTER_TRIPS = 9355.0      # 개편 후 1일 편도 운행횟수
BEFORE_TRAVEL_MIN = 25.2  # 개편 전 평균 통행시간 — 승객 기준. 배차 추정에 안 쓴다
AFTER_TRAVEL_MIN = 20.7   # 개편 후 평균 통행시간(시청 추정) — 같다

# 배차간격이 넘어설 수 없는 울타리. 개편 전에 **실제로 관측된** 범위다(진월07 5분, 송정99 250분).
# 지어낸 값이 아니라 원천 CSV의 최솟값·최댓값이라, 추정이 관측 밖으로 나가지 않는다는 뜻이다
HEADWAY_FLOOR = 5.0
HEADWAY_CEILING = 250.0

# 「간선 및 급행 기능 강화」를 배차에 옮긴 배수. 시가 비율을 안 밝혔으므로 **가정**이고,
# 밴드가 이것을 끈 갈래를 포함한다 — 이 값 하나로 답이 뒤집히지 않는지 밴드가 보여 준다
POLICY = {"직행": 1.15, "급행": 1.15, "간선": 1.10, "지선": 0.90, "": 1.00}

# 차량 대수로 옮길 때의 가정 둘. 대수 자체보다 **개편 전 대비 비**가 이 모듈의 결론이고,
# 그 비는 두 값에 거의 안 흔들린다(둘 다 전후에 똑같이 걸리므로 약분된다)
CRUISE_KMH = 19.0   # 표정속도 — 정차·신호를 포함한 실제 평균 속도
LAYOVER = 0.15      # 종점 회차 여유. 왕복 주행시간에 이만큼 더한다

# 권고 등급. 유한 집합이고 여기 없는 문자열은 나오지 않는다(G11)
NEEDS_BUSES = "증차 필요"
NEEDS_SHIFT = "재배치 검토"
ADEQUATE = "현행 적정"
HAS_SLACK = "여력 있음"
VERDICTS = (NEEDS_BUSES, NEEDS_SHIFT, ADEQUATE, HAS_SLACK)

# 밴드가 몇 배까지 벌어지면 「이 노선은 모형에 따라 답이 갈린다」고 말할 것인가.
# 이 값이 LLM의 말투를 가른다 — 확신이 낮은 노선은 점 추정 대신 범위로만 답하게 한다
CONFIDENT = 1.5
UNCERTAIN = 3.0
HIGH, MEDIUM, LOW = "높음", "보통", "낮음"
CONFIDENCES = (HIGH, MEDIUM, LOW)

# 등급을 가르는 문턱. 같은 종류의 중앙 배차 대비 몇 배인지와, 회랑 서비스가 망 평균만큼 늘었는지
LONG_RATIO = 1.5      # 이보다 배차가 길면 「길다」
SHORT_RATIO = 0.7     # 이보다 짧으면 「촘촘하다」
CORRIDOR_KEEP = 1.0   # 회랑 서비스가 망 평균만큼 늘었으면 감소가 아니다

DIGITS = 3


@dataclass(frozen=True)
class Estimated:
    """개편 후 노선 하나의 추정. 방면을 합친 번호 단위다(지선97 두 방면이 한 줄)."""

    name: str            # 노선 이름 「간선18」 — 방면을 뗀 번호
    kind: str            # 종류 「간선」. 228·419·518·1187은 빈 문자열
    slots: int           # 방향 칸 수 — 방면마다 상행 1 + 하행 있으면 1. 지선97은 3
    trips: float         # 추정 1일 편도 운행횟수
    headway: float       # 추정 배차간격(분) = slots × E / trips
    low: float           # 밴드 아래 — 네 갈래 중 가장 촘촘한 배차
    high: float          # 밴드 위 — 네 갈래 중 가장 성긴 배차
    length_km: float     # 편도 노선 길이. 방면 여럿이면 평균
    cycle_min: float     # 왕복 운행시간(회차 여유 포함) = 2 × 길이 / 표정속도 × (1+여유)
    buses: float         # 이 배차를 유지하는 데 드는 첨두 차량 = cycle / headway
    fit: float           # 적합 배차간격 — 같은 차량으로 대기시간 총합을 최소화하는 배차(제곱근 법칙)
    fit_buses: float     # 그 배차를 유지하는 데 드는 차량. 지금 대수와의 차이가 곧 옮겨야 할 대수다
    corridor: float      # 회랑 서비스 변화 — 망 전체 증가분(9355/8394)으로 나눈 상대값. 1이면 평균만큼 늘었다
    demand: float        # 정류장 승계 수요 가중치. 등급이 아니라 순위를 볼 때 쓴다
    verdict: str         # 권고 등급 — VERDICTS 중 하나
    kind_median: float   # 같은 종류의 중앙 배차간격. 등급의 분모라 답에 같이 싣는다

    @property
    def confidence(self) -> str:
        """밴드가 좁으면 「높음」. 모형을 달리 골랐을 때 답이 갈리는 노선을 말투로 드러낸다."""
        spread = self.high / self.low if self.low > 0 else float("inf")
        if spread <= CONFIDENT:
            return HIGH
        return MEDIUM if spread <= UNCERTAIN else LOW

    def with_buses(self, extra: int) -> float:
        """차량을 `extra`대 더(또는 빼서) 넣었을 때의 배차간격. 시민이 가장 자주 묻는 값이다."""
        n = self.buses + extra
        return self.cycle_min / n if n > 0 else float("inf")


@dataclass(frozen=True)
class Network:
    """망 전체의 수지. 노선 하나가 아니라 광주 전체를 두고 하는 이야기다."""

    span_min: float          # 유효 운행시간 E(분)
    before_trips: float      # 개편 전 총 운행횟수 — 발표 8394를 되찾는다(항등)
    after_trips: float       # 개편 후 총 운행횟수 — 9355
    before_routes: int       # 103
    after_routes: int        # 118
    before_bus_km: float     # 개편 전 1일 총 주행거리(운행횟수 × 편도 길이)
    after_bus_km: float      # 개편 후 같은 것
    before_buses: float      # 개편 전 첨두 소요 차량(표정속도 가정 아래)
    after_buses: float       # 개편 후 같은 것
    before_headway: float    # 개편 전 노선 배차간격 중앙값
    after_headway: float     # 개편 후 같은 것
    fit_headway: float       # 적합 배차간격 중앙값
    fit_spread: float        # 적합 배차의 최대÷최소. 개편안의 그것보다 좁아야 한다(제곱근 법칙의 예측)
    plan_spread: float       # 개편안 배차의 최대÷최소
    weighted_km: float       # 개편 전 운행횟수 가중 평균 편도 길이 — 25.2분 검증에 쓴다
    self_r: float            # 정류장 승계 연산자의 자기일관성(로그 상관). 모형의 유일한 독립 검사
    variant_gain: tuple[float, ...]  # 네 갈래가 각각 내놓은 필요 표정속도 상승률(%). 폭이 곧 흔들림

    @property
    def demand_ratio(self) -> float:
        """증차 없이 9355회를 돌리는 데 필요한 차량의 배. 1을 넘으면 차량이 모자란다."""
        return self.after_bus_km / self.before_bus_km

    @property
    def speed_gain(self) -> float:
        """그 모자람을 표정속도로 메우려면 몇 % 올라야 하는가. 이 모듈의 결론이다."""
        return (self.demand_ratio - 1.0) * 100.0

    @property
    def claimed_gain(self) -> float:
        """시가 주장한 통행시간 단축을 같은 눈금으로 옮긴 것. `speed_gain`과 견준다."""
        return (BEFORE_TRAVEL_MIN / AFTER_TRAVEL_MIN - 1.0) * 100.0


@dataclass(frozen=True)
class Estimate:
    """`estimate()`의 산출물 전부. 번들과 실측 스크립트가 이것만 본다."""

    network: Network
    routes: tuple[Estimated, ...]         # 개편 후 118개. 이름 차례는 노선안 CSV 차례다
    before_headways: dict[str, float]     # 개편 전 노선 103개의 배차간격(번호 단위) — 역산 검사용
    spare: tuple[str, ...]                # 차량을 내줄 수 있는 노선(등급 「여력 있음」) 이름
    successors: dict[str, tuple[str, ...]]  # 개편 전 번호 → 대체 노선 이름들. 시민은 옛 번호로 묻는다


def read_headways(source: Path) -> dict[str, float]:
    """`route_headways.csv` 120행 → 노선 표기별 배차간격(분).

    이 파일의 표기는 노선안 CSV와 또 다르다 — 순환01은 A·B로 갈라져 있고, 노선안에 없는
    마을버스 7행이 섞여 있다. 잇는 것은 `headway_of`가 하고, 여기서는 읽기만 한다.
    """
    rows = read_csv(source / HEADWAY_CSV, HEADWAY_COLUMNS)
    table: dict[str, float] = {}
    for row in rows:
        name = "".join(row["route_name"].split())
        try:
            value = float(row["headway_minutes"])
        except ValueError:
            raise BuildError(
                f"{HEADWAY_CSV}의 배차간격을 읽을 수 없습니다: {name} {row['headway_minutes']!r}"
            ) from None
        if value <= 0:
            raise BuildError(f"{HEADWAY_CSV}의 배차간격이 0 이하입니다: {name} {value}")
        if name in table:
            raise BuildError(f"{HEADWAY_CSV}에 같은 노선이 두 번 있습니다: {name}")
        table[name] = value
    return table


def headway_of(name: str, table: dict[str, float]) -> float:
    """노선안의 이름 하나 → 배차간격. 없으면 그 이름으로 시작하는 줄들의 평균을 쓴다.

    순환01이 그 경우다 — 노선안은 한 행인데 배차 파일은 「순환01A(…)」「순환01B(…)」 두 행이라
    이름이 그대로는 안 맞는다. 두 방향이 번갈아 오므로 평균이 그 노선의 배차다.
    """
    if name in table:
        return table[name]
    # 뒤에 숫자가 이어지면 다른 노선이다 — 「송정9」가 「송정90」에 붙으면 안 된다.
    # 「순환01」 뒤의 「A(…)」처럼 숫자가 아닌 것이 이어질 때만 같은 노선의 방면으로 본다
    prefixed = [
        v
        for k, v in table.items()
        if k.startswith(name) and not k[len(name) :][:1].isdigit()
    ]
    if not prefixed:
        raise BuildError(
            f"{HEADWAY_CSV}에서 배차간격을 못 찾았습니다: {name}"
            f" (파일에 있는 이름 예: {', '.join(sorted(table)[:3])} …)"
        )
    return sum(prefixed) / len(prefixed)


def _by_number(routes: list[Route]) -> dict[str, list[Route]]:
    """노선안 행들을 번호로 묶는다. 방면이 갈라진 번호는 행이 여럿이다."""
    grouped: dict[str, list[Route]] = {}
    for r in routes:
        grouped.setdefault(r.number, []).append(r)
    return grouped


def _slots(rows: list[Route]) -> int:
    """방향 칸 수 — 방면마다 상행 하나, 하행이 있으면 하나 더. 순환·편도는 하나뿐이다."""
    return sum(2 if r.down else 1 for r in rows)


def _length_km(index, names: tuple[str, ...]) -> float:
    """정류장 이름 차례 → 편도 길이(km). 좌표를 못 이은 정류장은 건너뛰고 앞뒤를 잇는다."""
    points = [p for p in chain(index, names) if p is not None]
    return sum(metres(a, b) for a, b in zip(points, points[1:])) / 1000.0


def _stop_sets(grouped: dict[str, list[Route]], canon) -> dict[str, frozenset[str]]:
    """번호마다 그 노선이 지나는 정류장 이름 집합. 명칭 사전을 거쳐 개편 전후 이름을 맞춘다."""
    return {
        number: frozenset(canon(s) for r in rows for s in (r.up + r.down))
        for number, rows in grouped.items()
    }


def _service(stop_sets: dict[str, frozenset[str]], trips: dict[str, float]) -> dict[str, float]:
    """정류장마다 그곳을 지나는 일 편도 운행횟수의 합. 「이 정류장의 서비스 수준」이다."""
    total: dict[str, float] = defaultdict(float)
    for number, stops in stop_sets.items():
        for stop in stops:
            total[stop] += trips[number]
    return total


def _stop_weights(
    after_sets: dict[str, frozenset[str]], before_service: dict[str, float]
) -> dict[str, float]:
    """정류장 승계 — 개편 전 서비스를 그 정류장을 지나는 개편 후 노선들이 나눠 갖는다.

    노선을 따라 **평균**을 낸다. 합이 아니라 평균인 까닭은, 배차는 노선이 길다고 촘촘해지는 것이
    아니라 지나는 회랑이 붐빌수록 촘촘해지기 때문이다.
    """
    sharing: dict[str, int] = defaultdict(int)
    for stops in after_sets.values():
        for stop in stops:
            sharing[stop] += 1
    weights: dict[str, float] = {}
    for number, stops in after_sets.items():
        shares = [before_service.get(s, 0.0) / sharing[s] for s in sorted(stops)]
        weights[number] = statistics.fmean(shares) if shares else 0.0
    return weights


def _table_weights(
    after: list[Route],
    replacements: list[Replacement],
    before_by_number: dict[str, list[Route]],
    after_by_number: dict[str, list[Route]],
    before_trips: dict[str, float],
    fallback: dict[str, float],
) -> dict[str, float]:
    """비교표 승계 — 개편 전 노선의 운행횟수를 대체 노선들에 정류장 겹침만큼 나눠 준다.

    비교표가 아무 데도 안 적어 둔 개편 후 노선 셋(신설)은 `fallback`(정류장 승계)으로 채운다.
    0으로 두면 배차가 무한대가 되고, 중앙값 같은 것을 넣으면 근거 없는 수를 지어내는 셈이다.
    """
    inherited: dict[str, float] = defaultdict(float)
    for rep in replacements:
        targets: list[str] = []
        for spelled in rep.spelled:
            for route in find_after(after, spelled):
                if route.number not in targets:
                    targets.append(route.number)
        if not targets:
            continue  # 두암181 — 대체 노선이 없다. 그 운행횟수는 어디로도 가지 않는다
        up = before_by_number[rep.before][0].up
        overlap = [
            max(lcs_length(up, r.up) for r in after_by_number[t]) for t in targets
        ]
        if sum(overlap) == 0:
            overlap = [1] * len(targets)
        total = sum(overlap)
        for target, share in zip(targets, overlap):
            inherited[target] += before_trips[rep.before] * share / total
    return {n: (inherited[n] if inherited[n] > 0 else fallback[n]) for n in after_by_number}


def _allocate(
    weights: dict[str, float], slots: dict[str, int], span: float, total: float
) -> dict[str, float]:
    """가중치 → 운행횟수. 합은 정확히 `total`, 배차는 관측 범위 안에 있게 물을 채운다.

    배차의 울타리를 운행횟수의 울타리로 옮겨 놓고, 울타리에 닿은 노선을 고정한 뒤 남은 몫을
    나머지에 다시 비례 배분한다. 고정될 노선이 없어질 때까지 되풀이하므로 합이 안 흐트러진다.
    """
    low = {n: slots[n] * span / HEADWAY_CEILING for n in weights}
    high = {n: slots[n] * span / HEADWAY_FLOOR for n in weights}
    if sum(low.values()) > total or sum(high.values()) < total:
        raise BuildError(
            f"운행횟수 {total:.0f}회를 배차 {HEADWAY_FLOOR:.0f}~{HEADWAY_CEILING:.0f}분 안에서"
            f" 나눌 수 없습니다 (가능 범위 {sum(low.values()):.0f}~{sum(high.values()):.0f})"
        )
    fixed: dict[str, float] = {}
    free = sorted(weights)
    remaining = total
    while True:
        share = sum(weights[n] for n in free)
        if share <= 0:
            # 남은 노선의 가중치가 다 0이면 비례 배분할 수가 없다. 고루 나눠 합만은 지킨다
            for n in free:
                fixed[n] = remaining / len(free)
            break
        pinned = []
        for n in free:
            value = remaining * weights[n] / share
            if value < low[n]:
                pinned.append((n, low[n]))
            elif value > high[n]:
                pinned.append((n, high[n]))
        if not pinned:
            for n in free:
                fixed[n] = remaining * weights[n] / share
            break
        for n, value in pinned:
            fixed[n] = value
            free.remove(n)
            remaining -= value
    return fixed


def _variants(
    stop_w: dict[str, float], table_w: dict[str, float], kinds: dict[str, str]
) -> list[dict[str, float]]:
    """밴드를 만드는 네 갈래. 중심값은 첫째(기하 혼합 · 정책 켬)다.

    갈래를 늘리는 것이 목적이 아니라, **모형을 달리 골랐을 때 답이 어디까지 가는지**를 노선마다
    같이 싣는 것이 목적이다. 정책 배수를 끈 갈래가 들어 있어, 가정 하나로 답이 뒤집히면 밴드가
    그것을 드러낸다.
    """
    def with_policy(w: dict[str, float]) -> dict[str, float]:
        return {n: w[n] * POLICY[kinds[n]] for n in w}

    blend = {n: math.sqrt(stop_w[n] * table_w[n]) for n in stop_w}
    return [with_policy(blend), with_policy(stop_w), with_policy(table_w), blend]


def _log_correlation(xs: list[float], ys: list[float]) -> float:
    """로그를 씌운 피어슨 상관. 운행횟수가 5회부터 400회까지라 눈금을 로그로 봐야 한다."""
    lx = [math.log(v) for v in xs]
    ly = [math.log(v) for v in ys]
    mx, my = statistics.fmean(lx), statistics.fmean(ly)
    cov = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    var = math.sqrt(sum((a - mx) ** 2 for a in lx) * sum((b - my) ** 2 for b in ly))
    return cov / var if var else 0.0


def _fit_headways(
    trips: dict[str, float], cycle: dict[str, float], fleet: float
) -> dict[str, float]:
    """적합 배차간격 — **차량을 하나도 안 늘리고** 대기시간 총합을 가장 줄이는 배차.

    승객이 기다리는 시간의 합 Σ 수요×배차/2를 차량 Σ 왕복시간/배차 = 지금 그대로라는 조건 아래
    최소화하면 **배차 ∝ √(왕복시간 ÷ 수요)** 가 나온다(Mohring 1972의 제곱근 법칙). 뜻은 이렇다 —
    수요가 네 배인 노선의 배차는 1/4이 아니라 **1/2**이어야 한다. 수요에 비례해 배차를 벌리면
    한산한 노선의 승객이 지나치게 오래 기다려 총합이 커진다.

    수요 대리값은 배분된 운행횟수를 쓴다. 승객 수를 아는 자료가 없어서이고, 이 값은 개편 전
    **실측 배차**에서 온 것이라 실제 수요만큼 벌어져 있다(최대÷최소 14배).

    그래서 이 값은 「이 노선의 진짜 적정 배차」가 아니라 **「같은 차량을 다시 나누면 이렇게 된다」**이다.
    지금 대수와 적합 대수의 차이가 곧 다른 노선에서 옮겨 와야 할 대수다.
    """
    scale = sum(math.sqrt(cycle[n] * trips[n]) for n in trips) / fleet
    return {n: scale * math.sqrt(cycle[n] / trips[n]) for n in trips}


def _verdict(headway: float, kind_median: float, corridor: float) -> str:
    """등급 하나. 문턱이 상수라 같은 입력이면 늘 같은 등급이 나온다(G11).

    가르는 축 둘 — 같은 종류 안에서 배차가 성긴가, 그리고 이 노선이 지나는 회랑의 서비스가
    개편 전보다 줄었는가. 줄지 않았는데 배차만 긴 것은 노선이 갈라진 것이므로 증차가 아니라
    재배치 이야기다.
    """
    ratio = headway / kind_median
    if ratio >= LONG_RATIO:
        return NEEDS_BUSES if corridor < CORRIDOR_KEEP else NEEDS_SHIFT
    if ratio < SHORT_RATIO:
        return HAS_SLACK
    return ADEQUATE


def estimate(
    before: list[Route],
    after: list[Route],
    replacements: list[Replacement],
    headways: dict[str, float],
    index,
    renames: RenameDict,
) -> Estimate:
    """노선안 · 비교표 · 배차간격 원천 → 개편 후 노선 118개의 배차간격과 망 전체의 차량 수지.

    같은 입력이면 늘 같은 답이 나온다 — 난수도, 시각도, 집합 순회도 쓰지 않는다. 정류장 집합을
    돌 때는 `sorted`를 거치고, 노선 차례는 노선안 CSV 차례 그대로다.
    """
    before_by_number = _by_number(before)
    after_by_number = _by_number(after)
    before_slots = {n: _slots(rows) for n, rows in before_by_number.items()}
    after_slots = {n: _slots(rows) for n, rows in after_by_number.items()}

    # ① 유효 운행시간 — 발표 8394에서 거꾸로 푼 보정 상수 하나
    per_minute = sum(
        (2 if r.down else 1) / headway_of(r.name, headways) for r in before
    )
    span = BEFORE_TRIPS / per_minute

    before_trips = {
        n: sum((2 if r.down else 1) * span / headway_of(r.name, headways) for r in rows)
        for n, rows in before_by_number.items()
    }
    before_headways = {n: before_slots[n] * span / before_trips[n] for n in before_trips}

    # ② 정류장에 실어 둔 개편 전 서비스
    canon = renames.canon
    before_sets = _stop_sets(before_by_number, canon)
    after_sets = _stop_sets(after_by_number, canon)
    before_service = _service(before_sets, before_trips)

    # ③ 연산자를 개편 전 망에 되먹여 본다 — 8394에 안 맞춘 유일한 독립 검사
    echo = _stop_weights(before_sets, before_service)
    scale = sum(before_trips.values()) / sum(echo.values())
    order = sorted(before_trips)
    self_r = _log_correlation(
        [before_trips[n] for n in order], [max(echo[n] * scale, 1e-9) for n in order]
    )

    # ④ 두 연산자와 네 갈래
    kinds = {n: rows[0].kind for n, rows in after_by_number.items()}
    stop_w = _stop_weights(after_sets, before_service)
    table_w = _table_weights(
        after, replacements, before_by_number, after_by_number, before_trips, stop_w
    )
    spreads = [
        _allocate(w, after_slots, span, AFTER_TRIPS) for w in _variants(stop_w, table_w, kinds)
    ]
    trips = spreads[0]
    band = {
        n: sorted(after_slots[n] * span / s[n] for s in spreads) for n in after_by_number
    }

    # ⑤ 길이와 차량. 대수는 가정 둘에 기대지만 전후 **비**는 그 가정에 거의 안 흔들린다
    lengths_before = {
        n: statistics.fmean([_length_km(index, r.up) for r in rows])
        for n, rows in before_by_number.items()
    }
    lengths_after = {
        n: statistics.fmean([_length_km(index, r.up) for r in rows])
        for n, rows in after_by_number.items()
    }
    cycle = {n: 2 * lengths_after[n] / CRUISE_KMH * 60 * (1 + LAYOVER) for n in lengths_after}

    # ⑥ 회랑 서비스 변화 — 등급을 가르는 둘째 축. 배분에 안 쓴 값이라 순환논법이 아니다
    after_service = _service(after_sets, trips)
    # 망 전체가 이미 11%쯤 늘었으므로 그만큼으로 나눈다 — 「평균만큼 늘었는가」를 묻는 것이지
    # 「늘었는가」를 묻는 것이 아니다. 절대값으로 보면 거의 모든 회랑이 늘어 등급이 무뎌진다
    growth = AFTER_TRIPS / BEFORE_TRIPS
    corridor: dict[str, float] = {}
    for n, stops in after_sets.items():
        pairs = [
            (after_service.get(s, 0.0), before_service.get(s, 0.0)) for s in sorted(stops)
        ]
        known = [(a, b) for a, b in pairs if b > 0]
        corridor[n] = (
            statistics.fmean([a for a, _ in known])
            / statistics.fmean([b for _, b in known])
            / growth
            if known
            else 1.0
        )

    headway = {n: after_slots[n] * span / trips[n] for n in trips}
    medians = {
        k: statistics.median([headway[n] for n in headway if kinds[n] == k])
        for k in sorted(set(kinds.values()))
    }

    # 개편안 배차가 쓰는 차량 총량. 적합 배차는 이 값을 그대로 지켜야 한다(증차 없음)
    fleet = sum(cycle[n] / headway[n] for n in headway)
    fit = _fit_headways(trips, cycle, fleet)

    rows_out: list[Estimated] = []
    seen: set[str] = set()
    for r in after:
        if r.number in seen:
            continue  # 방면 둘째 행 — 번호 단위로 한 줄만 낸다
        seen.add(r.number)
        n = r.number
        rows_out.append(
            Estimated(
                name=n,
                kind=kinds[n],
                slots=after_slots[n],
                trips=round(trips[n], DIGITS),
                headway=round(headway[n], DIGITS),
                low=round(band[n][0], DIGITS),
                high=round(band[n][-1], DIGITS),
                length_km=round(lengths_after[n], DIGITS),
                cycle_min=round(cycle[n], DIGITS),
                buses=round(cycle[n] / headway[n], DIGITS),
                fit=round(fit[n], DIGITS),
                fit_buses=round(cycle[n] / fit[n], DIGITS),
                corridor=round(corridor[n], DIGITS),
                demand=round(stop_w[n], DIGITS),
                verdict=_verdict(headway[n], medians[kinds[n]], corridor[n]),
                kind_median=round(medians[kinds[n]], DIGITS),
            )
        )

    before_km = sum(before_trips[n] * lengths_before[n] for n in before_trips)
    after_km = sum(trips[n] * lengths_after[n] for n in trips)
    network = Network(
        span_min=round(span, DIGITS),
        before_trips=round(sum(before_trips.values()), DIGITS),
        after_trips=round(sum(trips.values()), DIGITS),
        before_routes=len(before_by_number),
        after_routes=len(after_by_number),
        before_bus_km=round(before_km, DIGITS),
        after_bus_km=round(after_km, DIGITS),
        before_buses=round(
            sum(
                2 * lengths_before[n] / CRUISE_KMH * 60 * (1 + LAYOVER) / before_headways[n]
                for n in before_trips
            ),
            DIGITS,
        ),
        after_buses=round(sum(e.buses for e in rows_out), DIGITS),
        before_headway=round(statistics.median(before_headways.values()), DIGITS),
        after_headway=round(statistics.median([e.headway for e in rows_out]), DIGITS),
        fit_headway=round(statistics.median([e.fit for e in rows_out]), DIGITS),
        fit_spread=round(max(fit.values()) / min(fit.values()), DIGITS),
        plan_spread=round(max(headway.values()) / min(headway.values()), DIGITS),
        weighted_km=round(before_km / sum(before_trips.values()), DIGITS),
        self_r=round(self_r, DIGITS),
        variant_gain=tuple(
            round((sum(s[n] * lengths_after[n] for n in s) / before_km - 1.0) * 100.0, DIGITS)
            for s in spreads
        ),
    )
    successors: dict[str, tuple[str, ...]] = {}
    for rep in replacements:
        names: list[str] = []
        for spelled in rep.spelled:
            for route in find_after(after, spelled):
                if route.number not in names:
                    names.append(route.number)
        successors[rep.before] = tuple(names)

    return Estimate(
        network=network,
        routes=tuple(rows_out),
        before_headways={n: round(v, DIGITS) for n, v in before_headways.items()},
        spare=tuple(e.name for e in rows_out if e.verdict == HAS_SLACK),
        successors=successors,
    )


def as_json(result: Estimate) -> dict:
    """Worker가 읽는 모양. 키 이름은 `worker/headway.js`가 읽는 이름과 같아야 한다."""
    n = result.network
    return {
        "망": {
            "유효운행시간": n.span_min,
            "개편전운행횟수": n.before_trips,
            "개편후운행횟수": n.after_trips,
            "개편전노선": n.before_routes,
            "개편후노선": n.after_routes,
            "개편전주행거리": n.before_bus_km,
            "개편후주행거리": n.after_bus_km,
            "개편전차량": n.before_buses,
            "개편후차량": n.after_buses,
            "개편전중앙배차": n.before_headway,
            "개편후중앙배차": n.after_headway,
            "적합중앙배차": n.fit_headway,
            "적합배차편차": n.fit_spread,
            "개편안배차편차": n.plan_spread,
            "차량소요비": round(n.demand_ratio, DIGITS),
            "필요표정속도상승": round(n.speed_gain, DIGITS),
            "발표통행시간단축": round(n.claimed_gain, DIGITS),
            "자기일관성": n.self_r,
            "갈래상승률": list(n.variant_gain),
            "배차하한": HEADWAY_FLOOR,
            "배차상한": HEADWAY_CEILING,
            "표정속도": CRUISE_KMH,
            "회차여유": LAYOVER,
        },
        "노선": {
            e.name: {
                "종류": e.kind,
                "방향칸": e.slots,
                "운행횟수": e.trips,
                "배차간격": e.headway,
                "밴드": [e.low, e.high],
                "노선길이": e.length_km,
                "왕복시간": e.cycle_min,
                "차량": e.buses,
                "적합배차": e.fit,
                "적합차량": e.fit_buses,
                "회랑변화": e.corridor,
                "수요": e.demand,
                "등급": e.verdict,
                "종류중앙배차": e.kind_median,
                "확신": e.confidence,
                "차량더": [
                    round(e.with_buses(k), DIGITS) for k in (1, 2, 3)
                ],
            }
            for e in result.routes
        },
        "개편전": {
            b: {"대체노선": list(a), "배차간격": result.before_headways[b]}
            for b, a in result.successors.items()
        },
        "여력노선": list(result.spare),
        "등급목록": list(VERDICTS),
        "확신목록": list(CONFIDENCES),
    }


def write(path: Path, result: Estimate) -> str:
    """추정 표를 한 줄 JSON으로 쓰고 그 글을 돌려준다. 같은 글이 `out/`에도 그대로 나간다.

    번들(`data.json`)과 따로 두는 까닭은 크기와 쓰임이 다르기 때문이다 — 이것은 100KB가 안 되고,
    주소 하나로 통째로 받아 가는 쪽(LLM 도구)이 있다.
    """
    text = json.dumps(as_json(result), ensure_ascii=False, separators=(",", ":")) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text
