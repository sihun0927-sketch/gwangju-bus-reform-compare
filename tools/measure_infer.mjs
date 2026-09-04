/**
 * 배차간격 추론 실측 (architecture §6-5의 근거, ADR-0011).
 *
 * 이것만은 가짜 모형으로 못 잰다 — **진짜로 부르면 답이 얼마나 흩어지는가**와 **돈이 얼마나 드는가**.
 * `worker/infer.test.js`는 우리 층이 지키는 것을 보고, 여기서는 모형이 실제로 어떻게 답하는지를 본다.
 *
 * 실행:  node tools/measure_infer.mjs [노선] [표본 수]
 *        node tools/measure_infer.mjs --gate G27
 * 입력:  `.dev.vars`(또는 `.env`, 또는 환경 변수)의 제공자 키(`worker/infer.js`의 `PROVIDERS`).
 *        `MODEL_NAME`·`MODEL_BASE_URL`·`PRICE_IN`·`PRICE_OUT`도 있으면 읽는다
 *        worker/headway.json (먼저 `python -m tools.build`를 돌려야 한다)
 * 출력:  흩어짐 · 밴드 안에 드는가 · 토큰과 돈. 값은 docs/architecture.md §6-5에 옮긴다.
 *
 * **돈이 든다.** 표본 하나가 진짜 요청 하나다. 얼마인지는 모형과 값표에 달렸다 — 그래서 여기서는
 * **토큰 수를 실측으로 내고**, 값표(`PRICE_IN`·`PRICE_OUT`)를 적어 둔 경우에만 돈으로 옮긴다.
 *
 * 부르는 것은 Worker가 실제로 쓰는 `sample`·`settle` 그대로다 — 여기서 따로 만들면 실측과
 * 배포본이 조용히 갈린다.
 *
 * 표본을 12개 뽑아 놓고 **셋씩 네 묶음**으로 갈라 각 묶음의 중앙값을 낸다. 그러면 요청을 더 쓰지
 * 않고도 「표본 하나일 때」와 「셋의 중앙값일 때」의 흩어짐을 나란히 잴 수 있다.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import { answer } from "../worker/headway.js";
import { PROVIDERS, SAMPLES, open, pick, sample, settle } from "../worker/infer.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

/**
 * 토큰 값($/백만). **기본은 0이다** — 값표는 자주 바뀌고 모형마다 달라 여기에 못 박으면 곧 거짓이 된다.
 * `.dev.vars`에 `PRICE_IN=`·`PRICE_OUT=`을 적으면 그 값으로 돈을 셈해 준다. 안 적으면 토큰만 낸다.
 * 토큰 수는 실측이고 돈은 그 위의 곱셈일 뿐이라, 못 미더운 쪽을 빼도 실측은 남는다.
 */
const 값이름 = { 입력: "PRICE_IN", 출력: "PRICE_OUT" };

const 기본노선 = "급행03";
// 무료 등급은 하루 요청 수가 빠듯하다. 묶음 둘이면 흩어짐을 견주기에 모자라지 않으면서
// 할당량을 덜 먹는다 — 더 촘촘히 보고 싶으면 인자로 늘린다
const 기본표본 = 6;

/** 게이트 문턱. 이보다 못하면 추론 층을 화면에 올릴 수 없다. */
const 최소응답 = 0.8; // 표본 중 답이 온 비율
const 묶음 = SAMPLES; // 중앙값을 잡는 묶음 크기 — Worker가 쓰는 것과 같아야 한다
// 묶음 사이에 쉬는 시간(ms). 무료 등급은 분당 요청 수를 재므로 몰아 던지면 429가 온다.
// 화면은 노선 하나에 묶음 하나만 던지니, 여기서 몰아 던지는 것이 오히려 실제와 다르다
const 묶음간쉼 = 20_000;

