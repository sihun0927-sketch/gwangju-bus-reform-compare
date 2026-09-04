/**
 * 도보권 후보 — 지점 하나에서 걸어가 탈 수 있는 정류장 (CONTEXT 「도보권」).
 *
 * 출발지는 500m 안에 하나도 없으면 100m씩 1,000m까지 넓히고, 도착지는 500m로 고정한다.
 * 넓히기가 출발지에만 있는 까닭은, 도착지를 넓히면 「내려서 한참 걷는 길」이 답으로 나오는데
 * 그것은 시민이 물어본 것이 아니기 때문이다.
 */
import {
  STOP_CANDIDATES,
  WALK_RADIUS_M,
  WALK_RADIUS_MAX_M,
  WALK_RADIUS_STEP_M,
} from "./rules.js";

// 지구 반지름(m). 고르는 값이 아니라 물리 상수라 `rules`에 두지 않는다
const EARTH_RADIUS_M = 6371000;

const 라디안 = (도) => (도 * Math.PI) / 180;

/**
 * `"35.17,126.90"` → `{lat, lng}`. 숫자 둘이 아니면 `null`.
 *
 * 두 곳이 이 글자를 읽는다 — `compare`는 요청 매개변수에서, `journey`는 경로 키에서. 따로 두었더니
 * 한쪽만 `?? ""`를 달아 빈 값에서 갈렸다. 지점을 아는 곳이 여기 하나이므로 여기 둔다.
 */
export function point(글) {
  const [lat, lng] = String(글 ?? "").split(",").map(Number);
  return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null;
}

/**
 * 요청 매개변수 → 시민이 고른 두 장소의 이름 `{from, to}` (CONTEXT 「경로 줄」).
 *
 * 좌표와 달리 이름은 경로 키에 **없다** — 이름까지 키에 넣으면 같은 경로가 무엇으로 검색했는지에
 * 따라 다른 키가 되고, 키는 남에게 보내는 링크다(`journey.js` 머리말). 그래서 `/compare`와
 * `/journey/{id}` 둘 다 매개변수로 받는다. 없으면 비고, 그때 카드는 「출발 지점」이라 적는다.
 */
export const placeNames = (params) => ({
  from: params?.get("fromName") || undefined,
  to: params?.get("toName") || undefined,
});

/** 두 지점 사이 직선 거리(m). 도로를 따르지 않는다 — 도보 거리는 모두 이 값이다. */
export function metresBetween(a, b) {
  const φ1 = 라디안(a.lat);
  const φ2 = 라디안(b.lat);
  const Δφ = 라디안(b.lat - a.lat);
  const Δλ = 라디안(b.lng - a.lng);
  const h = Math.sin(Δφ / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
}

/**
 * 지점 하나의 도보권 후보를 가까운 순으로. 없으면 빈 목록.
 *
 * `expand`가 참이면 출발지 규칙(100m씩 1,000m까지)을, 거짓이면 도착지 규칙(500m 고정)을 쓴다.
 * 거리는 후보마다 `walk`(m)로 실려 나간다 — 순위와 카드가 그 값을 다시 재지 않는다.
 */
export function walkableStops(network, point, { expand = false } = {}) {
  // 거리는 한 번만 잰다. 반경을 넓히는 것은 이미 잰 값을 다시 거르는 일이다
  const 가까운 = [];
  for (const stop of network.served) {
    const walk = metresBetween(point, stop);
    if (walk <= WALK_RADIUS_MAX_M) 가까운.push({ ...stop, walk });
  }
  가까운.sort((a, b) => a.walk - b.walk);

  const 끝 = expand ? WALK_RADIUS_MAX_M : WALK_RADIUS_M;
  for (let 반경 = WALK_RADIUS_M; ; 반경 += WALK_RADIUS_STEP_M) {
    const 안에 = 가까운.filter((s) => s.walk <= 반경).slice(0, STOP_CANDIDATES);
    if (안에.length || 반경 >= 끝) return 안에;
  }
}
