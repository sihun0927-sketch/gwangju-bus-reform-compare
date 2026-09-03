/**
 * Worker의 바깥만 검사한다 — `fetch(request, env)`에 `Request`를 넣고 나온 응답 문자열.
 *
 * 이음새는 이 하나다(스펙의 이음새 ②). 안의 함수 모양은 이 파일이 모른다.
 * 번들은 빌드가 만든 것을 그대로 쓴다 — 먼저 `python -m tools.build`를 돌려야 한다(`npm test`가 부른다).
 *
 *     node --test "worker/*.test.js"
 */
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import worker from "./index.js";
import * as rules from "./rules.js";

/** 정적 자산 바인딩 대신 세우는 가짜 — 요청이 여기로 흘러갔는지만 본다. */
const env = {
  ASSETS: {
    fetch: () => new Response("정적 자산", { headers: { "content-type": "text/html" } }),
  },
};

const 부른다 = (url) => worker.fetch(new Request(`https://example.com${url}`), env);

test("/compare는 HTML 조각을 돌려준다", async () => {
  // 안에 무엇이 실리는지는 `compare.test.js`가 본다. 여기서는 주소가 코드로 온다는 것만
  const 응답 = await 부른다("/compare?from=35.1702,126.9040&to=35.1381,126.7918");
  assert.equal(응답.status, 200);
  assert.match(응답.headers.get("content-type"), /text\/html/);
  assert.match(await 응답.text(), /개편 전[\s\S]*개편 후/);
});

test("/places와 /journey는 아직 준비 중 조각을 돌려준다", async () => {
  for (const url of ["/places?q=전남대", "/journey/abc"]) {
    assert.match(await (await 부른다(url)).text(), /준비 중/, url);
  }
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

test("규칙 값이 rules 밖에 박혀 있지 않다", () => {
  // 값이 같기만 하면 앞 검사는 통과하므로, 「rules에서 **읽는지**」는 소스를 훑어야 알 수 있다.
  // 화면 문구("도보권 500m 안에")까지 포함해서다 — 규칙을 고칠 때 문구가 따로 낡는 것이 이 검사가 막는 것
  const 자리 = dirname(fileURLToPath(import.meta.url));
  // 한 자리 수(2·4·5·8)와 1000은 뺐다 — 셈이나 문자열("utf-8", 1km=1000m)에 흔히 나와
  // 규칙 값과 구별할 수 없다. 나머지 여섯은 이 검사가 잡는다
  const 규칙_값 = [
    rules.WALK_RADIUS_M,
    rules.WALK_RADIUS_STEP_M,
    rules.TRANSFER_WALK_M,
    rules.SECONDS_PER_STOP,
    rules.PLACE_CACHE_SECONDS,
    rules.PLACE_SEARCH_MARGIN_M,
  ];
  const 모듈 = readdirSync(자리).filter(
    (이름) => 이름.endsWith(".js") && 이름 !== "rules.js" && !이름.endsWith(".test.js"),
  );
  assert.ok(모듈.length > 1, 모듈);
  for (const 이름 of 모듈) {
    // 주석은 뺀다 — 규칙을 말로 설명한 곳(「출발지는 500m 안에」)은 박아 넣은 값이 아니다.
    // 이 파일들에는 `//`가 든 문자열이 없어 이만큼으로 충분하다
    const 글 = readFileSync(join(자리, 이름), "utf8")
      .replace(/\/\*[\s\S]*?\*\//g, " ")
      .replace(/\/\/.*$/gm, " ");
    for (const 값 of 규칙_값) {
      const 박힌_숫자 = new RegExp(`(^|[^0-9.])${값}([^0-9.]|$)`);
      assert.ok(!박힌_숫자.test(글), `${이름}에 규칙 값 ${값}이 그대로 적혀 있다`);
    }
  }
});
