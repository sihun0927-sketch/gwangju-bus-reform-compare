/**
 * 경로 지도의 라벨 겹침 실측 (이슈 #68 · ADR-0010의 근거).
 *
 * 재는 것은 **화면에 남은 라벨끼리 겹친 쌍의 수**다. 이슈 #68이 라이브 브라우저 콘솔에서 세던
 * 그 셈을 그대로 여기서 돌린다 — 라벨 상자를 글자 수로 어림하지 않고 진짜 브라우저가 잰다.
 *
 * 실행:  node tools/measure_labels.mjs [쌍 수] [--ref <git 참조>] [--png <파일>] [--width <px>]
 *                                        [--only <번호>]  ← 그 한 장만 그린다(그림 찍을 때)
 * 입력:  worker/data.json · out/site.css · out/map.js (먼저 `python -m tools.build`)
 * 출력:  지도마다 「라벨 수 · 겹친 쌍 · 감춘 수」와 그 합계
 *
 * **그리는 코드는 배포본 그대로다.** `out/map.js`와 `out/site.css`를 그대로 실어 헤드리스 크롬에
 * 띄우고, 좌표는 진짜 Worker의 `/compare` 답에서 뽑는다. 가짜는 **타일과 투영뿐**이다 —
 * Kakao SDK 자리에 최소한의 대역(지도·오버레이·선·`idle`)을 세운다. 그래서 이 값은 라이브와
 * 같은 코드가 낸 값이되 **타일 위 실측은 아니다**. 두 가지가 라이브와 다를 수 있다:
 *
 *   1. 배율 — `setBounds`를 슬리피 맵처럼 **2의 거듭제곱 단계**로 맞춘다. 진짜 Kakao도 단계로
 *      맞추지만 단계의 절대값이 우리 것과 같다는 보장은 없다. 단계가 한 칸 낮으면 점 사이가
 *      최대 절반으로 좁아지므로 이 값은 **라이브보다 빡빡한 쪽**으로 치우친다.
 *   2. 글꼴 — 이 PC의 글꼴로 잰다. 라벨 폭은 글꼴에 따라 몇 px 달라진다.
 *
 * `--ref`를 주면 그 참조의 `tools/build/map.js`·`site.css`로 잰다. 고치기 전(`--ref develop`)과
 * 고친 뒤를 **같은 자와 같은 좌표로** 견주는 자리다.
 */
import { execFileSync, execSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import process from "node:process";
import { fileURLToPath, pathToFileURL } from "node:url";

import { 정류장_쌍 } from "./measure_pairs.mjs";
import worker from "../worker/index.js";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** 이슈 #68이 라이브에서 재던 그 쌍. 카카오가 준 장소 좌표를 그대로 적어 둔다 */
const 이슈_쌍 = {
  이름: "전남대학교 광주캠퍼스 → 광주송정역 관광안내소",
  from: { lat: 35.1757, lng: 126.9058 },
  to: { lat: 35.1395, lng: 126.7911 },
};

/** 기본 표본 수. 지도 40장이면 「겹침이 남은 지도」가 있는지 없는지는 갈린다 */
const DEFAULT_PAIRS = 40;

/** 화면 폭(px). 900px 껍데기에 좌우 여백 20px이라 지도는 860px이 된다 */
const DEFAULT_WIDTH = 900;

/* `tools/render_canvas.py`와 같은 목록이다. 크롬 자리는 PC마다 다르므로 여기 적어 둔다 */
const 크롬_후보 = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "google-chrome",
  "chromium",
];

/** 정적 자산 바인딩 대신 세우는 가짜. `/compare`는 여기로 안 간다 */
const env = { ASSETS: { fetch: () => new Response("") } };

function 크롬을_찾는다() {
  for (const 자리 of 크롬_후보) {
    if (existsSync(자리)) return 자리;
    try {
      const 찾은 = execSync(`where ${자리}`, { encoding: "utf8" }).split(/\r?\n/)[0];
      if (찾은 && existsSync(찾은)) return 찾은;
    } catch { /* PATH에 없다 — 다음 후보 */ }
  }
  throw new Error("크롬을 못 찾았다. PATH에 넣거나 이 파일의 `크롬_후보`에 자리를 더한다");
}

