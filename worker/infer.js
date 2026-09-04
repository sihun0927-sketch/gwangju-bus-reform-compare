/**
 * 배차간격 추론 층 — 「계산중」 뒤에 오는 값을 만든다 (ADR-0010).
 *
 * `headway.js`가 주는 것은 **빌드가 미리 계산해 둔 값**이라 늘 같다. 여기서 하는 일은 그 값을
 * 근거로 삼아 LLM에게 **다시 판단하게** 하는 것이다. 그래서 나오는 수는 표에 박힌 값이 아니라
 * 추론값이고, 부를 때마다 조금씩 다르다.
 *
 * ## 다른데 어떻게 한곳으로 모으나
 *
 * 부를 때마다 다른 수가 나와도 좋지만, 시민이 같은 노선을 두 번 물어 15분과 40분을 들으면
 * 답이 아니라 소음이다. 그래서 흔들림을 셋으로 줄인다.
 *
 * 1. **구조화 출력** — 답의 모양을 스키마로 못 박는다. 수가 아닌 것이 올 자리가 없다.
 * 2. **여러 번 물어 중앙값** — 같은 물음을 `SAMPLES`번 던져 가운데 값을 쓴다. 표본이 늘수록
 *    중앙값의 흔들림은 √n에 반비례해 줄어든다. 이것이 「무한히 물으면 한곳으로 모인다」의 실체다.
 * 3. **밴드 가두기** — 빌드가 낸 밴드 밖으로는 못 나간다. 모형 넷이 다 아니라고 한 값을
 *    LLM 혼자 부를 수는 없다.
 * 4. **낮은 온도** — `temperature`를 낮춰 애초에 덜 흩어지게 한다.
 *
 * 넷째는 제공자를 바꾸면서 얻은 것이다. 처음에 짰던 Claude Opus 5는 `temperature`를 아예 안 받아
 * (보내면 400) 셋으로만 버텨야 했다. 추론 계열 모형은 여전히 거부하므로, 거부당하면 그 인자만
 * 빼고 한 번 다시 부른다(`sample`).
 *
 * ## 제공자
 *
 * 부르는 방법은 하나뿐이다 — OpenAI SDK의 `chat.completions.parse`. Gemini도 OpenAI 호환 창구를
 * 열어 두어 밑주소만 바꾸면 같은 코드로 통한다. 그래서 제공자를 바꾸는 일이 코드가 아니라
 * `PROVIDERS` 표 한 줄이다. 어느 것을 쓸지는 **어느 키가 들어와 있는지**가 정한다.
 *
 * ## 대수는 왜 안 물어보나
 *
 * 운용 대수는 배차간격이 정해지면 나눗셈으로 따라 나온다(`왕복시간 ÷ 배차간격`). 그것마저
 * 따로 물으면 화면의 두 수가 서로 어긋날 수 있다 — 「19분인데 3대」처럼. 그래서 배차간격 둘만
 * 묻고 대수는 셈한다. 값은 추론을 따라 움직이되 서로 어긋나지는 않는다.
 *
 * ## 키가 없을 때
 *
 * 키가 없으면 부르지 않고 빌드가 낸 값을 그대로 보인다(ADR-0005가 Kakao 키에 쓴 방식과 같다).
 * 화면은 그대로 돌고, 「?」 상자가 추론 없이 나온 값이라고 밝힌다.
 */
import OpenAI from "openai";
import { zodResponseFormat } from "openai/helpers/zod";
import { z } from "zod";

import table from "./headway.json" with { type: "json" };
import { answer } from "./headway.js";

/** 한 물음에 몇 번 물을 것인가. 홀수라야 중앙값이 표본 하나로 딱 떨어진다. */
export const SAMPLES = 3;

/**
 * 쓸 수 있는 제공자들. **위에서부터 찾아 키가 있는 첫째를 쓴다.**
 *
 * 부르는 방법은 하나뿐이다 — OpenAI SDK의 `chat.completions.parse`. Gemini도 OpenAI 호환 창구를
 * 열어 두어서 밑주소만 바꾸면 같은 코드로 통한다(구조화 출력·`temperature`까지 그대로).
 * 그래서 제공자를 바꾸는 일이 **코드가 아니라 이 표 한 줄**이 된다.
 *
 * 모형 이름을 코드에 박되 덮어쓸 수 있게 둔다 — 계정마다 열려 있는 모형이 다르고, 옛 이름은
 * 신규 계정에 안 열리기도 한다(`gemini-2.5-flash`가 그랬다). 무엇이 열려 있는지는
 * `node tools/check_key.mjs --live`가 목록으로 낸다.
 */
