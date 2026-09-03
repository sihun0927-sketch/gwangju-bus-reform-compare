/**
 * `/compare` 조각의 바깥만 검사한다 — `fetch(request, env)`에 좌표를 넣고 나온 응답 문자열.
 *
 * 이음새는 이 하나다(스펙의 이음새 ②). `candidates` · `search` · `rank` · `render`의 함수 모양은
 * 이 파일이 모른다. 번들은 빌드가 만든 것을 그대로 쓴다 — 먼저 `python -m tools.build`를
 * 돌려야 한다(`npm test`가 부른다).
 *
 * 좌표는 실제 정류장에서 골랐고, 어느 검사가 무엇을 걸어 두는지는 각 검사에 적었다.
 */
import assert from "node:assert/strict";
import test from "node:test";

import worker from "./index.js";

const env = {
  ASSETS: { fetch: () => new Response("정적 자산", { headers: { "content-type": "text/html" } }) },
};

/** 좌표 쌍 → 응답 문자열. 시민이 화면에서 보는 것과 같은 것만 돌려받는다. */
async function 비교(from, to) {
  const url = `https://example.com/compare?from=${from.join(",")}&to=${to.join(",")}`;
  const 응답 = await worker.fetch(new Request(url), env);
  assert.equal(응답.status, 200);
  return await 응답.text();
}

/** 조각에서 노선망 하나의 카드만 떼어 낸다. 카드가 없으면 빈 문자열. */
function 카드(글, 노선망) {
  const 자리 = new RegExp(`<article[^>]*data-network="${노선망}"[^]*?</article>`);
  return (글.match(자리) ?? [""])[0];
}

// 실제 정류장 좌표. 이름은 `data/source/stops.csv`의 것이다
const 전남대 = [35.1702, 126.904];
const 광주송정역 = [35.1381, 126.7918];
const 전남대_북쪽_300m = [35.1729, 126.904];
const 서울시청 = [37.5665, 126.978];
const 외곽_이동_남서쪽 = [35.1, 126.85];           // 500m 안에 정류장이 없고 548m에 「이동」이 있다
const 광곡입구 = [35.10151, 126.86949];
const 장등동 = [35.200286, 126.933692];
const 두정리입구 = [35.30934534, 126.93567071];    // 좌표 없는 신설 정류장 — 추정 좌표로만 있다
const 시청 = [35.158911, 126.854246];              // 순환01 상행 8번째
const 교육대 = [35.16366785, 126.92340336];        // 순환01 상행 18번째
// 직행이 없고 환승 2회로 가는 쌍. 갈아타는 자리 둘 중 하나는 같은 줄, 하나는 77m 걷는다
const 승촌주택단지 = [35.05800556, 126.78651667];
const 앵남2구 = [35.048077, 126.905535];
// 직행(228, 17분)이 있는데 환승 1회(6분)가 훨씬 빠른 쌍. 환승 도보 147m
const 이십곡리 = [35.070098, 126.973775];
const 기아자동차 = [35.15872338, 126.87684885];
// 개편 전·후 어느 쪽도 환승 2회로는 못 가고 3회면 가는 쌍(개편 전 지원152 → 매월16 → 송정29 → 송정97)
const 화순터널 = [35.07535556, 126.96113056];
const 양화 = [35.13895247, 126.65986465];

test("좌표 둘을 주면 개편 전 카드와 개편 후 카드가 온다", async () => {
  const 글 = await 비교(전남대, 광주송정역);
  for (const [노선망, 머리] of [["before", "개편 전"], ["after", "개편 후"]]) {
    const 한장 = 카드(글, 노선망);
    assert.ok(한장.includes(머리), `${노선망} 카드에 「${머리}」`);
    assert.match(한장, /직행|환승 [12]회|경로 없음/, `${노선망} 카드 머리의 상태`);
  }
});

test("카드에 승차·하차 정류장과 노선 이름과 도보 거리가 있다", async () => {
  const 글 = await 비교(전남대, 광주송정역);
  const 개편_후 = 카드(글, "after");
  assert.ok(개편_후.includes("직행"), 개편_후);
  assert.ok(개편_후.includes("전남대"), "승차 정류장");
  assert.ok(개편_후.includes("광주송정역"), "하차 정류장");
  assert.ok(개편_후.includes("직행1001"), "노선 이름");
  assert.match(개편_후, /9m/, "출발 도보 거리");
  assert.match(개편_후, /11m/, "도착 도보 거리");

  // 개편 전에도 좌석02 직행이 있지만, 전남대 앞에서 갈아타는 쪽이 도보가 짧아 더 빠르다
  const 개편_전 = 카드(글, "before");
  assert.ok(개편_전.includes("좌석02"), 개편_전);
  assert.ok(개편_전.includes("광주송정역"), 개편_전);
});

test("지표 줄에 예상 시간과 배차간격 「정보 없음」이 있고 추정치라는 줄이 있다", async () => {
  const 개편_후 = 카드(await 비교(전남대, 광주송정역), "after");
  assert.match(개편_후, /예상 시간[^<]*7분/);
  assert.match(개편_후, /환승 없음/);
  assert.match(개편_후, /정류장[^<]*21곳/);
  assert.match(개편_후, /도보 합계[^<]*20m/);
  assert.match(개편_후, /배차간격[^<]*정보 없음/);
  assert.match(개편_후, /추정치/);
});

test("두 지점이 500m 이하면 카드 없이 「걸어갈 수 있는 거리」", async () => {
  const 글 = await 비교(전남대, 전남대_북쪽_300m);
  assert.match(글, /걸어갈 수 있는 거리/);
  assert.equal(카드(글, "before"), "");
  assert.equal(카드(글, "after"), "");
});

