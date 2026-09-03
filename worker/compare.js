/**
 * `GET /compare?from=lat,lng&to=lat,lng` — 개편 전 카드와 개편 후 카드 한 쌍.
 *
 * 하는 일은 노선망마다 `candidates` → `search` → `rank` → `render` 넷을 차례로 부르는 것뿐이다.
 * 규칙이 어디에 사는지는 그 넷의 머리말에 적혀 있고, 여기에는 **차례**와 카드가 안 나오는
 * 두 경우만 있다 — 두 지점이 도보권 안일 때와 도착지에 정류장이 없을 때.
 */
import { metresBetween, placeNames, point, walkableStops } from "./candidates.js";
import { geometry } from "./geometry.js";
import { key } from "./journey.js";
import { NETWORKS } from "./network.js";
import { rank } from "./rank.js";
import * as render from "./render.js";
import { journeys } from "./search.js";
import { ALTERNATIVE_JOURNEYS, WALK_RADIUS_M } from "./rules.js";

/** 검색 조건 → 조각 하나. 좌표가 없거나 깨져도 조각을 돌려준다 — 화면이 조용히 멈추지 않는다. */
export function compare(params) {
  const from = point(params.get("from"));
  const to = point(params.get("to"));
  if (!from || !to) return render.pickPoints();

  const 사이 = metresBetween(from, to);
  if (사이 <= WALK_RADIUS_M) return render.walkable();

  const places = placeNames(params);
  return render.cardPair(NETWORKS.map((network) => 카드(network, from, to, places)));
}

/**
 * 노선망 하나의 카드. 도착 지점에 정류장이 없으면 카드 대신 안내 한 줄이다.
 *
 * `rank`가 노선 조합이 같은 것을 이미 하나로 줄여 놓았으므로, 뒤에서 둘을 그냥 떼면 그것이
 * 「노선 조합이 다른 다른 경로 2개」다(CONTEXT 「다른 경로 카드」). 카드에는 키만 싣고 조각은
 * 시민이 「다른 경로 더 보기」를 누를 때 `/journey/{id}`가 만든다.
 */
function 카드(network, from, to, places) {
  const 도착 = walkableStops(network, to);
  if (!도착.length) return render.outOfReach(network);

  const 출발 = walkableStops(network, from, { expand: true });
  const [기본, ...나머지] = rank(journeys(network, 출발, 도착));
  if (!기본) return render.card(network, 기본);
  return render.card(network, 기본, {
    places,
    key: key(network, 기본, from, to),
    geometry: geometry(network, 기본, from, to),
    alternatives: 나머지
      .slice(0, ALTERNATIVE_JOURNEYS)
      .map((경로) => key(network, 경로, from, to)),
  });
}