export const PROVIDERS = [
  {
    이름: "gemini",
    키: "GEMINI_API_KEY",
    밑주소: "https://generativelanguage.googleapis.com/v1beta/openai/",
    모형: "gemini-3.6-flash",
    // 생각을 바짝 줄인다. 근거를 다 주었으니 깊이 생각할 것이 없는데, 두면 요청 하나가
    // **11초에 생각 토큰 646개**가 된다. 128로 묶으면 **2.1초에 생각 0**이고 답은 같았다.
    // `0`은 이 모형이 거부한다(400) — 끄는 것이 아니라 좁히는 것이다.
    추가: { extra_body: { google: { thinking_config: { thinking_budget: 128 } } } },
  },
  { 이름: "openai", 키: "OPENAI_API_KEY", 밑주소: "", 모형: "gpt-5", 추가: {} },
];

/** 덮어쓰기 이름. 제공자를 안 가리고 하나씩만 둔다. */
export const MODEL_ENV = "MODEL_NAME";
export const BASE_URL_ENV = "MODEL_BASE_URL";

/** 기본 제공자의 키 이름과 모형 — 글이나 검사가 「하나」를 가리켜야 할 때 쓴다. */
export const KEY_ENV = PROVIDERS[0].키;
export const MODEL = PROVIDERS[0].모형;

/**
 * 환경에서 쓸 제공자를 고른다. 없으면 `null`이고, 그때 화면은 계산값만 보인다.
 *
 * `MODEL_NAME`·`MODEL_BASE_URL`이 있으면 그것이 이긴다 — 표의 기본값은 어디까지나 기본값이다.
 */
export function pick(env = {}) {
  const 고른것 = PROVIDERS.find((p) => looksLikeKey(env[p.키]));
  if (!고른것) return null;
  return {
    제공자: 고른것.이름,
    키: env[고른것.키],
    밑주소: env[BASE_URL_ENV] || 고른것.밑주소,
    모형: env[MODEL_ENV] || 고른것.모형,
    추가: 고른것.추가 ?? {},
  };
}

/**
 * 흩어짐을 줄이는 셋째 손잡이. **Anthropic Opus 5에서는 못 쓰던 것**이다(그쪽은 `temperature`를
 * 아예 안 받는다). OpenAI 쪽에서는 받으므로 낮게 준다.
 *
 * 다만 추론 계열 모형(o 시리즈 등)은 이 인자를 거부한다. 그래서 거부당하면 한 번은 빼고 다시
 * 부른다(`sample` 아래) — 모형을 바꿔도 층이 그대로 돌게.
 */
const TEMPERATURE = 0.2;

/**
 * 키처럼 생겼는가. `.dev.vars`에 자리만 잡아 둔 「AIza여기에_키_붙여넣기」 같은 것을
 * **키 없음으로 본다** — 그대로 들고 부르면 표본 셋을 던져 401 셋을 받고 버릴 뿐이다.
 *
 * **앞머리로 가리지 않는다.** 제공자마다 꼴이 다르고(`sk-proj-…`·`AIza…`·`AQ.…`) 그 꼴도 바뀐다 —
 * 실제로 이 리포에서 한 번 겪었다: `AIza`만 안다고 적어 두었더니 멀쩡히 살아 있는 Gemini 키를
 * 「모르는 꼴」이라 했다. 그래서 길이와 글자 종류만 본다.
 *
 * 진짜로 살아 있는 키인지는 여기서 못 가린다 — 그것은 `tools/check_key.mjs --live`가 물어서 본다.
 */
export function looksLikeKey(value) {
  return typeof value === "string" && value.length >= 30 && /^[A-Za-z0-9._:~+/=-]+$/.test(value);
}

/** 적합 배차간격을 빌드 값의 몇 배까지 움직이게 둘 것인가. 밖으로 나가면 가둔다. */
const FIT_SWING = 2;

/**
 * 한 번 부르는 데 줄 시간(ms)과 생각+답에 줄 토큰.
 *
 * 12초는 시민이 「계산중…」을 보며 기다릴 만한 끝이다. 넘으면 그 표본을 버리고, 다 버려지면
 * 빌드가 낸 값을 그대로 보인다 — 오래 도는 것보다 조금 덜 다듬어진 값이 낫다.
 */
const TIMEOUT_MS = 12_000;
const MAX_TOKENS = 8_000;

