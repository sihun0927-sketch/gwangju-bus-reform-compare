"""번들 만들기의 바깥만 검사한다 — 진짜 CSV로 한 번 돌린 `worker/data.json`의 내용.

이음새는 `build(source, out, bundle)` 하나다(스펙의 이음새 ①). 모듈 안의 함수 모양은 이 파일이 모른다.
보는 것은 번들의 **사실**이다 — 줄 수, 어떤 정류장이 몇 줄에 붙었는지, 좌표 범위.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.build import BuildError, build
from tools.build.bundle import TRANSFER_WALK_M

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE = DATA / "source"

# Worker 무료 요금제의 번들 상한. wrangler가 재는 것은 압축 뒤 크기다(ADR-0008 결정 3)
FREE_PLAN_LIMIT = 3 * 1024 * 1024


@pytest.fixture(scope="session")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """진짜 CSV로 한 번만 빌드하고 모든 검사가 그 번들을 나눠 쓴다."""
    자리 = tmp_path_factory.mktemp("bundle")
    build(SOURCE, 자리 / "out", 자리 / "data.json")
    return json.loads((자리 / "data.json").read_text(encoding="utf-8"))


def run_cli(data: Path, out: Path, bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.build", str(data / "source"), str(out), str(bundle)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def 이름_하나를_없는_것으로(data: Path) -> None:
    """개편 후 노선안의 정류장 하나를 stops.csv에도 신설 CSV에도 없는 이름으로 바꾼다."""
    노선안 = data / "source" / "광주권역 개편후 노선안.csv"
    바뀐 = 노선안.read_text(encoding="utf-8-sig").replace("> 문화육교 >", "> 없는정류장 >", 1)
    assert "없는정류장" in 바뀐
    노선안.write_text(바뀐, encoding="utf-8-sig")


def route_stops(bundle: dict, route: str) -> list[dict]:
    """노선 하나의 상행·하행 정류장을 순서대로 이어 붙인 것."""
    묶음 = bundle["route_stops"][route]
    return [*묶음["up"], *묶음["down"]]


def test_명령_하나로_정적_조각과_번들_JSON이_함께_생긴다(tmp_path: Path) -> None:
    out, 번들 = tmp_path / "out", tmp_path / "worker" / "data.json"
    build(SOURCE, out, 번들)
    assert (out / "index.html").exists()
    assert len(list(out.glob("route/*/*/*/*.html"))) == 205
    assert 번들.exists()


def test_명령줄로도_번들_자리를_줄_수_있다(tmp_path: Path) -> None:
    번들 = tmp_path / "data.json"
    끝 = run_cli(DATA, tmp_path / "out", 번들)
    assert 끝.returncode == 0, 끝.stderr
    assert 번들.exists()
    assert "번들 JSON" in 끝.stdout


def test_routes가_111더하기_119이고_노선망_표시가_있다(bundle: dict) -> None:
    노선 = bundle["routes"]
    assert len(노선) == 230
    assert sum(1 for v in 노선.values() if v["network"] == "before") == 111
    assert sum(1 for v in 노선.values() if v["network"] == "after") == 119
    assert 노선["before:문흥18"]["name"] == "문흥18"
    assert 노선["after:간선18"]["name"] == "간선18"


def test_배차간격은_개편_전에만_붙는다(bundle: dict) -> None:
    """시가 공표한 값이 개편 전에만 있다. 빈칸을 화면이 「정보 없음」으로 읽는다(CONTEXT 「경로 줄」)."""
    노선 = bundle["routes"]
    붙은_것 = {k: v["headway"] for k, v in 노선.items() if v["headway"] is not None}
    assert len(붙은_것) == 110, "배차 CSV 110행"
    assert all(k.startswith("before:") for k in 붙은_것), "개편 후에는 붙지 않는다"
    assert all(isinstance(v, int) and v > 0 for v in 붙은_것.values()), "분 단위 숫자다"

    # 이름이 두 노선망에 다 있는 노선. 노선망을 안 가리고 이름으로 찾으면 개편 후가 개편 전 값을 문다
    assert 노선["before:228(구151.화순사평)"]["headway"] is not None
    assert 노선["after:228"]["headway"] is None
    # 개편 전 111행 중 순환01 한 행만 배차 CSV에 없다
    assert 노선["before:순환01"]["headway"] is None
    assert 노선["before:좌석02"]["headway"] == 7


def test_문흥18의_같은_이름이_STATION_NUM_둘로_붙는다(bundle: dict) -> None:
    """정류장의 정체성은 `stops.csv`의 줄이다(ADR-0008 결정 2) — 길 양쪽을 따로 다룬다."""
    줄 = route_stops(bundle, "before:문흥18")
    장등동 = next(x for x in 줄 if x["name"] == "장등동")
    assert len(장등동["stops"]) == 2
    assert len({tuple(x["stops"]) for x in 줄 if len(x["stops"]) == 2}) > 20


def test_노선안_이름은_그_이름의_줄_전부에_붙는다(bundle: dict) -> None:
    """개편 전 이름은 명칭 변경도 신설도 없다 — 붙은 줄이 전부 그 이름이라야 한다."""
    정류장 = bundle["stops"]
    이름별_줄 = {}
    for i, v in 정류장.items():
        이름별_줄.setdefault(v["name"], set()).add(i)
    for x in route_stops(bundle, "before:문흥18"):
        assert {정류장[i]["name"] for i in x["stops"]} == {x["name"]}
        assert set(x["stops"]) == 이름별_줄[x["name"]]


def test_개편_후_문화육교는_개편_전_문흥고가의_STATION_NUM에_붙는다(bundle: dict) -> None:
    """이름이 바뀐 정류장은 같은 정류장이다. 안 이으면 개편 후 그 자리에 정류장이 없는 것이 된다."""
    문흥고가 = [i for i, v in bundle["stops"].items() if v["name"] == "문흥고가"]
    assert len(문흥고가) == 2
    문화육교 = next(x for x in route_stops(bundle, "after:간선18") if x["name"] == "문화육교")
    assert 문화육교["stops"] == 문흥고가


def test_옛_이름_하나가_새_이름_둘로_갈리면_줄도_갈린다(bundle: dict) -> None:
    """법원입구(ARS 1056·1057) → 1번출구 / 2번출구. 이름으로 이으면 둘 다 두 줄이 붙는다."""
    이름 = {}
    for 노선 in bundle["route_stops"]:
        for x in route_stops(bundle, 노선):
            if x["name"].startswith("광주법원검찰역"):
                이름[x["name"]] = tuple(x["stops"])
    assert len(이름) == 2
    assert all(len(v) == 1 for v in 이름.values()), 이름
    assert len(set(이름.values())) == 2


def test_추정_좌표_플래그가_켜진_정류장이_57개다(bundle: dict) -> None:
    """신설 56 + 광주교대역2번출구. 좌표를 지어내지 않되 경로에서 빠뜨리지도 않는다(ADR-0007 개정)."""
    추정 = {i: v for i, v in bundle["stops"].items() if v["estimated"]}
    assert len(추정) == 57
    assert "광주교대역2번출구" in {v["name"] for v in 추정.values()}


def test_추정_좌표는_어느_노선에선가_앞뒤_정류장_사이에_있다(bundle: dict) -> None:
    """중점이라면 그 값을 준 노선에서는 앞뒤 정류장 사이에 든다.

    다른 노선에서까지 사이에 들 이유는 없다 — 같은 정류장을 여러 노선이 다른 차례로 지난다.
    이웃이 저도 추정 좌표일 수 있다(신설 정류장이 잇달아 놓인 자리). 그때는 앞 바퀴에서 확정된
    값이라 여전히 사이에 든다. 엉뚱한 좌표가 들어오면 어느 노선에서도 사이에 못 든다.
    """
    정류장 = bundle["stops"]

    def 한가운데(줄들: list[str]) -> tuple[float, float]:
        return (sum(정류장[i]["lat"] for i in 줄들) / len(줄들),
                sum(정류장[i]["lng"] for i in 줄들) / len(줄들))

    사이에_든_적 = {i for i, v in 정류장.items() if v["estimated"]}
    assert len(사이에_든_적) == 57
    남은 = set(사이에_든_적)
    여유 = 1e-6   # 소수 8자리로 끊은 만큼
    for 묶음 in bundle["route_stops"].values():
        for 차례 in 묶음.values():
            for i, x in enumerate(차례):
                줄 = x["stops"][0]
                if 줄 not in 남은:
                    continue
                이웃 = [한가운데(차례[j]["stops"])
                       for j in (i - 1, i + 1) if 0 <= j < len(차례)]
                if not 이웃:
                    continue
                안에 = (
                    min(c[0] for c in 이웃) - 여유 <= 정류장[줄]["lat"]
                    <= max(c[0] for c in 이웃) + 여유
                    and min(c[1] for c in 이웃) - 여유 <= 정류장[줄]["lng"]
                    <= max(c[1] for c in 이웃) + 여유
                )
                if 안에:
                    남은.discard(줄)
    assert 남은 == set()


def test_stops_csv는_빌드_전후_같다(tmp_path: Path) -> None:
    """추정 좌표는 번들에만 넣는다. 좌표의 유일한 출처는 사람이 받아 커밋한 파일이다(ADR-0007)."""
    원본 = (SOURCE / "stops.csv").read_bytes()
    build(SOURCE, tmp_path / "out", tmp_path / "data.json")
    assert hashlib.sha256((SOURCE / "stops.csv").read_bytes()).hexdigest() == \
        hashlib.sha256(원본).hexdigest()


def test_bbox가_노선안_정류장_좌표_범위와_같다(bundle: dict) -> None:
    쓰인_줄 = {i for v in bundle["route_stops"].values() for side in v.values()
              for x in side for i in x["stops"]}
    위도 = [bundle["stops"][i]["lat"] for i in 쓰인_줄]
    경도 = [bundle["stops"][i]["lng"] for i in 쓰인_줄]
    assert bundle["bbox"] == {
        "min_lat": min(위도), "min_lng": min(경도),
        "max_lat": max(위도), "max_lng": max(경도),
    }
    # 광주와 그 노선망이 닿는 전남 인근. `stops.csv` 전체(순천·여수까지)보다 좁다
    assert 34.88 < min(위도) < 34.89 and 35.31 < max(위도) < 35.32
    assert 126.38 < min(경도) < 126.39 and 127.17 < max(경도) < 127.18


def test_route_stops의_STATION_NUM이_모두_stops에_있다(bundle: dict) -> None:
    """번들 안에서 끊긴 고리가 없어야 Worker가 조회 실패를 다룰 일이 없다."""
    없는_줄 = [
        i for v in bundle["route_stops"].values() for side in v.values()
        for x in side for i in x["stops"] if i not in bundle["stops"]
    ]
    assert 없는_줄 == []
    빈_칸 = [
        x["name"] for v in bundle["route_stops"].values() for side in v.values()
        for x in side if not x["stops"]
    ]
    assert 빈_칸 == []


def test_순환_노선은_하행이_비어_있다(bundle: dict) -> None:
    assert bundle["route_stops"]["before:순환01"]["down"] == []
    assert bundle["route_stops"]["before:문흥18"]["down"] != []


def test_번들은_무료_요금제_상한_안이다(tmp_path: Path) -> None:
    """wrangler가 재는 것은 압축 뒤 크기이므로, 압축 전 크기가 상한 안이면 넉넉히 든다."""
    번들 = tmp_path / "data.json"
    build(SOURCE, tmp_path / "out", 번들)
    assert 번들.stat().st_size < FREE_PLAN_LIMIT


def test_노선안에_없는_이름을_넣으면_멈추고_그_이름을_낸다(tmp_path: Path) -> None:
    """조용히 건너뛰면 그 정류장은 지도에서만 사라지는 것이 아니라 경로 탐색에서 통째로 없어진다."""
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    이름_하나를_없는_것으로(data)
    끝 = run_cli(data, tmp_path / "out", tmp_path / "data.json")
    assert 끝.returncode == 1
    assert "없는정류장" in 끝.stderr


def test_신설_정류소도_명칭_변경도_아닌_이름은_추정하지_않는다(tmp_path: Path) -> None:
    """빠진 좌표를 추정으로 덮으면 자료가 틀렸다는 사실이 화면에서 안 보인다."""
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    이름_하나를_없는_것으로(data)
    with pytest.raises(BuildError) as 오류:
        build(data / "source", tmp_path / "out", tmp_path / "data.json")
    assert "없는정류장" in str(오류.value)


def test_번들을_못_만들면_지난번_조각을_남긴다(tmp_path: Path) -> None:
    """이름을 못 이어 멈출 때 `out/`을 반쯤 지운 채로 두지 않는다."""
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    out = tmp_path / "out"
    build(data / "source", out, tmp_path / "data.json")
    이름_하나를_없는_것으로(data)
    with pytest.raises(BuildError):
        build(data / "source", out, tmp_path / "data.json")
    assert (out / "index.html").exists()


def 이름별_줄(bundle: dict, name: str) -> set[str]:
    return {i for i, v in bundle["stops"].items() if v["name"] == name}


def test_표_다섯과_좌표_범위가_있다(bundle: dict) -> None:
    assert set(bundle) == {
        "stops", "routes", "route_stops", "transfers", "route_links", "bbox",
    }


def test_transfers의_거리는_모두_환승_도보_안이다(bundle: dict) -> None:
    """350m를 넘는 쌍이 하나라도 있으면 환승이 아닌 것을 환승으로 잇는다."""
    거리 = [m for _, _, m in bundle["transfers"]]
    assert 거리 and max(거리) <= TRANSFER_WALK_M
    assert min(거리) >= 0
    # 0m 쌍 34개는 진짜다 — `stops.csv`에 좌표가 똑같은 다른 줄이 있고(화순서라아파트 ARS 셋),
    # 종점의 추정 좌표는 이웃이 한쪽뿐이라 그 이웃 자리에 그대로 놓인다. 같은 줄끼리만 아니면 된다
    assert all(a != b for a, b, _ in bundle["transfers"])


def test_transfers는_노선안이_지나는_줄끼리만_잇는다(bundle: dict) -> None:
    """아무 버스도 안 서는 줄을 환승 후보로 두면 「갈아탈 곳」이 못 타는 곳이 된다."""
    쓰인_줄 = {i for v in bundle["route_stops"].values() for side in v.values()
              for x in side for i in x["stops"]}
    밖 = [쌍 for 쌍 in bundle["transfers"] if 쌍[0] not in 쓰인_줄 or 쌍[1] not in 쓰인_줄]
    assert 밖 == []


def test_transfers에_같은_쌍이_두_번_없다(bundle: dict) -> None:
    쌍 = [frozenset((a, b)) for a, b, _ in bundle["transfers"]]
    assert len(쌍) == len(set(쌍))


def test_아는_정류장_쌍의_환승_도보_거리가_실제_값과_맞는다(bundle: dict) -> None:
    """전남대사거리(서) 길 양쪽 두 줄(ARS 4351·4350)은 43m 떨어져 있다.

    위도 차 0.00018362°(20.4m)와 경도 차 0.00041704°(위도 35.17°에서 37.9m)의 빗변이
    43.0m다 — 번들이 쓰는 것과 다른 셈으로 낸 값이라 공식이 바뀌면 이 검사가 걸린다.
    """
    거리 = {
        (a, b): m for a, b, m in bundle["transfers"]
    }
    서쪽 = sorted(이름별_줄(bundle, "전남대사거리(서)"))
    assert len(서쪽) == 2
    잰_값 = 거리.get(tuple(서쪽)) or 거리.get(tuple(reversed(서쪽)))
    assert 잰_값 == 43, f"{서쪽} → {잰_값}"


def test_route_links가_노선_쌍당_한_줄이다(bundle: dict) -> None:
    """쌍당 최단 1개다(ADR-0008 결정 1) — 두 줄이면 번들이 그만큼 커진다."""
    쌍 = [frozenset((a, b)) for a, b, *_ in bundle["route_links"]]
    assert 쌍 and len(쌍) == len(set(쌍))
    assert all(a != b for a, b, *_ in bundle["route_links"]), "자기 자신과는 환승하지 않는다"


def test_route_links는_한_노선망_안에서만_잇는다(bundle: dict) -> None:
    """경로는 늘 한 노선망 안에서만 찾는다(CONTEXT 「노선망」)."""
    망 = bundle["routes"]
    다른_망 = [(a, b) for a, b, *_ in bundle["route_links"]
              if 망[a]["network"] != 망[b]["network"]]
    assert 다른_망 == []


def test_route_links의_환승_지점이_그_노선의_정류장이다(bundle: dict) -> None:
    """엉뚱한 줄이 실리면 화면에는 이름이 나오는데 그 노선은 거기 서지 않는다."""
    노선_줄 = {
        r: {i for side in v.values() for x in side for i in x["stops"]}
        for r, v in bundle["route_stops"].items()
    }
    어긋난 = [
        (a, b) for a, b, here, there, _ in bundle["route_links"]
        if here not in 노선_줄[a] or there not in 노선_줄[b]
    ]
    assert 어긋난 == []


def test_route_links의_거리는_transfers에_있거나_같은_줄이라_0이다(bundle: dict) -> None:
    """환승 지점은 같은 줄(0m)이거나 350m 안 쌍이다. 그 밖의 값은 어디서도 나올 수 없다."""
    쌍 = {frozenset((a, b)): m for a, b, m in bundle["transfers"]}
    for a, b, here, there, m in bundle["route_links"]:
        if here == there:
            assert m == 0, (a, b, here)
        else:
            assert 쌍.get(frozenset((here, there))) == m, (a, b, here, there, m)


def test_route_links가_그_노선_쌍의_최단_환승_지점이다(bundle: dict) -> None:
    """노선 하나를 골라 손으로 다시 세어 본다 — 「최단」이 실제로 최단인지."""
    노선_줄 = {
        r: {i for side in v.values() for x in side for i in x["stops"]}
        for r, v in bundle["route_stops"].items()
    }
    가까운: dict[str, dict[str, int]] = {}
    for a, b, m in bundle["transfers"]:
        가까운.setdefault(a, {})[b] = m
        가까운.setdefault(b, {})[a] = m

    골라본 = [x for x in bundle["route_links"] if x[0] == "before:문흥18"]
    assert len(골라본) > 10, 골라본
    for a, b, _here, _there, m in 골라본:
        최단 = min(
            0 if i == j else 가까운.get(i, {}).get(j, 10**9)
            for i in 노선_줄[a]
            for j in 노선_줄[b]
        )
        assert m == 최단, (a, b, m, 최단)


def test_빌드_상수가_worker_rules와_같다() -> None:
    """빌드는 파이썬이라 `rules.js`를 import할 수 없다. 값이 어긋나면 여기서 걸린다."""
    글 = (ROOT / "worker" / "rules.js").read_text(encoding="utf-8")
    적힌 = re.search(r"TRANSFER_WALK_M\s*=\s*(\d+)", 글)
    assert 적힌 and int(적힌.group(1)) == TRANSFER_WALK_M
