/**
 * 경로 탐색 실측 (architecture §6-3의 근거).
 *
 * 번들 표의 크기는 파이썬 쪽 `tools/measure_transfers.py`가 잰다. 여기서 재는 것은 그 표로 **찾은
 * 결과**다 — 환승 2회 안에 길이 나오는 쌍이 얼마나 되는지(route_links 「쌍당 최단 1개」가 치르는 값)와
 * 요청 하나에 걸리는 시간(무료 요금제 CPU 상한 판정의 재료).
 *
 * 실행:  node tools/measure_search.mjs [쌍 수]
 * 입력:  worker/data.json (먼저 `python -m tools.build`를 돌려야 한다)
 * 출력:  노선망별 상태 분포와 요청 시간. 값은 docs/architecture.md §6-3 에 옮긴다.
 *
 * **규칙은 Worker에서 가져다 쓴다** — `compare`가 실제로 부르는 그 `fetch`를 부른다. 여기서 따로
 * 세면 실측과 배포본이 조용히 갈린다.
 *
 * 정류장 쌍은 씨앗을 고정한 난수로 고른다. 다시 돌리면 같은 쌍이 나오므로 값이 재현된다.
 */
import process from "node:process";

import { NETWORKS } from "../worker/network.js";
import worker from "../worker/index.js";

/** 서로 이만큼(m)은 떨어진 쌍만 본다. 붙어 있는 쌍은 「걸어갈 수 있는 거리」라 경로를 안 찾는다. */
const MIN_APART_M = 3000;

/** 기본 표본 수. 400쌍이면 노선망당 「경로 없음」 비율의 소수 첫째 자리가 흔들리지 않는다. */
const DEFAULT_PAIRS = 400;

const 씨앗_처음 = 20260904;

/** 씨앗을 고정한 난수. 다시 돌리면 같은 쌍이 나온다. */
function 난수(씨앗) {
  let 값 = 씨앗;
  return () => {
    값 = (값 * 1103515245 + 12345) % 2147483648;
    return 값 / 2147483648;
  };
}

/** 정적 자산 바인딩 대신 세우는 가짜. `/compare`는 여기로 안 간다. */
const env = { ASSETS: { fetch: () => new Response("") } };

const 대략_미터 = (a, b) =>
  Math.hypot((a.lat - b.lat) * 111000, (a.lng - b.lng) * 91000);

const 상태 = (글, key) =>
  (글.match(
    new RegExp(`data-network="${key}"[^]*?<span class="status">([^<]*)</span>`),
  ) ?? [, "카드 없음"])[1];

async function main() {
  const 쌍_수 = Number(process.argv[2] ?? DEFAULT_PAIRS);
  const [before] = NETWORKS;
  const 다음 = 난수(씨앗_처음);
  const 쌍 = [];
  while (쌍.length < 쌍_수) {
    const a = before.served[Math.floor(다음() * before.served.length)];
    const b = before.served[Math.floor(다음() * before.served.length)];
    if (a && b && a.id !== b.id && 대략_미터(a, b) >= MIN_APART_M) 쌍.push([a, b]);
  }

  const 셈 = new Map(NETWORKS.map((n) => [n.key, new Map()]));
  const 잰_시간 = [];
  for (const [a, b] of 쌍) {
    const url = `https://example.com/compare?from=${a.lat},${a.lng}&to=${b.lat},${b.lng}`;
    const 시작 = process.hrtime.bigint();
    const 글 = await (await worker.fetch(new Request(url), env)).text();
    잰_시간.push(Number(process.hrtime.bigint() - 시작) / 1e6);
    for (const n of NETWORKS) {
      const 값 = 상태(글, n.key);
      셈.get(n.key).set(값, (셈.get(n.key).get(값) ?? 0) + 1);
    }
  }

  console.log(
    `${MIN_APART_M}m 넘게 떨어진 정류장 쌍 ${쌍.length}개 (씨앗 ${씨앗_처음})\n`,
  );
  for (const n of NETWORKS) {
    const 값 = [...셈.get(n.key)].sort((x, y) => y[1] - x[1]);
    const 못_감 = 셈.get(n.key).get("경로 없음") ?? 0;
    console.log(
      `${n.label}: ` +
        값.map(([말, 수]) => `${말} ${수}`).join(" · ") +
        ` → 환승 2회로 못 가는 쌍 ${(못_감 / 쌍.length * 100).toFixed(1)}%`,
    );
  }

  잰_시간.sort((x, y) => x - y);
  const 몫 = (p) => 잰_시간[Math.min(잰_시간.length - 1, Math.floor(잰_시간.length * p))];
  console.log(
    `\n요청 하나(노선망 둘 합쳐) — 중앙값 ${몫(0.5).toFixed(1)}ms` +
      ` · p90 ${몫(0.9).toFixed(1)}ms · 최대 ${잰_시간.at(-1).toFixed(1)}ms`,
  );
  console.log("  이 PC의 Node에서 잰 값이다. Workers의 CPU 시간은 아니다");
}

await main();
