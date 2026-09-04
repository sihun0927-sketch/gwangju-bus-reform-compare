/**
 * 추론 층의 바깥만 검사한다 — 가짜 모형을 끼우고 나온 값과 조각.
 *
 * 진짜 모형은 여기서 안 부른다. 돈이 들고, 답이 매번 달라 검사가 흔들리며, 키가 리포에 없다.
 * 대신 **모형이 무엇을 내놓든** 우리 층이 지키는 것을 본다 — 밴드 밖으로 안 나가는가,
 * 여러 표본을 한 점으로 모으는가, 모형이 지어낸 글자가 화면으로 새지 않는가.
 *
 * 진짜 키로 한 번 불러 보는 것은 이 파일이 못 하는 일이라 GATES.md의 G27로 남겨 두었다.
 *
 *     node --test worker/infer.test.js
 */
import assert from "node:assert/strict";
import test from "node:test";

import { answer } from "./headway.js";
import {
  KEY_ENV, MODEL, MODEL_ENV, PROVIDERS, REASON_MAX, SAMPLES, fragment, infer, looksLikeKey,
  median, pick, respond, settle,
} from "./infer.js";
import worker from "./index.js";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const env = { ASSETS: { fetch: () => new Response("정적 자산") } };
const 기록 = answer("급행03"); // 확신 「높음」 — 밴드가 좁아 가두기를 보기 좋다
const 갈린기록 = answer("간선18"); // 확신 「낮음」 — 점 추정을 안 내는 쪽

/** 정해진 답을 차례로 내놓는 가짜 모형. 보낸 요청도 모아 둔다. */
function 가짜(답들, { 온도거부 = false } = {}) {
  const 보낸것 = [];
  let i = 0;
  return {
    보낸것,
    chat: {
      completions: {
        parse: async (request) => {
          보낸것.push(request);
          // 추론 계열 모형 흉내 — `temperature`가 붙어 오면 400으로 되받는다
          if (온도거부 && request.temperature !== undefined) {
            const e = new Error("Unsupported parameter: 'temperature' is not supported");
            e.status = 400;
            throw e;
          }
          const 값 = 답들[i % 답들.length];
          i += 1;
          if (값 instanceof Error) throw 값;
          return { choices: [{ message: { parsed: 값 } }], usage: { total_tokens: 1 } };
        },
      },
    },
  };
}

const 답 = (배차, 적합 = 배차, 이유 = "근거대로 봤다") => ({
  배차간격: 배차,
  적합배차간격: 적합,
  이유,
});

/** 씨앗 고정 난수 — 흔들림을 재는 검사가 돌릴 때마다 달라지면 안 된다. */
function 난수(씨앗) {
  let x = 씨앗;
  return () => {
    x = (x * 1664525 + 1013904223) % 4294967296;
    return x / 4294967296;
  };
}

const 표준편차 = (xs) => {
  const m = xs.reduce((a, b) => a + b, 0) / xs.length;
  return Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / xs.length);
};

test("median이 가운데 값을 낸다", () => {
  assert.equal(median([3, 1, 2]), 2);
  assert.equal(median([4, 1, 3, 2]), 2.5);
  assert.equal(median([7]), 7);
});

test("키가 없으면 부르지 않고 null을 준다", async () => {
  assert.equal(await infer(기록, {}), null);
  assert.equal(await infer(기록, { OTHER: "x" }), null);
});

test("`.dev.vars.example`에 적어 둔 자리 값이 **하나도** 키로 안 읽힌다", async () => {
  // 이 검사가 없으면, 자리만 잡아 둔 값을 들고 표본 셋을 던져 401 셋을 받고 버린다.
  // 파일에 실제로 적힌 글자를 읽어 본다 — 틀을 고치면 이 검사가 같이 움직여야 한다.
  // 틀에는 제공자마다 한 줄씩 있으므로 줄을 다 훑는다
  const 뿌리 = join(dirname(fileURLToPath(import.meta.url)), "..");
  const 틀 = readFileSync(join(뿌리, ".dev.vars.example"), "utf8");
  const 자리줄 = 틀
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => /^[A-Z0-9_]+_API_KEY=/.test(l));
  assert.ok(자리줄.length >= 1, ".dev.vars.example에 키 줄이 없다");
  assert.ok(
    자리줄.some((l) => l.startsWith(`${KEY_ENV}=`)),
    `.dev.vars.example에 ${KEY_ENV}= 줄이 없다 — 코드가 읽는 이름과 틀이 갈렸다`,
  );
  for (const 줄 of 자리줄) {
    const 자리값 = 줄.slice(줄.indexOf("=") + 1).trim();
    assert.ok(자리값.length > 0, `${줄}: 자리 값이 비면 사람이 어디에 넣을지 모른다`);
    assert.equal(looksLikeKey(자리값), false, `자리 값이 키로 읽힌다: ${줄}`);
  }
  const 내것 = 자리줄.find((l) => l.startsWith(`${KEY_ENV}=`));
  assert.equal(await infer(기록, { [KEY_ENV]: 내것.slice(내것.indexOf("=") + 1) }), null);
});

