/**
 * `/compare` 요청당 CPU 실측 (architecture §6-4의 근거, 티켓 6).
 *
 * §6-3은 이 PC의 Node에서 잰 **벽시계** 시간이라 Workers가 세는 CPU 시간이 아니다. 그 값으로는
 * 무료 요금제 상한 10ms 안에 드는지 말할 수 없다 — 기계 사정에 따라 몇 배씩 흔들리기도 한다.
 * 여기서는 `wrangler dev`가 띄운 **workerd 아이솔레이트**에 V8 CPU 프로파일러를 붙여, 요청
 * 하나가 도는 동안 실제로 돈 시간만 센다.
 *
 * 실행:  node tools/measure_cpu.mjs [요청 수]
 * 입력:  worker/data.json (먼저 `python -m tools.build`를 돌려야 한다)
 * 출력:  요청당 CPU 시간의 중앙값·p90·최대와 많이 돈 함수 차례. 값은 docs/architecture.md §6-4로.
 *
 * 재는 법: 요청 하나마다 `Profiler.start` → 요청 → `Profiler.stop`. 창 안에서 `(idle)`이 아닌
 * 표본의 시간을 더한 것이 그 요청의 CPU다. 요청을 안 보낸 빈 창도 한 번 재서 함께 찍는다 —
 * 그 값이 0에 가깝지 않으면 「논 시간을 일한 시간으로 세고 있다」는 뜻이라 아래 수치를 믿을 수 없다.
 *
 * 정류장 쌍은 §6-3과 같다(`tools/measure_pairs.mjs`). 두 §를 나란히 읽으라고 그렇게 둔다.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import process from "node:process";

import { 붙는다, 인스펙터_주소 } from "./cdp.mjs";
import { MIN_APART_M, 씨앗_처음, 정류장_쌍 } from "./measure_pairs.mjs";

/** 기본 표본 수. 프로파일러를 요청마다 켜고 끄느라 §6-3(400쌍)보다 느리다. */
const DEFAULT_REQUESTS = 120;

/** 남이 열어 둔 `wrangler dev`(8787·9229)와 안 부딪히게 다른 포트를 쓴다. */
const DEV_PORT = 8799;
const INSPECTOR_PORT = 9299;

/** `wrangler dev`가 뜨기를 기다리는 한도(ms). 넘으면 로그를 그대로 보이고 멈춘다. */
const 뜨기_한도_MS = 90000;

/** 무료 요금제의 요청당 CPU 상한(ms). 판정 문장 하나를 위해 여기 적는다. */
const FREE_PLAN_CPU_MS = 10;

/** 이 이름의 표본은 아이솔레이트가 논 시간이다. 나머지는 전부 일한 시간으로 센다(GC 포함). */
const 논_이름 = new Set(["(idle)", "(root)"]);

const 몫 = (정렬된, p) =>
  정렬된[Math.min(정렬된.length - 1, Math.floor(정렬된.length * p))];

/**
 * `wrangler dev`를 띄우고 「Ready on」이 나올 때까지 기다린다.
 *
 * `npx`가 아니라 `node_modules`에 깔린 wrangler를 직접 부른다 — ① 판이 `package.json`에 박힌
 * 그것이라 실측이 재현되고 ② 셸을 거치지 않아 끝날 때 확실히 죽는다(셸을 끼우면 Windows에서
 * 껍데기만 죽고 workerd가 남는다). 그래서 이 스크립트는 `npm ci`가 먼저다.
 */
async function 개발_서버() {
  const 뿌리 = fileURLToPath(new URL("..", import.meta.url));
  const 명령 = fileURLToPath(new URL("../node_modules/wrangler/bin/wrangler.js", import.meta.url));
  if (!existsSync(명령)) {
    console.error("node_modules에 wrangler가 없다. `npm ci`부터 돌린다");
    process.exit(1);
  }
  const 아이 = spawn(
    process.execPath,
    [명령, "dev", "--port", String(DEV_PORT), "--inspector-port", String(INSPECTOR_PORT)],
    { cwd: 뿌리 },
  );
  let 로그 = "";
  const 뜸 = new Promise((풀림, 깨짐) => {
    const 시계 = setTimeout(() => 깨짐(new Error(`wrangler dev가 ${뜨기_한도_MS}ms 안에 안 떴다\n${로그}`)), 뜨기_한도_MS);
    const 본다 = (칸) => {
      로그 += 칸;
      if (로그.includes("Ready on")) {
        clearTimeout(시계);
        풀림();
      }
    };
    아이.stdout.on("data", 본다);
    아이.stderr.on("data", 본다);
    아이.on("exit", (코드) => 깨짐(new Error(`wrangler dev가 먼저 끝났다(${코드})\n${로그}`)));
  });
  await 뜸;
  const 판 = 로그.match(/wrangler (\S+)/)?.[1] ?? "?";
  return { 아이, 판 };
}

/** 창 하나를 프로파일러로 감싸고, 그 안에서 일한 시간(ms)과 함수별 몫을 낸다. */
async function 재며(cdp, 일) {
  await cdp.부른다("Profiler.start");
  const 값 = await 일();
  const { profile } = await cdp.부른다("Profiler.stop");
  const 마디 = new Map(profile.nodes.map((n) => [n.id, n]));
  const 함수별 = new Map();
  let 일한 = 0;
  for (let i = 0; i < profile.samples.length; i++) {
    const 간격 = profile.timeDeltas[i] ?? 0;
    const 이름 = 마디.get(profile.samples[i])?.callFrame?.functionName || "(익명)";
    if (논_이름.has(이름)) continue;
    일한 += 간격;
    함수별.set(이름, (함수별.get(이름) ?? 0) + 간격);
  }
  return { 값, cpu: 일한 / 1000, 함수별, 표본: profile.samples.length };
}