/** `.dev.vars`·`.env`의 `이름=값` 줄을 다 읽는다. 환경 변수가 이긴다. */
function 설정읽기() {
  const 설정 = { ...process.env };
  let 어디 = pick(설정) ? "환경 변수" : "";
  for (const 이름 of [".dev.vars", ".env", ".env.local"]) {
    let 글;
    try {
      글 = readFileSync(join(ROOT, 이름), "utf8");
    } catch {
      continue;
    }
    for (const 줄 of 글.split("\n")) {
      const 다듬은 = 줄.trim();
      if (!다듬은 || 다듬은.startsWith("#")) continue;
      const 자리 = 다듬은.indexOf("=");
      if (자리 < 0) continue;
      const 이름칸 = 다듬은.slice(0, 자리).trim();
      const 값칸 = 다듬은.slice(자리 + 1).trim().replace(/^["']|["']$/g, "");
      if (!(이름칸 in process.env) && 값칸) 설정[이름칸] = 값칸;
      if (!어디 && PROVIDERS.some((p) => p.키 === 이름칸)) {
        어디 = pick(설정) ? 이름 : `${이름}(자리만 잡혀 있음)`;
      }
    }
  }
  return { 고른것: pick(설정), 어디, 설정 };
}

const 중앙값 = (xs) => {
  const 늘어놓음 = [...xs].sort((a, b) => a - b);
  const 가운데 = Math.floor(늘어놓음.length / 2);
  return 늘어놓음.length % 2 ? 늘어놓음[가운데] : (늘어놓음[가운데 - 1] + 늘어놓음[가운데]) / 2;
};
const 표준편차 = (xs) => {
  if (xs.length < 2) return 0;
  const m = xs.reduce((a, b) => a + b, 0) / xs.length;
  return Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / xs.length);
};
const 소수 = (x, n = 2) => Number(x.toFixed(n));

/** 진짜로 `count`번 부른다. 실패한 것은 까닭만 남기고 넘어간다. */
async function 재기(노선, count, 고른것) {
  const 기록 = answer(노선);
  if (기록.갈래 !== "개편후") throw new Error(`개편 후 노선이 아닙니다: ${노선}`);
  const 모형 = open(고른것.키, 고른것.밑주소);
  const 이름 = 고른것.모형;
  const 시작 = Date.now();
  // **화면이 하는 그대로 묶음씩 부른다.** 한 번에 다 던지면 무료 등급 분당 할당량에 걸려
  // 429가 무더기로 온다 — 그것은 모형이 못 답한 것이 아니라 우리가 잘못 잰 것이다.
  // 실제 카드도 노선 하나에 `SAMPLES`개씩만 동시에 던진다
  const 결과 = [];
  for (let 남은 = count; 남은 > 0; 남은 -= 묶음) {
    if (결과.length > 0) await new Promise((r) => setTimeout(r, 묶음간쉼));
    결과.push(
      ...(await Promise.allSettled(
        Array.from({ length: Math.min(묶음, 남은) }, () =>
          sample(모형, 기록, { model: 이름, extra: 고른것.추가 }),
        ),
      )),
    );
  }
  const 걸린 = Date.now() - 시작;

  const 온것 = [];
  const 탈 = [];
  let 입력토큰 = 0;
  let 출력토큰 = 0;
  let 전체토큰 = 0;
  for (const r of 결과) {
    if (r.status !== "fulfilled") {
      탈.push(String(r.reason?.message ?? r.reason).slice(0, 120));
      continue;
    }
    const u = r.value.씀씀이;
    if (u) {
      입력토큰 += u.prompt_tokens ?? u.input_tokens ?? 0;
      출력토큰 += u.completion_tokens ?? u.output_tokens ?? 0;
      // 합이 입력+출력보다 크면 그 차이가 **숨은 생각 토큰**이다. 돈은 그것까지 물린다
      전체토큰 += u.total_tokens ?? 0;
    }
    if (r.value.값) 온것.push(r.value.값);
    else 탈.push("구조화 출력 파싱 실패");
  }
  return {
    기록, 온것, 탈, 입력토큰, 출력토큰, 전체토큰, 걸린, 부른수: count,
    모형이름: 이름, 제공자: 고른것.제공자,
  };
}

/** 표본 하나일 때와 셋의 중앙값일 때의 흩어짐을 나란히 낸다. */
function 흩어짐(잰것) {
  const 하나씩 = 잰것.온것.map((v) => settle([v], 잰것.기록).배차간격);
  const 묶은것 = [];
  for (let i = 0; i + 묶음 <= 잰것.온것.length; i += 묶음) {
    묶은것.push(settle(잰것.온것.slice(i, i + 묶음), 잰것.기록).배차간격);
  }
  return { 하나씩, 묶은것 };
}

function 보고(잰것, 설정) {
  const { 기록 } = 잰것;
  const { 하나씩, 묶은것 } = 흩어짐(잰것);
  const [아래, 위] = 기록.밴드;
  const 입력값 = Number(설정[값이름.입력] ?? 0);
  const 출력값 = Number(설정[값이름.출력] ?? 0);
  // 생각 토큰은 출력으로 물리는 것이 보통이라, 합에서 입력을 뺀 값을 출력으로 셈한다
  const 물릴출력 = Math.max(잰것.출력토큰, 잰것.전체토큰 - 잰것.입력토큰);
  const 돈 = (잰것.입력토큰 / 1e6) * 입력값 + (물릴출력 / 1e6) * 출력값;
  const 가둔수 = 잰것.온것.filter((v) => v.배차간격 < 아래 || v.배차간격 > 위).length;

  console.log(
    `노선 ${기록.노선} · ${잰것.제공자} ${잰것.모형이름} · 요청 ${잰것.부른수}개 (${(잰것.걸린 / 1000).toFixed(1)}초)`,
  );
  console.log(`답이 온 것 ${잰것.온것.length}/${잰것.부른수}${잰것.탈.length ? ` · 못 온 까닭: ${[...new Set(잰것.탈)].join(" / ")}` : ""}`);
  console.log(`빌드 계산값 ${기록.배차간격 ?? "갈림"}분 · 밴드 ${아래}~${위}분 · 확신 ${기록.확신}`);
  console.log(`모형이 부른 값(가두기 전) ${잰것.온것.map((v) => 소수(v.배차간격, 1)).join(" · ")}`);
  console.log(`  밴드 밖이라 가둔 것 ${가둔수}개`);
  console.log(
    `표본 하나일 때  중앙 ${소수(중앙값(하나씩), 1)}분 · 폭 ${소수(Math.min(...하나씩), 1)}~${소수(Math.max(...하나씩), 1)} · 표준편차 ${소수(표준편차(하나씩))}`,
  );
  console.log(
    `${묶음}개의 중앙값일 때  값 ${묶은것.map((v) => 소수(v, 1)).join(" · ")} · 표준편차 ${소수(표준편차(묶은것))}`,
  );
  const 숨은생각 = 잰것.전체토큰 - 잰것.입력토큰 - 잰것.출력토큰;
  console.log(
    `토큰 입력 ${잰것.입력토큰} · 출력 ${잰것.출력토큰}` +
      (숨은생각 > 0 ? ` · 숨은 생각 ${숨은생각}` : "") +
      ` (합 ${잰것.전체토큰})`,
  );
  console.log(
    `  요청 하나 평균 입력 ${Math.round(잰것.입력토큰 / 잰것.온것.length)}` +
      ` · 물릴 출력 ${Math.round(물릴출력 / 잰것.온것.length)}`,
  );
  if (입력값 > 0 || 출력값 > 0) {
    console.log(
      `돈 이번 실측 $${소수(돈, 4)} → 노선 하나(${묶음}표본) $${소수((돈 / 잰것.온것.length) * 묶음, 4)}` +
        `  (값 입력 $${입력값} · 출력 $${출력값} per MTok — ${값이름.입력}/${값이름.출력}에 적은 값)`,
    );
  } else {
    console.log(
      `돈: 값표를 안 적어 못 셈했습니다. \`.dev.vars\`에 ${값이름.입력}=·${값이름.출력}=(백만 토큰당 $)를` +
        " 적으면 위 토큰 수로 셈해 줍니다. 토큰 수 자체는 실측입니다.",
    );
  }
  return { 하나씩, 묶은것, 돈, 가둔수 };
}

/** G27 — 진짜로 답이 오는가, 묶으면 덜 흔들리는가, 밴드 안에 드는가. */
function 게이트(잰것, 잰값) {
  const { 하나씩, 묶은것 } = 잰값;
  if (잰것.온것.length < 잰것.부른수 * 최소응답) {
    // 429는 **모형이 못 답한 것이 아니라 우리가 못 물어본 것**이다. 둘을 같은 말로 적으면
    // 「모형이 이 일을 못 한다」로 잘못 읽힌다
    const 할당량 = 잰것.탈.filter((t) => t.includes("429") || t.includes("quota")).length;
    const 앞말 = `답이 온 표본이 너무 적습니다: ${잰것.온것.length}/${잰것.부른수}`;
    if (할당량 > 0) {
      return (
        `${앞말} — 그중 ${할당량}개가 **429 할당량**입니다. 모형이 못 답한 것이 아니라 우리가 못 물어본 것이라,` +
        " 할당량이 풀린 뒤(무료 등급은 하루 단위) 다시 돌리거나 결제를 등록하면 됩니다." +
        ` 온 표본은 ${잰것.온것.map((v) => v.배차간격).join(" · ")}였습니다.`
      );
    }
    return `${앞말} (${[...new Set(잰것.탈)].join(" / ")})`;
  }
  if (묶은것.length < 2) {
    return `묶음이 ${묶은것.length}개뿐이라 흩어짐을 견줄 수 없습니다 — 표본을 ${묶음 * 2}개 이상 주세요`;
  }
  const 하나흔들 = 표준편차(하나씩);
  const 묶음흔들 = 표준편차(묶은것);
  if (묶음흔들 > 하나흔들) {
    return `묶어도 안 좁아졌습니다: 표본 하나 ${소수(하나흔들)} → ${묶음}개 중앙값 ${소수(묶음흔들)}`;
  }
  const [아래, 위] = 잰것.기록.밴드;
  const 밖 = 묶은것.filter((v) => v < 아래 - 0.05 || v > 위 + 0.05);
  if (밖.length) return `모은 값이 밴드 ${아래}~${위} 밖입니다: ${밖.join(" · ")}`;
  return "";
}

async function main(argv) {
  const 게이트모드 = argv[0] === "--gate" && argv[1] === "G27";
  const 노선 = 게이트모드 ? 기본노선 : (argv[0] ?? 기본노선);
  const 표본수 = 게이트모드 ? 기본표본 : Number(argv[1] ?? 기본표본);
  const { 고른것, 어디, 설정 } = 설정읽기();
  if (!고른것) {
    console.error(
      [
        `쓸 수 있는 키를 못 찾았습니다${어디 ? ` (${어디})` : ""}.`,
        `  아는 이름: ${PROVIDERS.map((p) => p.키).join(" · ")}`,
        `  1) ${join(ROOT, ".dev.vars")} 의 알맞은 줄 오른쪽에 키를 붙여 넣는다`,
        "  2) node tools/check_key.mjs --live  ← 키가 살아 있는지 본다(키는 안 찍는다, 공짜다)",
        "  3) 이 명령을 다시 돌린다",
        "키가 없어도 화면은 계산값으로 그대로 돕니다 — 이 실측만 못 합니다.",
      ].join("\n"),
    );
    return 1;
  }
  if (!게이트모드) {
    console.log(
      `키를 ${어디}에서 읽었습니다(${고른것.제공자}). 모형 ${고른것.모형}으로 진짜 ${표본수}번 부릅니다 — 돈이 듭니다.\n`,
    );
  }
  const 잰것 = await 재기(노선, 표본수, 고른것);
  const 잰값 = 보고(잰것, 설정);
  if (!게이트모드) return 0;
  const 까닭 = 게이트(잰것, 잰값);
  if (까닭) {
    console.error(`G27 어긋남 — ${까닭}`);
    return 1;
  }
  console.log("GATE-G27 OK");
  return 0;
}

process.exitCode = await main(process.argv.slice(2));
