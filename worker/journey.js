/**
 * `GET /journey/{id}` — 다른 경로 카드 하나 (CONTEXT 「다른 경로 카드」).
 *
 * 저장소가 없다. 키 안에 경로를 되살릴 것이 다 들어 있고, Worker는 번들에서 정류장 목록·지표·좌표를
 * 복원해 조각으로 돌려준다(ADR-0008 · 스펙 Q12). 그래서 링크를 그대로 남에게 보내도 열린다.
 *
 * 키에 적는 것, `|`로 이어 base64url:
 *
 *     노선망 | 출발 지점 | 도착 지점 | (승차 | 노선 이름 | 하차)…
 *
 * 머리 셋 뒤로 구간마다 세 칸이다 — 정류장은 STATION_NUM, 노선은 화면 이름(「간선18」).
 * 구간이 n개면 칸이 3n+3개다.
 *
 * **두 지점을 스펙이 적은 목록에 더했다.** 스펙의 칸은 노선망·정류장·노선뿐인데, 그것만으로는
 * 「출발 지점에서 몇 m 걷기」와 지표의 예상 시간·도보 합계를 되살릴 수 없다 — 도보권 후보의 거리는
 * 시민이 고른 두 지점에서 재는 값이라 번들에 없다. 두 지점을 빼면 다른 경로 카드의 예상 시간이 기본
 * 카드와 다른 자로 잰 값이 되어 견줄 수가 없다. 요청에 매개변수로 붙이는 길도 있지만 그러면 키
 * 하나로 열린다는 성질(스펙 User Story 34)이 깨진다.
 *
 * 방향과 순번은 키에 없다. 승차·하차 줄과 노선이 정해지면 **같은 방향에서 승차보다 뒤 순번에 내리는
 * 짝** 중 지나는 정류장이 가장 적은 것 하나로 정해지고(CONTEXT 「경로」), 그것이 `rank`가 같은 노선
 * 조합에서 남긴 경로와 같다 — 순위가 추정 소요 시간을 따르고 도보가 같으면 정류장 수가 순위를 정한다.
 *
 * ⚠️ 키에 두 지점이 들어 있으므로 **경로 키를 남에게 보내면 출발·도착 좌표가 함께 간다.** 링크를
 * 공유해도 열리게 하려면 어느 방법으로든 지점이 키에 있어야 하니 피할 수 없고, 여기 적어 둔다.
 */
import { metresBetween, placeNames, point } from "./candidates.js";
import { geometry } from "./geometry.js";
import { NETWORKS } from "./network.js";
import { measure } from "./rank.js";
import * as render from "./render.js";
import { TRANSFER_WALK_M, WALK_RADIUS_M, WALK_RADIUS_MAX_M } from "./rules.js";

const 칸_나눔 = "|";
const 지점_나눔 = ",";
/** 구간 하나가 키에서 차지하는 칸 수 — 하차 · 승차 · 노선. 머리 셋과 승차 하나가 앞에 더 붙는다. */
const 구간_칸 = 3;

/** 경로 하나 → 조각에 실을 키. `/compare`가 카드마다 이것을 적어 둔다. */
export function key(network, journey, from, to) {
  const 칸 = [network.key, 지점_적기(from), 지점_적기(to), journey.legs[0].board.id];
  journey.legs.forEach((leg, i) => {
    칸.push(network.routeName(leg.route), leg.alight.id);
    const 다음 = journey.legs[i + 1];
    if (다음) 칸.push(다음.board.id);
  });
  return base64url(칸.join(칸_나눔));
}

/** `GET /journey/{id}`의 조각과 상태. 키가 번들과 안 맞으면 404와 한 줄 문구다. */
export function journey(id, params) {
  const 되살린 = 되살린다(id);
  if (!되살린) return { html: render.brokenJourney(), status: 404 };
  const { network, journey: 경로, from, to } = 되살린;
  return {
    html: render.alternative(network, 경로, {
      key: id,
      geometry: geometry(network, 경로, from, to),
      places: placeNames(params),
    }),
    status: 200,
  };
}

/** 키 하나 → `{ network, journey, from, to }`. 어디 한 칸이라도 안 맞으면 `null`. */
function 되살린다(id) {
  const 칸 = 푼다(id);
  if (!칸 || 칸.length < 구간_칸 * 2 || 칸.length % 구간_칸 !== 0) return null;
  const [노선망, 출발, 도착, ...나머지] = 칸;
  const network = NETWORKS.find((n) => n.key === 노선망);
  const from = point(출발);
  const to = point(도착);
  if (!network || !from || !to) return null;

  const legs = [];
  for (let i = 0; i + 구간_칸 <= 나머지.length; i += 구간_칸) {
    const leg = 구간(network, 나머지[i], 나머지[i + 1], 나머지[i + 2]);
    if (!leg) return null;
    legs.push(leg);
  }
  const journey = 잰다(network, legs, from, to);
  return 규칙에_맞나(journey) ? { network, journey, from, to } : null;
}

