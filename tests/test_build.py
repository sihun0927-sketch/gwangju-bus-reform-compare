"""빌드의 바깥만 검사한다 — 진짜 CSV로 한 번 돌린 `out/`의 파일 내용.

이음새는 `build(source, out)` 하나다. 모듈 안의 함수 모양은 이 파일이 모른다.
검사 하나가 규칙 하나에 대응한다. 보는 것은 시민이 화면에서 읽는 문자열이다.
"""
from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.build import BuildError, build

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE = DATA / "source"
ALIGN_TABLE = DATA / "기종점정렬표.csv"

문흥18 = ("문흥18", "기본", "간선18", "기본.html")
순환01 = ("순환01", "기본", "간선01", "기본.html")
선운101 = ("선운101", "빛그린산단", "지선97", "빛그린산단출근.html")
두암81 = ("두암81", "각화초교.장등동", "지선81", "기본.html")


@pytest.fixture(scope="session")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """진짜 CSV로 한 번만 빌드하고 모든 검사가 그 결과를 나눠 쓴다."""
    out = tmp_path_factory.mktemp("out")
    build(SOURCE, out)
    return out


def fragment(site: Path, parts: tuple[str, ...]) -> str:
    return (site / "route" / Path(*parts)).read_text(encoding="utf-8")


def card(site: Path, number: str) -> str:
    return (site / "route" / f"{number}.html").read_text(encoding="utf-8")


def buttons(html: str) -> list[str]:
    return re.findall(r"<button[^>]*>(.*?)</button>", html)


def rows(html: str) -> list[str]:
    return re.findall(r"<tr><td class=\"index\">.*?</tr>", html)


def write_bom_csv(path: Path, lines: list[str]) -> None:
    """빌드가 읽는 모양대로 UTF-8 BOM으로 다시 쓴다."""
    path.write_text("﻿" + "\n".join(lines) + "\n", encoding="utf-8")


