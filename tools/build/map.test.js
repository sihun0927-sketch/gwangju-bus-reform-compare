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

/** 가짜 DOM 조각 하나. `map.js`가 쓰는 것만 있다. */
function 조각(tag) {
  return {
    tag,
    className: "",
    style: {},
    textContent: "",
    children: [],
    append(...애들) { this.children.push(...애들); },
    replaceChildren(...애들) { this.children = 애들; },
  };
}

/** `className`으로 자식을 찾는다 — 검사가 점과 라벨을 집을 때 쓴다. */
function 자식(부모, 갈래) {
  return 부모.children.find((애) => String(애.className).split(" ").includes(갈래)) ?? null;
}

/** `map.js`를 가짜 브라우저에 실어 `window.busMap`과 얹힌 것 목록을 돌려준다. */
function 싣는다() {
  const 얹힌 = { polylines: [], overlays: [], maps: [], observers: [] };

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
      },
    },
  };

  const 상자 = { window, document, ResizeObserver, WeakMap, console };
  상자.globalThis = 상자;
  vm.runInNewContext(readFileSync(join(여기, "map.js"), "utf8"), 상자, { filename: "map.js" });
  return { busMap: window.busMap, 얹힌 };
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
