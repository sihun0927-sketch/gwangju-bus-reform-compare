/**
 * 순위 — 추정 소요 시간 → 환승 횟수 → 도보 합계 (CONTEXT 「추정 소요 시간」).
 *
 * 시각표가 없어 시간은 추정이다. 버스 구간은 통과 정류장 수 × 20초, 도보는 4km/h이고 배차 대기는
 * 넣지 않는다. 값은 `rules` 한 곳에서만 읽는다 — 자료가 들어오면 그곳만 바꾼다.
 *
 * 노선 조합이 같으면 하나만 남긴다. 같은 노선을 길 건너에서 타는 경로가 셋 나오면 시민에게는
 * 같은 답이 셋인 것과 다르지 않다. 환승 경로도 같다 — 「좌석02 → 간선18」이 갈아타는 자리만
 * 달리해 둘 나오지 않는다.
 */
import { SECONDS_PER_STOP, WALK_SPEED_KMH } from "./rules.js";

const SECONDS_PER_HOUR = 3600;
const METRES_PER_KM = 1000;

/** 도보 거리(m)를 걷는 데 걸리는 시간(초). */
export function walkSeconds(metres) {
  return (metres / (WALK_SPEED_KMH * METRES_PER_KM)) * SECONDS_PER_HOUR;
}

/**
 * 정류장 몇 개와 도보 몇 미터의 추정 소요 시간(초).
 *
 * `search`의 가지치기도 이 함수를 부른다 — 「어느 쪽이 더 빠른가」를 두 곳이 다르게 세면
 * 탐색이 버린 것이 순위에서는 1등일 수 있다.
 */
export function estimateSeconds(stopsPassed, walkMetres) {
  return stopsPassed * SECONDS_PER_STOP + walkSeconds(walkMetres);
}

/**
 * 경로 목록에 지표를 붙여 좋은 순으로 돌려준다.
 *
 * 붙는 것은 셋 — `walk`(도보 합계 m, 환승 도보까지), `stopsPassed`(구간을 통틀어 지난 정류장 수),
 * `seconds`(추정 소요 시간). 카드는 이 값을 다시 재지 않는다.
 */
export function rank(journeys) {
  const 잰 = journeys.map((journey) => {
    const 구간 = journey.legs;
    const walk = 구간[0].board.walk
      + 구간[구간.length - 1].alight.walk
      + journey.transferWalks.reduce((합, m) => 합 + m, 0);
    const stopsPassed = 구간.reduce((n, leg) => n + leg.stopsPassed, 0);
    return { ...journey, walk, stopsPassed, seconds: estimateSeconds(stopsPassed, walk) };
  });
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
