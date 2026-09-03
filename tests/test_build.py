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
법원입구 = ("1187", "기본", "1187", "기본.html")
금남59 = ("금남59", "기본", "지선59", "기본.html")
송정93 = ("송정93", "기본", "지선93", "기본.html")
상무62 = ("상무62", "상무역경유시청행", "지선62", "기본.html")
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


def test_명령_하나로_노선_변화_표_205개가_생긴다(site: Path) -> None:
    assert len(list(site.rglob("*.html"))) == 205


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
    for 개수 in ("49곳", "9곳", "3곳", "52곳", "10곳", "4곳"):
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
    assert '<td class="dropped">현대위아</td><td class="dropped"></td>' in html
    assert '<td class="added"></td><td class="added">전남대동문</td>' in html


def test_이름만_바뀐_정류장은_한_줄_유지이고_비고에_명칭_변경(site: Path) -> None:
    html = fragment(site, 문흥18)
    assert '<td class="kept">문흥고가</td><td class="kept">문화육교</td>' in html
    assert "명칭 변경: 문흥고가 → 문화육교" in html


def test_옛_이름_하나가_새_이름_여럿이어도_어느_쪽과_만나든_유지다(site: Path) -> None:
    """법원입구는 방향별로 1번출구·2번출구로 갈라진다. 한쪽만 잡으면 다른 쪽이 경유 제외로 보인다."""
    html = fragment(site, 법원입구)
    assert "명칭 변경: 법원입구 → 광주법원검찰역1번출구" in html
    assert "명칭 변경: 법원입구 → 광주법원검찰역2번출구" in html


def test_통폐합이전_CSV의_정류장은_구분_값만_보이고_사유는_title이다(site: Path) -> None:
    폐지 = fragment(site, 금남59)
    assert '<td class="note" title="도시철도 2호선 1단계 개통에 맞춰' in 폐지
    assert '">폐지</td>' in 폐지
    assert ">도시철도 2호선" not in 폐지   # 사유는 칸에 적히지 않는다

    이전 = fragment(site, 송정93)
    assert '<td class="dropped">옥동차량기지</td>' in 이전
    assert '">이전</td>' in 이전


def test_신설_CSV의_정류장은_개편_후에만_있는_줄에_적힌다(site: Path) -> None:
    html = fragment(site, 금남59)
    assert '<td class="added"></td><td class="added">광주체육회관</td>' in html
    assert ">신설 정류소</td>" in html


def test_비고에_상태_문구는_적지_않는다(site: Path) -> None:
    """상태는 줄 색과 요약 칸이 말한다 (ADR-0003 2026-09-03 개정)."""
    칸 = re.compile(r'<td class="note"[^>]*>([^<]*)</td>')
    for path in site.rglob("*.html"):
        for 비고 in 칸.findall(path.read_text(encoding="utf-8")):
            assert not any(말 in 비고 for 말 in ("유지", "경유 제외", "경유 추가")), path


def test_CSV_이름이_노선안과_안_맞으면_비고를_비우고_빌드는_성공한다(site: Path) -> None:
    """통폐합 CSV는 흡수된 정류장을 「계수초교(상무한국아파트)」로 적어 노선안 이름과 안 맞는다."""
    html = fragment(site, 상무62)
    assert '<td class="dropped">상무한국아파트</td>' in html
    줄 = next(r for r in rows(html) if ">상무한국아파트<" in r)
    assert 줄.endswith('<td class="note"></td></tr>')


def test_한_줄에_사실이_둘이면_이어_적는다(site: Path) -> None:
    html = fragment(site, ("금호36", "기본", "간선36", "기본.html"))
    assert (
        "명칭 변경: 금남로4가역 → 금남로4가역3번출구 · 명칭 변경: 돌고개역(동) → 돌고개역1번출구"
        in html
    )


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
