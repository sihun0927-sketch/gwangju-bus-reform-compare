/**
 * 키가 어느 것인지만 알려 준다 — **키 자체는 절대 안 찍는다** (ADR-0010).
 *
 * 키를 채팅창이나 로그에 붙이는 것은 안전하지 않다. 그래서 사람은 `.dev.vars`에 넣기만 하고,
 * 이 스크립트가 **앞머리 여덟 글자와 길이**만 내어 어느 제공자의 것인지 가려 준다.
 * 나머지 글자는 읽되 어디에도 안 내보낸다.
 *
 *     node tools/check_key.mjs          # 모양만 본다. 부르지 않는다
 *     node tools/check_key.mjs --live   # 진짜로 한 번 물어본다 (모형 목록 — 공짜다)
 *
 * 나오는 것: 파일마다 키 변수 이름 · 앞머리 · 글자 수 · 판정. 그뿐이다.
 * `--live`는 제공자에게 **모형 목록**만 물어 키가 살아 있는지 본다. 토큰을 안 쓰므로 돈이 안 든다.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const 파일들 = [".dev.vars", ".env", ".env.local"];

/** 앞머리를 몇 글자까지 보일 것인가. 제공자를 가리기에 충분하고 키를 되살리기에는 턱없다. */
const 앞머리 = 8;

/**
 * 아는 키 모양. 앞머리만으로 가른다.
 *
 * 자리 값(사람이 아직 안 바꾼 것)을 먼저 걸러야 「짧은 키」로 잘못 읽지 않는다.
 */
const 모양 = [
  { 앞: "sk-ant-api", 이름: "Anthropic API 키", 제공자: "anthropic" },
  { 앞: "sk-ant-admin", 이름: "Anthropic 관리자 키", 제공자: "anthropic" },
  { 앞: "sk-ant-", 이름: "Anthropic 키", 제공자: "anthropic" },
  { 앞: "sk-proj-", 이름: "OpenAI API 키(프로젝트)", 제공자: "openai" },
  { 앞: "sk-svcacct-", 이름: "OpenAI 서비스 계정 키", 제공자: "openai" },
  { 앞: "sk-None-", 이름: "OpenAI 키(옛 꼴)", 제공자: "openai" },
  { 앞: "sk-", 이름: "OpenAI API 키(구버전 꼴)", 제공자: "openai" },
  { 앞: "gsk_", 이름: "Groq 키", 제공자: "기타" },
  { 앞: "AIza", 이름: "Google 키", 제공자: "기타" },
];

