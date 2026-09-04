/**
 * 순위 — 순위용 시간 → 환승 0회 → 환승 1회 → 도보 합계 → 환승 2회 (CONTEXT 「추정 소요 시간」).
 *
 * 시각표가 없어 시간은 추정이다. 무엇을 어떻게 세는지는 `rules`의 `estimateSeconds`·
 * `waitSeconds`에 있고 — 여기서는 그 값으로 줄을 세우기만 한다. 자료가 들어오면 `rules`만 바꾼다.
 *
 * **재는 시간이 둘이다** (2026-09-04 세 번째 고침).
 *
 *     seconds     — 카드에 「예상 시간」으로 적는 값. 정류장 · 도보만 센다
 *     rankSeconds — 줄을 세울 때만 쓰는 값. 거기에 구간마다의 배차 대기를 더한다
 *
 * 대기를 화면 값에 안 더하는 까닭은 배차간격의 출처가 두 카드에서 다르기 때문이다 — 개편 전은
 * 시가 공표한 값, 개편 후는 우리가 나눈 추정이다(ADR-0010). 더해 버리면 견주라고 나란히 세운
 * 두 숫자가 서로 다른 자로 잰 값이 된다. 그렇다고 순위에서까지 빼면 배차 37분 노선으로
 * 갈아타는 길을 곧장 가는 길보다 빠르다고 말하게 된다. 그래서 값을 둘로 나눠 들고 있다.
 *
 * 그 대가로 **카드에 적힌 분이 순서와 어긋나 보일 수 있다** — 32분이 39분보다 아래 설 수 있다.
 * 까닭은 카드 아래 각주 한 줄이 말한다(`render`의 `각주`).
 *
 * 노선 조합이 같으면 하나만 남긴다. 같은 노선을 길 건너에서 타는 경로가 셋 나오면 시민에게는
 * 같은 답이 셋인 것과 다르지 않다. 환승 경로도 같다 — 「좌석02 → 간선18」이 갈아타는 자리만
 * 달리해 둘 나오지 않는다.
 */
import { MAX_TRANSFERS, estimateSeconds, waitSeconds } from "./rules.js";

/**
 * 줄 세우는 잣대 다섯. 앞의 것이 같을 때만 뒤의 것을 본다 (2026-09-04 두 번째 고침).
 *
 *     ① 순위용 시간 → ② 환승 0회 → ③ 환승 1회 → ④ 도보 합계 → ⑤ 환승 2회
 *
 * **시간이 맨 앞이다.** ①이 보는 것은 카드에 적히는 `seconds`가 아니라 배차 대기까지 든
 * `rankSeconds`다(이 파일 머리). 빨리 닿는 길이 먼저이고, 환승 횟수는 시간이 **똑같을 때**만
 * 본다 — 그때는 적게 갈아타는 쪽이다(②③⑤가 차례로 0회 · 1회 · 2회를 가른다).
 *
 * 그래서 뒤 넷은 좀처럼 안 불린다. 소수점까지 있는 초라 두 경로의 시간이 딱 맞아떨어지는 일이
 * 드물다. **사실상 시간 하나로 줄이 선다** — 갈아타지 않는 길이라도 1분 느리면 뒤로 간다.
 * 그 자리는 「다른 경로 더 보기」가 받는다.
 *
 * ⑤는 `MAX_TRANSFERS`가 2인 동안은 ②③이 이미 다 갈라 놓아 한 번도 안 불린다. 상한을 올리면
 * 그때부터 일한다 — 잣대를 다섯으로 적어 둔 대로 남긴다.
 */
const 잣대 = [
  (j) => j.rankSeconds,
  (j) => (j.transfers === 0 ? 0 : 1),
  (j) => (j.transfers === 1 ? 0 : 1),
  (j) => j.walk,
  (j) => (j.transfers === MAX_TRANSFERS ? 1 : 0),
];

/** 잣대를 차례로 대 본다. 다 같으면 0 — 그때는 먼저 찾은 것이 앞선다. */
function 견준다(a, b) {
  for (const 재기 of 잣대) {
    const 차 = 재기(a) - 재기(b);
    if (차) return 차;
  }
  return 0;
}

/**
 * 경로 하나에 지표 다섯을 붙인다 — `walks` · `walk` · `stopsPassed` · `seconds` · `rankSeconds`.
 *
 * `journey`가 경로 키에서 되살린 경로에도 같은 값을 붙여야 해서 따로 내놓는다. 두 곳에서 각자
 * 세면 카드마다 다른 자로 잰 예상 시간이 나온다. 배차간격을 노선에서 꺼내야 해서 `network`를 받는다.
 */
export function measure(journey, network) {
  const 구간 = journey.legs;
  const walks = [
    구간[0].board.walk,
    ...journey.transferWalks,
    구간[구간.length - 1].alight.walk,
  ];
  const walk = walks.reduce((합, m) => 합 + m, 0);
  const stopsPassed = 구간.reduce((n, leg) => n + leg.stopsPassed, 0);
  // 대기는 **구간마다 하나씩** — 첫 승차도 갈아타는 자리도 그 노선을 기다린다
  const wait = 구간.reduce((합, leg) => 합 + waitSeconds(network.headway(leg.route)), 0);
  const seconds = estimateSeconds(stopsPassed, walk);
  return { ...journey, walks, walk, stopsPassed, seconds, rankSeconds: seconds + wait };
}

/**
 * 경로 목록에 지표를 붙여 좋은 순으로 돌려준다.
 *
 * 붙는 것은 다섯 — `walks`(걷는 구간의 거리 목록: 출발 도보 · 환승 도보들 · 도착 도보) ·
 * `walk`(그 합) · `stopsPassed`(구간을 통틀어 지난 정류장 수) · `seconds`(카드에 적는 추정 소요
 * 시간) · `rankSeconds`(거기에 배차 대기를 더한, 줄 세울 때만 쓰는 값).
 *
 * 목록과 합을 같이 붙이는 까닭은 카드가 **반올림한 뒤에** 더하기 때문이다 — 시민이 눈으로 줄마다의
 * 값을 더한 것과 카드의 합계가 1m 어긋나 보이지 않게. 시간은 반올림 전 값으로 재야 하므로 둘이 다르다.
 */
export function rank(journeys, network) {
  const 잰 = journeys.map((journey) => measure(journey, network));
  잰.sort(견준다);

  const 남길 = [];
  const 본_조합 = new Set();
  for (const journey of 잰) {
    const 조합 = journey.legs.map((leg) => leg.route).join(">");
    if (본_조합.has(조합)) continue;
    본_조합.add(조합);
    남길.push(journey);
  }
  return 남길;
}
