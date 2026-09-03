/**
 * 조각 만들기 — htmx가 결과 영역에 그대로 끼우는 HTML (ADR-0001).
 *
 * 화면에 나가는 말은 CONTEXT 「장소로 찾기」 절을 따른다. 카드 머리에 상태만 적고, 두 카드를
 * 합쳐 말하는 **판정 문장은 두지 않는다** — 견주는 일은 시민이 카드 둘을 보고 한다.
 *
 * 숫자를 문장에 적을 때도 상수는 `rules`에서 읽는다. 안내문에 500이라 적어 두면 도보권을 고칠 때
 * 규칙과 문구가 따로 낡는다.
 */
import { SECONDS_PER_STOP, WALK_RADIUS_M, WALK_SPEED_KMH } from "./rules.js";

const SECONDS_PER_MINUTE = 60;

const 문자 = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** 정류장·노선 이름은 CSV에서 온 남의 글자다. 그대로 붙이지 않는다. */
const 벗김 = (글) => String(글).replace(/[&<>"']/g, (c) => 문자[c]);

const 미터 = (m) => `${Math.round(m)}m`;

/**
 * 카드에 적는 도보 합계. 구간마다 반올림한 값을 더한다 — 시민이 눈으로 두 값을 더한 것과
 * 합계가 1m 어긋나 보이지 않게.
 */
const 도보_합계 = (journey) =>
  미터(Math.round(journey.board.walk) + Math.round(journey.alight.walk));
const 분 = (초) => `${Math.round(초 / SECONDS_PER_MINUTE)}분`;

const 안내 = (글, 노선망) =>
  `<p class="notice"${노선망 ? ` data-network="${노선망.key}"` : ""}>${글}</p>`;

/** 출발·도착 중 하나라도 아직 안 골랐거나 좌표가 깨졌을 때. */
export const pickPoints = () => 안내("출발 지점과 도착 지점을 모두 골라 주세요.");

/**
 * 두 지점이 도보권 안이라 버스를 탈 일이 없을 때 (CONTEXT 「도보권」).
 * 잰 거리는 적지 않는다 — 용어집이 「걸어갈 수 있는 거리」라고만 알린다고 적었다.
 */
export const walkable = () => 안내("걸어갈 수 있는 거리입니다.");

/** 도착 지점 도보권에 이 노선망의 정류장이 하나도 없을 때 — 카드 대신 한 줄이다. */
export const outOfReach = (network) =>
  안내(
    `${network.label} 노선망에는 도착 지점 ${WALK_RADIUS_M}m 안에 정류장이 없습니다.`,
    network,
  );

/** 카드 한 쌍(또는 그 자리를 대신한 안내)을 조각 하나로 묶는다. */
export const cardPair = (조각들) => `<div class="compare">${조각들.join("")}</div>`;

/** 줄 목록을 `<ul>`이나 `<ol>` 하나로. 경로 줄과 지표 줄이 같은 모양이라 한 곳에 둔다. */
const 목록 = (태그, 갈래, 줄들) =>
  `<${태그} class="${갈래}">${줄들.map((줄) => `<li>${줄}</li>`).join("")}</${태그}>`;

/** 화면에 적는 노선 이름. */
const 노선_이름 = (network, journey) => 벗김(network.routeName(journey.route));

/** 추정 좌표를 쓴 정류장이면 이름 옆에 표시를 붙인다 (CONTEXT 「추정 좌표」). */
function 정류장(stop) {
  const 표시 = stop.estimated ? ' <span class="estimated">추정 위치</span>' : "";
  return `<b>${벗김(stop.name)}</b>${표시}`;
}

/**
 * 노선망 하나의 카드. `journey`가 없으면 머리가 「경로 없음」이고 안이 한 줄이다.
 *
 * 「다른 경로 더 보기」 자리는 아직 비워 둔다(티켓 5).
 */
export function card(network, journey) {
  const 상태 = journey ? "직행" : "경로 없음";
  const 머리 =
    `<h3><span class="network">${network.label}</span>` +
    ` <span class="status">${상태}</span></h3>`;
  const 안쪽 = journey
    ? 경로(network, journey) + 지표(network, journey) + 추정치
    : `<p class="notice">이 노선망에서는 갈아타지 않고 가는 길을 찾지 못했습니다.</p>`;
  return `<article class="journey-card" data-network="${network.key}">${머리}${안쪽}</article>`;
}

/** 출발 지점 → 도보 → 승차 → 노선 → 하차 → 도보 → 도착 지점. */
function 경로(network, journey) {
  const 줄 = [
    `출발 지점에서 ${미터(journey.board.walk)} 걷기`,
    `승차 ${정류장(journey.board)}`,
    `${노선_이름(network, journey)} 타고 ${journey.stopsPassed}개 정류장`,
    `하차 ${정류장(journey.alight)}`,
    `${미터(journey.alight.walk)} 걸어 도착 지점`,
  ];
  return 목록("ol", "legs", 줄);
}

/** 카드 아래 수치 줄 (CONTEXT 「지표」). 배차간격은 값이 없으면 「정보 없음」이다. */
function 지표(network, journey) {
  const 배차 = network.headway(journey.route);
  const 줄 = [
    `예상 시간 ${분(journey.seconds)}`,
    `환승 ${journey.transfers ? `${journey.transfers}회` : "없음"}`,
    `노선 ${노선_이름(network, journey)}`,
    `정류장 ${journey.stopsPassed}곳`,
    `도보 합계 ${도보_합계(journey)}`,
    `배차간격 ${배차 === null || 배차 === undefined ? "정보 없음" : 벗김(배차)}`,
  ];
  return 목록("ul", "metrics", 줄);
}

const 추정치 =
  `<p class="estimate-note">예상 시간은 정류장당 ${SECONDS_PER_STOP}초와` +
  ` 걷는 속도 ${WALK_SPEED_KMH}km/h로 잡은 추정치입니다. 배차 대기는 넣지 않았습니다.</p>`;
