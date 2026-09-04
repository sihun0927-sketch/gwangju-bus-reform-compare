/**
 * 경로 탐색 — 직행과 환승 1~2회 (CONTEXT 「경로」).
 *
 * 구간 하나를 잇는 조건은 어느 깊이에서나 같다. **같은 노선 · 같은 방향**에서, 승차보다 **뒤 순번**에
 * 내린다. 이 한 조건이 순환 노선의 한 바퀴 넘김도 함께 막는다 — 한 바퀴를 넘으려면 목록 끝을 지나
 * 앞 순번으로 돌아와야 하는데, 순번 비교가 한 목록 안에서만 이루어지므로 그런 짝이 아예 만들어지지 않는다.
 *
 * 갈아탈 자리는 여기서 찾지 않는다. 번들의 `route_links`가 노선 쌍마다 가장 가까운 환승 지점 하나를
 * 이미 적어 두었고(ADR-0008), 요청 때 하는 일은 그 한 자리가 **순번 조건에 맞는지** 보는 것뿐이다.
 * 한 쌍에 자리가 하나뿐인 만큼, 그 자리가 승차 지점보다 앞이면 그 노선 쌍으로는 경로가 안 나온다.
 *
 * 돌려주는 경로 하나의 모습:
 *
 *     { legs: [{ route, side, board, alight, boardOrder, alightOrder, stopsPassed }],
 *       transferWalks: [m], transfers }
 *
 * 순번 둘을 실어 보내는 까닭은 경로 지도 때문이다 — 승차·하차 사이에 지나는 정류장을 다시
 * 훑으려면 「몇 번째에서 몇 번째까지」가 있어야 하고, 그 값은 여기 말고는 아는 곳이 없다.
 *
 * `legs[0].board`와 마지막 `alight`만 도보권 후보라 `walk`(지점까지 도보 m)를 달고 있다. 가운데
 * 정류장은 번들에서 꺼낸 줄이고, 그 사이를 걷는 거리는 `transferWalks`에 구간 사이마다 하나씩 있다.
 */
import { MAX_TRANSFERS, estimateSeconds, waitSeconds } from "./rules.js";

/**
 * 출발 후보에서 도착 후보까지 가는 경로 전부. 환승은 `MAX_TRANSFERS`까지다.
 *
 * 한 바퀴에 「지금 타고 있는 것들」을 손에 들고, 내려서 끝나는 경로를 거두고, 남은 것을 갈아태워
 * 다음 바퀴로 넘긴다. 순위는 여기서 매기지 않는다 — `rank`가 한다.
 */
export function journeys(network, from, to) {
  const 하차 = 하차표(network, to);
  const 경로 = [];
  let 손 = 첫_승차(network, from);
  for (let 환승 = 0; 손.length; 환승 += 1) {
    for (const 한칸 of 손) 내린다(한칸, 하차, 경로);
    if (환승 >= MAX_TRANSFERS) break;
    손 = 갈아탄다(network, 손);
  }
  return 경로;
}

/** 도착 후보를 노선·방향으로 묶는다. 승차 자리마다 목록 전체를 다시 훑지 않기 위해서다. */
function 하차표(network, to) {
  const 표 = new Map();
  for (const stop of to) {
    for (const { lane, order } of network.rides.get(stop.id) ?? []) {
      const 목록 = 표.get(lane);
      if (목록) 목록.push({ stop, order });
      else 표.set(lane, [{ stop, order }]);
    }
  }
  return 표;
}

/**
 * 손에 든 것 하나 — 「지금 이 노선을 타고 있다」. 이하 **칸**이라 부른다.
 *
 * 구간을 배열로 이어 붙이며 다니지 않는다. `앞`으로 앞 칸을 가리키기만 하고, 경로가 끝날 때
 * 그 사슬을 거슬러 한 번에 펴 놓는다. 갈아타기 한 바퀴에 만드는 칸이 수천 개라, 칸마다
 * 배열을 복사하면 그 복사가 요청당 CPU의 대부분이 된다.
 */
const 칸 = (앞, 탈것, board, alight, alightOrder, stops, walk, wait) => ({
  앞,
  route: 탈것.route,
  side: 탈것.side,
  order: 탈것.order,
  lane: 탈것.lane,
  spot: 탈것.spot,
  board,
  alight,
  alightOrder,
  stops,
  walk,
  wait,
  // 가지치기가 견주는 값은 `rank`의 잣대 ①과 같은 것이라야 한다 — 배차 대기까지 든 값이다.
  // 다르면 탐색이 버린 것이 순위에서 1등일 수 있다
  seconds: estimateSeconds(stops, walk) + wait,
});

