/**
 * `GET /compare?from=lat,lng&to=lat,lng` — 개편 전 카드와 개편 후 카드 한 쌍.
 *
 * 하는 일은 노선망마다 `candidates` → `search` → `rank` → `render` 넷을 차례로 부르는 것뿐이다.
 * 규칙이 어디에 사는지는 그 넷의 머리말에 적혀 있고, 여기에는 **차례**와 카드가 안 나오는
 * 두 경우만 있다 — 두 지점이 도보권 안일 때와 도착지에 정류장이 없을 때.
 */
import { metresBetween, walkableStops } from "./candidates.js";
import { NETWORKS } from "./network.js";
import { rank } from "./rank.js";
import * as render from "./render.js";
import { directJourneys } from "./search.js";
import { WALK_RADIUS_M } from "./rules.js";

/** 검색 조건 → 조각 하나. 좌표가 없거나 깨져도 조각을 돌려준다 — 화면이 조용히 멈추지 않는다. */
export function compare(params) {
  const from = 지점(params.get("from"));
  const to = 지점(params.get("to"));
  if (!from || !to) return render.pickPoints();

  const 사이 = metresBetween(from, to);
  if (사이 <= WALK_RADIUS_M) return render.walkable(사이);

  return render.fragment(NETWORKS.map((network) => 카드(network, from, to)));
}

/** 노선망 하나의 카드. 도착 지점에 정류장이 없으면 카드 대신 안내 한 줄이다. */
function 카드(network, from, to) {
  const 도착 = walkableStops(network, to);
  if (!도착.length) return render.outOfReach(network);

  const 출발 = walkableStops(network, from, { expand: true });
  const [기본] = rank(directJourneys(network, 출발, 도착));
  return render.card(network, 기본);
}

/** `"35.17,126.90"` → `{lat, lng}`. 숫자 둘이 아니면 `null`. */
function 지점(글) {
  const [lat, lng] = String(글 ?? "").split(",").map(Number);
  return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null;
}
