/**
 * `map.js` 검사 — 브라우저도 Kakao SDK도 없이 돌린다.
 *
 * 이 파일은 브라우저 스크립트라 `import`할 수 없다. 대신 `vm`으로 가짜 `window`·`document`·
 * Kakao SDK 위에 실어 놓고, 얹힌 것(선·점·감시자)을 그대로 들여다본다. 진짜 지도가 없으므로
 * **타일 위에서 어떻게 보이는지는 못 잰다** — 재는 것은 `draw`가 SDK에 무엇을 넘겼는가다.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const 여기 = dirname(fileURLToPath(import.meta.url));

/** CSS 토큰 값. 진짜 `site.css`가 아니라 검사가 알아볼 수 있는 표식이다. */
const 색표 = {
  "--map-before": "#0e6b5c",
  "--map-after": "#1d4ed8",
  "--map-walk": "#8a8a8a",
  "--before-line": "#0e6b5c",
  "--after-line": "#1d4ed8",
  "--kept-dot": "#5a6b67",
  "--dropped-dot": "#b2402f",
  "--added-dot": "#1d4ed8",
};

/** 글자 하나의 너비(px)와 줄 높이. 진짜 폰트가 아니라 검사가 셈할 수 있는 값이다 */
const 글자폭 = 8;
const 줄높이 = 16;

/** 가짜 DOM 조각 하나. `map.js`가 쓰는 것만 있다. */
function 조각(tag) {
  return {
    tag,
    className: "",
    style: {},
    textContent: "",
    hidden: false,
    children: [],
    append(...애들) { this.children.push(...애들); },
    replaceChildren(...애들) { this.children = 애들; },
    /* `map.js`는 라벨을 이걸로 집는다. 자식 하나 깊이면 되므로 그만큼만 흉내 낸다 */
    querySelector(선택자) { return 자식(this, 선택자.replace(".", "")); },
    /* 진짜 폰트가 없으니 글자 수로 잰다. 감춘 라벨은 크기가 0이다 — 브라우저와 같다 */
    getBoundingClientRect() {
      return this.hidden
        ? { width: 0, height: 0 }
        : { width: this.textContent.length * 글자폭, height: 줄높이 };
    },
  };
}

/** `className`으로 자식을 찾는다 — 검사가 점과 라벨을 집을 때 쓴다. */
function 자식(부모, 갈래) {
  return 부모.children.find((애) => String(애.className).split(" ").includes(갈래)) ?? null;
}

/** `map.js`를 가짜 브라우저에 실어 `window.busMap`과 얹힌 것 목록을 돌려준다. */
function 싣는다() {
  const 얹힌 = { polylines: [], overlays: [], maps: [], observers: [], 듣는것: [] };

  /* 점의 화면 자리를 내는 가짜 투영. 검사가 `배율`을 바꾸면 확대·축소가 된다 —
     진짜 타일은 없지만 라벨 자리 잡기가 보는 것은 이 픽셀 값뿐이다 */
  const 투영 = {
    배율: 1000,
    기준: { lat: 35.13, lng: 126.80 },
    containerPointFromCoords(점) {
      return { x: (점.lng - 투영.기준.lng) * 투영.배율, y: (투영.기준.lat - 점.lat) * 투영.배율 };
    },
  };

  class LatLng {
    constructor(lat, lng) { this.lat = lat; this.lng = lng; }
  }
  class LatLngBounds {
    constructor() { this.점들 = []; }
    extend(점) { this.점들.push(점); }
  }
  class 지도 {
    constructor(자리, 설정) {
      this.자리 = 자리;
      this.설정 = 설정;
      this.relayout횟수 = 0;
      this.가운데 = 설정.center;
      얹힌.maps.push(this);
    }
    relayout() { this.relayout횟수 += 1; }
    getProjection() { return 투영; }
    getCenter() { return this.가운데; }
    setCenter(점) { this.가운데 = 점; }
    setBounds(테두리, ...여백) { this.테두리 = 테두리; this.여백 = 여백; }
  }
  class Polyline {
    constructor(설정) { Object.assign(this, 설정); 얹힌.polylines.push(this); }
    setMap() {}
  }
  class CustomOverlay {
    constructor(설정) { Object.assign(this, 설정); 얹힌.overlays.push(this); }
    setMap() {}
  }
  class ResizeObserver {
    constructor(할일) { this.할일 = 할일; this.본것 = []; 얹힌.observers.push(this); }
    observe(자리) { this.본것.push(자리); }
    disconnect() {}
  }

  const document = {
    documentElement: 조각("html"),
    createElement: 조각,
    addEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; },
  };
  const window = {
    document,
    getComputedStyle: () => ({ getPropertyValue: (이름) => 색표[이름] ?? "" }),
    kakao: {
      maps: {
        load: (준비) => 준비(),
        LatLng, LatLngBounds, Map: 지도, Polyline, CustomOverlay,
        event: {
          addListener(대상, 이름, 할일) { 얹힌.듣는것.push({ 대상, 이름, 할일 }); },
        },
      },
    },
  };

  const 상자 = { window, document, ResizeObserver, WeakMap, console };
  상자.globalThis = 상자;
  vm.runInNewContext(readFileSync(join(여기, "map.js"), "utf8"), 상자, { filename: "map.js" });
  return { busMap: window.busMap, 얹힌, 투영 };
}