test("도착지가 노선안 범위 밖이면 그 노선망 카드 대신 안내 한 줄", async () => {
  const 글 = await 비교(전남대, 서울시청);
  assert.equal(카드(글, "before"), "");
  assert.equal(카드(글, "after"), "");
  assert.match(글, /도착 지점[\s\S]*정류장이 없습니다/);
  assert.ok(글.includes("개편 전") && 글.includes("개편 후"), "어느 노선망 이야기인지 적는다");
});

test("출발지 500m 안에 정류장이 없으면 1,000m까지 넓혀 카드가 온다", async () => {
  const 글 = await 비교(외곽_이동_남서쪽, 광곡입구);
  const 개편_전 = 카드(글, "before");
  assert.ok(개편_전.includes("직행"), 개편_전);
  assert.ok(개편_전.includes("이동"), "500m 밖 승차 정류장");
  assert.match(개편_전, /548m/, "도보권을 넓혀 잡은 거리");
});

test("좌표 없는 신설 정류장을 도착지로 주면 개편 후 카드에 「추정 위치」", async () => {
  const 글 = await 비교(장등동, 두정리입구);
  const 개편_후 = 카드(글, "after");
  assert.ok(개편_후.includes("두정리입구"), 개편_후);
  assert.ok(개편_후.includes("추정 위치"), "추정 좌표를 쓴 정류장에는 표시가 붙는다");
  assert.ok(!카드(글, "before").includes("추정 위치"), "개편 전 카드에는 없다");
});

test("순환 노선을 거슬러 타는 경로는 나오지 않는다", async () => {
  const 정방향 = await 비교(시청, 교육대);
  assert.ok(카드(정방향, "before").includes("순환01"), "앞에서 뒤로는 순환01을 탄다");

  // 뒤에서 앞으로 가려면 목록 끝을 지나 앞 순번으로 돌아와야 한다. 환승 구간으로도 마찬가지다
  const 역방향 = await 비교(교육대, 시청);
  assert.ok(!역방향.includes("순환01"), 카드(역방향, "before"));
  assert.match(카드(역방향, "before"), /환승 [12]회|경로 없음/, "그래도 카드는 선다");
});

test("직행이 없으면 환승 카드가 서고 환승 정류장과 환승 도보가 보인다", async () => {
  const 개편_전 = 카드(await 비교(승촌주택단지, 앵남2구), "before");
  assert.ok(개편_전.includes("환승 2회"), 개편_전);
  // 갈아타는 자리 둘. 같은 줄에서 갈아타면 걸을 일이 없으므로 거리 대신 그렇다고 적는다
  assert.ok(개편_전.includes("<b>입암</b>에서 환승 · 같은 정류장"), "내려서 그 자리에서 타는 환승");
  assert.ok(
    개편_전.includes("환승 도보 77m · <b>신기교</b> → <b>빛고을노인건강타운</b>"),
    "걸어서 옮기는 환승 — 내리는 곳 → 타는 곳과 거리",
  );
  assert.ok(개편_전.includes("<li>환승 2회</li>"), "지표 줄의 환승 횟수");
  assert.match(개편_전, /도보 합계[^<]*77m/, "환승 도보도 도보 합계에 든다");
});

test("직행이 있어도 환승 경로가 빠르면 그쪽이 기본 경로다", async () => {
  // 이십곡리 → 기아자동차는 228 직행(17분)이 있지만, 만연빌딩에서 147m 걸어 송암31로
  // 갈아타면 6분이다. 순위는 추정 소요 시간을 따르므로 카드에 서는 것은 환승 쪽이다
  const 개편_전 = 카드(await 비교(이십곡리, 기아자동차), "before");
  assert.ok(개편_전.includes("환승 1회"), 개편_전);
  assert.match(개편_전, /예상 시간[^<]*6분/);
  assert.ok(개편_전.includes("환승 도보 147m · <b>만연빌딩</b> → <b>현대자동차</b>"), 개편_전);
  assert.ok(개편_전.includes("지원152(도웅리)") && 개편_전.includes("송암31"), "두 구간의 노선");
});

test("환승 3회가 필요한 쌍은 「경로 없음」", async () => {
  // 개편 전에는 지원152 → 매월16 → 송정29 → 송정97로 갈 수 있다. 상한이 2회라 답으로 내지 않는다
  const 글 = await 비교(화순터널, 양화);
  for (const 노선망 of ["before", "after"]) {
    const 한장 = 카드(글, 노선망);
    assert.ok(한장.includes("경로 없음"), 노선망 + 한장);
    assert.match(한장, /환승 2회 안에 가는 길을 찾지 못했습니다/, 노선망);
  }
});

test("응답에 옛 용어가 없다", async () => {
  const 글 = await 비교(전남대, 광주송정역);
  for (const 옛말 of ["기존", "신규", "현행"]) {
    assert.ok(!글.includes(옛말), `조각에 「${옛말}」`);
  }
});

test("좌표가 없거나 깨졌으면 한 줄로 알린다", async () => {
  for (const url of ["/compare", "/compare?from=35.17,126.90", "/compare?from=x,y&to=1,2"]) {
    const 응답 = await worker.fetch(new Request(`https://example.com${url}`), env);
    assert.equal(응답.status, 200, url);
    const 글 = await 응답.text();
    assert.match(글, /출발 지점과 도착 지점/, url);
    assert.equal(카드(글, "before"), "", url);
  }
});