/** 출발 후보에서 바로 탈 수 있는 자리 전부. 여기서 시작해 구간을 하나씩 잇는다. */
function 첫_승차(network, from) {
  return from.flatMap((stop) =>
    (network.rides.get(stop.id) ?? []).map((탈것) =>
      칸(null, 탈것, stop, null, 0, 0, stop.walk, waitSeconds(network.headway(탈것.route)))),
  );
}

/** 타고 있는 자리에서 도착 후보에 내려 경로를 끝맺는다. 뒤 순번만 짝이 된다. */
function 내린다(손, 하차, 경로) {
  for (const 내림 of 하차.get(손.lane) ?? []) {
    if (내림.order <= 손.order) continue;
    경로.push(펴다(손, 내림.stop, 내림.order));
  }
}

/**
 * 타고 있는 자리마다 환승 지점에서 내려 다른 노선으로 갈아탄다.
 *
 * 한 경로에서 같은 노선을 두 번 타지 않는다 — 되돌아 탈 바에는 안 내리면 된다.
 * 노선 · 방향 · 승차 순번이 같으면 싼 쪽만 남긴다 — 싼지는 `rank`의 잣대 ①과 같은 자로,
 * 곧 배차 대기까지 든 값으로 잰다.
 *
 * 그 둘이 겹치는 자리에 아주 좁은 구멍이 하나 있다. 같은 자리에 이르는 사슬 둘 중 **느린 쪽만**
 * 아직 안 탄 노선이 있고 다음 구간이 하필 그 노선이면, 남은 빠른 사슬이 「같은 노선 두 번 금지」에
 * 걸려 그 길을 못 간다. 막으려면 「여기까지 탄 노선의 조합」까지 열쇠에 넣어야 하는데 그러면 손에 든
 * 것이 조합만큼 불어난다. 되돌아 타는 자리에서만 생기는 일이라 값을 치르지 않는다.
 */
function 갈아탄다(network, 손) {
  const 다음 = new Map();
  for (const 앞 of 손) {
    for (const [other, 이음] of network.links.get(앞.route) ?? []) {
      if (탔던_노선(앞, other)) continue;
      const 내림 = 이른_순번(이음.hereRides, 앞.side, 앞.order);
      if (내림 === null) continue;
      const stops = 앞.stops + (내림 - 앞.order);
      const walk = 앞.walk + 이음.walk;
      // 탄 몫은 자리마다 한 번만 잰다. 대기는 갈아탈 노선마다 달라 안쪽에서 더한다
      const 탄_초 = estimateSeconds(stops, walk);
      for (const 탈것 of 이음.thereRides) {
        const wait = 앞.wait + waitSeconds(network.headway(탈것.route));
        const seconds = 탄_초 + wait;
        const 있던 = 다음.get(탈것.spot);
        if (있던 && 있던.seconds <= seconds) continue;
        다음.set(탈것.spot, 칸(앞, 탈것, 이음.there, 이음.here, 내림, stops, walk, wait));
      }
    }
  }
  return [...다음.values()];
}

/** 승차 순번보다 뒤이면서 가장 이른 순번. 같은 방향에 없으면 `null`. */
function 이른_순번(rides, side, 뒤로) {
  let 이른 = null;
  for (const r of rides) {
    if (r.side !== side || r.order <= 뒤로) continue;
    if (이른 === null || r.order < 이른) 이른 = r.order;
  }
  return 이른;
}

/** 이 사슬에서 이미 탄 노선인가. 사슬이 셋을 넘지 않아 거슬러 보는 편이 집합을 만드는 것보다 싸다. */
function 탔던_노선(손, route) {
  for (let 한칸 = 손; 한칸; 한칸 = 한칸.앞) if (한칸.route === route) return true;
  return false;
}

/**
 * 사슬을 거슬러 구간 목록과 환승 도보로 편다. 경로 하나가 끝날 때만 부른다.
 *
 * 한 칸의 `alight`·`alightOrder`는 **앞 칸에서 내린 자리**다(첫 칸은 내린 적이 없어 비어 있다).
 * 그래서 거슬러 가며 「지금 칸의 하차」를 다음 바퀴로 넘겨 준다.
 */
function 펴다(손, alight, alightOrder) {
  const legs = [];
  const transferWalks = [];
  for (let 한칸 = 손; 한칸; 한칸 = 한칸.앞) {
    legs.unshift({
      route: 한칸.route,
      side: 한칸.side,
      board: 한칸.board,
      alight,
      boardOrder: 한칸.order,
      alightOrder,
      stopsPassed: alightOrder - 한칸.order,
    });
    // 도보는 쌓인 값이라 앞 칸과의 차이가 그 자리에서 걸은 거리다
    if (한칸.앞) transferWalks.unshift(한칸.walk - 한칸.앞.walk);
    alight = 한칸.alight;
    alightOrder = 한칸.alightOrder;
  }
  return { legs, transferWalks, transfers: legs.length - 1 };
}
