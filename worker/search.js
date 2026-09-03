/**
 * 경로 탐색 — 지금은 직행뿐이다 (CONTEXT 「경로」).
 *
 * 직행은 출발 후보와 도착 후보가 **같은 노선 · 같은 방향**에 함께 있는 것이다. 승차 뒤 하차는
 * 그 방향 목록의 **뒤 순번**이어야 한다. 이 한 조건이 순환 노선의 한 바퀴 넘김도 함께 막는다 —
 * 한 바퀴를 넘으려면 목록 끝을 지나 앞 순번으로 돌아와야 하는데, 순번 비교가 한 목록 안에서만
 * 이루어지므로 그런 짝이 아예 만들어지지 않는다. 순환 노선에 하행 목록이 생기더라도 같다.
 *
 * 환승(최대 2회)은 다음 티켓이다. 여기서 나온 경로의 `transfers`는 모두 0이다.
 */

/** 노선 하나의 방향 하나. 순번을 견줄 수 있는 것은 이것이 같은 정류장끼리뿐이다. */
const 방향 = (route, side) => `${route}|${side}`;

/** 같은 노선·방향에서 승차보다 뒤 순번인 하차를 모두 짝지어 경로 목록을 만든다. */
export function directJourneys(network, from, to) {
  // 하차 쪽을 먼저 노선·방향으로 묶는다. 승차 후보마다 목록 전체를 다시 훑지 않기 위해서다
  const 하차 = new Map();
  for (const stop of to) {
    for (const { route, side, order } of network.rides.get(stop.id) ?? []) {
      const 목록 = 하차.get(방향(route, side));
      if (목록) 목록.push({ stop, order });
      else 하차.set(방향(route, side), [{ stop, order }]);
    }
  }

  const 경로 = [];
  for (const stop of from) {
    for (const { route, side, order } of network.rides.get(stop.id) ?? []) {
      for (const 내림 of 하차.get(방향(route, side)) ?? []) {
        if (내림.order <= order) continue;
        경로.push({
          route,
          side,
          board: stop,
          alight: 내림.stop,
          stopsPassed: 내림.order - order,
          transfers: 0,
        });
      }
    }
  }
  return 경로;
}
