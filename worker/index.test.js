/**
 * Worker의 바깥만 검사한다 — `fetch(request, env)`에 `Request`를 넣고 나온 응답 문자열.
 *
 * 이음새는 이 하나다(스펙의 이음새 ②). 안의 함수 모양은 이 파일이 모른다.
 * 번들은 빌드가 만든 것을 그대로 쓴다 — 먼저 `python -m tools.build`를 돌려야 한다(`npm test`가 부른다).
 *
 *     node --test "worker/*.test.js"
 */
import assert from "node:assert/strict";
import test from "node:test";

import worker from "./index.js";
import * as rules from "./rules.js";

/** 정적 자산 바인딩 대신 세우는 가짜 — 요청이 여기로 흘러갔는지만 본다. */
const env = {
  ASSETS: {
    fetch: () => new Response("정적 자산", { headers: { "content-type": "text/html" } }),
  },
};

const 부른다 = (url) => worker.fetch(new Request(`https://example.com${url}`), env);

test("/compare는 준비 중 조각을 돌려준다", async () => {
  const 응답 = await 부른다("/compare?from=35.17,126.90&to=35.13,126.79");
  assert.equal(응답.status, 200);
  assert.match(응답.headers.get("content-type"), /text\/html/);
  assert.match(await 응답.text(), /준비 중/);
});

test("/journey는 준비 중 조각을 돌려준다", async () => {
  assert.match(await (await 부른다("/journey/abc")).text(), /준비 중/);
});

test("/places는 한 글자에는 빈 조각을, 두 글자에는 Kakao 후보 다섯 개를 돌려준다", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalCaches = globalThis.caches;
  const calls = [];
  const cached = new Map();
  globalThis.caches = {
    default: {
      async match(request) { return cached.get(request.url)?.clone(); },
      async put(request, response) { cached.set(request.url, response.clone()); },
    },
  };
  globalThis.fetch = async (url) => {
    calls.push(new URL(url));
    return Response.json({ documents: Array.from({ length: 6 }, (_, index) => ({
      place_name: `전남대 ${index + 1}`,
      address_name: `광주 ${index + 1}`,
      y: `35.17${index}`,
      x: `126.90${index}`,
    })) });
  };
  t.after(() => {
    globalThis.fetch = originalFetch;
    globalThis.caches = originalCaches;
  });

  assert.equal(await (await 부른다("/places?q=전")).text(), "");
  const first = await (await 부른다("/places?q=전남대")).text();
  const second = await (await 부른다("/places?q=전남대")).text();

  assert.equal((first.match(/<li\b/g) ?? []).length, 5);
  assert.match(first, /전남대 1/);
  assert.match(first, /광주 1/);
  assert.match(first, /data-lat="35\.170"/);
  assert.match(first, /data-lng="126\.900"/);
  assert.equal(first, second);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].searchParams.get("query"), "전남대");
  assert.ok(calls[0].searchParams.get("rect"));
});

test("/places는 Kakao 실패 때 한 줄 안내 조각을 돌려준다", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalCaches = globalThis.caches;
  globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
  globalThis.fetch = async () => new Response("failed", { status: 500 });
  t.after(() => {
    globalThis.fetch = originalFetch;
    globalThis.caches = originalCaches;
  });

  const html = await (await 부른다("/places?q=실패")).text();
  assert.match(html, /^<p class="notice">.+<\/p>$/);
});

test("/ 와 노선번호 탭 조각은 정적 자산으로 흘러간다", async () => {
  for (const url of ["/", "/index.html", "/route/문흥18.html", "/site.css"]) {
    assert.equal(await (await 부른다(url)).text(), "정적 자산", url);
  }
});

test("화면 문구에 옛 용어가 없다", async () => {
  const 글 = await (await 부른다("/compare")).text();
  for (const 옛말 of ["기존", "신규", "현행"]) {
    assert.ok(!글.includes(옛말), `조각에 「${옛말}」`);
  }
});

test("번들이 Worker에 실려 있다", async () => {
  // 뼈대 단계에서 번들을 아무 데도 안 쓰면 번들러가 지운다. 배포 크기를 재기 전에 여기서 잡는다
  // 줄 수 자체는 번들 검사(pytest)가 본다. 여기서는 번들이 살아 있다는 것만 본다
  const 표식 = (await 부른다("/compare")).headers.get("x-bundle");
  assert.match(표식, /^stops=[1-9]\d{3,} routes=[1-9]\d{2,}$/);
});

test("규칙 상수는 rules 한 곳에 있다", () => {
  assert.equal(rules.WALK_RADIUS_M, 500);
  assert.equal(rules.WALK_RADIUS_MAX_M, 1000);
  assert.equal(rules.TRANSFER_WALK_M, 350);
  assert.equal(rules.MAX_TRANSFERS, 2);
  assert.equal(rules.SECONDS_PER_STOP, 20);
  assert.equal(rules.WALK_SPEED_KMH, 4);
  assert.equal(rules.PLACE_QUERY_MIN_LENGTH, 2);
  assert.equal(rules.PLACE_CACHE_SECONDS, 86400);
});
