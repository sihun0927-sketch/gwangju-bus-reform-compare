/**
 * 배차간격 함수의 바깥만 검사한다 — `answer(물음)`이 돌려준 기록과 `/headway`의 응답.
 *
 * 이 파일이 지키는 것은 값의 크기가 아니라 **모양과 안정성**이다. 값이 맞는지는 파이썬 쪽
 * (`tests/test_headway.py`)과 실측(`tools/measure_headway.py`)이 본다. 여기서 보는 것은
 * 「몇 번을 물어도 같은 답이 나오는가」와 「무엇을 물어도 던지지 않는가」다.
 *
 * 표를 빌드가 만들므로 먼저 `python -m tools.build`를 돌려야 한다(`npm test`가 부른다).
 *
 *     node --test worker/headway.test.js
 */
import assert from "node:assert/strict";
import test from "node:test";

import table from "./headway.json" with { type: "json" };
import worker from "./index.js";
import { CONFIDENCES, VERDICTS, answer, normalise, overview, resolveAfter } from "./headway.js";

const env = {
  ASSETS: { fetch: () => new Response("정적 자산", { headers: { "content-type": "text/html" } }) },
};

const ROUTES = Object.keys(table.노선);

/** 같은 물음을 여러 번 물어 답이 글자 하나까지 같은지 본다. */
function repeat(query, times) {
  const seen = new Set();
  for (let i = 0; i < times; i += 1) seen.add(JSON.stringify(answer(query)));
  return seen;
}

test("표에 개편 후 노선 118개가 있다", () => {
  assert.equal(ROUTES.length, 118);
  assert.equal(table.망.개편후노선, 118);
});

test("같은 노선을 1000번 물어도 답이 바이트 단위로 같다", () => {
  for (const name of ["간선18", "지선76", "급행03", "228"]) {
    assert.equal(repeat(name, 1000).size, 1, `${name}의 답이 갈렸다`);
  }
});

test("다른 노선을 사이에 끼워 물어도 답이 안 바뀐다 — 부르는 차례가 답을 안 건드린다", () => {
  const first = JSON.stringify(answer("간선18"));
  for (const other of ROUTES) answer(other);
  assert.equal(JSON.stringify(answer("간선18")), first);
});

test("노선 118개 전부가 같은 모양의 기록을 준다", () => {
  const shape = Object.keys(answer(ROUTES[0])).join(",");
  for (const name of ROUTES) {
    const got = answer(name);
    assert.equal(Object.keys(got).join(","), shape, `${name}의 기록 모양이 다르다`);
    assert.equal(got.찾음, true);
    assert.equal(got.노선, name);
  }
});

test("표기가 흔들려도 한 노선으로 모인다", () => {
  const canonical = JSON.stringify({ ...answer("간선18"), 물음: "" });
  for (const query of ["간선18", "간선 18", " 간선18 ", "간선18번", "간선18(기본)", "간선 18 번버스"]) {
    assert.equal(JSON.stringify({ ...answer(query), 물음: "" }), canonical, `${query}가 다른 답을 냈다`);
  }
  // 숫자만 적힌 것은 앞자리 0을 무시하고, 급행 아닌 것으로 읽는다(ADR-0006)
  assert.equal(answer("18").노선, "간선18");
  assert.equal(answer("018").노선, "간선18");
  assert.equal(resolveAfter("01"), "간선01");
});

test("급행과 간선은 숫자가 같아도 안 섞인다", () => {
  assert.equal(answer("급행03").노선, "급행03");
  assert.equal(answer("간선03").노선, "간선03");
  assert.notEqual(answer("급행03").배차간격, undefined);
  assert.equal(answer("03").노선, "간선03");
});

test("개편 전 번호로 물으면 대체 노선을 모아 답한다", () => {
  const got = answer("문흥18");
  assert.equal(got.갈래, "개편전");
  assert.deepEqual(got.대체노선, ["간선18", "지선10"]);
  assert.equal(got.배차간격, table.개편전.문흥18.배차간격);
  assert.equal(got.대체.length, 2);
  assert.ok(got.뼈대.some((line) => line.includes("간선18")));
});

test("개편 전 방면 접미를 붙여 물어도 같은 노선이다", () => {
  assert.equal(answer("두암81(각화초교.장등동)").노선, "두암81");
  assert.equal(answer("두암81").갈래, "개편전");
});

test("무엇을 넣어도 던지지 않고 같은 모양으로 답한다", () => {
  const keys = Object.keys(answer("없는번호9999")).join(",");
  for (const query of [null, undefined, "", "   ", 18, {}, [], "ㅁㄴㅇㄹ", "간선99999", "급행18"]) {
    const got = answer(query);
    assert.equal(typeof got, "object");
    assert.ok(Array.isArray(got.뼈대) && got.뼈대.length > 0, `${String(query)}에 뼈대가 없다`);
    assert.ok(got.망, "망 수지는 늘 붙는다");
    if (!got.찾음) assert.equal(Object.keys(got).join(","), keys);
  }
  assert.equal(answer("간선99999").찾음, false);
  assert.equal(answer("급행18").찾음, false, "급행18은 없는 노선이다");
});