test("키처럼 생긴 것만 키로 본다 — 제공자마다 꼴이 달라 앞머리로 안 가린다", () => {
  // 실제로 겪은 것들이다. 앞머리를 목록으로 두었더니 살아 있는 Gemini 키를 「모르는 꼴」이라 했다
  assert.equal(looksLikeKey(`sk-ant-api03-${"x".repeat(60)}`), true, "Anthropic 꼴");
  assert.equal(looksLikeKey(`sk-proj-${"x".repeat(160)}`), true, "OpenAI 꼴");
  assert.equal(looksLikeKey(`AQ.Ab8RN6${"x".repeat(44)}`), true, "Gemini 꼴");
  assert.equal(looksLikeKey(`AIza${"x".repeat(35)}`), true, "Google 옛 꼴");
  for (const 아닌것 of [undefined, null, "", "   ", "AIza여기에_키_붙여넣기", "짧음", 12345, {}]) {
    assert.equal(looksLikeKey(아닌것), false, String(아닌것));
  }
});

test("어느 키가 들어와 있는지가 제공자를 정한다", () => {
  assert.equal(pick({}), null);
  const 진짜 = "x".repeat(40);
  const 첫째 = pick({ [PROVIDERS[0].키]: 진짜 });
  assert.equal(첫째.제공자, PROVIDERS[0].이름);
  assert.equal(첫째.모형, PROVIDERS[0].모형);
  assert.equal(첫째.밑주소, PROVIDERS[0].밑주소);
  // 위에서부터 찾으므로 첫째가 있으면 첫째다
  const 둘다 = pick({ [PROVIDERS[0].키]: 진짜, [PROVIDERS[1].키]: 진짜 });
  assert.equal(둘다.제공자, PROVIDERS[0].이름);
  // 둘째만 있으면 둘째
  const 둘째 = pick({ [PROVIDERS[1].키]: 진짜 });
  assert.equal(둘째.제공자, PROVIDERS[1].이름);
  assert.equal(둘째.모형, PROVIDERS[1].모형);
});

test("제공자 표가 저마다 다른 키 이름을 쓴다 — 겹치면 하나가 다른 것을 가린다", () => {
  const 이름들 = PROVIDERS.map((p) => p.키);
  assert.equal(new Set(이름들).size, 이름들.length, 이름들.join(" · "));
  for (const p of PROVIDERS) {
    assert.ok(p.모형, `${p.이름}에 기본 모형이 없다`);
    assert.ok(/^[A-Z0-9_]+$/.test(p.키), `${p.키}는 환경 변수 이름 꼴이 아니다`);
  }
});

test("키가 없어도 조각이 나오고 계산값을 보인다", async () => {
  const html = fragment(기록, null);
  assert.match(html, /data-state="계산"/);
  assert.match(html, /12\.6분/);
  assert.match(html, /추론 없이 계산값/);
});

test("/headway/{노선}이 키 없이도 200과 조각을 준다", async () => {
  const res = await worker.fetch(new Request("https://x/headway/급행03"), env);
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /text\/html/);
  assert.equal(res.headers.get("x-headway"), "mode=computed reason=no-key");
  assert.match(await res.text(), /headway-now/);
});

test("머리글이 Latin-1로만 되어 있다 — 한글을 실으면 Response가 던진다", async () => {
  const res = await worker.fetch(new Request("https://x/headway/급행03"), env);
  for (const [, value] of res.headers) {
    assert.ok(/^[\x20-\x7e]*$/.test(value), `머리글에 Latin-1 밖 글자: ${value}`);
  }
});

test("없는 번호에도 200과 안내를 준다 — 「계산중」이 영영 남지 않는다", async () => {
  const res = await worker.fetch(new Request("https://x/headway/없는번호9999"), env);
  assert.equal(res.status, 200);
  assert.match(await res.text(), /낼 수 없습니다/);
});

test("개편 전 번호로 불러도 틀린 수를 안 보인다", () => {
  assert.match(fragment(answer("문흥18"), null), /낼 수 없습니다/);
});

