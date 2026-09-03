"""아트보드(`docs/canvas/*.dc.html`) → PNG(`docs/images/*.png`).

전에는 아트보드가 세션 작업 파일에만 있어 「캔버스가 바뀌면 다시 뽑는다」를 사람이 손으로 했고,
그 원본이 사라지자 그림을 고칠 길이 없어졌다. 그래서 아트보드를 리포에 넣고 뽑는 일을 여기 적는다.

실행:  python tools/render_canvas.py [아트보드 파일 이름 …]
입력:  docs/canvas/canvas.json (아트보드 목록과 크기) · docs/canvas/*.dc.html
출력:  docs/images/*.png

크롬을 헤드리스로 띄워 창 크기 그대로 찍는다. 그림은 반응형일 까닭이 없으므로 크기는
`canvas.json`에 박아 두고 아트보드 CSS도 그 폭에 맞춘다. **찍기 전에 내용 높이를 재서 창보다 길면
멈춘다** — 잘린 PNG는 눈으로 봐야만 알 수 있고, 그러면 아무도 안 본다.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANVAS = ROOT / "docs" / "canvas"
IMAGES = ROOT / "docs" / "images"

# 이 PC에 실제로 있는 자리부터. 없으면 PATH에서 찾는다
크롬_후보 = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
)

# 내용이 창보다 이만큼 넘게 짧으면 흰 여백이 남았다는 뜻이라 알려 준다
여백_한도 = 40


def 크롬을_찾는다() -> str:
    for 자리 in 크롬_후보:
        if Path(자리).exists():
            return 자리
        찾은 = shutil.which(자리)
        if 찾은:
            return 찾은
    raise SystemExit("크롬을 못 찾았다. PATH에 넣거나 이 파일의 `크롬_후보`에 자리를 더한다")


def 크롬을_돌린다(크롬: str, 창: tuple[int, int], 주소: str, *더: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as 임시:
        return subprocess.run(
            [
                크롬,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                "--default-background-color=FFFFFFFF",
                f"--user-data-dir={임시}",
                f"--window-size={창[0]},{창[1]}",
                "--virtual-time-budget=3000",
                *더,
                주소,
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )


def 내용_높이(크롬: str, 아트보드: dict) -> int:
    """아트보드 내용의 실제 높이(px).

    재는 글을 붙인 사본을 **같은 자리에** 두었다가 지운다 — `canvas.css`가 상대 경로라
    다른 자리에 두면 스타일 없이 재게 되고, 그러면 높이가 엉뚱하게 나온다.
    """
    원본 = CANVAS / 아트보드["file"]
    사본 = CANVAS / f".{원본.stem}.measure.html"
    사본.write_text(
        원본.read_text(encoding="utf-8")
        + "\n<script>document.title="
        "String(Math.ceil(document.body.getBoundingClientRect().height))</script>",
        encoding="utf-8",
    )
    try:
        결과 = 크롬을_돌린다(크롬, (아트보드["w"], 1000), 사본.as_uri(), "--dump-dom")
    finally:
        사본.unlink()
    잰_값 = re.search(r"<title>(\d+)</title>", 결과.stdout)
    if not 잰_값:
        raise SystemExit(f"{원본.name}의 높이를 못 쟀다")
    return int(잰_값.group(1))


def 찍는다(크롬: str, 아트보드: dict) -> Path:
    나갈_곳 = IMAGES / 아트보드["png"]
    크롬을_돌린다(
        크롬,
        (아트보드["w"], 아트보드["h"]),
        (CANVAS / 아트보드["file"]).as_uri(),
        f"--screenshot={나갈_곳}",
    )
    return 나갈_곳


def main() -> None:
    고른_것 = set(sys.argv[1:])
    크롬 = 크롬을_찾는다()
    목록 = json.loads((CANVAS / "canvas.json").read_text(encoding="utf-8"))["artboards"]
    골라진 = [a for a in 목록 if not 고른_것 or a["file"] in 고른_것 or a["png"] in 고른_것]
    if not 골라진:
        raise SystemExit(f"그런 아트보드가 없다: {sorted(고른_것)}")

    잘린 = []
    for 아트보드 in 골라진:
        if not (CANVAS / 아트보드["file"]).exists():
            raise SystemExit(f"{CANVAS / 아트보드['file']}이 없다")
        높이 = 내용_높이(크롬, 아트보드)
        찍은 = 찍는다(크롬, 아트보드)
        말 = f"{아트보드['png']}  {아트보드['w']}×{아트보드['h']}  {찍은.stat().st_size // 1024}KB"
        if 높이 > 아트보드["h"]:
            잘린.append((아트보드, 높이))
            말 += f"  [잘림] 내용 {높이}px — 아래 {높이 - 아트보드['h']}px가 안 찍혔다"
        elif 아트보드["h"] - 높이 > 여백_한도:
            말 += f"  · 내용 {높이}px (흰 여백 {아트보드['h'] - 높이}px)"
        print(말)

    if 잘린:
        줄 = " · ".join(f"{a['file']} → h를 {h}로" for a, h in 잘린)
        raise SystemExit(f"canvas.json의 h를 고치고 다시 돌린다: {줄}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
