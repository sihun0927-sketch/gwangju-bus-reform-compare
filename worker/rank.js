/**
 * 순위 — 추정 소요 시간 → 환승 횟수 → 도보 합계 (CONTEXT 「추정 소요 시간」).
 *
 * 시각표가 없어 시간은 추정이다. 무엇을 어떻게 세는지는 `rules`의 `estimateSeconds`에 있고 —
 * 여기서는 그 값으로 줄을 세우기만 한다. 자료가 들어오면 `rules`만 바꾼다.
 *
 * 노선 조합이 같으면 하나만 남긴다. 같은 노선을 길 건너에서 타는 경로가 셋 나오면 시민에게는
 * 같은 답이 셋인 것과 다르지 않다. 환승 경로도 같다 — 「좌석02 → 간선18」이 갈아타는 자리만
 * 달리해 둘 나오지 않는다.
 */
import { estimateSeconds } from "./rules.js";

/**
 * 경로 하나에 지표 넷을 붙인다 — `walks` · `walk` · `stopsPassed` · `seconds`.
 *
 * `journey`가 경로 키에서 되살린 경로에도 같은 값을 붙여야 해서 따로 내놓는다. 두 곳에서 각자
 * 세면 카드마다 다른 자로 잰 예상 시간이 나온다.
 */
export function measure(journey) {
  const 구간 = journey.legs;
  const walks = [
    구간[0].board.walk,
    ...journey.transferWalks,
    구간[구간.length - 1].alight.walk,
  ];
  const walk = walks.reduce((합, m) => 합 + m, 0);
  const stopsPassed = 구간.reduce((n, leg) => n + leg.stopsPassed, 0);
  return { ...journey, walks, walk, stopsPassed, seconds: estimateSeconds(stopsPassed, walk) };
}

/**
 * 경로 목록에 지표를 붙여 좋은 순으로 돌려준다.
 *
 * 붙는 것은 넷 — `walks`(걷는 구간의 거리 목록: 출발 도보 · 환승 도보들 · 도착 도보) ·
 * `walk`(그 합) · `stopsPassed`(구간을 통틀어 지난 정류장 수) · `seconds`(추정 소요 시간).
 *
 * 목록과 합을 같이 붙이는 까닭은 카드가 **반올림한 뒤에** 더하기 때문이다 — 시민이 눈으로 줄마다의
 * 값을 더한 것과 카드의 합계가 1m 어긋나 보이지 않게. 시간은 반올림 전 값으로 재야 하므로 둘이 다르다.
 */
export function rank(journeys) {
  const 잰 = journeys.map(measure);
  잰.sort(
    (a, b) => a.seconds - b.seconds || a.transfers - b.transfers || a.walk - b.walk,
  );

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