/** `/compare` 답에서 카드에 실린 좌표 JSON을 뽑는다. 답에는 기본 카드 둘만 들어 있다 */
async function 좌표들(from, to) {
  const 주소 = `https://example.com/compare?from=${from.lat},${from.lng}&to=${to.lat},${to.lng}`;
  const 글 = await (await worker.fetch(new Request(주소), env)).text();
  return [...글.matchAll(/<script type="application\/json" class="geometry">([^<]*)<\/script>/g)]
    .map((맞은것) => JSON.parse(맞은것[1]));
}

/** 그 참조(또는 빌드 산출물)의 화면 자산 둘. */
function 자산(ref) {
  if (!ref) {
    return {
      css: readFileSync(join(ROOT, "out", "site.css"), "utf8"),
      js: readFileSync(join(ROOT, "out", "map.js"), "utf8"),
    };
  }
  const 꺼낸다 = (경로) =>
    execFileSync("git", ["show", `${ref}:${경로}`], { cwd: ROOT, encoding: "utf8", maxBuffer: 1 << 24 });
  return { css: 꺼낸다("tools/build/site.css"), js: 꺼낸다("tools/build/map.js") };
}

/* ── 타일 없는 가짜 Kakao SDK ────────────────────────────────────────
   브라우저에서 도는 글이라 문자열로 둔다. 재는 것은 **점의 화면 자리**뿐이므로 타일·조작은 없다 */