test("밴드 밖 답을 가둔다 — 대조군으로 밴드 안 답은 그대로 통과시킨다", () => {
  const [아래, 위] = 기록.밴드;
  // 대조군 — 밴드 안이면 손대지 않는다. 이것이 통과해야 아래 검사가 뜻이 있다
  const 안쪽 = 위 - 0.4;
  assert.equal(settle([답(안쪽)], 기록).배차간격, Math.round(안쪽 * 10) / 10);
  // 밖이면 가둔다. 위아래 둘 다
  assert.equal(settle([답(9999)], 기록).배차간격, Math.round(위 * 10) / 10);
  assert.equal(settle([답(0.01)], 기록).배차간격, Math.round(아래 * 10) / 10);
  assert.equal(settle([답(-5)], 기록).배차간격, Math.round(아래 * 10) / 10);
});

test("적합 배차간격도 빌드 값의 두 배 밖으로는 못 간다", () => {
  const 빌드값 = 기록.적합.배차;
  assert.ok(settle([답(13, 9999)], 기록).적합배차간격 <= 빌드값 * 2 + 0.05);
  assert.ok(settle([답(13, 0.001)], 기록).적합배차간격 >= 빌드값 / 2 - 0.05);
  assert.equal(settle([답(13, 빌드값)], 기록).적합배차간격, 빌드값);
});

test("흩어진 표본을 한 점으로 모은다", () => {
  const 모은것 = settle([답(11.5), 답(13.0), 답(14.5)], 기록);
  assert.equal(모은것.배차간격, 13);
  assert.deepEqual(모은것.표본, [11.5, 13, 14.5]);
  assert.equal(모은것.버린표본, 0);
});

test("표본을 늘리면 흔들림이 준다 — 이것이 중심수렴의 실체다", () => {
  const 밴드폭 = 기록.밴드[1] - 기록.밴드[0];
  const 시행 = (k) => {
    const rnd = 난수(20260904);
    const 중앙값들 = [];
    for (let t = 0; t < 300; t += 1) {
      const 표본 = Array.from({ length: k }, () =>
        답(기록.밴드[0] + rnd() * 밴드폭),
      );
      중앙값들.push(settle(표본, 기록).배차간격);
    }
    return 표준편차(중앙값들);
  };
  const 하나 = 시행(1);
  const 셋 = 시행(3);
  const 아홉 = 시행(9);
  assert.ok(셋 < 하나, `k=3(${셋.toFixed(3)})이 k=1(${하나.toFixed(3)})보다 좁아야 한다`);
  assert.ok(아홉 < 셋, `k=9(${아홉.toFixed(3)})가 k=3(${셋.toFixed(3)})보다 좁아야 한다`);
});

test("수가 아닌 표본은 버리고, 다 버려지면 null이라 계산값으로 내려앉는다", () => {
  assert.equal(settle([{ 배차간격: "열세", 적합배차간격: 1 }], 기록), null);
  assert.equal(settle([null, undefined], 기록), null);
  assert.equal(settle([{ 배차간격: NaN, 적합배차간격: 1 }], 기록), null);
  assert.equal(settle([], 기록), null);
  const 섞임 = settle([null, 답(13), { 배차간격: Infinity, 적합배차간격: 1 }], 기록);
  assert.equal(섞임.배차간격, 13);
  assert.equal(섞임.버린표본, 2);
});

test("운용 대수는 묻지 않고 셈한다 — 화면의 두 수가 어긋나지 않는다", () => {
  const 모은것 = settle([답(13, 20)], 기록);
  const 왕복 = 기록.근거.왕복시간;
  assert.equal(모은것.운용대수, Math.round((왕복 / 모은것.배차간격) * 10) / 10);
  assert.equal(모은것.적합운용대수, Math.round((왕복 / 모은것.적합배차간격) * 10) / 10);
});

test("늦은 표본은 마감에서 버리고 온 것으로 답한다 — 카드가 붙들리지 않는다", async () => {
  // 표본 하나가 아주 늦게 오는 모형. 마감이 없으면 카드가 그 하나를 기다린다
  const 느린놈 = {
    보낸것: [],
    chat: {
      completions: {
        parse: async (request) => {
          느린놈.보낸것.push(request);
          if (느린놈.보낸것.length === 1) return { choices: [{ message: { parsed: 답(13) } }] };
          await new Promise((r) => setTimeout(r, 5_000));
          return { choices: [{ message: { parsed: 답(99) } }] };
        },
      },
    },
  };
  const 잰시각 = Date.now();
  const 모은것 = await infer(기록, {}, { client: 느린놈, samples: 3, deadline: 120 });
  const 걸린 = Date.now() - 잰시각;
  assert.ok(걸린 < 1_000, `마감이 안 먹었다: ${걸린}ms`);
  assert.equal(모은것.배차간격, 13, "제때 온 표본으로 답해야 한다");
  assert.equal(모은것.표본.length, 1);
});

