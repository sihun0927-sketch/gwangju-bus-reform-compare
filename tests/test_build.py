"""빌드의 바깥만 검사한다 — 진짜 CSV로 한 번 돌린 `out/`의 파일 내용.

이음새는 `build(source, out)` 하나다. 모듈 안의 함수 모양은 이 파일이 모른다.
검사 하나가 규칙 하나에 대응한다. 보는 것은 시민이 화면에서 읽는 문자열이다.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter
from html import unescape
from pathlib import Path

import pytest

from tools.build import BuildError, build

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE = DATA / "source"

# 카드가 Worker에게 배차간격을 물으러 가는 주소의 앞머리(ADR-0011)
HEADWAY_PREFIX = "/headway/"
# 껍데기의 <script> 태그. 여는 태그만 센다
SCRIPT_TAG = r"<script\b[^>]*>"
ALIGN_TABLE = DATA / "기종점정렬표.csv"

문흥18 = ("문흥18", "기본", "간선18", "기본.html")
순환01 = ("순환01", "기본", "간선01", "기본.html")
선운101 = ("선운101", "빛그린산단", "지선97", "빛그린산단출근.html")
두암81 = ("두암81", "각화초교.장등동", "지선81", "기본.html")
노선1187 = ("1187", "기본", "1187", "기본.html")
문흥80 = ("문흥80", "기본", "간선80", "기본.html")
송정93 = ("송정93", "기본", "지선93", "기본.html")
운림54 = ("운림54", "기본", "간선54", "기본.html")
매월06 = ("매월06", "기본", "간선06", "기본.html")


@pytest.fixture(scope="session")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """진짜 CSV로 한 번만 빌드하고 모든 검사가 그 결과를 나눠 쓴다."""
    자리 = tmp_path_factory.mktemp("out")
    build(SOURCE, 자리 / "out", 자리 / "data.json")
    return 자리 / "out"


def fragment(site: Path, parts: tuple[str, ...]) -> str:
    return (site / "route" / Path(*parts)).read_text(encoding="utf-8")


def notes(site: Path) -> list[tuple[Path, str]]:
    """모든 조각의 비고 칸을 (파일, 적힌 말)로 모은다."""
    칸 = re.compile(r'<td class="note"[^>]*>([^<]*)</td>')
    return [
        (path, 비고)
        for path in site.rglob("*.html")
        for 비고 in 칸.findall(path.read_text(encoding="utf-8"))
    ]


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


def test_명령_하나로_껍데기와_노선_변화_표_205개와_카드_103개가_생긴다(site: Path) -> None:
    assert (site / "index.html").exists()
    assert len(list(site.glob("route/*/*/*/*.html"))) == 205
    assert len(list(site.glob("route/*.html"))) == 103
    assert len(list(site.rglob("*.html"))) == 309


def test_out을_비우고_다시_쓴다(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    stale = out / "지난번.html"
    stale.write_text("옛 조각", encoding="utf-8")
    build(SOURCE, out, tmp_path / "data.json")
    assert not stale.exists()


def test_상행_하행_요약_칸_여섯(site: Path) -> None:
    html = fragment(site, 문흥18)
    for 문구 in ("상행 · 유지", "상행 · 경유 제외", "상행 · 경유 추가",
                 "하행 · 유지", "하행 · 경유 제외", "하행 · 경유 추가"):
        assert 문구 in html
    # 명칭 사전을 적용해 손으로 센 값 — 상행 개편 전 58곳 = 유지 49 + 경유 제외 9,
    # 개편 후(뒤집어 맞댄 간선18 하행) 52곳 = 49 + 경유 추가 3. 하행은 62 = 52 + 10, 56 = 52 + 4
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
    # 현대위아는 새 이름(모비언트)이 간선18에 없어 진짜 경유 제외다. 전남대동문은 개편 후에만 있다
    assert '<td class="dropped">현대위아</td><td class="dropped"></td>' in html
    assert '<td class="added"></td><td class="added">전남대동문</td>' in html


def test_이름만_바뀐_정류장은_한_줄_유지이고_비고에_명칭_변경(site: Path) -> None:
    """ADR-0003 결정 2. 두 줄로 갈라 두면 개편을 실제보다 나쁘게 보여 준다."""
    html = fragment(site, 문흥18)
    assert '<td class="kept">문흥고가</td><td class="kept">문화육교</td>' in html
    assert "명칭 변경: 문흥고가 → 문화육교" in html


def test_옛_이름_하나가_새_이름_여럿이어도_어느_쪽과_만나든_유지다(site: Path) -> None:
    """법원입구는 방향별로 1번출구·2번출구로 갈라진다(ADR-0003 결정 2). 한쪽만 잡으면 나머지가
    경유 제외로 보인다. 1187은 두 새 이름이 개편 후 노선안에 다 있는 노선이다."""
    html = fragment(site, 노선1187)
    assert "명칭 변경: 법원입구 → 광주법원검찰역1번출구" in html
    assert "명칭 변경: 법원입구 → 광주법원검찰역2번출구" in html


def test_통폐합이전_CSV의_정류장은_구분_값만_보이고_사유는_title이다(site: Path) -> None:
    """ADR-0003 2026-09-03 개정 — 사유 문장까지 칸에 적으면 표가 어수선하다."""
    폐지 = fragment(site, 문흥80)
    assert '<td class="dropped">충장로5가입구</td>' in 폐지
    assert '">폐지</td>' in 폐지
    assert 'title="이번 노선개편에서 해당 정류소에 노선이 경유하지 않습니다.' in 폐지
    assert ">이번 노선개편에서" not in 폐지   # 사유는 칸에 안 적힌다

    이전 = fragment(site, 송정93)
    assert '<td class="dropped">옥동차량기지</td>' in 이전
    assert 'title="평동산단방향 광산생활환경종합센터(약100m)로 이전합니다."' in 이전
    assert '">이전</td>' in 이전
    assert ">평동산단방향" not in 이전


def test_신설_CSV의_정류장은_개편_후에만_있는_줄에_적힌다(site: Path) -> None:
    html = fragment(site, 문흥80)
    assert '<td class="added"></td><td class="added">백운광장역2번출구</td>' in html
    assert ">신설 정류소</td>" in html


def test_비고에_상태_문구는_적지_않는다(site: Path) -> None:
    """상태는 줄 색과 요약 칸이 말한다 (ADR-0003 2026-09-03 개정). 205개 표 전수."""
    for path, 비고 in notes(site):
        assert not any(말 in 비고 for 말 in ("유지", "경유 제외", "경유 추가")), path


def test_통폐합은_흡수된_쪽이_개편_전_열에_나오는_줄에_붙는다(site: Path) -> None:
    """통폐합 CSV의 「A(B)」는 B가 A에 흡수된 것 — 「오치한전(오치한전(북))」은 오치한전(북)이 오치한전에
    (architecture §7-3 Q3). 비고는 B가 개편 전 열에 나오는 줄에 붙고 사유 문장은 title이다."""
    html = fragment(site, 운림54)
    줄 = next(r for r in rows(html) if ">오치한전(북)<" in r)
    assert '<td class="dropped">오치한전(북)</td>' in 줄
    assert ">통폐합: 오치한전에 흡수</td>" in 줄
    assert 'title="정류소간 거리가 짧아(약 120m) 통합운영합니다."' in 줄


def test_통폐합_CSV와_노선안이_어긋나도_노선안을_고쳐_읽지_않는다(site: Path) -> None:
    """서방사거리육교는 통폐합 CSV가 계림사거리에 흡수·폐지됐다고 적었지만 개편 후 노선안(간선19·간선39
    ·419)에 그대로 있다. 정류장 목록의 출처는 노선안 하나이므로 그 줄은 「유지」인 채 비고만 붙는다 —
    두 공표 자료가 어긋난다는 것을 그대로 보인다(architecture §7-3 Q3)."""
    줄 = next(r for r in rows(fragment(site, 매월06)) if ">서방사거리육교<" in r)
    assert '<td class="dropped">서방사거리육교</td>' in 줄
    assert ">통폐합: 계림사거리에 흡수</td>" in 줄

    유지줄 = [
        r
        for path in site.rglob("*.html")
        for r in rows(path.read_text(encoding="utf-8"))
        if 'class="kept">서방사거리육교' in r
    ]
    assert 유지줄, "개편 후 노선안에 남은 서방사거리육교가 「유지」 줄로 나와야 한다"
    assert all(">통폐합: 계림사거리에 흡수</td>" in r for r in 유지줄)


def test_통폐합_행이_A_B_꼴이_아니면_멈춘다() -> None:
    """비고를 짐작으로 붙이지 않는다 — 가를 수 없는 이름이면 빌드가 선다."""
    from tools.build.notes import split_absorbed

    assert split_absorbed("오치한전(오치한전(북))") == ("오치한전", "오치한전(북)")
    assert split_absorbed("계수초교(상무한국아파트)") == ("계수초교", "상무한국아파트")
    with pytest.raises(BuildError):
        split_absorbed("계수초교")


def test_한_줄에_사실이_둘이면_이어_적는다(site: Path) -> None:
    """줄 하나에 상행 칸과 하행 칸이 같이 있어 사실이 겹칠 수 있다. 어느 줄에서 겹치는지는 대조
    결과라 노선을 못 박지 않고, 두 사실이 " · "로 이어진 칸이 있는지만 본다."""
    겹친_칸 = [비고 for _, 비고 in notes(site) if 비고.count("명칭 변경: ") == 2]
    assert 겹친_칸, "두 사실이 한 칸에 모인 줄이 하나도 없다 — 잇지 않고 덮어썼을 수 있다"
    assert all(" · " in 비고 for 비고 in 겹친_칸)


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


def test_기종점_정렬표는_18행이고_확인_열이_다_차_있다() -> None:
    # 2026-09-04 확인: 18쌍 모두 겹침이 0~9곳뿐이라 방향이 표를 거의 안 바꾼다(architecture §7-3 Q4)
    with io.open(ALIGN_TABLE, encoding="utf-8-sig", newline="") as f:
        표 = list(csv.DictReader(f))
    assert len(표) == 18
    assert {r["개편전상행이맞닿는쪽"] for r in 표} <= {"상행", "하행"}
    assert all(r["확인"].strip() for r in 표)


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


def test_같은_정류장의_통폐합_행이_서로_다른_말을_하면_멈춘다(tmp_path: Path) -> None:
    """ID 단위라 같은 이름이 두 행인 것은 정상이지만, 구분이 갈리면 어느 쪽을 적을지 못 고른다."""
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    표 = data / "source" / "통폐합이전정류소.csv"
    줄 = 표.read_text(encoding="utf-8-sig").splitlines()
    # 계림사거리는 ID가 둘이라 두 행이다. 그 중 한 행의 구분만 바꿔 서로 다른 말을 하게 만든다
    바뀐 = [줄[0], 줄[1].replace(",통폐합,", ",폐지,"), *줄[2:]]
    assert 바뀐[1] != 줄[1]
    write_bom_csv(표, 바뀐)

    끝 = run_cli(data, tmp_path / "out")
    assert 끝.returncode == 1
    assert "계림사거리(서방사거리육교)" in 끝.stderr


def test_같은_정류장을_두_곳에_흡수시키면_멈춘다(tmp_path: Path) -> None:
    """정류소명이 행마다 달라 위 검사에는 안 걸리지만, 흡수된 쪽(B)이 같으면 어느 곳에 흡수됐다고
    적을지 우리가 고를 수 없다."""
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    표 = data / "source" / "통폐합이전정류소.csv"
    줄 = 표.read_text(encoding="utf-8-sig").splitlines()
    바뀐 = [줄[0], 줄[1].replace("계림사거리(", "서방사거리("), *줄[2:]]
    assert 바뀐[1] != 줄[1]
    write_bom_csv(표, 바뀐)

    끝 = run_cli(data, tmp_path / "out")
    assert 끝.returncode == 1
    assert "서방사거리육교" in 끝.stderr


def test_입력이_든_자리는_출력으로_받아도_지우지_않는다(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    with pytest.raises(BuildError):
        build(data / "source", data, tmp_path / "data.json")
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
    # 품은 표는 조각과 같은 표다 — 수치도 test_상행_하행_요약_칸_여섯과 같아야 한다(명칭 사전 적용값)
    for 개수 in ("49곳", "9곳", "3곳", "52곳", "10곳", "4곳"):
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
    assert "노선 사라짐" in html
    assert "<table" not in html
    assert "hx-get" not in html
    assert "대덕" in html   # 개편 전 정류장 목록은 있다


def test_카드가_가리키는_조각_주소에_파일이_다_있다(site: Path) -> None:
    """카드의 `hx-get`은 두 갈래다 — 정적 조각과 Worker 경로. 갈래마다 다른 것을 본다.

    표 조각(`route/…`)은 빌드가 쓴 **파일**이라 파일이 있어야 하고, 배차간격(`/headway/…`)은
    Worker가 그때 만드는 **경로**라 파일이 없다(ADR-0011). 그쪽은 가리키는 노선이 배차간격 표에
    실제로 있는지를 본다 — 없는 번호를 가리키면 카드에 「계산중…」이 영영 남는다.
    """
    import json
    from urllib.parse import unquote

    노선 = json.loads((site / "headway.json").read_text(encoding="utf-8"))["노선"]
    버튼_없는_카드 = []
    배차_자리 = 0
    for path in site.glob("route/*.html"):
        주소 = re.findall(r'hx-get="([^"]+)"', path.read_text(encoding="utf-8"))
        if not 주소:
            버튼_없는_카드.append(path.stem)
        for url in 주소:
            if url.startswith(HEADWAY_PREFIX):
                이름 = unquote(url[len(HEADWAY_PREFIX):])
                assert 이름 in 노선, f"{path.name} → {url} (배차간격 표에 없는 노선)"
                배차_자리 += 1
                continue
            assert (site / url).exists(), f"{path.name} → {url}"
    assert 버튼_없는_카드 == ["두암181"]   # 고를 것이 없는 번호는 이 하나뿐이다
    assert 배차_자리 > 0, "배차간격 자리가 하나도 없다"


def test_배차간격_주소만_Worker로_간다(site: Path) -> None:
    """정적 자산으로 나가는 주소와 Worker가 받는 주소가 섞이면 배포 설정이 조용히 어긋난다.

    `wrangler.jsonc`의 `run_worker_first`에 적힌 것만 Worker가 받는다. 카드가 그 밖의 절대 경로를
    가리키면 정적 자산 쪽으로 가서 404가 된다.
    """
    import json

    무늬 = json.loads(
        re.sub(r"^\s*//.*$", "", (ROOT / "wrangler.jsonc").read_text(encoding="utf-8"), flags=re.M)
    )["assets"]["run_worker_first"]
    for path in site.glob("route/*.html"):
        for url in re.findall(r'hx-get="([^"]+)"', path.read_text(encoding="utf-8")):
            if not url.startswith("/"):
                continue   # 표 조각은 상대 경로다
            assert any(
                url.startswith(p[:-1]) if p.endswith("*") else url == p for p in 무늬
            ), f"{path.name} → {url} 은 Worker가 안 받는다"


def test_화면_문구에_옛_용어가_없다(site: Path) -> None:
    for path in site.rglob("*.html"):
        글 = path.read_text(encoding="utf-8")
        for 옛말 in ("기존", "신규", "현행"):
            assert 옛말 not in 글, f"{path.name}에 「{옛말}」"


def index(site: Path) -> str:
    return (site / "index.html").read_text(encoding="utf-8")


def list_rows(html: str) -> list[str]:
    본문 = re.search(r'<tbody class="reform">(.*?)</tbody>', html, re.S)
    assert 본문, "목록 표의 본문을 못 찾았습니다"
    return re.findall(r"<tr\b.*?</tr>", 본문.group(1), re.S)


def list_row(html: str, number: str) -> str:
    for 줄 in list_rows(html):
        if f'hx-get="route/{number}.html"' in 줄:
            return 줄
    raise AssertionError(f"목록에 {number} 줄이 없습니다")


def test_껍데기에_제목과_탭_둘과_목록_제목이_있다(site: Path) -> None:
    html = index(site)
    for 문구 in ("버스개편 비교", "장소로 찾기", "노선번호로 찾기", "노선번호 개편안"):
        assert 문구 in html


def test_목록은_103줄이고_줄마다_카드를_겨눈다(site: Path) -> None:
    html = index(site)
    줄 = list_rows(html)
    assert len(줄) == 103
    assert 'hx-get="route/문흥18.html"' in html
    assert all('hx-target="#result"' in r for r in 줄)


def test_목록_줄은_눌리는_것으로_읽히고_끼운_자리를_보여_준다(site: Path) -> None:
    """마우스가 없는 사람도 줄을 누를 수 있어야 하고, 카드가 화면 밖에서 바뀌면 안 된다."""
    줄 = list_row(index(site), "문흥18")
    assert 'role="button"' in 줄 and 'tabindex="0"' in 줄
    assert "keyup[key=='Enter']" in 줄 and "keyup[key==' ']" in 줄
    assert 'hx-swap="innerHTML show:top"' in 줄
    assert 'aria-label="문흥18 — 간선18, 지선10"' in 줄
    assert 'aria-label="두암181 — 노선 사라짐"' in list_row(index(site), "두암181")


def test_노선번호_입력칸은_후보_목록을_달고_고르면_카드_조각을_부른다(site: Path) -> None:
    """자동완성 후보는 <datalist> 103개 — 값은 번호, 설명은 대체 노선(§7-3 Q1·Q2)."""
    html = index(site)
    입력칸 = re.search(r'<input id="number"[^>]*>', html)
    assert 입력칸, "노선번호 입력칸을 못 찾았습니다"
    칸 = 입력칸.group(0)
    assert "disabled" not in 칸
    assert 'list="route-numbers"' in 칸 and 'name="number"' in 칸
    assert 'hx-ext="path-params"' in 칸 and 'hx-get="route/{number}.html"' in 칸
    assert 'hx-target="#result"' in 칸 and 'hx-trigger="change"' in 칸
    후보 = re.findall(r'<option value="([^"]*)" label="([^"]*)">', html)
    assert len(후보) == 103
    assert ("문흥18", "간선18 · 지선10") in 후보
    assert ("지원152", "급행1003 · 228") in 후보
    assert ("두암181", "노선 사라짐") in 후보
    # 후보 순서는 목록 표 순서 그대로다 — 같은 번호를 두 곳이 다르게 적는 일이 없다
    번호 = [re.search(r"route/(.*?)\.html", 줄).group(1) for 줄 in list_rows(html)]
    assert [값 for 값, _ in 후보] == 번호


def test_껍데기의_스크립트는_htmx와_확장과_우리_스크립트_둘뿐이다(site: Path) -> None:
    """확장은 htmx 뒤에 와야 켜진다. 우리 스크립트는 장소 탭 place.js와 두 탭 공용 map.js 둘이다(§7-3 Q1)."""
    태그 = re.findall(SCRIPT_TAG, index(site))
    assert len(태그) == 4
    htmx태그, 확장태그, 장소태그, 지도태그 = 태그
    assert "htmx.org" in htmx태그
    assert "htmx-ext-path-params" in 확장태그
    assert 'integrity="sha384-' in 확장태그   # CDN이 다른 파일을 내주면 아예 싣지 않는다
    assert 'src="place.js"' in 장소태그
    assert 'src="map.js"' in 지도태그
    assert (site / "map.js").exists()


def test_Kakao_JS_키가_없으면_지도_SDK를_안_싣는다(site: Path) -> None:
    """JS 키는 리포에 없다(ADR-0005). 없는 채로 빌드하면 태그가 아예 없고 지도만 안 뜬다."""
    assert "dapi.kakao.com" not in index(site)
    assert "appkey" not in index(site)


def test_Kakao_JS_키를_주면_그_키로_SDK_태그가_박힌다(tmp_path: Path) -> None:
    build(SOURCE, tmp_path / "out", tmp_path / "data.json", kakao_js_key="열쇠값")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    태그 = [줄 for 줄 in re.findall(SCRIPT_TAG, html) if "dapi.kakao.com" in 줄]
    assert len(태그) == 1
    assert "appkey=%EC%97%B4%EC%87%A0%EA%B0%92" in 태그[0]
    assert "autoload=false" in 태그[0]   # `defer`로 싣기 때문에 `map`이 직접 기다린다


def test_지도_스크립트는_좌표_배열만_받는다(site: Path) -> None:
    """두 탭이 같은 그리는 함수를 쓴다(이슈 #27). 선과 점을 따로 받는다(2026-09-04)."""
    script = (site / "map.js").read_text(encoding="utf-8")
    assert "window.busMap" in script
    assert "function draw(자리, 그림)" in script
    # 탭마다 좌표 조각을 그림으로 옮기는 순수 함수. 그리는 일은 여전히 `draw` 하나가 한다
    assert "function journey(경로들, 형상표)" in script
    assert "function route(geometry)" in script


def test_목록_표는_다섯_줄만_펼쳐지고_나머지는_접혀_있다(site: Path) -> None:
    """103줄이 다 서면 목록이 화면을 다 먹어 결과가 어디에 떴는지 안 보인다(2026-09-04).

    줄을 덜어 내지는 않는다 — 표에 103줄이 다 있고 CSS가 여섯째 줄부터 감춘다. 열 너비가 접기
    전후로 안 흔들리고 브라우저의 「페이지에서 찾기」도 접힌 줄을 찾는다.
    """
    html = index(site)
    assert '<input type="checkbox" id="route-list-all" class="list-toggle">' in html
    assert '<span class="shut">나머지 98개 더 보기</span>' in html
    assert '<span class="open">접기</span>' in html
    assert html.count('<tr hx-get="route/') == 103, "줄은 다 실린다"

    css = (site / "site.css").read_text(encoding="utf-8")
    assert ".reform-list tbody tr:nth-child(n + 6) { display: none; }" in css
    assert "#route-list-all:checked ~ .reform-list tbody tr:nth-child(n + 6)" in css
    # 접기는 우리 스크립트를 늘리지 않는다(ADR-0001) — 탭 전환과 같은 수법이다
    assert "route-list-all" not in (site / "map.js").read_text(encoding="utf-8")
    assert "route-list-all" not in (site / "place.js").read_text(encoding="utf-8")

def test_첫_화면은_장소_탭이다(site: Path) -> None:
    """시민이 먼저 묻는 것은 「내 길이 어떻게 달라지나」다(2026-09-04)."""
    html = index(site)
    assert 'id="tab-place" class="tab-toggle" checked' in html
    assert 'id="tab-route" class="tab-toggle">' in html


def test_예시_검색_셋이_실제_정류장_자리를_가리킨다(site: Path) -> None:
    """예시는 첫 화면에서 눌러 볼 것을 준다. 좌표는 지어내지 않는다(ADR-0007).

    이름은 시민이 부르는 말이고(「유스퀘어」·「첨단지구」) 좌표는 `stops.csv`에 실제로 있는 줄이다.
    둘이 정확히 같은 곳을 가리킬 필요는 없다 — 장소 탭은 좌표로 비교하고, 타고 내릴 정류장은
    도보권 안에서 엔진이 고른다.
    """
    html = index(site)
    단추 = re.findall(
        r'<button type="button" class="example" data-from="([^"]+)" data-from-name="([^"]+)"'
        r' data-to="([^"]+)" data-to-name="([^"]+)">([^<]+)</button>',
        html,
    )
    assert [b[4] for b in 단추] == [
        "유스퀘어 → 전남대",
        "금남로4가역 → 첨단지구",
        "조선대 → 수완지구",
    ]

    자리 = {
        (r["LATITUDE"], r["LONGITUDE"])
        for r in csv.DictReader(io.open(SOURCE / "stops.csv", encoding="utf-8-sig"))
    }
    for 프롬, _, 투, _, 이름 in 단추:
        for 점 in (프롬, 투):
            assert tuple(점.split(",")) in 자리, f"{이름}의 {점}이 stops.csv에 없다"

def test_목록_줄에_대체_노선_이름이_적힌다(site: Path) -> None:
    html = index(site)
    문흥18줄 = list_row(html, "문흥18")
    assert "간선18" in 문흥18줄 and "지선10" in 문흥18줄
    순환01줄 = list_row(html, "순환01")
    assert "간선01" in 순환01줄 and "간선11" in 순환01줄
    assert "노선 사라짐" in list_row(html, "두암181")


def test_목록이_가리키는_카드_파일이_다_있다(site: Path) -> None:
    # 입력칸의 `route/{number}.html`은 틀이라 뺀다 — 값이 들어가야 주소가 된다
    주소 = [u for u in re.findall(r'hx-get="(route/[^"]+)"', index(site)) if "{" not in u]
    assert len(주소) == 103
    for url in 주소:
        assert (site / url).exists(), url


def test_껍데기는_htmx와_CSS_한_장을_부른다(site: Path) -> None:
    html = index(site)
    assert 'href="site.css"' in html
    assert html.count('<link rel="stylesheet"') == 1
    assert "htmx.org" in html
    assert 'integrity="sha384-' in html   # CDN이 다른 파일을 내주면 아예 싣지 않는다
    assert (site / "site.css").exists()


def test_두_탭의_입력칸이_자리를_잡고_결과_영역은_비어_있다(site: Path) -> None:
    html = index(site)
    assert "노선번호 입력 (예: 지원152)" in html
    assert html.count("장소나 주소 입력 (예: 전남대)") == 2   # 출발·도착
    assert 'id="result"' in html
    assert "route-change" not in html   # 카드는 아직 안 끼워져 있다


def test_장소_입력칸_둘은_자동완성을_부르고_후보를_고르면_비교를_요청한다(site: Path) -> None:
    html = index(site)
    assert html.count('hx-get="/places"') == 2
    assert html.count('hx-trigger="keyup changed delay:250ms"') == 2
    장소칸 = [줄 for 줄 in html.splitlines() if "장소나 주소 입력 (예: 전남대)" in 줄]
    assert all("disabled" not in 줄 for 줄 in 장소칸)
    assert "장소로 찾기는 아직 준비 중입니다" not in html
    assert 'id="from-candidates"' in html
    assert 'id="to-candidates"' in html
    assert 'id="place-result"' in html
    assert (site / "place.js").exists()
    script = (site / "place.js").read_text(encoding="utf-8")
    assert "/compare?" in script
    # 좌표뿐 아니라 고른 장소의 **이름**도 보낸다 — 카드 경로 줄의 양 끝이 「출발 지점」이 아니라
    # 시민이 고른 곳이 되게 (CONTEXT 「경로 줄」)
    for 칸 in ("from:", "to:", "fromName:", "toName:"):
        assert 칸 in script, 칸


# ── 노선 지도 (③ #36) ─────────────────────────────────────────────────────────

GEOMETRY_RE = re.compile(
    r'<script type="application/json" class="route-geometry">(.*?)</script>', re.S
)
# 좌표가 없는 것이 확인된 이름 둘 — 신설 정류소와 `name_canon.json`이 `null`이라 적은 것
좌표_없는_정류장 = {"광주교대역1번출구", "광주교대역2번출구"}


def geometry(html: str) -> dict:
    """조각 하나에 실린 노선 지도 좌표 JSON."""
    실린_것 = GEOMETRY_RE.search(html)
    assert 실린_것, "노선 지도 좌표 JSON을 못 찾았습니다"
    return json.loads(실린_것.group(1))


def geometries(site: Path) -> list[tuple[Path, dict]]:
    return [
        (path, geometry(path.read_text(encoding="utf-8")))
        for path in site.glob("route/*/*/*/*.html")
    ]


def test_표_조각_205개가_모두_노선_지도_좌표를_싣는다(site: Path) -> None:
    실린_것 = geometries(site)
    assert len(실린_것) == 205
    for path, g in 실린_것:
        assert set(g) == {"before", "after", "stops", "missing"}, path
        assert g["before"] and g["after"], path
        assert all(len(점) == 2 for 점 in g["before"] + g["after"]), path


def _미터(a: tuple[float, float], b: tuple[float, float]) -> float:
    """광주 한 도시 안이라 위경도를 평면으로 놓고 재도 충분하다(`route_geometry.metres`와 같다)."""
    dy = (a[0] - b[0]) * 111_000
    dx = (a[1] - b[1]) * 111_000 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def test_문흥18_지도는_선_둘과_점_61개다(site: Path) -> None:
    """상행만 그린다(§7-3 Q7). 점은 대조 줄에서 나오므로 요약 칸 수치와 같아야 한다.

    선은 정류장 직선이 아니라 차도 경로다(ADR-0009). 그래서 꼭짓점이 정류장보다 많다 —
    정류장 사이의 굽이가 선에 들어 있기 때문이다.
    """
    g = geometry(fragment(site, 문흥18))
    assert len(g["before"]) > 58           # 문흥18 상행 58곳보다 꼭짓점이 많다
    assert len(g["after"]) > 52            # 간선18 하행 52곳(뒤집어 맞댄 쪽)
    assert len(g["stops"]) == 61
    assert Counter(s["state"] for s in g["stops"]) == {"유지": 49, "경유 제외": 9, "경유 추가": 3}
    assert g["missing"] == 0


def test_뒤집힌_쌍의_대체_노선_선은_하행_순서로_그린다(site: Path) -> None:
    """하남고등학교는 간선18의 기점이다. 뒤집어 맞댔으니 대체 노선 선의 끝에 와야 한다.

    선이 차도 경로라 정류장을 정확히 밟지는 않는다(ADR-0009). 끝이 그 정류장 **곁**인지를 본다.
    """
    g = geometry(fragment(site, 문흥18))
    하남 = next(s for s in g["stops"] if s["name"] == "하남고등학교")
    끝점 = (하남["lat"], 하남["lng"])
    assert _미터(tuple(g["after"][-1]), 끝점) < 100
    assert _미터(tuple(g["after"][0]), 끝점) > 1000


def test_유지와_경유_제외는_개편_전_선_곁_경유_추가는_개편_후_선_곁이다(site: Path) -> None:
    """점은 정류장 좌표(사실), 선은 차도 경로(추정)라 겹치지 않는다(ADR-0009 결정 1).

    그래도 **그 선이 그 정류장을 지나가야** 한다 — 상태마다 어느 선 곁인지가 갈린다.
    """
    g = geometry(fragment(site, 문흥18))
    for s in g["stops"]:
        선 = g["after"] if s["state"] == "경유 추가" else g["before"]
        가장 = min(_미터(tuple(꼭짓점), (s["lat"], s["lng"])) for 꼭짓점 in 선)
        assert 가장 < 150, s


def test_좌표_없는_정류장은_건너뛰고_개수를_센다(site: Path) -> None:
    """순환01 ↔ 간선01의 광주교대역1번출구는 좌표가 없다. 지어내지 않고 앞뒤를 잇는다."""
    html = fragment(site, 순환01)
    g = geometry(html)
    assert g["missing"] == 1
    assert len(g["stops"]) == 79   # 대조 줄 80개에서 하나가 빠졌다
    assert "좌표 없는 정류장 1곳은 지도에 없습니다" in html


def test_좌표를_지어내지_않는다(site: Path) -> None:
    """신설 정류소와 `name_canon.json`이 `null`이라 적은 이름은 점이 되지 않는다(ADR-0007).

    추정 좌표는 장소 탭 계산 전용이라 지도에는 오지 않는다. 205개 표 전수.
    """
    빠진_표 = 0
    for path, g in geometries(site):
        assert not ({s["name"] for s in g["stops"]} & 좌표_없는_정류장), path
        빠진_표 += bool(g["missing"])
    assert 빠진_표 == 85   # 205개 중 좌표 없는 정류장이 있는 표


상행_줄_RE = re.compile(
    r'<td class="index">\d+</td>'
    r'<td class="(kept|dropped|added)">([^<]*)</td><td class="\1">([^<]*)</td>'
)


def 지도에_설_이름(html: str) -> set[str]:
    """표의 상행 줄이 지도에 점으로 세울 정류장 이름들.

    경유 추가는 개편 후 칸, 유지·경유 제외는 개편 전 칸의 이름이다(§7-3 Q6). 상행이 먼저 끝난
    줄은 두 칸이 비어 있어 여기 걸리지 않는다.
    """
    return {
        unescape(개편_후 if 상태 == "added" else 개편_전)
        for 상태, 개편_전, 개편_후 in 상행_줄_RE.findall(html)
    }


def test_그리지_못한_정류장은_반드시_센다(site: Path) -> None:
    """조용히 흘린 정류장이 없다. `missing`은 **정류장 수**다 — 화면 문구가 「정류장 N곳」이라,
    한 노선이 같은 정류장을 두 번 지나도(지선92의 왕동저수지·내동·원당) 한 곳으로 센다."""
    for path, g in geometries(site):
        설_이름 = 지도에_설_이름(path.read_text(encoding="utf-8"))
        그려진 = {s["name"] for s in g["stops"]}
        assert 그려진 <= 설_이름, path
        assert g["missing"] == len(설_이름 - 그려진), path


def test_같은_정류장을_두_번_지나도_한_곳으로_센다(site: Path) -> None:
    """지선92는 왕동저수지·내동·원당을 두 번씩 지난다. 줄로 세면 8곳, 정류장으로 세면 6곳이다."""
    html = fragment(site, ("송정197", "기본", "지선92", "기본.html"))
    assert "좌표 없는 정류장 6곳은 지도에 없습니다" in html


def test_카드에_노선_지도_자리와_범례가_있다(site: Path) -> None:
    html = card(site, "문흥18")
    assert '<div class="route-map"' in html
    assert "초록 = 개편 전 노선, 파랑 = 개편 후 대체 노선" in html
    assert "회색점: 경유 유지, 빨강점: 경유 제외, 파랑점: 경유 추가" in html
    # 선이 추정이라는 한 줄도 함께 선다 (ADR-0009 결정 1)
    assert "실제 운행 경로와 다를 수 있습니다" in html
    assert "지도에 없습니다" not in html   # 문흥18 ↔ 간선18은 좌표가 다 있다


def test_좌표_없는_정류장이_있는_카드에는_그_줄이_따라온다(site: Path) -> None:
    """카드는 기본 표를 품으므로 그 표의 안내 줄도 함께 온다 — 표가 바뀌면 줄도 바뀐다."""
    assert "좌표 없는 정류장 1곳은 지도에 없습니다" in card(site, "순환01")


def test_대체_노선이_없는_카드에는_지도가_없다(site: Path) -> None:
    """두암181은 표가 없으니 그릴 좌표도 없다."""
    html = card(site, "두암181")
    assert "route-map" not in html
    assert "route-geometry" not in html


def test_map_js는_kakao가_없으면_조용히_끝난다(site: Path) -> None:
    """키 없이 배포해도 화면이 깨지지 않는다 — 지도 자리에 한 줄만 남는다."""
    script = (site / "map.js").read_text(encoding="utf-8")
    assert "지도를 불러오지 못했습니다" in script
    assert "htmx:afterSwap" in script
    assert "route-geometry" in script


def 사이_거리(a: list[float], b: list[float]) -> float:
    """두 좌표 사이 거리(m). 광주 한 도시 안이라 위경도를 평면으로 놓고 재도 충분하다."""
    return math.hypot(
        (a[1] - b[1]) * 111_000 * math.cos(math.radians(a[0])), (a[0] - b[0]) * 111_000
    )


def 가장_먼_이웃(g: dict) -> float:
    """선 둘에서 이웃한 두 점이 가장 멀리 벌어진 거리."""
    return max(
        [0.0]
        + [사이_거리(a, b) for 선 in (g["before"], g["after"]) for a, b in zip(선, 선[1:])]
    )


def test_같은_이름이_여러_곳이면_노선에_가까운_곳을_고른다(site: Path) -> None:
    """`stops.csv`는 광주와 전남을 함께 담아 「금곡마을」이 55km 떨어진 여섯 줄이다. 이름이 붙은
    줄을 다 평균 내면 아무 정류장도 없는 들판에 점이 찍히고 선이 왕복 50km를 튄다 — 그렇게 하면
    205개 표 중 130개에 3km 넘는 튐이 생겼다. 노선을 따라 가장 짧아지는 자리를 고른다.
    """
    벌어짐 = {path: 가장_먼_이웃(g) for path, g in geometries(site)}
    # 충효188 ↔ 지선187-1은 「금곡마을」 하나 때문에 31km를 튀었다
    충효 = site / "route" / "충효188" / "기본" / "지선187-1" / "기본.html"
    assert 벌어짐[충효] < 3_000

    # 남는 것은 진짜로 먼 구간뿐이다 — 나주·화순으로 곧장 가는 직행·급행, 그리고 좌표 없는
    # 정류장을 건너뛰어 이은 자리. 55km짜리 들판 점이 하나라도 있으면 여기서 걸린다
    먼_표 = {path.name: round(m) for path, m in 벌어짐.items() if m > 13_000}
    assert 먼_표 == {}
    assert sum(1 for m in 벌어짐.values() if m > 3_000) <= 23


def 부분_차례(작은: list, 큰: list) -> bool:
    """`작은`이 `큰`의 차례를 지키는 부분열인가."""
    남은 = iter(큰)
    return all(any(x == y for y in 남은) for x in 작은)


def test_점은_선_곁에_찍힌다(site: Path) -> None:
    """점과 선이 다른 것을 가리키면 점이 지도에서 길 밖으로 떨어진다. 205개 표 전수.

    선이 차도 경로가 된 뒤로 점은 선 **위**가 아니라 **곁**에 있다(ADR-0009). 그래도 모든 점이
    제 선에서 150m 안에 있어야 한다 — 그보다 멀면 선과 점이 서로 다른 노선을 그리고 있는 것이다.
    """
    for path, g in geometries(site):
        for s in g["stops"]:
            선 = g["after"] if s["state"] == "경유 추가" else g["before"]
            가장 = min(_미터(tuple(꼭짓점), (s["lat"], s["lng"])) for 꼭짓점 in 선)
            assert 가장 < 150, (path, s)