test("권고 등급과 확신이 유한 집합에서만 나온다", () => {
  assert.deepEqual(VERDICTS, ["증차 필요", "재배치 검토", "현행 적정", "여력 있음"]);
  assert.deepEqual(CONFIDENCES, ["높음", "보통", "낮음"]);
  for (const name of ROUTES) {
    const got = answer(name);
    assert.ok(VERDICTS.includes(got.등급), `${name}의 등급 ${got.등급}`);
    assert.ok(CONFIDENCES.includes(got.확신), `${name}의 확신 ${got.확신}`);
  }
});

test("등급마다 수치 근거가 함께 온다 — 등급만 있고 수가 없는 답은 없다", () => {
  for (const name of ROUTES) {
    const { 근거, 차량, 밴드 } = answer(name);
    assert.ok(근거.종류중앙배차 > 0 && 근거.종류대비 > 0, `${name}의 근거가 비었다`);
    assert.ok(근거.운행횟수 > 0 && 근거.왕복시간 > 0, `${name}의 근거가 비었다`);
    assert.ok(차량.지금 > 0 && 차량.한대더 > 0, `${name}의 차량 수가 비었다`);
    assert.ok(밴드[0] <= 밴드[1], `${name}의 밴드가 뒤집혔다`);
    assert.ok(차량.한대더 < 차량.지금 * 1000, `${name}의 차량 계산이 이상하다`);
  }
});

test("차량을 더 넣을수록 배차가 짧아진다", () => {
  for (const name of ROUTES) {
    const { 차량 } = answer(name);
    assert.ok(차량.한대더 > 차량.두대더, `${name}`);
    assert.ok(차량.두대더 > 차량.세대더, `${name}`);
  }
});

test("확신이 낮은 노선은 점 추정을 안 내고 범위로만 말한다", () => {
  const low = ROUTES.filter((n) => answer(n).확신 === "낮음");
  assert.ok(low.length > 0, "확신 낮은 노선이 하나는 있어야 이 검사가 뜻이 있다");
  for (const name of low) {
    const got = answer(name);
    assert.equal(got.배차간격, null, `${name}이 점 추정을 냈다`);
    assert.ok(got.뼈대[0].includes("~"), `${name}의 첫 줄이 범위가 아니다`);
  }
  for (const name of ROUTES.filter((n) => answer(n).확신 !== "낮음")) {
    assert.ok(answer(name).배차간격 > 0, `${name}에 점 추정이 없다`);
  }
});

test("밴드가 점 추정을 감싼다", () => {
  for (const name of ROUTES) {
    const got = answer(name);
    if (got.배차간격 === null) continue;
    assert.ok(got.밴드[0] <= got.배차간격 + 0.05 && got.배차간격 <= got.밴드[1] + 0.05, `${name}`);
  }
});

test("망 이야기는 어느 노선을 묻든 같다", () => {
  const line = answer(ROUTES[0]).뼈대.at(-2);
  for (const name of ROUTES) assert.equal(answer(name).뼈대.at(-2), line);
  assert.ok(line.includes("8394") && line.includes("9355"));
});

test("추정이지 발표가 아니라는 말이 모든 노선 답에 있다", () => {
  for (const name of ROUTES) {
    assert.ok(answer(name).뼈대.at(-1).includes("추정"), `${name}`);
  }
});

test("normalise는 공백과 꼬리말만 뗀다", () => {
  assert.equal(normalise(" 간선 18 번 "), "간선18");
  assert.equal(normalise("지선97(빛그린산단출근)"), "지선97");
  assert.equal(normalise(null), "");
  assert.equal(normalise(228), "228");
});

test("망 전체 답에도 뼈대가 있다", () => {
  const got = overview();
  assert.equal(got.노선수, 118);
  assert.ok(got.뼈대.length >= 3);
  assert.equal(JSON.stringify(overview()), JSON.stringify(overview()));
});

test("/headway가 노선 기록을 JSON으로 준다", async () => {
  const res = await worker.fetch(new Request("https://x/headway?route=간선18"), env);
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /application\/json/);
  const body = JSON.parse(await res.text());
  assert.equal(body.노선, "간선18");
  assert.deepEqual(body, answer("간선18"));
});

test("/headway에 번호를 안 주면 망 전체를 준다", async () => {
  const res = await worker.fetch(new Request("https://x/headway"), env);
  assert.equal(JSON.parse(await res.text()).노선수, 118);
});

test("/headway가 없는 번호에도 200과 안내를 준다 — LLM이 예외를 만나지 않는다", async () => {
  const res = await worker.fetch(new Request("https://x/headway?route=없는번호"), env);
  assert.equal(res.status, 200);
  const body = JSON.parse(await res.text());
  assert.equal(body.찾음, false);
  assert.ok(body.뼈대[0].includes("못 찾았다"));
});

test("/headway 두 번 부르면 같은 글자가 온다", async () => {
  const once = async () => (await worker.fetch(new Request("https://x/headway?route=지선76"), env)).text();
  assert.equal(await once(), await once());
});

test("다른 경로는 전과 같이 돈다", async () => {
  const res = await worker.fetch(new Request("https://x/index.html"), env);
  assert.equal(await res.text(), "정적 자산");
});
