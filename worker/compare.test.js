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

test("좌표 둘을 주면 개편 전 카드와 개편 후 카드가 온다", async () => {
  const 글 = await 비교(전남대, 광주송정역);
  for (const [노선망, 머리] of [["before", "개편 전"], ["after", "개편 후"]]) {
    const 한장 = 카드(글, 노선망);
    assert.ok(한장.includes(머리), `${노선망} 카드에 「${머리}」`);
    assert.match(한장, /직행|경로 없음/, `${노선망} 카드 머리의 상태`);
  }
});

test("카드에 승차·하차 정류장과 노선 이름과 도보 거리가 있다", async () => {
  const 글 = await 비교(전남대, 광주송정역);
  const 개편_전 = 카드(글, "before");
  assert.ok(개편_전.includes("직행"), 개편_전);
  assert.ok(개편_전.includes("전남대사거리(서)"), "승차 정류장");
  assert.ok(개편_전.includes("광주송정역"), "하차 정류장");
  assert.ok(개편_전.includes("좌석02"), "노선 이름");
  assert.match(개편_전, /164m/, "출발 도보 거리");
  assert.match(개편_전, /11m/, "도착 도보 거리");

  const 개편_후 = 카드(글, "after");
  assert.ok(개편_후.includes("직행1001"), `개편 후 노선 이름\n${개편_후}`);
  assert.ok(개편_후.includes("전남대"), "승차 정류장");
});

test("지표 줄에 예상 시간과 배차간격 「정보 없음」이 있고 추정치라는 줄이 있다", async () => {
  const 개편_전 = 카드(await 비교(전남대, 광주송정역), "before");
  assert.match(개편_전, /예상 시간[^<]*8분/);
  assert.match(개편_전, /환승 없음/);
  assert.match(개편_전, /정류장[^<]*16곳/);
  assert.match(개편_전, /도보 합계[^<]*175m/);
  assert.match(개편_전, /배차간격[^<]*정보 없음/);
  assert.match(개편_전, /추정치/);
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
  assert.ok(카드(정방향, "before").includes("순환01"), "앞에서 뒤로는 순환01이 직행이다");

  const 역방향 = await 비교(교육대, 시청);
  assert.ok(!역방향.includes("순환01"), "뒤에서 앞으로는 한 바퀴를 넘겨야 하므로 없다");
  assert.ok(카드(역방향, "before").includes("경로 없음"), 카드(역방향, "before"));
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