def run_cli(data: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.build", str(data / "source"), str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_명령_하나로_노선_변화_표_205개와_카드_103개가_생긴다(site: Path) -> None:
    assert len(list(site.glob("route/*/*/*/*.html"))) == 205
    assert len(list(site.glob("route/*.html"))) == 103
    assert len(list(site.rglob("*.html"))) == 308


def test_out을_비우고_다시_쓴다(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    stale = out / "지난번.html"
    stale.write_text("옛 조각", encoding="utf-8")
    build(SOURCE, out)
    assert not stale.exists()


def test_상행_하행_요약_칸_여섯(site: Path) -> None:
    html = fragment(site, 문흥18)
    for 문구 in ("상행 · 유지", "상행 · 경유 제외", "상행 · 경유 추가",
                 "하행 · 유지", "하행 · 경유 제외", "하행 · 경유 추가"):
        assert 문구 in html
    for 개수 in ("47곳", "11곳", "5곳", "50곳", "12곳", "6곳"):
        assert 개수 in html


def test_기종점이_반대인_쌍은_뒤집어_맞대고_그_사실을_적는다(site: Path) -> None:
    assert "기점·종점이 반대라 뒤집어 맞댔습니다" in fragment(site, 문흥18)


def test_기종점이_같은_쌍에는_뒤집었다는_줄이_없다(site: Path) -> None:
    assert "뒤집어 맞댔습니다" not in fragment(site, 순환01)


def test_표_제목은_번호와_방면(site: Path) -> None:
    assert "<h3>문흥18 노선 변화</h3>" in fragment(site, 문흥18)
    assert "<h3>두암81(각화초교.장등동) 노선 변화</h3>" in fragment(site, 두암81)


def test_열_머리_여섯(site: Path) -> None:
    html = fragment(site, 문흥18)
    머리 = re.findall(r"<th>(.*?)</th>", html)
    assert 머리 == ["#", "개편 전 상행 정류장", "개편 후 상행 정류장",
                   "개편 전 하행 정류장", "개편 후 하행 정류장", "비고"]


def test_개편_전에만_있는_줄과_개편_후에만_있는_줄이_다른_class다(site: Path) -> None:
    html = fragment(site, 문흥18)
    assert '<td class="dropped">문흥고가</td><td class="dropped"></td>' in html
    assert '<td class="added"></td><td class="added">문화육교</td>' in html


def test_출처_줄(site: Path) -> None:
    assert "출처: 광주광역시 시내버스 노선개편안" in fragment(site, 문흥18)


def test_순환_노선은_하행_두_칸을_비우고_비고에_적는다(site: Path) -> None:
    html = fragment(site, 순환01)
    assert "순환 노선 · 하행 없음" in html
    첫줄 = rows(html)[0]
    assert 첫줄.count("<td></td>") == 2


def test_편도_노선은_순환과_다르게_적는다(site: Path) -> None:
    html = fragment(site, 선운101)
    assert "편도 운행 · 하행 없음" in html
    assert "순환 노선" not in html


def test_편도_대체_노선의_정류장이_표에_실린다(site: Path) -> None:
    """하행이 없다고 개편 후 칸을 통째로 비우면 그 노선이 아무 데도 안 서는 표가 된다."""
    html = fragment(site, 선운101)
    assert "광주종합버스터미널" in html   # 지선97(빛그린산단출근)의 기점
    assert "수성" in html                # 그 종점
    assert '<span class="label">상행 · 유지</span> <span class="count">0곳</span>' not in html


def test_같은_번호라도_종류가_다르면_표가_따로다(site: Path) -> None:
    급행 = fragment(site, ("수완03", "기본", "급행03", "기본.html"))
    간선 = fragment(site, ("수완03", "기본", "간선03", "기본.html"))
    assert len(rows(급행)) != len(rows(간선))


def test_방면_이름이_든_네_단계_경로(site: Path) -> None:
    assert (site / "route" / "두암81" / "각화초교.장등동" / "지선81" / "기본.html").exists()
    assert (site / "route" / "선운101" / "빛그린산단" / "지선97" / "빛그린산단출근.html").exists()


def test_대체_노선이_없는_번호는_표가_없다(site: Path) -> None:
    assert not (site / "route" / "두암181").exists()


def test_기종점_정렬표는_18행이고_확인_열은_비어_있다() -> None:
    with io.open(ALIGN_TABLE, encoding="utf-8-sig", newline="") as f:
        표 = list(csv.DictReader(f))
    assert len(표) == 18
    assert {r["개편전상행이맞닿는쪽"] for r in 표} <= {"상행", "하행"}
    assert all(r["확인"] == "" for r in 표)


def test_정렬표에_사람이_안_적은_쌍이_있으면_멈춘다(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    표 = data / ALIGN_TABLE.name
    남길 = 표.read_text(encoding="utf-8-sig").splitlines()
    지운 = [줄 for 줄 in 남길 if not 줄.startswith("첨단94,기본,지선94,")]
    assert len(지운) == len(남길) - 1
    write_bom_csv(표, 지운)

    끝 = run_cli(data, tmp_path / "out")
    assert 끝.returncode == 1
    assert "첨단94 ↔ 지선94" in 끝.stderr


def test_뒤집을_하행이_없는_답이_적혀_있으면_멈춘다(tmp_path: Path) -> None:
    """편도 대체 노선(지선97(빛그린산단출근))에는 뒤집어 맞댈 하행이 아예 없다."""
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    표 = data / ALIGN_TABLE.name
    바뀐 = 표.read_text(encoding="utf-8-sig").replace(
        "선운101,빛그린산단,지선97,빛그린산단출근,상행,",
        "선운101,빛그린산단,지선97,빛그린산단출근,하행,",
    )
    표.write_text("﻿" + 바뀐, encoding="utf-8")

    끝 = run_cli(data, tmp_path / "out")
    assert 끝.returncode == 1
    assert "지선97(빛그린산단출근)" in 끝.stderr


def test_같은_쌍이_정렬표에_두_번_적히면_멈춘다(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    표 = data / ALIGN_TABLE.name
    줄 = 표.read_text(encoding="utf-8-sig").splitlines()
    write_bom_csv(표, 줄 + [줄[1]])

    끝 = run_cli(data, tmp_path / "out")
    assert 끝.returncode == 1
    assert "두 번" in 끝.stderr


def test_입력이_든_자리는_출력으로_받아도_지우지_않는다(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    with pytest.raises(BuildError):
        build(data / "source", data)
    assert (data / "source" / "노선개편 전후 비교표.csv").exists()


def test_비교표의_번호를_노선안에서_못_찾으면_멈춘다(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    비교표 = data / "source" / "노선개편 전후 비교표.csv"
    비교표.write_text(
        비교표.read_text(encoding="utf-8-sig").replace("순환01,\"1, 11\"", "순환01,\"1, 없는번호999\""),
        encoding="utf-8-sig",
    )
    끝 = run_cli(data, tmp_path / "out")
    assert 끝.returncode == 1
    assert "없는번호999" in 끝.stderr


def test_카드는_제목과_기종점과_정류장_수를_보인다(site: Path) -> None:
    html = card(site, "문흥18")
    assert "<h2>문흥18</h2>" in html
    assert "장등동 → 진곡산단" in html
    assert "상행 58곳" in html and "하행 62곳" in html


def test_카드에_대체_노선_목록이_기종점과_함께_있다(site: Path) -> None:
    html = card(site, "문흥18")
    assert "간선18" in html and "지선10" in html
    assert "하남고등학교 → 장등동" in html   # 간선18의 기·종점


def test_카드는_기본_방면과_첫_대체_노선의_표를_미리_품는다(site: Path) -> None:
    html = card(site, "문흥18")
    assert "<h3>문흥18 노선 변화</h3>" in html
    for 개수 in ("47곳", "11곳", "5곳", "50곳", "12곳", "6곳"):
        assert 개수 in html


def test_대체_노선_버튼_줄은_모든_카드에_있다(site: Path) -> None:
    html = card(site, "문흥18")
    assert "대체 노선을 고르세요" in html
    assert buttons(html) == ["간선18", "지선10"]
    assert 'hx-get="route/문흥18/기본/간선18/기본.html"' in html
    assert 'hx-get="route/문흥18/기본/지선10/기본.html"' in html


def test_방면이_하나뿐인_노선에는_방면_버튼_줄이_없다(site: Path) -> None:
    html = card(site, "문흥18")
    assert "개편 전 방면을 고르세요" not in html
    assert "개편 후 방면을 고르세요" not in html


def test_개편_전_방면이_여럿이면_그_버튼_줄이_있다(site: Path) -> None:
    html = card(site, "두암81")
    assert "개편 전 방면을 고르세요" in html
    for 방면 in ("각화초교.장등마을", "무등파크.장등동", "각화초교.장등동", "무등파크.장등마을"):
        assert 방면 in buttons(html)


def test_대체_노선에_방면이_있으면_개편_후_방면_버튼_줄이_있다(site: Path) -> None:
    html = card(site, "선운101")
    assert "개편 후 방면을 고르세요" in html
    assert "기본" in buttons(html) and "빛그린산단출근" in buttons(html)
    assert 'hx-get="route/선운101/송산유원지/지선97/빛그린산단출근.html"' in html


def test_방면이_없는_대체_노선에는_개편_후_방면_줄이_붙지_않는다(site: Path) -> None:
    """선운101의 대체 노선 셋 중 방면이 있는 것은 지선97뿐이다(개편 전 방면 둘 × 한 줄씩)."""
    html = card(site, "선운101")
    assert html.count("개편 후 방면을 고르세요") == 2
    for 줄 in re.findall(r'<div class="choice after-branch">.*?</div>', html, re.S):
        assert "지선94" not in 줄 and "지선197" not in 줄


def test_개편_전_방면이_여럿이면_대체_노선_줄도_방면마다_따로다(site: Path) -> None:
    """줄 하나가 든 주소는 하나뿐이라, 방면 줄과 대체 노선 줄이 하나씩이면 조합의 일부는 못 연다."""
    html = card(site, "두암81")
    assert html.count("대체 노선을 고르세요") == 4
    for 방면 in ("각화초교.장등마을", "무등파크.장등동", "각화초교.장등동", "무등파크.장등마을"):
        for 대체 in ("지선81", "지선87"):
            assert f'hx-get="route/두암81/{방면}/{대체}/기본.html"' in html


def test_표_205개가_모두_어느_카드에선가_닿는다(site: Path) -> None:
    """만들어 놓고 아무도 못 여는 표를 내보내지 않는다."""
    닿는_곳 = set()
    for path in site.glob("route/*.html"):
        for url in re.findall(r'hx-get="([^"]+)"', path.read_text(encoding="utf-8")):
            닿는_곳.add((site / url).resolve())
    표 = {p.resolve() for p in site.glob("route/*/*/*/*.html")}
    못_닿는 = sorted(p.relative_to(site.resolve()).as_posix() for p in 표 - 닿는_곳)
    assert 못_닿는 == []


def test_같은_번호라도_종류가_다른_대체_노선은_버튼이_따로다(site: Path) -> None:
    assert buttons(card(site, "수완03")) == ["간선03", "급행03", "간선80"]


def test_대체_노선이_없는_번호의_카드에는_표도_버튼도_없다(site: Path) -> None:
    html = card(site, "두암181")
    assert "대체 노선 없음" in html
    assert "<table" not in html
    assert "hx-get" not in html
    assert "대덕" in html   # 개편 전 정류장 목록은 있다


def test_카드가_가리키는_조각_주소에_파일이_다_있다(site: Path) -> None:
    버튼_없는_카드 = []
    for path in site.glob("route/*.html"):
        주소 = re.findall(r'hx-get="([^"]+)"', path.read_text(encoding="utf-8"))
        if not 주소:
            버튼_없는_카드.append(path.stem)
        for url in 주소:
            assert (site / url).exists(), f"{path.name} → {url}"
    assert 버튼_없는_카드 == ["두암181"]   # 고를 것이 없는 번호는 이 하나뿐이다


def test_화면_문구에_옛_용어가_없다(site: Path) -> None:
    for path in site.rglob("*.html"):
        글 = path.read_text(encoding="utf-8")
        for 옛말 in ("기존", "신규", "현행"):
            assert 옛말 not in 글, f"{path.name}에 「{옛말}」"