const 가짜_SDK = `
(function () {
  var 파이 = Math.PI;
  /* 웹 메르카토르 0~1 세계 좌표 */
  function 세계(점) {
    var 라 = 점.lat * 파이 / 180;
    return { x: (점.lng + 180) / 360,
             y: (1 - Math.log(Math.tan(라) + 1 / Math.cos(라)) / 파이) / 2 };
  }
  /** 세계 좌표 y → 위도. getCenter가 지금 화면의 가운데를 돌려주려면 되짚어야 한다 */
  function 위도(y) { return Math.atan(Math.sinh(파이 * (1 - 2 * y))) * 180 / 파이; }
  function LatLng(lat, lng) { this.lat = lat; this.lng = lng; }
  function LatLngBounds() { this.점들 = []; }
  LatLngBounds.prototype.extend = function (점) { this.점들.push(점); };

  function 지도(자리, 설정) {
    this.자리 = 자리;
    this.듣는것 = {};
    this.얹은것 = [];
    자리.style.position = "relative";
    자리.style.overflow = "hidden";
    this.판 = document.createElement("div");
    this.판.style.cssText = "position:absolute;left:0;top:0;right:0;bottom:0";
    this.선판 = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    this.선판.setAttribute("style", "position:absolute;left:0;top:0;width:100%;height:100%");
    this.판.append(this.선판);
    자리.replaceChildren(this.판);
    this.세계폭 = 256 * Math.pow(2, 14);
    this.가운데로(세계(설정.center));
  }
  지도.prototype.relayout = function () {};
  /* 지금 화면의 가운데를 되짚어 돌려준다. 처음 설정값을 그대로 돌려주면 ResizeObserver의
     「가운데를 붙잡고 relayout」이 지도를 엉뚱한 데로 옮긴다 */
  지도.prototype.getCenter = function () {
    var 상자 = this.자리.getBoundingClientRect();
    var x = (this.원점.x + 상자.width / 2) / this.세계폭;
    var y = (this.원점.y + 상자.height / 2) / this.세계폭;
    return new LatLng(위도(y), x * 360 - 180);
  };
  /* 가운데만 옮긴다. **배율은 그대로다** — 여기서 다시 맞추면 점 하나에 맞춰 최대로 확대돼,
     ResizeObserver가 부르는 relayout 한 번에 라벨 자리가 통째로 어긋난다(실제로 당했다) */
  지도.prototype.setCenter = function (점) {
    this.가운데로(세계(점));
    this.그린다();
  };
  지도.prototype.getProjection = function () {
    var 나 = this;
    return { containerPointFromCoords: function (점) { return 나.화면(점); } };
  };
  지도.prototype.setBounds = function (테두리, 위, 오른, 아래, 왼) {
    this.맞춘다(테두리.점들, 위 || 0);
    this.그린다();
    this.알린다("idle");
  };
  /** 점들이 여백 안에 들어오는 **가장 큰 2의 거듭제곱 단계**를 고른다 (슬리피 맵과 같다) */
  지도.prototype.맞춘다 = function (점들, 여백) {
    var 상자 = this.자리.getBoundingClientRect();
    var 폭 = Math.max(1, 상자.width - 여백 * 2);
    var 높이 = Math.max(1, 상자.height - 여백 * 2);
    var 세계점 = 점들.map(세계);
    var xs = 세계점.map(function (점) { return 점.x; });
    var ys = 세계점.map(function (점) { return 점.y; });
    var 가로 = Math.max(...xs) - Math.min(...xs);
    var 세로 = Math.max(...ys) - Math.min(...ys);
    var 단계 = 0;
    for (var z = 22; z >= 0; z -= 1) {
      var 세계폭 = 256 * Math.pow(2, z);
      if (가로 * 세계폭 <= 폭 && 세로 * 세계폭 <= 높이) { 단계 = z; break; }
    }
    this.세계폭 = 256 * Math.pow(2, 단계);
    this.가운데로({ x: (Math.max(...xs) + Math.min(...xs)) / 2, y: (Math.max(...ys) + Math.min(...ys)) / 2 });
  };
  /** 세계 좌표 한 점을 화면 가운데에 놓는다. 배율은 안 건드린다 */
  지도.prototype.가운데로 = function (가운데) {
    var 상자 = this.자리.getBoundingClientRect();
    this.원점 = { x: 가운데.x * this.세계폭 - 상자.width / 2, y: 가운데.y * this.세계폭 - 상자.height / 2 };
  };
  지도.prototype.화면 = function (점) {
    var 세계점 = 세계(점);
    return { x: 세계점.x * this.세계폭 - this.원점.x, y: 세계점.y * this.세계폭 - this.원점.y };
  };
  지도.prototype.그린다 = function () {
    this.얹은것.forEach(function (것) { 것.자리맞춤(); });
  };
  지도.prototype.알린다 = function (이름) {
    (this.듣는것[이름] || []).forEach(function (할일) { 할일(); });
  };

  function Polyline(설정) {
    this.설정 = 설정;
    this.선 = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    this.선.setAttribute("fill", "none");
    this.선.setAttribute("stroke", 설정.strokeColor);
    this.선.setAttribute("stroke-width", 설정.strokeWeight);
    this.선.setAttribute("stroke-opacity", 설정.strokeOpacity != null ? 설정.strokeOpacity : 1);
    if (설정.strokeStyle === "shortdash") this.선.setAttribute("stroke-dasharray", "8 6");
    if (설정.strokeStyle === "shortdot") this.선.setAttribute("stroke-dasharray", "2 5");
    if (설정.map) this.붙인다(설정.map);
  }
  Polyline.prototype.붙인다 = function (지도) {
    this.지도 = 지도;
    지도.선판.append(this.선);
    지도.얹은것.push(this);
    this.자리맞춤();
  };
  Polyline.prototype.자리맞춤 = function () {
    var 나 = this;
    this.선.setAttribute("points", this.설정.path.map(function (점) {
      var 자리 = 나.지도.화면(점);
      return 자리.x + "," + 자리.y;
    }).join(" "));
  };
  Polyline.prototype.setMap = function (지도) { if (!지도) this.선.remove(); };

  function CustomOverlay(설정) {
    this.설정 = 설정;
    this.감쌈 = document.createElement("div");
    this.감쌈.style.position = "absolute";
    this.감쌈.style.zIndex = 설정.zIndex || 0;
    this.감쌈.append(설정.content);
    if (설정.map) this.붙인다(설정.map);
  }
  CustomOverlay.prototype.붙인다 = function (지도) {
    this.지도 = 지도;
    지도.판.append(this.감쌈);
    지도.얹은것.push(this);
    this.자리맞춤();
  };
  CustomOverlay.prototype.자리맞춤 = function () {
    var 자리 = this.지도.화면(this.설정.position);
    var x = this.설정.xAnchor == null ? 0.5 : this.설정.xAnchor;
    var y = this.설정.yAnchor == null ? 0.5 : this.설정.yAnchor;
    this.감쌈.style.left = 자리.x + "px";
    this.감쌈.style.top = 자리.y + "px";
    this.감쌈.style.transform = "translate(" + (-x * 100) + "%," + (-y * 100) + "%)";
  };
  CustomOverlay.prototype.setMap = function (지도) { if (!지도) this.감쌈.remove(); };

  window.kakao = { maps: {
    load: function (준비) { 준비(); },
    LatLng: LatLng, LatLngBounds: LatLngBounds, Map: 지도,
    Polyline: Polyline, CustomOverlay: CustomOverlay,
    event: { addListener: function (대상, 이름, 할일) {
      (대상.듣는것[이름] = 대상.듣는것[이름] || []).push(할일);
    } },
  } };
})();
`;