/** 「?」 상자에 들어갈 이유의 길이 상한(글자). 상자는 짧아야 읽힌다. */
export const REASON_MAX = 160;

const 문자 = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const 벗김 = (글) => String(글).replace(/[&<>"']/g, (c) => 문자[c]);
const 소수1 = (x) => Math.round(x * 10) / 10;

const 답 = z.object({
  배차간격: z.number().describe("개편 후 이 노선의 배차간격 추정, 분"),
  적합배차간격: z.number().describe("차량을 안 늘리고 대기시간 총합을 줄이려면 몇 분이어야 하는가"),
  이유: z.string().describe(`왜 그렇게 봤는지 한두 문장, ${REASON_MAX}자 이내`),
});

const 규칙 = `너는 광주 시내버스 2026년 10월 노선 개편의 배차간격을 판단한다.

주어지는 근거는 시가 공표한 총량(운행횟수 8394→9355회, 노선 103→118개, 차량 증차 없음)을
노선별로 나눈 계산 결과다. 너는 그 계산을 **검토해 다시 판단한다** — 그대로 베끼지 않아도 되고,
근거가 서로 어긋나면 어느 쪽을 택했는지 이유에 적는다.

지킬 것:
- 배차간격은 주어진 밴드 안에서 고른다. 밴드는 배분 방식을 넷으로 달리해 본 폭이다.
- 적합 배차간격은 「차량을 한 대도 안 늘리고 대기시간 총합을 가장 줄이는 배차」다. 수요가
  네 배인 노선의 배차는 1/4이 아니라 1/2이어야 한다(제곱근 법칙). 주어진 계산값에서 크게
  벗어나려면 이유가 있어야 한다.
- 이유는 ${REASON_MAX}자 이내 한두 문장. 수치를 하나는 넣는다. 「추정」임을 숨기지 않는다.
- 없는 사실을 지어내지 않는다. 승객 수·혼잡도 자료는 주어지지 않았다.`;

/** 근거 묶음 — 같은 노선이면 늘 같은 글자다. 여기가 흔들리면 답도 흔들린다. */
export function evidence(record) {
  const n = record.망;
  const 근 = record.근거;
  return [
    `노선: ${record.노선} (종류 ${record.종류 || "번호만"})`,
    `계산된 배차간격: ${record.배차간격 === null ? "갈림" : `${record.배차간격}분`}` +
      ` · 밴드 ${record.밴드[0]}~${record.밴드[1]}분 · 확신 ${record.확신}`,
    `계산된 적합 배차간격: ${record.적합.배차}분 (그때 버스 ${record.적합.대수}대)`,
    `지금 배차의 버스: ${record.차량.지금}대 · 왕복 운행시간 ${근.왕복시간}분 · 편도 ${근.노선길이}km`,
    `하루 운행횟수 ${근.운행횟수}회 · 방향 칸 ${근.방향칸}`,
    `같은 종류의 중앙 배차 ${근.종류중앙배차}분 · 이 노선은 그 ${근.종류대비}배`,
    `이 노선이 지나는 길의 버스 총량은 개편으로 망 평균의 ${근.회랑변화}배만큼 늘었다`,
    `계산이 매긴 등급: ${record.등급}`,
    `대체한 개편 전 노선: ${record.대체한노선.length > 0 ? record.대체한노선.join(" · ") : "없음(신설)"}`,
    `광주 전체: 차량을 안 늘리려면 표정속도가 ${소수1(n.필요표정속도상승)}% 올라야 하고,` +
      ` 시가 밝힌 통행시간 단축은 ${소수1(n.발표통행시간단축)}%다`,
  ].join("\n");
}

/** 가운데 값. 표본이 짝수면 가운데 둘의 평균이다. */
export function median(numbers) {
  const 늘어놓음 = [...numbers].sort((a, b) => a - b);
  const 가운데 = Math.floor(늘어놓음.length / 2);
  return 늘어놓음.length % 2 === 1
    ? 늘어놓음[가운데]
    : (늘어놓음[가운데 - 1] + 늘어놓음[가운데]) / 2;
}

const 가둠 = (값, 아래, 위) => Math.min(Math.max(값, 아래), 위);

/**
 * 표본 여럿 → 값 하나. 흔들림을 줄이는 세 손잡이 중 둘(중앙값·밴드)이 여기 있다.
 *
 * 수가 아닌 표본은 버린다. 다 버려지면 `null`을 돌려주고, 부른 쪽이 빌드 값으로 내려앉는다.
 */
export function settle(samples, record) {
  const 쓸것 = samples.filter(
    (s) => s && Number.isFinite(s.배차간격) && Number.isFinite(s.적합배차간격),
  );
  if (쓸것.length === 0) return null;

  const [아래, 위] = record.밴드;
  // 가둔 뒤의 값을 표본으로 남긴다 — 중앙값을 그 위에서 잡았으므로, 「?」 상자에 가두기 전 값을
  // 보이면 화면의 수와 근거가 어긋나 보인다
  const 가둔표본 = 쓸것.map((s) => 소수1(가둠(s.배차간격, 아래, 위)));
  const 배차 = 소수1(median(가둔표본));
  const 적합바닥 = Math.max(table.망.배차하한, record.적합.배차 / FIT_SWING);
  const 적합천장 = Math.min(table.망.배차상한, record.적합.배차 * FIT_SWING);
  const 적합 = 소수1(median(쓸것.map((s) => 가둠(s.적합배차간격, 적합바닥, 적합천장))));
  // 대수는 묻지 않고 셈한다 — 배차간격이 정해지면 나눗셈으로 따라 나오기 때문이다
  const 왕복 = record.근거.왕복시간;
  const 이유 = (쓸것.find((s) => typeof s.이유 === "string" && s.이유.trim())?.이유 ?? "").slice(
    0,
    REASON_MAX,
  );
  return {
    배차간격: 배차,
    적합배차간격: 적합,
    운용대수: 소수1(왕복 / 배차),
    적합운용대수: 소수1(왕복 / 적합),
    이유,
    표본: 가둔표본,
    버린표본: samples.length - 쓸것.length,
    가둠: 쓸것.filter((s, i) => 소수1(s.배차간격) !== 가둔표본[i]).length,
  };
}

/**
 * 한 번 묻는다. 값과 함께 토큰 씀씀이를 돌려준다 — 실측 스크립트가 돈을 재는 자리다.
 *
 * 던지면 부른 쪽(`Promise.allSettled`)이 받는다.
 */
export async function sample(client, record, { model = MODEL, extra = {} } = {}) {
  const 물음 = {
    ...extra,
    model,
    max_completion_tokens: MAX_TOKENS,
    // 답의 모양을 스키마로 못 박는다 — 수가 아닌 것이 올 자리가 없다
    response_format: zodResponseFormat(답, "배차간격_판단"),
    messages: [
      { role: "system", content: 규칙 },
      { role: "user", content: evidence(record) },
    ],
  };
  let response;
  try {
    response = await client.chat.completions.parse({ ...물음, temperature: TEMPERATURE });
  } catch (e) {
    // 추론 계열 모형은 `temperature`를 거부한다. 그것 때문이면 한 번은 빼고 다시 부른다 —
    // 모형을 바꿨다고 층 전체가 멈추지 않게. 다른 까닭이면 그대로 올려 보낸다
    if (!거부당한인자(e, "temperature")) throw e;
    response = await client.chat.completions.parse(물음);
  }
  return {
    값: response.choices?.[0]?.message?.parsed ?? null,
    씀씀이: response.usage ?? null,
  };
}

/** 어떤 인자 하나 때문에 400을 맞았는가. 그 인자만 빼고 다시 부를지 정하는 데 쓴다. */
function 거부당한인자(e, 이름) {
  if (e?.status !== 400) return false;
  const 글 = `${e?.error?.error?.param ?? ""} ${e?.error?.error?.message ?? e?.message ?? ""}`;
  return 글.includes(이름);
}

/**
 * 키로 모형을 하나 만든다. 실측 스크립트도 같은 것을 쓴다 — 여기와 거기가 갈리지 않게.
 *
 * `baseURL`이 있으면 그쪽으로 간다(사내·대행 게이트웨이). 비면 api.openai.com이다.
 */
export function open(key, baseURL = "") {
  return new OpenAI({
    apiKey: key,
    baseURL: baseURL || undefined,
    timeout: TIMEOUT_MS,
    maxRetries: 1,
  });
}

/**
 * 노선 하나를 `SAMPLES`번 물어 값 하나로 모은다.
 *
 * 키가 없으면 부르지 않고 `null`을 돌려준다 — 그때 화면은 빌드 값을 그대로 보인다.
 * `client`를 넣어 주면 그것을 쓴다(검사가 가짜 모형을 끼우는 자리다).
 */
export async function infer(record, env = {}, { client, samples = SAMPLES } = {}) {
  const 고른것 = pick(env);
  if (!client && !고른것) return null;
  const 모형 = client ?? open(고른것.키, 고른것.밑주소);
  const 이름 = 고른것?.모형 ?? env[MODEL_ENV] ?? MODEL;
  const 더 = 고른것?.추가 ?? {};
  const 결과 = await Promise.allSettled(
    Array.from({ length: samples }, () => sample(모형, record, { model: 이름, extra: 더 })),
  );
  return settle(
    결과.map((r) => (r.status === "fulfilled" ? r.value.값 : null)),
    record,
  );
}

const 분 = (x) => `${Number.isInteger(x) ? x : x.toFixed(1)}분`;
const 대 = (x) => `${Number.isInteger(x) ? x : x.toFixed(1)}대`;

/**
 * 카드의 「계산중」 자리를 대신할 조각.
 *
 * 「?」는 `<details>`다 — 여는 데 우리 스크립트가 필요 없고, 키보드와 화면 낭독기가 그냥 된다.
 */
export function fragment(record, inferred) {
  // 개편 후 카드가 부르는 자리라 개편 후 노선만 온다. 그래도 다른 것이 오면 조용히 틀린 수를
  // 보이지 않고 말로 답한다 — `적합`이 없는 기록이기 때문이다
  if (!record.찾음 || record.갈래 !== "개편후") {
    return `<span class="headway" data-state="없음">배차간격을 낼 수 없습니다</span>`;
  }
  const 값 =
    inferred ??
    (record.배차간격 === null
      ? { 배차간격: null, 적합배차간격: record.적합.배차, 운용대수: null,
          적합운용대수: record.적합.대수, 이유: "", 표본: [] }
      : { 배차간격: record.배차간격, 적합배차간격: record.적합.배차,
          운용대수: record.차량.지금, 적합운용대수: record.적합.대수, 이유: "", 표본: [] });
  const 추론함 = inferred !== null && inferred !== undefined;
  const 머리 =
    값.배차간격 === null
      ? `${record.밴드[0]}~${분(record.밴드[1])}`
      : 분(값.배차간격);
  const 까닭 = [
    값.이유 ||
      (record.배차간격 === null
        ? "배분 방식에 따라 답이 크게 갈리는 노선이라 범위로만 냅니다."
        : `개편 전 ${record.대체한노선.join(" · ") || "대응 노선"}에서 물려받은 수요를 ${record.근거.방향칸}개 방향으로 나눈 값입니다.`),
    `같은 종류 중앙 ${분(record.근거.종류중앙배차)}의 ${record.근거.종류대비}배 · 등급 「${record.등급}」.`,
    추론함
      ? `${값.표본.length}번 물어 ${값.표본.join(" · ")}이 나왔고 그 가운데 값입니다. 밴드 ${record.밴드[0]}~${분(record.밴드[1])} 밖으로는 나가지 않습니다.`
      : "지금은 추론 없이 계산값을 그대로 보이고 있습니다.",
    "시가 발표한 노선별 배차간격이 아니라 총량에서 나눈 추정입니다.",
  ].join(" ");
  return (
    `<span class="headway" data-state="${추론함 ? "추론" : "계산"}">` +
    `<strong class="headway-now">${벗김(머리)}</strong>` +
    `<span class="headway-fit">적합 ${벗김(분(값.적합배차간격))}</span>` +
    `<span class="headway-buses">버스 ${벗김(대(값.적합운용대수))}` +
    (값.운용대수 === null ? "" : ` <span class="headway-now-buses">(지금 ${벗김(대(값.운용대수))})</span>`) +
    `</span>` +
    `<details class="headway-why"><summary aria-label="왜 이렇게 계산했는지">?</summary>` +
    `<p>${벗김(까닭)}</p></details>` +
    `</span>`
  );
}

/**
 * `GET /headway/{노선}` — 카드가 htmx로 부르는 조각 자리.
 *
 * 없는 번호에도 200을 준다. htmx는 200이 아닌 응답을 끼우지 않아서, 404를 주면 카드에
 * 「계산중」이 영영 남는다.
 */
export async function respond(name, env, options) {
  const record = answer(decodeURIComponent(name));
  const inferred = record.갈래 === "개편후" ? await infer(record, env, options) : null;
  return new Response(fragment(record, inferred), {
    headers: {
      "content-type": "text/html; charset=utf-8",
      // HTTP 머리는 Latin-1만 실을 수 있어 한글을 못 쓴다 — `x-bundle`과 같은 꼴로 적는다
      "x-headway": inferred
        ? `mode=inferred samples=${inferred.표본.length} clamped=${inferred.가둠}`
        : "mode=computed",
    },
  });
}
