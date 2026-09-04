/**
 * 「다른 경로 카드」와 경로 지도 좌표를 검사한다 — 이음새는 Worker `fetch(request, env)` 하나다.
 *
 * `/compare` 조각에서 경로 키를 꺼내 `/journey/{id}`를 부르고, 돌아온 조각의 문자열만 본다.
 * `journey`·`geometry`의 함수 모양은 이 파일이 모른다. 번들은 빌드가 만든 것을 그대로 쓴다.
 *
 *     node --test "worker/*.test.js"
 */
import assert from "node:assert/strict";
import test from "node:test";

import worker from "./index.js";
import { ALTERNATIVE_JOURNEYS, WALK_RADIUS_MAX_M } from "./rules.js";

const env = {
  ASSETS: { fetch: () => new Response("정적 자산", { headers: { "content-type": "text/html" } }) },
};

const 부른다 = (url) => worker.fetch(new Request(`https://example.com${url}`), env);

const 전남대 = [35.1702, 126.904];
const 광주송정역 = [35.1381, 126.7918];

async function 비교(from = 전남대, to = 광주송정역) {
  const 응답 = await 부른다(`/compare?from=${from.join(",")}&to=${to.join(",")}`);
  assert.equal(응답.status, 200);
  return await 응답.text();
}

/**
 * 조각에서 노선망 하나의 카드만 떼어 낸다.
 *
 * 「다른 경로 더 보기」는 카드 **밖**에 선다(격자 둘째 줄) — 같은 노선망의 것이라 함께 뗀다.
 */
function 카드(글, 노선망) {
  const 자리 = new RegExp(
    `<article[^>]*data-network="${노선망}"[^]*?</article>`
    + `(?:<details[^>]*data-network="${노선망}"[^]*?</details>)?`,
  );
  return (글.match(자리) ?? [""])[0];
}

/** 조각에 실린 경로 키 전부. 기본 경로가 먼저, 다른 경로가 뒤다. */
const 경로_키 = (글) => [...글.matchAll(/data-journey="([^"]+)"/g)].map((m) => m[1]);

/** 조각에 실린 경로 지도 좌표 JSON 전부. */
const 좌표 = (글) =>
  [...글.matchAll(/<script type="application\/json" class="geometry">([^]*?)<\/script>/g)]
    .map((m) => JSON.parse(m[1]));

/**
 * 경로 줄에 실린 노선 이름을 차례대로 이은 것. 노선 조합을 견줄 때 쓴다 (CONTEXT 「경로 줄」).
 *
 * 노선은 지표 표가 아니라 경로 줄의 그 노선 자리에 칩으로 적힌다. 조합이 없으면 `undefined`라야
 * 「둘 다 못 읽어서 같다」가 통과하지 않는다.
 */
const 노선_줄 = (글) =>
  [...글.matchAll(/<b class="chip">([^<]*)<\/b>/g)].map((m) => m[1]).join(" · ") || undefined;

/** 지표 표에서 한 줄의 값 — `<dt>예상 시간</dt><dd>7분</dd>` (CONTEXT 「지표」). */
const 지표 = (글, 이름) => (글.match(new RegExp(`<dt>${이름}</dt><dd>([^<]*)</dd>`)) ?? [])[1];

/** 카드에 적힌 승차·하차 정류장을 차례대로. 「추정 위치」 표시가 붙어도 이름을 읽는다. */
const 정류장_목록 = (글) =>
  [
    ...글.matchAll(
      /<span class="at"><b>([^<]*)<\/b>(?: <span class="estimated">[^<]*<\/span>)? ([^<]*)<\/span>/g,
    ),
  ].map((m) => `${m[2]} ${m[1]}`);

/** 경로 키를 열어 칸 목록으로. 검사가 키를 손으로 고쳐 볼 수 있게 여기서도 한 번 적는다. */
const 키를_푼다 = (id) =>
  new TextDecoder().decode(
    Uint8Array.from(atob(id.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0)),
  ).split("|");

/** 칸 목록 → 경로 키. */
const 키로_적는다 = (칸) =>
  btoa(String.fromCharCode(...new TextEncoder().encode(칸.join("|"))))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

async function 다른_경로(id) {
  const 응답 = await 부른다(`/journey/${id}`);
  assert.equal(응답.status, 200, id);
  return await 응답.text();
}

