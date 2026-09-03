"""광주 BIS 정류소 목록을 받아 data/back_up/api_stops.json으로 저장한다.

키는 .env의 GWANGJU_BUS_KEY(Decoding 키). 커밋하지 않는다(ADR-0005).
    python tools/fetch_stops.py
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "back_up" / "api_stops.json"

# 순서대로 시도한다. 첫 번째가 광주 BIS 자체 포털, 두 번째가 data.go.kr 경유.
ENDPOINTS = (
    ("http://api.gwangju.go.kr/json/stationInfo", "ServiceKey"),
    ("http://apis.data.go.kr/6290000/busStationService/getStationList", "serviceKey"),
)


def load_key() -> str:
    key = os.environ.get("GWANGJU_BUS_KEY")
    if key:
        return key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GWANGJU_BUS_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit(".env에 GWANGJU_BUS_KEY=<Decoding 키>를 넣어라")


def fetch(url: str, param: str, key: str) -> dict:
    qs = urllib.parse.urlencode({param: key, "numOfRows": 5000, "pageNo": 1, "_type": "json"})
    req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
    if not body.lstrip().startswith(("{", "[")):
        raise ValueError(f"JSON이 아님: {body[:300]}")
    return json.loads(body)


def main() -> None:
    key = load_key()
    for url, param in ENDPOINTS:
        print(f"시도: {url}")
        try:
            data = fetch(url, param, key)
        except Exception as e:  # noqa: BLE001 — 다음 엔드포인트로 넘어간다
            print(f"  실패: {type(e).__name__} {e}")
            continue
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  성공 → {OUT}")
        print(json.dumps(data, ensure_ascii=False)[:800])
        return
    sys.exit("모든 엔드포인트 실패")


if __name__ == "__main__":
    main()