test("마감 안에 하나도 안 오면 null이라 계산값으로 내려앉는다", async () => {
  const 다느림 = {
    chat: { completions: { parse: async () => {
      await new Promise((r) => setTimeout(r, 5_000));
      return { choices: [{ message: { parsed: 답(13) } }] };
    } } },
  };
  const 잰시각 = Date.now();
  assert.equal(await infer(기록, {}, { client: 다느림, samples: 2, deadline: 100 }), null);
  assert.ok(Date.now() - 잰시각 < 1_000);
});

test("주소가 망가져 있어도 500을 안 낸다 — 500이면 「계산중…」이 영영 남는다", async () => {
  // `decodeURIComponent`가 던지는 입력이다. 던지면 htmx가 조각을 안 끼운다
  const res = await respond("%EA%B0%84%EC%84%A018", {});
  assert.equal(res.status, 200);
  const 망가짐 = await respond("%", {});
  assert.equal(망가짐.status, 200);
  assert.match(await 망가짐.text(), /낼 수 없습니다/);
  const 반쪽 = await respond("%E0%A4%A", {});
  assert.equal(반쪽.status, 200);
});

test("모형이 던져도 죽지 않고 남은 표본으로 답한다", async () => {
  const client = 가짜([new Error("429"), 답(13), 답(13)]);
  const 모은것 = await infer(기록, {}, { client, samples: 3 });
  assert.equal(모은것.배차간격, 13);
  assert.equal(모은것.버린표본, 1);
});

test("다 던지면 null이고 조각은 계산값을 보인다", async () => {
  const client = 가짜([new Error("500")]);
  assert.equal(await infer(기록, {}, { client, samples: 3 }), null);
  assert.match(fragment(기록, null), /계산값/);
});

test("낮은 온도와 구조화 출력을 함께 보낸다 — 흔들림 손잡이 둘", async () => {
  const client = 가짜([답(13)]);
  await infer(기록, {}, { client, samples: 1 });
  const 보냄 = client.보낸것[0];
  assert.equal(보냄.model, MODEL);
  assert.ok(보냄.temperature > 0 && 보냄.temperature <= 0.5, `온도 ${보냄.temperature}`);
  assert.ok(보냄.response_format, "구조화 출력이 있어야 한다");
  assert.equal(보냄.response_format.type, "json_schema");
  assert.equal(보냄.messages[0].role, "system");
  assert.equal(보냄.messages[1].role, "user");
});

test("온도를 거부하는 모형이면 그것만 빼고 한 번 다시 부른다", async () => {
  const client = 가짜([답(13)], { 온도거부: true });
  const 모은것 = await infer(기록, {}, { client, samples: 1 });
  assert.equal(모은것.배차간격, 13, "다시 부른 결과가 와야 한다");
  assert.equal(client.보낸것.length, 2, "한 번 더 부른다");
  assert.ok(client.보낸것[0].temperature !== undefined, "처음에는 온도를 넣는다");
  assert.equal(client.보낸것[1].temperature, undefined, "두 번째는 뺀다");
});

test("온도 말고 다른 까닭의 400은 그대로 실패로 둔다 — 조용히 삼키지 않는다", async () => {
  const 딴것 = new Error("Invalid schema");
  딴것.status = 400;
  const client = 가짜([딴것]);
  assert.equal(await infer(기록, {}, { client, samples: 2 }), null);
  assert.equal(client.보낸것.length, 2, "다시 부르지 않는다 — 표본마다 한 번씩만");
});

test("모형 이름을 환경에서 덮어쓸 수 있다 — 표의 기본값보다 이긴다", async () => {
  const client = 가짜([답(13)]);
  await infer(기록, { [MODEL_ENV]: "딴모형" }, { client, samples: 1 });
  assert.equal(client.보낸것[0].model, "딴모형");
  const 키있음 = 가짜([답(13)]);
  await infer(기록, { [KEY_ENV]: "x".repeat(40), [MODEL_ENV]: "딴모형" }, { client: 키있음, samples: 1 });
  assert.equal(키있음.보낸것[0].model, "딴모형");
});

