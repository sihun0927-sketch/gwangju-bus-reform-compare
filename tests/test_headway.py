"""배차간격 추정의 바깥만 검사한다 — 진짜 CSV로 한 번 빌드한 `headway.json`의 내용.

이음새는 `build(source, out, bundle)` 하나다. 모듈 안의 함수 모양은 이 파일이 모른다.
보는 것은 표의 **사실**이다 — 노선 수, 합계, 되돌린 값이 원천과 같은지, 그리고 원천이 어긋났을 때
빌드가 서는지.

값이 「그럴듯한지」는 여기가 아니라 `tools/measure_headway.py`가 잰다 — 그쪽은 문턱을 넘는지 보고,
여기는 약속을 지키는지 본다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.build import BuildError, build
from tools.build.headway import (
    AFTER_TRIPS,
    BEFORE_TRIPS,
    HEADWAY_CEILING,
    HEADWAY_CSV,
    HEADWAY_FLOOR,
    JSON_NAME,
    VERDICTS,
    headway_of,
    read_headways,
)
from tools.build.load import read_before

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE = DATA / "source"

# 비교표가 대체 노선으로 아무 데도 안 적어 둔 개편 후 노선. 승계표만으로는 0이 되는 자리다
NEW_ROUTES = ("간선24", "지선71", "지선82")


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict, Path]:
    """진짜 CSV로 한 번만 빌드하고 모든 검사가 그 표를 나눠 쓴다."""
    자리 = tmp_path_factory.mktemp("headway")
    build(SOURCE, 자리 / "out", 자리 / "data.json")
    표 = json.loads((자리 / JSON_NAME).read_text(encoding="utf-8"))
    return 표, 자리


@pytest.fixture(scope="session")
def table(built: tuple[dict, Path]) -> dict:
    return built[0]


def run_cli(data: Path, out: Path, bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.build", str(data / "source"), str(out), str(bundle)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def write_csv(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def test_개편_후_노선_118개에_배차간격이_있다(table: dict) -> None:
    노선 = table["노선"]
    assert len(노선) == 118
    assert table["망"]["개편후노선"] == 118
    빈칸 = [이름 for 이름, 값 in 노선.items() if not 값["배차간격"] > 0]
    assert 빈칸 == []


def test_운행횟수_합이_발표와_같다(table: dict) -> None:
    """8394는 보정 상수를 그것으로 풀었으니 항등이고, 9355는 배분이 지켜야 할 약속이다."""
    assert table["망"]["개편전운행횟수"] == pytest.approx(BEFORE_TRIPS, abs=1e-3)
    assert table["망"]["개편후운행횟수"] == pytest.approx(AFTER_TRIPS, abs=1e-3)
    합 = sum(값["운행횟수"] for 값 in table["노선"].values())
    assert 합 == pytest.approx(AFTER_TRIPS, abs=0.5)


def test_개편_전_배차간격을_되돌리면_원천과_같다(table: dict) -> None:
    """운행횟수 ↔ 배차간격 변환이 가역이다. 방면이 하나인 노선은 원천 값이 그대로 나와야 한다."""
    원천 = read_headways(SOURCE)
    행들 = read_before(SOURCE)
    홀로 = [r for r in 행들 if sum(1 for x in 행들 if x.number == r.number) == 1]
    assert len(홀로) >= 90
    for r in 홀로:
        assert table["개편전"][r.number]["배차간격"] == pytest.approx(
            headway_of(r.name, 원천), abs=1e-3
        ), r.name


def test_배차간격이_개편_전에_관측된_범위_안에_있다(table: dict) -> None:
    """지어낸 울타리가 아니라 원천 CSV의 최솟값·최댓값이다."""
    원천 = sorted(read_headways(SOURCE).values())
    assert (원천[0], 원천[-1]) == (HEADWAY_FLOOR, HEADWAY_CEILING)
    for 이름, 값 in table["노선"].items():
        assert HEADWAY_FLOOR - 1e-6 <= 값["배차간격"] <= HEADWAY_CEILING + 1e-6, 이름


def test_밴드가_점_추정을_감싼다(table: dict) -> None:
    for 이름, 값 in table["노선"].items():
        아래, 위 = 값["밴드"]
        assert 아래 <= 값["배차간격"] <= 위, 이름


def test_비교표에_없는_신설_노선에도_값이_있다(table: dict) -> None:
    """승계표만 쓰면 0이 되어 배차가 무한대가 되는 자리다. 정류장 승계가 채운다."""
    for 이름 in NEW_ROUTES:
        assert 이름 in table["노선"]
        assert table["노선"][이름]["배차간격"] > 0
        assert table["노선"][이름]["수요"] > 0


def test_등급과_확신이_유한_집합에서만_나온다(table: dict) -> None:
    assert table["등급목록"] == list(VERDICTS)
    for 이름, 값 in table["노선"].items():
        assert 값["등급"] in table["등급목록"], 이름
        assert 값["확신"] in table["확신목록"], 이름


def test_차량을_더_넣을수록_배차가_짧아진다(table: dict) -> None:
    for 이름, 값 in table["노선"].items():
        assert 값["차량더"][0] > 값["차량더"][1] > 값["차량더"][2], 이름
        assert 값["차량더"][0] < 값["배차간격"], 이름


def test_개편_전_번호_103개가_대체_노선을_가리킨다(table: dict) -> None:
    개편전 = table["개편전"]
    assert len(개편전) == 103
    # 대체 노선이 비어 있는 것은 두암181 하나뿐이다(비교표의 빈 칸)
    빈칸 = [이름 for 이름, 값 in 개편전.items() if not 값["대체노선"]]
    assert 빈칸 == ["두암181"]
    for 이름, 값 in 개편전.items():
        for 대체 in 값["대체노선"]:
            assert 대체 in table["노선"], f"{이름} → {대체}"


def test_같은_자료가_정적_자산으로도_나간다(built: tuple[dict, Path]) -> None:
    """LLM은 주소 하나로 표를 통째로 받아 간다. 두 파일이 갈라지면 답이 갈린다."""
    _, 자리 = built
    assert (자리 / "out" / JSON_NAME).read_text(encoding="utf-8") == (
        자리 / JSON_NAME
    ).read_text(encoding="utf-8")


def test_두_번_빌드해도_같은_글이_나온다(tmp_path: Path) -> None:
    """중심수렴의 바닥 — 표가 흔들리면 그 위의 답도 흔들린다."""
    글 = []
    for 이름 in ("첫째", "둘째"):
        자리 = tmp_path / 이름
        build(SOURCE, 자리 / "out", 자리 / "data.json")
        글.append((자리 / JSON_NAME).read_text(encoding="utf-8"))
    assert 글[0] == 글[1]


def test_원천_배차간격_파일이_없으면_멈춘다(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    (data / "source" / HEADWAY_CSV).unlink()

    끝 = run_cli(data, tmp_path / "out", tmp_path / "data.json")
    assert 끝.returncode == 1
    assert HEADWAY_CSV in 끝.stderr


def test_배차간격이_0이면_멈춘다(tmp_path: Path) -> None:
    """0으로 나누면 운행횟수가 무한대가 된다. 조용히 넘어가지 않는다."""
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    줄 = (data / "source" / HEADWAY_CSV).read_text(encoding="utf-8-sig").splitlines()
    줄[1] = '"좌석02","0"'
    write_csv(data / "source" / HEADWAY_CSV, 줄)

    끝 = run_cli(data, tmp_path / "out", tmp_path / "data.json")
    assert 끝.returncode == 1
    assert "0 이하" in 끝.stderr


def test_노선안에_있는_번호가_배차간격_파일에_없으면_멈춘다(tmp_path: Path) -> None:
    """짐작으로 채우지 않는다 — 못 찾은 이름을 말하고 선다."""
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    줄 = (data / "source" / HEADWAY_CSV).read_text(encoding="utf-8-sig").splitlines()
    남길 = [줄[0]] + [행 for 행 in 줄[1:] if not 행.startswith('"좌석02"')]
    assert len(남길) == len(줄) - 1
    write_csv(data / "source" / HEADWAY_CSV, 남길)

    끝 = run_cli(data, tmp_path / "out", tmp_path / "data.json")
    assert 끝.returncode == 1
    assert "좌석02" in 끝.stderr


def test_배차간격_열_이름이_다르면_멈춘다(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    줄 = (data / "source" / HEADWAY_CSV).read_text(encoding="utf-8-sig").splitlines()
    줄[0] = '"route","headway"'
    write_csv(data / "source" / HEADWAY_CSV, 줄)

    끝 = run_cli(data, tmp_path / "out", tmp_path / "data.json")
    assert 끝.returncode == 1
    assert "열 이름이 다릅니다" in 끝.stderr


def test_울타리_안에서_합을_못_맞추면_멈춘다() -> None:
    """물채우기의 마지막 방어선. 이 검사만 모듈 안(`_allocate`)을 들여다본다.

    바깥 이음새로는 이 자리에 못 닿기 때문이다 — 원천 배차간격을 아무리 흔들어도 유효 운행시간
    `E`를 그 원천에서 다시 풀므로 울타리도 같이 늘어난다(원천을 전부 250분으로 바꿔도 빌드는
    그대로 돈다). 막을 수 없는 것을 막는 코드가 아니라는 것을 보이려면 여기서 직접 넣어야 한다.

    없는 것을 검사하는 것이라, 되는 경우(대조군)를 먼저 놓고 안 되는 경우를 본다.
    """
    from tools.build.headway import _allocate

    # 대조군 — 울타리 5~250분 안에서 나눌 수 있으면 합이 정확히 맞는다
    나뉜 = _allocate({"가": 1.0, "나": 3.0}, {"가": 2, "나": 2}, 600.0, 100.0)
    assert sum(나뉜.values()) == pytest.approx(100.0)
    assert 나뉜["나"] > 나뉜["가"]

    # 노선 둘이 배차 5분(가장 촘촘)으로 달려도 240회뿐인데 1000회를 시키면 나눌 수 없다
    with pytest.raises(BuildError, match="나눌 수 없습니다"):
        _allocate({"가": 1.0, "나": 1.0}, {"가": 2, "나": 2}, 600.0, 1000.0)
    # 반대쪽 울타리 — 250분으로 늘려도 9.6회라 1회를 못 맞춘다
    with pytest.raises(BuildError, match="나눌 수 없습니다"):
        _allocate({"가": 1.0, "나": 1.0}, {"가": 2, "나": 2}, 600.0, 1.0)


def test_원천을_다_250분으로_바꿔도_빌드는_돈다(tmp_path: Path) -> None:
    """위 검사의 짝 — 보정 상수가 원천을 따라가므로 울타리도 따라간다는 것을 눈으로 본다."""
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    줄 = (data / "source" / HEADWAY_CSV).read_text(encoding="utf-8-sig").splitlines()
    write_csv(
        data / "source" / HEADWAY_CSV,
        [줄[0]] + [행.rsplit(",", 1)[0] + ',"250"' for 행 in 줄[1:]],
    )

    build(data / "source", tmp_path / "out", tmp_path / "data.json")
    표 = json.loads((tmp_path / "data.json").parent.joinpath(JSON_NAME).read_text(encoding="utf-8"))
    assert 표["망"]["개편후운행횟수"] == pytest.approx(AFTER_TRIPS, abs=1e-3)
    assert 표["망"]["유효운행시간"] > 5000, "E가 원천을 따라 늘어야 한다"


def test_적합_배차가_차량을_안_늘리고_다시_나눈다(table: dict) -> None:
    """제곱근 법칙으로 다시 나눈 배차. 차량 총량이 그대로여야 「증차 없이」가 참이다."""
    노선 = table["노선"]
    지금 = sum(값["차량"] for 값 in 노선.values())
    적합 = sum(값["적합차량"] for 값 in 노선.values())
    assert 적합 == pytest.approx(지금, abs=0.5)
    # 대수는 배차에서 나눗셈으로 따라 나온다 — 화면의 두 수가 어긋나지 않는다는 뜻이다
    for 이름, 값 in 노선.items():
        assert 값["적합차량"] == pytest.approx(값["왕복시간"] / 값["적합배차"], abs=0.01), 이름
        assert 값["차량"] == pytest.approx(값["왕복시간"] / 값["배차간격"], abs=0.01), 이름
    # 배차가 촘촘할수록 차량이 많이 든다 — 방향이 뒤집히면 어딘가 부호가 틀린 것이다
    성긴쪽 = max(노선.values(), key=lambda 값: 값["적합배차"])
    촘촘한쪽 = min(노선.values(), key=lambda 값: 값["적합배차"])
    assert 촘촘한쪽["적합차량"] > 성긴쪽["적합차량"] or 촘촘한쪽["왕복시간"] < 성긴쪽["왕복시간"]


def test_적합_배차의_편차가_개편안보다_좁다(table: dict) -> None:
    """제곱근 법칙의 예측이다 — 수요에 비례가 아니라 √수요만큼만 배차를 벌린다."""
    망 = table["망"]
    assert 망["적합배차편차"] < 망["개편안배차편차"]
    assert 망["적합배차편차"] > 1.5, "수요 차이가 통째로 사라지면 안 된다"


def test_카드가_배차간격_자리를_htmx로_부른다(built: tuple[dict, Path]) -> None:
    """카드는 정적 파일이라 배차간격을 미리 못 적는다 — 자리와 「계산중…」만 적고 Worker가 채운다."""
    from urllib.parse import quote

    from tools.build.render import HEADWAY_LOADING

    _, 자리 = built
    글 = (자리 / "out" / "route" / "문흥18.html").read_text(encoding="utf-8")
    for 대체 in ("간선18", "지선10"):
        주소 = f'hx-get="/headway/{quote(대체, safe="")}"'
        assert 주소 in 글, f"{대체}의 배차간격 자리가 없습니다"
    assert HEADWAY_LOADING in 글
    assert 'hx-trigger="load"' in 글
    assert 'hx-swap="outerHTML"' in 글


def test_카드_103개에_배차간격_자리가_대체_노선마다_있다(built: tuple[dict, Path]) -> None:
    """대체 노선 줄 하나에 자리 하나다. 하나라도 빠지면 그 노선만 「계산중」이 안 뜬다."""
    import json as _json

    _, 자리 = built
    표 = _json.loads((자리 / JSON_NAME).read_text(encoding="utf-8"))
    자리수, 줄수 = 0, 0
    for 이름, 값 in 표["개편전"].items():
        글 = (자리 / "out" / "route" / f"{이름}.html").read_text(encoding="utf-8")
        자리수 += 글.count('hx-get="/headway/')
        줄수 += len(값["대체노선"])
    assert 자리수 == 줄수 > 0