/**
 * 우리가 낸 키인가 — 도보 셋이 규칙 안에 드는지 본다 (CONTEXT 「도보권」·「환승 도보」).
 *
 * `/compare`가 내놓는 키는 늘 이 안이다. 손으로 고친 주소가 「걸어서 5km 가서 타는 경로」를
 * 멀쩡한 카드로 만들어 내지 않게 막는다 — 그런 키는 번들과 안 맞는 키와 다르지 않다.
 */
function 규칙에_맞나(journey) {
  const [출발_도보, ...나머지] = journey.walks;
  const 도착_도보 = 나머지.pop();
  return (
    출발_도보 <= WALK_RADIUS_MAX_M
    && 도착_도보 <= WALK_RADIUS_M
    && 나머지.every((m) => m <= TRANSFER_WALK_M)
  );
}

/**
 * 구간 하나 — 승차 줄 · 노선 이름 · 하차 줄에서 방향과 순번을 정한다.
 *
 * 짝이 여럿이면 지나는 정류장이 가장 적은 것을 고른다. 한 노선이 한 줄을 두 번 지나거나
 * 상·하행이 같은 줄에 서는 자리에서 짝이 여럿이 된다.
 */
function 구간(network, boardId, name, alightId) {
  const route = network.route(name);
  const board = network.stop(boardId);
  const alight = network.stop(alightId);
  if (!route || !board || !alight) return null;

  const 탈_수 = (id) => (network.rides.get(id) ?? []).filter((r) => r.route === route);
  let 고른 = null;
  for (const 승차 of 탈_수(boardId)) {
    for (const 하차 of 탈_수(alightId)) {
      if (하차.side !== 승차.side || 하차.order <= 승차.order) continue;
      const stopsPassed = 하차.order - 승차.order;
      if (고른 && 고른.stopsPassed <= stopsPassed) continue;
      고른 = {
        route,
        side: 승차.side,
        board,
        alight,
        boardOrder: 승차.order,
        alightOrder: 하차.order,
        stopsPassed,
      };
    }
  }
  return 고른;
}

/**
 * 구간 목록에 도보를 달고 `rank`의 `measure`로 지표를 붙인다 — 카드 둘이 같은 자로 재게.
 *
 * 도보권 후보에만 있던 `walk`(지점까지 도보 m)를 첫 승차와 끝 하차에 새로 단다. 거리는 다시
 * 재지만 `rank`가 쓴 것과 같은 `metresBetween`이라 값이 같다. `network`는 `measure`가 배차
 * 대기를 꺼내는 데 쓴다 — 카드에 안 나가는 값이지만 여기서도 같은 자로 재 둔다.
 */
function 잰다(network, legs, from, to) {
  const 붙인 = legs.map((leg, i) => ({
    ...leg,
    board: i === 0 ? { ...leg.board, walk: metresBetween(from, leg.board) } : leg.board,
    alight:
      i === legs.length - 1
        ? { ...leg.alight, walk: metresBetween(to, leg.alight) }
        : leg.alight,
  }));
  const transferWalks = 붙인
    .slice(0, -1)
    .map((leg, i) => metresBetween(leg.alight, 붙인[i + 1].board));
  return measure({ legs: 붙인, transferWalks, transfers: 붙인.length - 1 }, network);
}

const 지점_적기 = ({ lat, lng }) => `${lat}${지점_나눔}${lng}`;

/** 글 → base64url. 한글이 들어가므로 UTF-8 바이트로 바꾼 뒤에 옮긴다. */
function base64url(글) {
  const 바이트 = new TextEncoder().encode(글);
  let 이진 = "";
  for (const b of 바이트) 이진 += String.fromCharCode(b);
  return btoa(이진).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** base64url → 칸 목록. 글자가 깨졌으면 `null`이다 — 던지지 않고 404로 답한다. */
function 푼다(id) {
  try {
    const 이진 = atob(String(id).replace(/-/g, "+").replace(/_/g, "/"));
    const 바이트 = Uint8Array.from(이진, (c) => c.charCodeAt(0));
    return new TextDecoder("utf-8", { fatal: true }).decode(바이트).split(칸_나눔);
  } catch {
    return null;
  }
}
