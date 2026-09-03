/**
 * 순위 — 추정 소요 시간 → 환승 횟수 → 도보 합계 (CONTEXT 「추정 소요 시간」).
 *
 * 시각표가 없어 시간은 추정이다. 버스 구간은 통과 정류장 수 × 20초, 도보는 4km/h이고 배차 대기는
 * 넣지 않는다. 값은 `rules` 한 곳에서만 읽는다 — 자료가 들어오면 그곳만 바꾼다.
 *
 * 노선 조합이 같으면 하나만 남긴다. 같은 노선을 길 건너에서 타는 경로가 셋 나오면 시민에게는
 * 같은 답이 셋인 것과 다르지 않다.
 */
import { SECONDS_PER_STOP, WALK_SPEED_KMH } from "./rules.js";

const SECONDS_PER_HOUR = 3600;
const METRES_PER_KM = 1000;

/** 도보 거리(m)를 걷는 데 걸리는 시간(초). */
export function walkSeconds(metres) {
  return (metres / (WALK_SPEED_KMH * METRES_PER_KM)) * SECONDS_PER_HOUR;
}

/** 경로가 쓰는 노선의 차례. 이것이 같으면 같은 경로로 본다. 직행은 노선 하나다. */
export function routeCombination(journey) {
  return journey.route;
}

/** 경로 목록에 `walk`(도보 합계 m)와 `seconds`(추정 소요 시간)를 붙여 좋은 순으로 돌려준다. */
export function rank(journeys) {
  const 잰 = journeys.map((journey) => {
    const walk = journey.board.walk + journey.alight.walk;
    return {
      ...journey,
      walk,
      seconds: journey.stopsPassed * SECONDS_PER_STOP + walkSeconds(walk),
    };
  });
  잰.sort(
    (a, b) => a.seconds - b.seconds || a.transfers - b.transfers || a.walk - b.walk,
  );

  const 남길 = [];
  const 본_조합 = new Set();
  for (const journey of 잰) {
    const 조합 = routeCombination(journey);
    if (본_조합.has(조합)) continue;
    본_조합.add(조합);
    남길.push(journey);
  }
  return 남길;
}