/** 값 하나를 읽되 **되돌려 주는 것은 판정뿐**이다. */
function 가리기(값) {
  const 다듬 = 값.trim().replace(/^["']|["']$/g, "");
  if (!다듬) return { 상태: "빈칸" };
  if (/[가-힣\s]/.test(다듬)) return { 상태: "자리만 잡혀 있음", 앞: 다듬.slice(0, 앞머리) };
  const 맞는것 = 모양.find((m) => 다듬.startsWith(m.앞));
  if (!맞는것) return { 상태: "모르는 꼴", 앞: 다듬.slice(0, 앞머리), 길이: 다듬.length };
  if (다듬.length < 40) {
    return { 상태: "너무 짧다 — 잘려 붙었을 수 있다", 앞: 다듬.slice(0, 앞머리), 길이: 다듬.length };
  }
  return {
    상태: 맞는것.이름,
    제공자: 맞는것.제공자,
    앞: 다듬.slice(0, 앞머리),
    길이: 다듬.length,
    흠: 흠찾기(값, 다듬),
  };
}

/**
 * 붙여 넣다 섞여 든 것을 찾는다 — **글자를 찍지 않고 종류만 센다**.
 *
 * 키가 401로 거부될 때 열에 아홉은 키가 틀린 게 아니라 붙여 넣기가 틀린 것이다: 따옴표가 딸려
 * 왔거나, 줄이 접혔거나, 눈에 안 보이는 공백이 끼었거나, 끝에 주석이 붙었다.
 */
function 흠찾기(원래, 다듬) {
  const 흠 = [];
  // OpenAI 키는 가운데에 늘 같은 표식이 박혀 있다(「OpenAI」를 base64로 적은 것). 그것이 없거나
  // 한쪽으로 치우쳐 있으면 붙여 넣다 잘린 것이다. 표식만 보므로 키를 드러내지 않는다
  if (다듬.startsWith("sk-")) {
    const 표식 = "T3BlbkFJ";
    const 자리 = 다듬.indexOf(표식);
    if (자리 < 0) 흠.push("가운데 표식 없음 — 잘렸거나 다른 꼴이다");
    else {
      const 앞쪽 = 자리;
      const 뒤쪽 = 다듬.length - 자리 - 표식.length;
      const 기울기 = Math.abs(앞쪽 - 뒤쪽) / Math.max(앞쪽, 뒤쪽);
      if (기울기 > 0.2) 흠.push(`표식이 치우침 (앞 ${앞쪽}자 · 뒤 ${뒤쪽}자) — 한쪽이 잘렸을 수 있다`);
    }
  }
  if (원래 !== 원래.trim()) 흠.push("앞뒤 공백");
  if (다듬.startsWith('"') || 다듬.startsWith("'") || 다듬.endsWith('"') || 다듬.endsWith("'")) {
    흠.push("따옴표");
  }
  const 셈 = { 공백: 0, 한글: 0, "그 밖": 0 };
  for (const c of 다듬) {
    if (/[A-Za-z0-9_-]/.test(c)) continue;
    if (/\s/.test(c)) 셈.공백 += 1;
    else if (/[가-힣]/.test(c)) 셈.한글 += 1;
    else 셈["그 밖"] += 1;
  }
  for (const [이름, n] of Object.entries(셈)) if (n) 흠.push(`${이름} ${n}자`);
  return 흠;
}

/** 제공자마다 「키가 살아 있나」를 물어볼 가장 싼 자리. 토큰을 안 쓴다. */
const 문두드리기 = {
  openai: async (키, 밑주소) => {
    const { default: OpenAI } = await import("openai");
    const c = new OpenAI({ apiKey: 키, baseURL: 밑주소 || undefined, timeout: 30_000, maxRetries: 0 });
    const 목록 = [];
    for await (const m of await c.models.list()) 목록.push(m.id);
    return 목록;
  },
  anthropic: async (키, 밑주소) => {
    const { default: Anthropic } = await import("@anthropic-ai/sdk");
    const c = new Anthropic({ apiKey: 키, baseURL: 밑주소 || undefined, timeout: 30_000, maxRetries: 0 });
    const 목록 = [];
    for await (const m of await c.models.list()) 목록.push(m.id);
    return 목록;
  },
};

/** 진짜로 물어본다. 키도, 응답 본문도 안 찍는다 — 되는지와 오류 갈래만 낸다. */
async function 살아있나(제공자, 키, 밑주소) {
  const 두드림 = 문두드리기[제공자];
  if (!두드림) return { 됨: false, 까닭: `${제공자}는 아직 두드릴 줄 모른다` };
  try {
    const 목록 = await 두드림(키, 밑주소);
    return { 됨: true, 모형수: 목록.length, 모형: 목록.sort() };
  } catch (e) {
    return {
      됨: false,
      상태: e?.status ?? "",
      갈래: e?.error?.error?.type ?? e?.error?.type ?? e?.name ?? "",
      까닭: String(e?.message ?? e).replace(/sk-[A-Za-z0-9_*-]+/g, "sk-…").slice(0, 160),
    };
  }
}

/** `이름=값` 줄만 읽는다. 주석과 빈 줄은 건너뛴다. */
function 읽기(경로) {
  let 글;
  try {
    글 = readFileSync(경로, "utf8");
  } catch {
    return null;
  }
  const 찾은것 = [];
  for (const 줄 of 글.split("\n")) {
    const 다듬 = 줄.trim();
    if (!다듬 || 다듬.startsWith("#")) continue;
    const 자리 = 다듬.indexOf("=");
    if (자리 < 0) continue;
    const 이름 = 다듬.slice(0, 자리).trim();
    const 값 = 다듬.slice(자리 + 1);
    if (/^[A-Z0-9_]*BASE_URL$/.test(이름)) {
      밑주소[이름] = 값.trim().replace(/^["']|["']$/g, "");
      continue;
    }
    if (!/KEY|TOKEN|SECRET/i.test(이름)) continue;
    찾은것.push({ 이름, 값: 값.trim().replace(/^["']|["']$/g, ""), ...가리기(값) });
  }
  return 찾은것;
}

/** 제공자별 밑주소(있으면). 사내 게이트웨이를 쓰는 경우가 있다. */
const 밑주소 = {};
const 밑주소이름 = { openai: "OPENAI_BASE_URL", anthropic: "ANTHROPIC_BASE_URL" };

const 살아있는지본다 = process.argv.includes("--live");
const 판정들 = new Set();
const 쓸것 = [];
let 본파일 = 0;
for (const 이름 of 파일들) {
  const 찾은것 = 읽기(join(ROOT, 이름));
  if (찾은것 === null) continue;
  본파일 += 1;
  console.log(`${이름}`);
  if (찾은것.length === 0) {
    console.log("  (키 줄이 없다)");
    continue;
  }
  for (const k of 찾은것) {
    const 꼬리 = k.앞 ? ` — ${k.앞}… (${k.길이 ?? "?"}자)` : "";
    console.log(`  ${k.이름.padEnd(20)} ${k.상태}${꼬리}`);
    if (k.흠?.length) console.log(`  ${" ".repeat(20)} ⚠ 섞여 든 것: ${k.흠.join(" · ")}`);
    if (k.제공자) {
      판정들.add(k.제공자);
      쓸것.push(k);
    }
  }
}
if (본파일 === 0) {
  console.log(`${파일들.join(" · ")} 중 어느 것도 없다.`);
}
console.log("");
if (판정들.size === 0) {
  console.log("판정: 쓸 수 있는 키가 아직 없다. `.dev.vars`의 자리 값을 진짜 키로 바꾸면 된다.");
  process.exitCode = 1;
} else {
  console.log(`판정: ${[...판정들].join(" + ")}`);
  console.log("키 자체는 어디에도 안 찍었다 — 앞머리 여덟 글자와 길이만 봤다.");
}

if (살아있는지본다 && 쓸것.length > 0) {
  console.log("\n진짜로 물어본다 (모형 목록 — 토큰을 안 쓰므로 돈이 안 든다)");
  for (const k of 쓸것) {
    const 주소 = 밑주소[밑주소이름[k.제공자]] ?? "";
    const 끝 = await 살아있나(k.제공자, k.값, 주소);
    const 어디 = 주소 ? ` @ ${주소}` : "";
    if (끝.됨) {
      console.log(`  ${k.이름}${어디}: 살아 있다 · 모형 ${끝.모형수}개`);
      const 관심 = 끝.모형.filter((id) => /^(gpt-5|gpt-4\.1|gpt-4o|o[34]|codex|claude)/.test(id));
      console.log(`    쓸 만한 것: ${관심.length ? 관심.join(" · ") : "(못 골랐다 — 아래 전체를 본다)"}`);
      if (!관심.length) console.log(`    전체: ${끝.모형.slice(0, 30).join(" · ")}`);
    } else {
      console.log(`  ${k.이름}${어디}: 거부됨 · 상태 ${끝.상태} · 갈래 ${끝.갈래}`);
      console.log(`    ${끝.까닭}`);
      process.exitCode = 2;
    }
  }
}