/** 검사마다 쓰는 자리 하나. */
const 자리 = () => 조각("div");

/* 개편 전 경로 — 승차 · 지나감 · 하차 셋. 마지막 정류장은 개편 후와 같은 자리다 */
const 개편전 = {
  network: "before",
  from: { lat: 35.10, lng: 126.80 },
  to: { lat: 35.13, lng: 126.83 },
  legs: [[
    { lat: 35.101, lng: 126.801, name: "가정류장" },
    { lat: 35.111, lng: 126.811, name: "나정류장" },
    { lat: 35.121, lng: 126.821, name: "다정류장" },
  ]],
  shapes: ["before|가노선|up"],
};
/* 개편 후 경로 — 승차가 개편 전의 하차와 **같은 자리**다. 그 점이 색 둘로 겹쳐야 한다 */
const 개편후 = {
  network: "after",
  from: { lat: 35.10, lng: 126.80 },
  to: { lat: 35.13, lng: 126.83 },
  legs: [[
    { lat: 35.121, lng: 126.821, name: "다정류장" },
    { lat: 35.129, lng: 126.829, name: "라정류장" },
  ]],
  shapes: ["after|나노선|up"],
};

const 노선표 = {
  before: [[35.10, 126.80], [35.11, 126.81]],
  after: [[35.10, 126.80], [35.12, 126.82]],
  stops: [
    { lat: 35.10, lng: 126.80, name: "가정류장", state: "유지" },
    { lat: 35.11, lng: 126.81, name: "나정류장", state: "경유 제외" },
    { lat: 35.12, lng: 126.82, name: "다정류장", state: "경유 추가" },
  ],
  missing: 0,
};

test("draw는 선과 점을 따로 받아 따로 얹는다", () => {
  const { busMap, 얹힌 } = 싣는다();
  busMap.draw(자리(), {
    paths: [
      { points: [{ lat: 1, lng: 1 }, { lat: 2, lng: 2 }], color: "#000", weight: 4, style: "solid" },
      // 점 하나짜리 선은 긋지 않는다 — 그어도 안 보이고 테두리만 흔든다
      { points: [{ lat: 3, lng: 3 }], color: "#000", weight: 4, style: "solid" },
    ],
    markers: [
      { lat: 1, lng: 1, colors: ["#000"], size: "small", label: "" },
      { lat: 2, lng: 2, colors: ["#000"], size: "normal", label: "끝" },
    ],
  });
  assert.equal(얹힌.polylines.length, 1, "점 둘 이상인 선만 긋는다");
  assert.equal(얹힌.overlays.length, 2, "점은 선과 따로 얹힌다");
  assert.equal(얹힌.maps.length, 1);
  assert.deepEqual(얹힌.maps[0].여백, [28, 28, 28, 28], "테두리 여백");
  assert.equal(얹힌.maps[0].테두리.점들.length, 5, "선 셋과 점 둘이 모두 테두리에 든다");
  console.log("MAP-G1 OK");
});

