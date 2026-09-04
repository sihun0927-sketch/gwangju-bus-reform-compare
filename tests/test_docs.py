"""CONTEXT.md 모듈 표가 코드와 갈리지 않는지 본다.

이름이 갈리면 문서가 거짓말을 한다 — 새 세션이 「`route_geometry`가 어디 있나」를 찾다 못 찾는다.
사람이 눈으로 대조하는 일은 두 번째부터 안 하게 되므로 검사로 박는다.

보는 것은 표의 **첫 칸(코드 이름)**과 파일뿐이다. 표의 설명 문장까지는 검사하지 않는다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTEXT = ROOT / "CONTEXT.md"

# 모듈 하나가 사는 자리. 빌드 모듈은 파이썬, Worker와 브라우저 스크립트는 JS다
자리들 = (ROOT / "tools" / "build", ROOT / "worker")
확장자들 = (".py", ".js")


def 코드_이름들() -> list[str]:
    """「모듈 이름」 절의 표 첫 칸에 적힌 이름 전부."""
    글 = CONTEXT.read_text(encoding="utf-8")
    시작 = 글.index("**모듈 이름 (module names)**")
    return re.findall(r"^\| `([a-z_]+)` \|", 글[시작:], flags=re.MULTILINE)


def 파일이_있나(이름: str) -> bool:
    return any((자리 / f"{이름}{확장}").exists() for 자리 in 자리들 for 확장 in 확장자들)


def test_모듈_표의_이름은_전부_있는_파일이다() -> None:
    이름들 = 코드_이름들()
    # 표 둘(빌드 스크립트·Worker)을 다 읽었다는 것부터 확인한다 — 정규식이 빗나가면 0건이 통과한다
    assert len(이름들) >= 18, 이름들
    없는 = [이름 for 이름 in 이름들 if not 파일이_있나(이름)]
    assert not 없는, f"CONTEXT.md 모듈 표에 있는데 코드에 없는 이름: {없는}"


def test_compare의_안_다섯도_있는_파일이다() -> None:
    """표 아래 문장이 세는 `compare`의 안 다섯 — 여기도 같은 이름이라야 한다."""
    글 = CONTEXT.read_text(encoding="utf-8")
    문장 = 글[글.index("`compare`의 안은 다섯으로 나뉜다") :].split("\n\n")[0]
    # 화살표로 이은 다섯만 고른다 — 뒤에 괄호로 하는 일을 적은 것이 그 다섯이다. 같은 문단의
    # `route_links`는 번들의 표 이름이지 모듈이 아니라 괄호가 안 붙는다
    다섯 = re.findall(r"`([a-z_]+)`\(", 문장)
    assert len(다섯) == 5, 다섯
    없는 = [이름 for 이름 in 다섯 if not 파일이_있나(이름)]
    assert not 없는, f"`compare`의 안인데 코드에 없는 이름: {없는}"