async function main() {
  if (!existsSync(new URL("../worker/data.json", import.meta.url))) {
    console.error("worker/data.json이 없다. `python -m tools.build`부터 돌린다");
    process.exit(1);
  }
  const 요청_수 = Number(process.argv[2] ?? DEFAULT_REQUESTS);
  const 쌍 = 정류장_쌍(요청_수);

  const { 아이, 판 } = await 개발_서버();
  try {
    const 주소 = await 인스펙터_주소(INSPECTOR_PORT);
    if (!주소) throw new Error(`인스펙터가 ${INSPECTOR_PORT}번에 안 열렸다`);
    const cdp = await 붙는다(주소);
    await cdp.부른다("Profiler.enable");

    const 부른다 = ([a, b]) =>
      fetch(`http://127.0.0.1:${DEV_PORT}/compare?from=${a.lat},${a.lng}&to=${b.lat},${b.lng}`)
        .then((답) => 답.text());

    // 첫 요청은 번들 JSON을 읽고 노선망을 세우는 몫이 얹혀 있다. 따로 찍고 표본에서 뺀다
    const 첫 = await 재며(cdp, () => 부른다(쌍[0]));

    // 대조군 하나 더 — 프로파일러를 끈 채 같은 쌍을 돌며 벽시계로 잰다. 표본을 뜨는 일 자체가
    // 아이솔레이트를 느리게 만들면 아래 CPU가 부풀 텐데, 그때 이 값이 CPU보다 작게 나온다
    const 잰_벽시계 = [];
    for (const 한쌍 of 쌍) {
      const 시작 = process.hrtime.bigint();
      await 부른다(한쌍);
      잰_벽시계.push(Number(process.hrtime.bigint() - 시작) / 1e6);
    }
    잰_벽시계.sort((a, b) => a - b);

    const 잰_cpu = [];
    const 함수별 = new Map();
    for (const 한쌍 of 쌍) {
      const { cpu, 함수별: 이번 } = await 재며(cdp, () => 부른다(한쌍));
      잰_cpu.push(cpu);
      for (const [이름, 값] of 이번) 함수별.set(이름, (함수별.get(이름) ?? 0) + 값);
    }

    // 대조군 — 요청을 안 보낸 창. 여기가 0에 가까워야 위 수치가 「일한 시간」이다
    const 빈창_MS = 300;
    const 빈창 = await 재며(cdp, () => new Promise((r) => setTimeout(r, 빈창_MS)));

    잰_cpu.sort((a, b) => a - b);
    const 합 = 잰_cpu.reduce((a, b) => a + b, 0);
    console.log(
      `wrangler ${판} · workerd 아이솔레이트 · ${MIN_APART_M}m 넘게 떨어진 정류장 쌍` +
        ` ${잰_cpu.length}개 (씨앗 ${씨앗_처음})\n`,
    );
    console.log(
      `/compare 요청당 CPU — 중앙값 ${몫(잰_cpu, 0.5).toFixed(1)}ms · p90 ${몫(잰_cpu, 0.9).toFixed(1)}ms` +
        ` · 최대 ${잰_cpu.at(-1).toFixed(1)}ms · 평균 ${(합 / 잰_cpu.length).toFixed(1)}ms`,
    );
    console.log(
      `  무료 요금제 상한 ${FREE_PLAN_CPU_MS}ms를 넘는 요청 ` +
        `${잰_cpu.filter((v) => v > FREE_PLAN_CPU_MS).length}/${잰_cpu.length}개`,
    );
    console.log(`  첫 요청(번들 읽기·노선망 세우기 포함) ${첫.cpu.toFixed(1)}ms — 표본에서 뺐다`);
    console.log(
      `  대조군: 프로파일러를 끄고 잰 벽시계(HTTP 포함) 중앙값 ${몫(잰_벽시계, 0.5).toFixed(1)}ms` +
        ` · p90 ${몫(잰_벽시계, 0.9).toFixed(1)}ms. CPU가 이보다 크면 재는 일이 값을 부풀린 것이다`,
    );
    console.log(
      `  대조군: 요청 없는 ${빈창_MS}ms 창에서 일한 시간 ${빈창.cpu.toFixed(1)}ms` +
        `(표본 ${빈창.표본}개). 0에 가까워야 위 수치를 믿을 수 있다`,
    );

    console.log("\n많이 돈 함수 (표본 전체의 자기 시간 몫)");
    const 전체 = [...함수별.values()].reduce((a, b) => a + b, 0);
    for (const [이름, 값] of [...함수별].sort((a, b) => b[1] - a[1]).slice(0, 10)) {
      console.log(
        `  ${(값 / 전체 * 100).toFixed(1).padStart(5)}%  ${(값 / 1000 / 잰_cpu.length).toFixed(2).padStart(6)}ms/요청  ${이름}`,
      );
    }
    cdp.끊는다();
  } finally {
    아이.kill();
  }
}

await main();
// wrangler가 띄운 workerd와 인스펙터 소켓이 이벤트 루프를 붙잡는다. 잴 것은 다 쟀으므로 여기서 끝낸다
process.exit(0);