/* 화면에 남은 라벨끼리 겹친 쌍을 센다. 이슈 #68의 콘솔 조각과 같은 셈이고, 감춘 라벨은
   상자가 0이라 세지 않는다 — 대신 몇 개를 감췄는지 따로 적는다 */
const 재는_글 = `
function 잰다(자리) {
  var 다 = [].slice.call(자리.querySelectorAll(".map-label"));
  var 보이는 = [];
  var 감춤 = 0;
  다.forEach(function (요소) {
    var 상자 = 요소.getBoundingClientRect();
    if (!상자.width) { 감춤 += 1; return; }
    보이는.push({ t: 요소.textContent.trim(), x: 상자.x, y: 상자.y, w: 상자.width, h: 상자.height });
  });
  var 쌍 = [];
  for (var i = 0; i < 보이는.length; i += 1) {
    for (var j = i + 1; j < 보이는.length; j += 1) {
      var 가 = 보이는[i], 나 = 보이는[j];
      if (가.x < 나.x + 나.w && 나.x < 가.x + 가.w && 가.y < 나.y + 나.h && 나.y < 가.y + 가.h) {
        쌍.push(가.t + " ✕ " + 나.t);
      }
    }
  }
  return { 라벨: 다.length, 보임: 보이는.length, 감춤: 감춤, 겹친쌍: 쌍 };
}
`;

