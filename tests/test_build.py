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
노선1187 = ("1187", "기본", "1187", "기본.html")
문흥80 = ("문흥80", "기본", "간선80", "기본.html")
송정93 = ("송정93", "기본", "지선93", "기본.html")
운림54 = ("운림54", "기본", "간선54", "기본.html")


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
    (architecture §7-3 Q3). 비고는 B가 개편 전 열에 있는 줄에, 사유는 title에."""
    html = fragment(site, 운림54)
    줄 = next(r for r in rows(html) if ">오치한전(북)<" in r)
    assert '<td class="dropped">오치한전(북)</td>' in 줄
    assert ">통폐합: 오치한전에 흡수</td>" in 줄
    assert 'title="정류소간 거리가 짧아(약 120m) 통합운영합니다."' in 줄


def test_통폐합_CSV와_노선안이_어긋나도_노선안을_고쳐_읽지_않는다(site: Path) -> None:
    """서방사거리육교는 통폐합 CSV가 계림사거리에 흡수·폐지됐다고 적었지만 개편 후 노선안(간선19·간선39·419)에
    그대로 있다. 그 줄은 「유지」인 채로 비고만 붙는다 — 두 공표 자료가 어긋난다는 것을 그대로 보인다."""
    html = fragment(site, ("매월06", "기본", "간선06", "기본.html"))
    줄 = next(r for r in rows(html) if ">서방사거리육교<" in r)
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
    assert 'aria-label="두암181 — 대체 노선 없음"' in list_row(index(site), "두암181")


def test_노선번호_입력칸은_후보_목록을_달고_고르면_카드_조각을_부른다(site: Path) -> None:
    """자동완성 후보는 <datalist> 103개 — 값은 번호, 설명은 대체 노선(§7-3 Q1·Q2). 우리 스크립트는 없다."""
    html = index(site)
    입력칸 = re.search(r'<input id="number"[^>]*>', html).group(0)
    assert "disabled" not in 입력칸
    assert 'list="route-numbers"' in 입력칸 and 'name="number"' in 입력칸
    assert 'hx-ext="path-params"' in 입력칸 and 'hx-get="route/{number}.html"' in 입력칸
    assert 'hx-target="#result"' in 입력칸 and 'hx-trigger="change"' in 입력칸
    후보 = re.findall(r'<option value="([^"]*)" label="([^"]*)">', html)
    assert len(후보) == 103
    assert ("지원152", "간선18 · 지선10") in 후보 or ("문흥18", "간선18 · 지선10") in 후보
    assert ("두암181", "대체 노선 없음") in 후보
    assert [n for n, _ in 후보] == [re.search(r'route/(.*?)\.html', r).group(1) for r in list_rows(html)]
    assert "htmx-ext-path-params" in html and 'integrity="sha384-' in html


def test_목록_줄에_대체_노선_이름이_적힌다(site: Path) -> None:
    html = index(site)
    문흥18줄 = list_row(html, "문흥18")
    assert "간선18" in 문흥18줄 and "지선10" in 문흥18줄
    순환01줄 = list_row(html, "순환01")
    assert "간선01" in 순환01줄 and "간선11" in 순환01줄
    assert "대체 노선 없음" in list_row(html, "두암181")


def test_목록이_가리키는_카드_파일이_다_있다(site: Path) -> None:
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
    assert 'disabled' not in html
    assert "장소로 찾기는 아직 준비 중입니다" not in html
    assert 'id="from-candidates"' in html
    assert 'id="to-candidates"' in html
    assert 'id="place-result"' in html
    assert (site / "place.js").exists()
    script = (site / "place.js").read_text(encoding="utf-8")
    assert "/compare?from=" in script