test("점 크기가 둘이고 큰 점만 가운데가 희다", () => {
  const { busMap, 얹힌 } = 싣는다();
  busMap.draw(자리(), {
    paths: [],
    markers: [
      { lat: 1, lng: 1, colors: ["#0e6b5c"], size: "small", label: "" },
      { lat: 2, lng: 2, colors: ["#0e6b5c"], size: "normal", label: "" },
    ],
  });
  const [작은, 큰] = 얹힌.overlays.map((겹) => 자식(겹.content, "map-dot"));
  assert.equal(작은.style.width, "8px");
  assert.equal(큰.style.width, "15px");
  assert.equal(자식(작은, "map-dot__core"), null, "작은 점은 속이 없다");
  assert.equal(자식(큰, "map-dot__core").style.width, "9px", "큰 점만 흰 속이 있다");
  console.log("MAP-G2 OK");
});

test("색이 둘인 점은 반씩 나뉜 부채꼴이다", () => {
  const { busMap, 얹힌 } = 싣는다();
  busMap.draw(자리(), {
    paths: [],
    markers: [
      { lat: 1, lng: 1, colors: ["#0e6b5c"], size: "small", label: "" },
      { lat: 2, lng: 2, colors: ["#0e6b5c", "#1d4ed8"], size: "small", label: "" },
    ],
  });
  const [하나, 둘] = 얹힌.overlays.map((겹) => 자식(겹.content, "map-dot").style.background);
  assert.equal(하나, "#0e6b5c", "색이 하나면 그냥 그 색이다");
  assert.match(둘, /^conic-gradient\(from 180deg,/);
  assert.match(둘, /#0e6b5c 0\.0000% 50\.0000%/);
  assert.match(둘, /#1d4ed8 50\.0000% 100\.0000%/);
  console.log("MAP-G3 OK");
});

test("라벨은 이름이 있는 점에만 붙고 색을 따라간다", () => {
  const { busMap, 얹힌 } = 싣는다();
  busMap.draw(자리(), {
    paths: [],
    markers: [
      { lat: 1, lng: 1, colors: ["#0e6b5c"], size: "small", label: "" },
      { lat: 2, lng: 2, colors: ["#0e6b5c"], size: "normal", label: "가정류장 승차" },
    ],
  });
  const [민, 붙은] = 얹힌.overlays.map((겹) => 자식(겹.content, "map-label"));
  assert.equal(민, null, "지나가는 점에는 이름을 안 붙인다");
  assert.equal(붙은.textContent, "가정류장 승차");
  assert.equal(붙은.style.color, "#0e6b5c");
  console.log("MAP-G4 OK");
});

test("자리 크기가 바뀌면 가운데를 붙잡고 다시 맞춘다", () => {
  const { busMap, 얹힌 } = 싣는다();
  const 곳 = 자리();
  busMap.draw(곳, { paths: [], markers: [{ lat: 1, lng: 1, colors: ["#000"], size: "small", label: "" }] });
  assert.equal(얹힌.observers.length, 1, "자리마다 감시자 하나");
  assert.deepEqual(얹힌.observers[0].본것, [곳]);

  const 지도 = 얹힌.maps[0];
  const 처음 = 지도.relayout횟수;
  지도.setCenter({ lat: 9, lng: 9 });
  얹힌.observers[0].할일();
  assert.equal(지도.relayout횟수, 처음 + 1, "다시 맞춘다");
  assert.deepEqual({ ...지도.가운데 }, { lat: 9, lng: 9 }, "가운데는 그대로다");
  console.log("MAP-G5 OK");
});

test("두 탭이 각각 paths와 markers를 낸다", () => {
  const { busMap } = 싣는다();

  const 경로 = busMap.journey([개편전, 개편후]);
  // 구간 둘 + 도보 넷(출발→승차, 하차→도착이 경로마다 하나씩)
  assert.equal(경로.paths.length, 6);
  assert.equal(경로.paths[0].color, "#0e6b5c");
  assert.equal(경로.paths[0].style, "shortdash", "개편 전은 점선");
  assert.equal(경로.paths.filter((선) => 선.style === "shortdot").length, 4, "도보 넷");

  // 정류장 다섯 자리 — 그 가운데 「다정류장」은 두 경로가 함께 쓴다
  assert.equal(경로.markers.length, 4);
  const 함께 = 경로.markers.find((점) => point키(점) === "35.121000,126.821000");
  assert.deepEqual(칸(함께.colors), ["#0e6b5c", "#1d4ed8"], "함께 쓰는 정류장은 색 둘");
  assert.equal(함께.size, "normal");
  assert.equal(함께.label, "다정류장 하차", "먼저 온 이름이 남는다");
  const 지나감 = 경로.markers.find((점) => 점.label === "");
  assert.equal(지나감.size, "small", "사이 정류장은 작은 점에 라벨이 없다");

  const 노선 = busMap.route(노선표);
  assert.equal(노선.paths.length, 2, "개편 전·후 선 둘");
  assert.deepEqual(칸(노선.paths).map((선) => 선.color), ["#0e6b5c", "#1d4ed8"]);
  assert.equal(노선.markers.length, 3);
  assert.deepEqual(칸(노선.markers).map((점) => 점.size), ["small", "normal", "normal"]);
  assert.deepEqual(칸(노선.markers).map((점) => 점.colors[0]), ["#5a6b67", "#b2402f", "#1d4ed8"]);
  assert.deepEqual(칸(노선.markers).map((점) => 점.label), ["", "", ""], "노선 지도에는 라벨이 없다");
  console.log("MAP-G6 OK");
});

/* `vm` 안에서 만들어진 배열은 바깥 `Array`와 프로토타입이 달라 엄격 비교가 어긋난다 */
const 칸 = (것) => Array.from(것);

function point키(점) {
  return 점.lat.toFixed(6) + "," + 점.lng.toFixed(6);
}

/* 노선 한 바퀴의 차도 경로. 승차·하차 정류장 근처를 지나가되 정확히 밟지는 않는다 */
const 가노선_형상 = [
  { lat: 35.090, lng: 126.790 },   // 승차보다 앞 — 잘려 나가야 한다
  { lat: 35.1012, lng: 126.8012 }, // 가정류장 곁
  { lat: 35.1055, lng: 126.8060 }, // 도로만 아는 굽이
  { lat: 35.1112, lng: 126.8113 }, // 나정류장 곁
  { lat: 35.1180, lng: 126.8180 }, // 도로만 아는 굽이
  { lat: 35.1213, lng: 126.8213 }, // 다정류장 곁
  { lat: 35.140, lng: 126.840 },   // 하차보다 뒤 — 잘려 나가야 한다
];

test("형상을 받으면 선이 도로를 타고, 못 받으면 정류장 직선이다", () => {
  const { busMap } = 싣는다();

  const 직선 = busMap.journey([개편전]);
  const 버스_직선 = 직선.paths.find((선) => 선.style === "shortdash");
  assert.equal(버스_직선.points.length, 3, "형상이 없으면 정류장 셋을 그대로 잇는다");

  const 도로 = busMap.journey([개편전], { "before|가노선|up": 가노선_형상 });
  const 버스_도로 = 도로.paths.find((선) => 선.style === "shortdash");
  const 점들 = 칸(버스_도로.points);
  assert.equal(점들.length, 7, "승차 + 자른 형상 다섯 + 하차");
  assert.deepEqual({ ...점들[0] }, { lat: 35.101, lng: 126.801, name: "가정류장" },
    "선은 승차 정류장에서 시작한다");
  assert.equal(점들[점들.length - 1].name, "다정류장", "그리고 하차 정류장에서 끝난다");
  assert.ok(점들.some((점) => 점.lat === 35.1180), "도로만 아는 굽이가 들어온다");
  assert.ok(!점들.some((점) => 점.lat === 35.090), "승차 앞 구간은 잘려 나간다");
  assert.ok(!점들.some((점) => 점.lat === 35.140), "하차 뒤 구간도 잘려 나간다");

  // 점은 형상이 있든 없든 정류장 좌표 그대로다 — 점은 사실, 선은 추정(ADR-0009)
  assert.equal(도로.markers.length, 직선.markers.length);
  console.log("MAP-G10 OK");
});

/* ── 라벨 자리 (ADR-0010) ────────────────────────────────────────────
   `map.js`의 셈을 그대로 베끼지 않고 **검사가 따로 적는다** — 같은 식을 두 번 적어야 한쪽이
   틀렸을 때 어긋난다. 점 반지름 밖으로 4px 띄운 자리가 라벨 상자다 */
const 점지름 = { small: 8, normal: 15 };

function 상자(하나, 자리) {
  const 틈 = 점지름[하나.size] / 2 + 4;
  if (자리 === "left") return { x: 하나.x - 틈 - 하나.w, y: 하나.y - 하나.h / 2, w: 하나.w, h: 하나.h };
  if (자리 === "top") return { x: 하나.x - 하나.w / 2, y: 하나.y - 틈 - 하나.h, w: 하나.w, h: 하나.h };
  if (자리 === "bottom") return { x: 하나.x - 하나.w / 2, y: 하나.y + 틈, w: 하나.w, h: 하나.h };
  return { x: 하나.x + 틈, y: 하나.y - 하나.h / 2, w: 하나.w, h: 하나.h };
}

const 겹치나 = (가, 나) =>
  가.x < 나.x + 나.w && 나.x < 가.x + 가.w && 가.y < 나.y + 나.h && 나.y < 가.y + 가.h;

/** 자리를 받은 라벨들이 서로 겹치는 쌍의 수. 이슈 #68이 라이브에서 세던 그 셈이다 */
function 겹친쌍(라벨들, 자리들) {
  const 놓인 = 라벨들
    .map((하나, i) => (자리들[i] ? 상자(하나, 자리들[i]) : null))
    .filter(Boolean);
  let 셈 = 0;
  for (let i = 0; i < 놓인.length; i += 1) {
    for (let j = i + 1; j < 놓인.length; j += 1) if (겹치나(놓인[i], 놓인[j])) 셈 += 1;
  }
  return 셈;
}

/** 같은 자리에 선 라벨 다섯 — 넷은 네 자리로 흩어지고 다섯째는 갈 데가 없다 */
const 한자리에 = () =>
  [1, 2, 3, 4, 5].map((번호) => ({ x: 100, y: 100, w: 60, h: 16, size: "normal", 번호 }));

test("놓는다는 겹치는 라벨을 비키게 하고, 자리가 없으면 감춘다", () => {
  const { busMap } = 싣는다();
  const 라벨들 = 한자리에();

  const 자리들 = 칸(busMap.놓는다(라벨들));
  assert.deepEqual(자리들, ["right", "left", "top", "bottom", null],
    "오른쪽 → 왼쪽 → 위 → 아래 차례로 보고, 다 막히면 감춘다");
  assert.equal(겹친쌍(라벨들, 자리들), 0, "놓인 라벨끼리는 겹치지 않는다");

  // 같은 입력에 같은 답 — 자리가 프레임마다 흔들리면 라벨이 춤춘다
  assert.deepEqual(칸(busMap.놓는다(한자리에())), 자리들);

  // 멀리 떨어진 라벨은 아무도 안 밀어낸다 — 기본은 오른쪽 그대로다
  assert.deepEqual(칸(busMap.놓는다([
    { x: 100, y: 100, w: 60, h: 16, size: "normal" },
    { x: 400, y: 400, w: 60, h: 16, size: "normal" },
  ])), ["right", "right"]);
  console.log("MAP-G11 OK");
});

test("큰 점이 먼저 자리를 고르고, 못 잰 라벨은 남을 밀어내지 않는다", () => {
  const { busMap } = 싣는다();

  // 작은 점이 먼저 들어와도 오른쪽은 큰 점(타고 내리는 곳) 차지다
  assert.deepEqual(칸(busMap.놓는다([
    { x: 100, y: 100, w: 60, h: 16, size: "small" },
    { x: 100, y: 100, w: 60, h: 16, size: "normal" },
  ])), ["left", "right"]);

  // 크기를 아직 못 잰 것(첫 프레임)은 첫 자리를 받되 자리를 잡아 두지 않는다
  assert.deepEqual(칸(busMap.놓는다([
    { x: 100, y: 100, w: 0, h: 0, size: "normal" },
    { x: 100, y: 100, w: 60, h: 16, size: "normal" },
  ])), ["right", "right"]);
  console.log("MAP-G12 OK");
});

/* 환승 2회 경로 — 타고 내리는 곳 여섯이 한 화면에 몰린다. 이슈 #68이 라이브에서 잰
   「라벨 6개 · 겹친 쌍 6개」와 같은 모양이다 */
const 몰린경로 = {
  network: "before",
  from: { lat: 35.1290, lng: 126.8000 },
  to: { lat: 35.1250, lng: 126.8040 },
  legs: [
    [{ lat: 35.1290, lng: 126.8005, name: "가정류장" }, { lat: 35.1288, lng: 126.8010, name: "나정류장" }],
    [{ lat: 35.1286, lng: 126.8014, name: "다정류장" }, { lat: 35.1284, lng: 126.8018, name: "라정류장" }],
    [{ lat: 35.1282, lng: 126.8022, name: "마정류장" }, { lat: 35.1280, lng: 126.8026, name: "바정류장" }],
  ],
};

test("draw가 얹은 라벨의 자리를 실제로 고쳐 잡는다 — 겹친 쌍 0", () => {
  const { busMap, 얹힌, 투영 } = 싣는다();
  busMap.draw(자리(), busMap.journey([몰린경로]));

  const 라벨들 = 얹힌.overlays
    .map((것) => ({ 점: 것.position, 요소: 자식(것.content, "map-label") }))
    .filter((것) => 것.요소);
  assert.equal(라벨들.length, 6, "타고 내리는 곳 여섯에 라벨이 붙는다");
  assert.equal(얹힌.overlays.length, 6, "점은 라벨과 상관없이 다 얹힌다 — 사실은 안 지운다");

  const 잰것 = 라벨들.map((하나) => {
    const 자리점 = 투영.containerPointFromCoords(하나.점);
    return { x: 자리점.x, y: 자리점.y, w: 하나.요소.textContent.length * 글자폭, h: 줄높이,
      size: "normal" };
  });
  const 고른자리 = 라벨들.map((하나) => (하나.요소.hidden
    ? null
    : String(하나.요소.className).replace("map-label map-label--", "")));

  assert.equal(겹친쌍(잰것, 고른자리), 0, "화면에 남은 라벨끼리 겹치지 않는다");
  assert.ok(고른자리.some((자리) => 자리 && 자리 !== "right"),
    "적어도 하나는 오른쪽에서 비켰다 — 자리 고르기가 실제로 돌았다는 증거");
  assert.ok(고른자리.filter(Boolean).length >= 2, "감추기만 하고 끝내지 않는다");
  // 자리가 넷뿐이라 여섯은 다 못 선다. 못 선 것은 **감춘다** — 겹쳐 읽히느니 없는 편이 낫다
  const 감춘것 = 라벨들.filter((하나) => 하나.요소.hidden);
  assert.equal(감춘것.length, 라벨들.length - 고른자리.filter(Boolean).length);
  assert.ok(감춘것.length >= 1, "자리가 모자라면 감춘 라벨이 있다");
  console.log("MAP-G13 OK · 라벨 " + 라벨들.length + "개 · 겹친 쌍 0 · 감춤 " + 감춘것.length);
});

test("확대·이동하면 자리를 다시 고른다 — idle에 다시 돈다", () => {
  const { busMap, 얹힌, 투영 } = 싣는다();
  busMap.draw(자리(), busMap.journey([몰린경로]));

  const 요소들 = 얹힌.overlays.map((것) => 자식(것.content, "map-label")).filter(Boolean);
  assert.ok(요소들.some((요소) => 요소.hidden || 요소.className !== "map-label map-label--right"),
    "좁게 보면 비키거나 감춘 라벨이 있다");

  const 듣기 = 얹힌.듣는것.filter((것) => 것.이름 === "idle");
  assert.equal(듣기.length, 1, "지도마다 `idle` 하나");
  투영.배율 = 100000;              // 크게 확대하면 점 사이가 멀어진다
  듣기[0].할일();
  assert.deepEqual(요소들.map((요소) => 요소.className), 요소들.map(() => "map-label map-label--right"),
    "널찍해지면 다들 기본 자리로 돌아온다");
  assert.deepEqual(요소들.map((요소) => 요소.hidden), 요소들.map(() => false),
    "감췄던 라벨도 자리가 나면 다시 보인다");
  console.log("MAP-G14 OK");
});

test("개편 전·후가 같은 정류장에서 타면 라벨은 하나다", () => {
  const { busMap } = 싣는다();
  const 같은데서_탄다 = { ...개편후, legs: [[
    { lat: 35.101, lng: 126.801, name: "가정류장" },
    { lat: 35.129, lng: 126.829, name: "라정류장" },
  ]] };
  const 그림 = busMap.journey([개편전, 같은데서_탄다]);
  const 라벨들 = 칸(그림.markers).map((점) => 점.label).filter(Boolean);
  assert.deepEqual(라벨들.filter((글) => 글.startsWith("가정류장")), ["가정류장 승차"],
    "같은 자리의 승차는 점 하나이므로 라벨도 하나다");
  console.log("MAP-G15 OK");
});