test("표본 수만큼 부른다", async () => {
  const client = 가짜([답(13)]);
  await infer(기록, {}, { client });
  assert.equal(client.보낸것.length, SAMPLES);
});

test("근거는 같은 노선이면 늘 같은 글자다 — 여기가 흔들리면 답이 흔들린다", async () => {
  const a = 가짜([답(13)]);
  const b = 가짜([답(13)]);
  await infer(기록, {}, { client: a, samples: 1 });
  await infer(기록, {}, { client: b, samples: 1 });
  assert.equal(a.보낸것[0].messages[0].content, b.보낸것[0].messages[0].content);
  assert.equal(a.보낸것[0].system, b.보낸것[0].system);
});

test("조각에 배차간격 · 적합 배차간격 · 운용 대수 · 「?」 상자가 다 있다", () => {
  const html = fragment(기록, settle([답(13, 15)], 기록));
  assert.match(html, /class="headway-now">13분/);
  assert.match(html, /적합 15분/);
  assert.match(html, /버스 [\d.]+대/);
  assert.match(html, /지금 [\d.]+대/);
  assert.match(html, /<details class="headway-why">/);
  assert.match(html, /<summary aria-label="왜 이렇게 계산했는지">\?<\/summary>/);
  assert.match(html, /data-state="추론"/);
  assert.match(html, /1번 물어/);
});

test("확신이 낮은 노선은 조각도 범위로 말한다", () => {
  const html = fragment(갈린기록, null);
  assert.match(html, /9\.6~74\.7분/);
  assert.match(html, /크게 갈리는 노선/);
});

test("모형이 지어낸 글자가 화면으로 새지 않는다", () => {
  const 나쁜 = settle([답(13, 15, '<script>alert(1)</script>"><img src=x>')], 기록);
  const html = fragment(기록, 나쁜);
  assert.ok(!html.includes("<script>"), "스크립트 태그가 그대로 들어갔다");
  assert.ok(!html.includes("<img"), "태그가 그대로 들어갔다");
  assert.match(html, /&lt;script&gt;/);
});

test("이유가 길면 잘린다 — 「?」 상자는 짧아야 읽힌다", () => {
  const 긴 = "가".repeat(REASON_MAX * 3);
  assert.equal(settle([답(13, 15, 긴)], 기록).이유.length, REASON_MAX);
});

test("추론이 붙으면 머리글이 표본 수와 가둔 수를 밝힌다", async () => {
  // `worker.fetch`로는 가짜 모형을 못 끼운다(index는 옵션을 안 넘긴다). 그래서 조각 경로를
  // 직접 부른다 — 진짜 키를 넣어 검사에서 API를 부르는 일은 하지 않는다
  const client = 가짜([답(13), 답(9999), 답(13)]);
  const res = await respond("급행03", {}, { client, samples: 3 });
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("x-headway"), "mode=inferred samples=3 clamped=1");
  const html = await res.text();
  assert.match(html, /data-state="추론"/);
  assert.match(html, /3번 물어/);
});

test("검사가 진짜 API를 부르지 않는다 — 가짜 모형을 안 끼우면 키가 없어 부르지 않는다", async () => {
  assert.equal(await infer(기록, {}), null);
  assert.match((await respond("급행03", {})).headers.get("x-headway"), /^mode=computed reason=no-key/);
});

test("계산값으로 내려앉은 까닭을 머리글이 밝힌다 — 고치는 방법이 다르기 때문이다", async () => {
  // 키가 아예 없을 때
  const 키없음 = await respond("급행03", {});
  assert.equal(키없음.headers.get("x-headway"), "mode=computed reason=no-key");

  // 키는 있는데 표본이 다 버려졌을 때(할당량·시간 초과). 여기서 진짜로 부르지는 않는다
  const 다실패 = 가짜([new Error("429 quota")]);
  const 표본없음 = await respond("급행03", { [KEY_ENV]: "x".repeat(40) }, { client: 다실패, samples: 2 });
  const 머리 = 표본없음.headers.get("x-headway");
  assert.match(머리, /^mode=computed reason=no-samples/);
  assert.match(머리, /provider=\w+ model=/);
  assert.notEqual(머리, 키없음.headers.get("x-headway"), "둘이 같으면 가릴 수가 없다");
});

test("다른 경로는 전과 같이 돈다", async () => {
  assert.equal(await (await worker.fetch(new Request("https://x/index.html"), env)).text(), "정적 자산");
  const json = await worker.fetch(new Request("https://x/headway?route=급행03"), env);
  assert.match(json.headers.get("content-type"), /application\/json/);
});
