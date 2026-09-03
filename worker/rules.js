/**
 * 장소 탭의 계산 규칙 상수 — 한 곳 (ADR-0008).
 *
 * 값이 코드 여기저기 흩어지면 「도보권이 몇 미터였더라」를 읽는 곳마다 찾아야 하고, 배차 자료가
 * 들어오거나 실측으로 값을 고칠 때 한 군데를 빠뜨린다. 뜻은 CONTEXT.md 「장소로 찾기」 절에 있고,
 * 여기에는 숫자와 그 숫자를 고른 까닭만 적는다.
 */

/** 지점에서 이만큼 안의 정류장을 걸어갈 수 있다고 본다. 도착지는 이 값 하나로 고정이다. */
export const WALK_RADIUS_M = 500;

/** 출발지 500m 안에 정류장이 없으면 이만큼씩 넓혀 다시 찾는다. */
export const WALK_RADIUS_STEP_M = 100;

/** 출발지 넓히기의 끝. 여기까지 없으면 그 노선망에는 경로가 없다고 답한다. */
export const WALK_RADIUS_MAX_M = 1000;

/** 한 지점에서 볼 승·하차 후보 정류장 수. 가까운 것부터. */
export const STOP_CANDIDATES = 8;

/** 환승으로 걸어서 옮길 수 있는 두 정류장 사이 거리. 길 건너기까지가 이 안이다. */
export const TRANSFER_WALK_M = 350;

/** 환승 횟수 상한. 두 번 넘게 갈아타는 경로는 답으로 내지 않는다. */
export const MAX_TRANSFERS = 2;

/**
 * 버스가 정류장 하나를 지나는 데 걸린다고 보는 시간(초).
 * 사용자가 추천값(120초)을 듣고도 확정한 값이다. 바꾸려면 이 상수만 바꾼다.
 */
export const SECONDS_PER_STOP = 20;

/** 걷는 속도(km/h). 출발·환승·도착 도보에 모두 같은 값을 쓴다. */
export const WALK_SPEED_KMH = 4;

/** 「다른 경로 더 보기」로 펼치는 경로 수. 기본 경로 하나 뒤에 붙는다. */
export const ALTERNATIVE_JOURNEYS = 2;

/** 이 글자 수보다 짧게 친 검색어에는 후보를 안 띄운다. */
export const PLACE_QUERY_MIN_LENGTH = 2;

/** 자동완성 후보로 보일 장소 수. */
export const PLACE_CANDIDATES = 5;

/** 같은 검색어의 Kakao 응답을 Cache API에 두는 시간(초) = 하루. */
export const PLACE_CACHE_SECONDS = 24 * 60 * 60;

/** Kakao 검색 범위를 번들의 노선안 정류장 bbox에서 이만큼 넓힌다. */
export const PLACE_SEARCH_MARGIN_M = 5000;