test("카드마다 「다른 경로 더 보기」와 다른 경로 2개의 키가 있다", async () => {
  const 글 = await 비교();
  for (const 노선망 of ["before", "after"]) {
    const 한장 = 카드(글, 노선망);
    assert.ok(한장.includes("다른 경로 더 보기"), 노선망);
    // 기본 경로 하나 + 다른 경로 둘
    assert.equal(경로_키(한장).length, 1 + ALTERNATIVE_JOURNEYS, 노선망);
  }
});

test("「다른 경로 더 보기」는 카드 밖에 서고 펴고 접힌다", async () => {
  const 글 = await 비교();
  for (const 노선망 of ["before", "after"]) {
    // 카드 **안**에 있으면 한쪽만 펼쳐도 격자 첫 줄이 커져 옆 카드가 빈 채로 따라 늘어난다
    const 카드만 = (글.match(
      new RegExp(`<article[^>]*data-network="${노선망}"[^]*?</article>`),
    ) ?? [""])[0];
    assert.ok(!카드만.includes("<details"), `${노선망} — 다른 경로가 카드 안에 있다`);
    assert.match(
      글,
      new RegExp(`</article><details class="alternatives" id="more-${노선망}"`),
      `${노선망} — 카드 바로 뒤에 선다`,
    );

    // 펴고 접는 일은 `<details>` 몫이라 우리 스크립트가 없다(ADR-0001). 조각은 처음 펼 때 한 번만
    // 부르고(`toggle once`), 그 뒤 접었다 펴는 것은 다시 받아 오지 않는다
    const 방아쇠 = [...카드(글, 노선망).matchAll(/hx-trigger="([^"]*)"/g)].map((m) => m[1]);
    assert.equal(방아쇠.length, ALTERNATIVE_JOURNEYS, 노선망);
    assert.ok(
      방아쇠.every((t) => t === `toggle once from:#more-${노선망}`),
      `${노선망} — ${방아쇠.join(" / ")}`,
    );
  }
});

test("기본 경로의 키로 부르면 카드와 같은 정류장 목록이 온다", async () => {
  const 글 = await 비교();
  for (const 노선망 of ["before", "after"]) {
    const 한장 = 카드(글, 노선망);
    const [기본] = 경로_키(한장);
    const 복원 = await 다른_경로(기본);
    assert.ok(정류장_목록(한장).length >= 2, `${노선망} ${정류장_목록(한장)}`);
    assert.deepEqual(정류장_목록(복원), 정류장_목록(한장), 노선망);
    assert.equal(노선_줄(복원), 노선_줄(한장), 노선망);
  }
});

test("다른 경로 2개의 노선 조합이 기본 경로와 서로 다르다", async () => {
  const 글 = await 비교();
  for (const 노선망 of ["before", "after"]) {
    const 한장 = 카드(글, 노선망);
    const 조합 = [노선_줄(한장)];
    for (const 키 of 경로_키(한장).slice(1)) 조합.push(노선_줄(await 다른_경로(키)));
    assert.ok(조합.every(Boolean), `${노선망} ${조합}`);
    assert.equal(new Set(조합).size, 조합.length, `${노선망} ${조합}`);
  }
});

test("깨진 키는 404와 한 줄 문구", async () => {
  // 마지막 둘은 base64로는 멀쩡한데 번들과 안 맞는 키다 — 없는 노선망과 없는 노선
  const 없는_노선망 = btoa("nowhere|35.1,126.9|35.2,126.9|1|228|2");
  const 없는_노선 = btoa("before|35.1,126.9|35.2,126.9|1|nope|2");
  for (const id of ["abc", "", "!!!!", 없는_노선망, 없는_노선]) {
    const 응답 = await 부른다(`/journey/${id}`);
    assert.equal(응답.status, 404, id);
    assert.match(await 응답.text(), /^<p class="notice">[^<]+<\/p>$/, id);
  }
});

test("도보가 규칙을 넘는 키는 우리가 낸 키가 아니라 404다", async () => {
  // 손으로 고친 주소가 「1km 넘게 걸어가 타는 경로」를 멀쩡한 카드로 만들어 내지 않게 막는다
  // (CONTEXT 「도보권」). 진짜 키의 출발 지점만 멀리 옮긴다 — 나머지 칸은 번들과 그대로 맞는다
  const 진짜 = 경로_키(카드(await 비교(), "after"))[0];
  const 칸 = 키를_푼다(진짜);
  assert.equal(칸.length % 3, 0, 칸.join("|"));
  칸[1] = "35.0,126.5";                       // 승차 정류장에서 수십 km 떨어진 출발 지점
  const 응답 = await 부른다(`/journey/${키로_적는다(칸)}`);
  assert.equal(응답.status, 404, `도보권 상한은 ${WALK_RADIUS_MAX_M}m다`);

  // 지점을 그대로 두면 같은 칸이 200으로 돌아온다 — 막은 것이 지점 하나였다는 증거
  assert.equal((await 부른다(`/journey/${키로_적는다(키를_푼다(진짜))}`)).status, 200);
});

