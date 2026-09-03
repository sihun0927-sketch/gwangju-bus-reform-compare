/**
 * 경로 지도 좌표 — 경로 하나를 점 목록으로 편다 (CONTEXT 「경로 지도」).
 *
 * 그리는 것은 브라우저 `map` 스크립트이고(htmx는 지도를 못 그린다, ADR-0001), 여기서는 조각에
 * 실을 좌표만 만든다. 도로 형상은 따르지 않는다 — 정류장을 차례대로 직선으로 잇는다(스펙 Out of Scope).
 *
 * 만드는 모습:
 *
 *     { network, from: {lat,lng}, to: {lat,lng}, legs: [[{lat,lng,name}]] }
 *
 * `legs`는 구간마다 하나, 그 안은 승차부터 하차까지 **지나는 정류장 전부**다. 카드에 적힌
 * 「정류장 N곳」이 구간의 순번 차이이므로 점은 구간마다 N+1개가 된다.
 *
 * 자리 하나에 줄이 여럿인 것은 길 양쪽이 따로이기 때문이다(ADR-0008 결정 2). 어느 쪽에 서는지는
 * 번들이 모르므로 **앞 점에 가장 가까운 줄**을 고른다 — 버스가 길을 건너뛰며 다니지 않는다는 뜻이다.
 * 승차·하차 자리만은 고를 것이 없다. 경로가 그 줄을 집어 놓았다.
 *
 * 좌표가 없는 줄은 건너뛰고 앞뒤를 잇는다. 오늘 번들에는 그런 줄이 없지만(좌표 없는 57개는 추정
 * 좌표를 받는다) 규칙은 남겨 둔다 — 추정 좌표를 못 내는 정류장이 생기면 지도가 (0, 0)으로 튀는 대신
 * 그 점만 빠진다.
 */
import { metresBetween } from "./candidates.js";

/** 경로 하나 → 조각에 실을 좌표. `from`·`to`는 시민이 고른 두 지점이다. */
export function geometry(network, journey, from, to) {
  let 앞점 = from;
  const legs = journey.legs.map((leg) => {
    const 자리들 = network.along(leg.route, leg.side, leg.boardOrder, leg.alightOrder);
    const 끝 = 자리들.length - 1;
    const 점들 = [];
    // 한 바퀴에 자리 하나씩 정하고 앞 점을 바로 옮긴다 — 고르는 기준이 「바로 앞에 그린 점」이라
    // 자리들을 먼저 다 고른 뒤에 옮기면 구간 내내 승차 자리에서만 재게 된다
    자리들.forEach((자리, i) => {
      const id = i === 0 ? leg.board.id : i === 끝 ? leg.alight.id : 가까운_줄(network, 자리, 앞점);
      const 점 = 점으로(network.stop(id));
      if (!점) return;                         // 좌표 없는 줄은 건너뛰고 앞뒤를 잇는다
      점들.push(점);
      앞점 = 점;
    });
    return 점들;
  });
  return { network: network.key, from: 지점(from), to: 지점(to), legs };
}

/** 자리 하나에 선 줄 여럿 중 앞 점에 가장 가까운 것. 좌표 있는 줄이 없으면 `null`. */
function 가까운_줄(network, 자리, 앞점) {
  let 고른 = null;
  let 가장_가까움 = Infinity;
  for (const id of 자리.stops) {
    const 줄 = network.stop(id);
    if (!줄) continue;
    const 거리 = metresBetween(앞점, 줄);
    if (거리 < 가장_가까움) {
      가장_가까움 = 거리;
      고른 = id;
    }
  }
  return 고른;
}

const 지점 = ({ lat, lng }) => ({ lat, lng });

/** 줄 하나 → 점. 좌표가 없으면 `null`이다 — 지어낸 좌표를 넣지 않는다(ADR-0007). */
function 점으로(줄) {
  if (!줄 || !Number.isFinite(줄.lat) || !Number.isFinite(줄.lng)) return null;
  return { lat: 줄.lat, lng: 줄.lng, name: 줄.name };
}