function 판을_짠다(자산들, 지도들, 폭) {
  const 칸 = 지도들.map((하나, i) => `
    <section class="한장">
      <h2>${i + 1}. ${하나.이름}</h2>
      <div class="journey-map"><div class="canvas" id="지도${i}"></div></div>
    </section>`).join("");
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>재는 중</title>
<style>${자산들.css}</style>
<style>
  body { margin: 0; }
  .판 { max-width: ${폭}px; margin: 0 auto; padding: 0 20px 24px; }
  .요약 { position: sticky; top: 0; background: #111; color: #fff; padding: 10px 20px;
          font: 700 15px/1.5 system-ui, sans-serif; }
  .한장 h2 { font: 600 13px/1.6 system-ui, sans-serif; margin: 14px 0 6px; color: #444; }
</style></head><body>
<div class="요약" id="요약">재는 중…</div>
<div class="판">${칸}</div>
<script>${가짜_SDK}</script>
<script>${자산들.js}</script>
<script>${재는_글}</script>
<script>
  var 지도들 = ${JSON.stringify(지도들)};
  var 잰것 = 지도들.map(function (하나, i) {
    var 자리 = document.getElementById("지도" + i);
    window.busMap.draw(자리, window.busMap.journey(하나.좌표들));
    var 값 = 잰다(자리);
    값.이름 = 하나.이름;
    return 값;
  });
  var 합 = jsonify(잰것);
  function jsonify(것들) {
    return {
      지도: 것들.length,
      라벨: 것들.reduce(function (a, b) { return a + b.라벨; }, 0),
      감춤: 것들.reduce(function (a, b) { return a + b.감춤; }, 0),
      겹친쌍: 것들.reduce(function (a, b) { return a + b.겹친쌍.length; }, 0),
      겹친지도: 것들.filter(function (하나) { return 하나.겹친쌍.length; }).length,
      낱장: 것들,
    };
  }
  document.getElementById("요약").textContent =
    "지도 " + 합.지도 + "장 · 라벨 " + 합.라벨 + "개 · 겹친 쌍 " + 합.겹친쌍 +
    " · 감춘 라벨 " + 합.감춤 + "개";
  document.title = "결과:" + btoa(unescape(encodeURIComponent(JSON.stringify(합))));
</script></body></html>`;
}

function 크롬을_돌린다(크롬, 파일, 폭, 높이, ...더) {
  const 임시 = mkdtempSync(join(tmpdir(), "labels-"));
  try {
    return execFileSync(크롬, [
      "--headless=new", "--disable-gpu", "--hide-scrollbars",
      "--force-device-scale-factor=1", "--default-background-color=FFFFFFFF",
      `--user-data-dir=${임시}`, `--window-size=${폭},${높이}`,
      "--virtual-time-budget=4000", ...더, pathToFileURL(파일).href,
    ], { encoding: "utf8", maxBuffer: 1 << 28 });
  } finally {
    rmSync(임시, { recursive: true, force: true });
  }
}

async function main() {
  const 인자 = process.argv.slice(2);
  const 값 = (이름, 기본) => {
    const i = 인자.indexOf(이름);
    return i === -1 ? 기본 : 인자[i + 1];
  };
  const ref = 값("--ref", null);
  const png = 값("--png", null);
  const 폭 = Number(값("--width", DEFAULT_WIDTH));
  const 쌍_수 = Number(인자.find((하나) => /^\d+$/.test(하나)) ?? DEFAULT_PAIRS);

  const 지도들 = [{ 이름: 이슈_쌍.이름, 좌표들: await 좌표들(이슈_쌍.from, 이슈_쌍.to) }];
  for (const [a, b] of 정류장_쌍(쌍_수)) {
    지도들.push({ 이름: `${a.name} → ${b.name}`, 좌표들: await 좌표들(a, b) });
  }

  const only = 값("--only", null);
  if (only) {
    const 고른 = 지도들[Number(only) - 1];
    if (!고른) throw new Error(`${only}번 지도가 없다 — 쌍 수를 늘리거나 번호를 낮춘다`);
    지도들.splice(0, 지도들.length, 고른);
  }

  const 임시 = mkdtempSync(join(tmpdir(), "labels-page-"));
  const 파일 = join(임시, "index.html");
  writeFileSync(파일, 판을_짠다(자산(ref), 지도들, 폭), "utf8");

  const 크롬 = 크롬을_찾는다();
  const 찍힌 = 크롬을_돌린다(크롬, 파일, 폭, 900, "--dump-dom");
  const 맞은것 = /<title>결과:([A-Za-z0-9+/=]+)<\/title>/.exec(찍힌);
  if (!맞은것) throw new Error("재지 못했다 — 크롬이 판을 끝까지 못 그렸다");
  const 합 = JSON.parse(Buffer.from(맞은것[1], "base64").toString("utf8"));

  if (png) {
    mkdirSync(dirname(resolve(png)), { recursive: true });
    크롬을_돌린다(크롬, 파일, 폭, 480, `--screenshot=${resolve(png)}`);
  }
  rmSync(임시, { recursive: true, force: true });

  console.log(`${ref ? `${ref}의 ` : "빌드 산출물의 "}map.js·site.css로 잰 값 · 폭 ${폭}px\n`);
  for (const 하나 of 합.낱장) {
    const 겹침 = 하나.겹친쌍.length;
    console.log(
      `${겹침 ? "✕" : "·"} 라벨 ${String(하나.라벨).padStart(2)}개`
      + ` (보임 ${하나.보임} · 감춤 ${하나.감춤}) · 겹친 쌍 ${겹침}  ${하나.이름}`,
    );
    하나.겹친쌍.forEach((글) => console.log(`    ${글}`));
  }
  console.log(
    `\n지도 ${합.지도}장 · 라벨 ${합.라벨}개 · **겹친 쌍 ${합.겹친쌍}**`
    + ` · 겹침이 남은 지도 ${합.겹친지도}장 · 감춘 라벨 ${합.감춤}개`,
  );
  if (png) console.log(`그림: ${png}`);
}

await main();