test("`/compare` 조각에 카드마다 경로 지도 좌표 JSON이 하나씩 있다", async () => {
  const 글 = await 비교();
  const 지도들 = 좌표(글);
  assert.equal(지도들.length, 2);
  assert.deepEqual(지도들.map((g) => g.network), ["before", "after"]);
  for (const 지도 of 지도들) {
    assert.ok(지도.legs.length >= 1, JSON.stringify(지도).slice(0, 200));
    for (const 점 of [...지도.legs.flat(), 지도.from, 지도.to]) {
      assert.ok(Number.isFinite(점.lat) && Number.isFinite(점.lng), JSON.stringify(점));
    }
  }
});

test("좌표 JSON의 점 수가 경로 줄의 「N개 정류장」과 맞는다", async () => {
  // 구간 하나가 지나는 정류장이 N개면 점은 승차까지 더해 N+1개다. 좌표가 있는 줄만 실리므로,
  // 이 검사가 어긋나면 좌표 없는 정류장이 생긴 것이다(오늘은 추정 좌표까지 있어 0개).
  // 정류장 수는 노선마다 달라지는 값이라 지표 표가 아니라 경로 줄에 있다(CONTEXT 「경로 줄」)
  const 글 = await 비교();
  for (const 노선망 of ["before", "after"]) {
    const 한장 = 카드(글, 노선망);
    const 구간별 = [...한장.matchAll(/· (\d+)개 정류장</g)].map((m) => Number(m[1]));
    const [지도] = 좌표(한장);
    assert.equal(구간별.length, 지도.legs.length, `${노선망} 구간 수`);
    구간별.forEach((지난_곳, i) => {
      assert.equal(지도.legs[i].length, 지난_곳 + 1, `${노선망} ${i + 1}번째 구간`);
    });
  }
});

test("사이 정류장은 길 양쪽 중 바로 앞 점에 가까운 쪽으로 그린다", async () => {
  // 자리 하나에 줄이 둘(길 양쪽)이면 앞 점에 가까운 쪽을 고른다(CONTEXT 「경로 지도」).
  // 「앞 점」을 자리마다 옮기지 않고 구간 승차 자리에 고정하면 이 점이 길 건너로 넘어간다 —
  // 개편 전 좌석02 구간에서 세 자리가 갈리고, 그중 하나를 값으로 박아 둔다. 승차 자리에 고정하면
  // 5,425m 쪽을, 앞 점(한국수자원공사)에서 재면 422m 쪽을 고른다
  const [지도] = 좌표(카드(await 비교(), "before"));
  const 농협운천지점 = 지도.legs[0][9];
  assert.equal(농협운천지점.name, "농협운천지점");
  assert.equal(농협운천지점.lat.toFixed(6), "35.148730");
  assert.equal(농협운천지점.lng.toFixed(6), "126.848071");
});

test("다른 경로 카드에도 좌표 JSON과 「지도에 표시」가 있다", async () => {
  const 한장 = 카드(await 비교(), "after");
  const 복원 = await 다른_경로(경로_키(한장)[1]);
  assert.equal(좌표(복원).length, 1);
  assert.equal(좌표(복원)[0].network, "after");
  assert.ok(복원.includes("지도에 표시"), 복원);
});

test("다른 경로 카드에도 예상 시간과 도보 합계가 적힌다", async () => {
  // 키에 두 지점이 실려 있어야 출발·도착 도보를 되살릴 수 있다 — 기본 카드와 같은 자로 잰다
  const 복원 = await 다른_경로(경로_키(카드(await 비교(), "after"))[1]);
  assert.match(지표(복원, "예상 시간"), /^\d+분$/, 복원);
  assert.match(지표(복원, "도보 합계"), /^\d+m$/, 복원);
  assert.match(복원, /배차간격 약 [\d.]+분\(추정\) · \d+개 정류장/, "배차간격은 경로 줄의 노선 자리에 있다");
});

test("응답에 옛 용어가 없다", async () => {
  const 한장 = 카드(await 비교(), "before");
  const 글 = 한장 + (await 다른_경로(경로_키(한장)[1]));
  for (const 옛말 of ["기존", "신규", "현행"]) {
    assert.ok(!글.includes(옛말), `조각에 「${옛말}」`);
  }
});
