/**
 * 조각 만들기 — htmx가 결과 영역에 그대로 끼우는 HTML (ADR-0001).
 *
 * 화면에 나가는 말은 CONTEXT 「장소로 찾기」 절을 따른다. 카드 머리에 상태만 적고, 두 카드를
 * 합쳐 말하는 **판정 문장은 두지 않는다** — 견주는 일은 시민이 카드 둘을 보고 한다.
 *
 * 숫자를 문장에 적을 때도 상수는 `rules`에서 읽는다. 안내문에 500이라 적어 두면 도보권을 고칠 때
 * 규칙과 문구가 따로 낡는다.
 */
import { MAX_TRANSFERS, SECONDS_PER_STOP, WALK_RADIUS_M, WALK_SPEED_KMH } from "./rules.js";

const SECONDS_PER_MINUTE = 60;

const 문자 = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** 정류장·노선 이름은 CSV에서 온 남의 글자다. 그대로 붙이지 않는다. */
const 벗김 = (글) => String(글).replace(/[&<>"']/g, (c) => 문자[c]);

const 미터 = (m) => `${Math.round(m)}m`;

/**
 * 카드에 적는 도보 합계. `rank`가 붙인 걷는 구간 목록을 **구간마다 반올림해서** 더한다 —
 * 시민이 눈으로 줄마다의 값을 더한 것과 합계가 1m 어긋나 보이지 않게. 환승 도보도 그 목록에 있다.
 */
const 도보_합계 = (journey) =>
  미터(journey.walks.reduce((합, m) => 합 + Math.round(m), 0));
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

/**
 * 카드 한 쌍(또는 그 자리를 대신한 안내)을 조각 하나로 묶는다.
 *
 * 경로 지도는 카드 **위**에 하나만 놓는다 — 두 노선망의 경로를 겹쳐 봐야 개편으로 길이 어떻게
 * 달라졌는지가 보이기 때문이다(CONTEXT 「경로 지도」). 좌표는 카드마다 실려 있고, 어느 것을
 * 올릴지 고르는 일과 그리는 일은 브라우저 `map`이 한다. 그릴 것이 없으면 `map`이 감춘다.
 */
export const cardPair = (조각들) =>
  '<div class="journey-map" hidden>'
  + '<div class="canvas" id="journey-map-canvas"></div>'
  + `<p class="legend">${지도_범례}</p></div>`
  + `<div class="compare">${조각들.join("")}</div>`;

/** 지도의 선 둘이 무엇인지 한 줄로 (CONTEXT 「경로 지도」). */
const 지도_범례 = "개편 전 경로는 점선, 개편 후 경로는 실선입니다. 회색 점선은 걷는 구간입니다.";

/** 줄 목록을 `<ul>`이나 `<ol>` 하나로. 경로 줄과 지표 줄이 같은 모양이라 한 곳에 둔다. */
const 목록 = (태그, 갈래, 줄들) =>
  `<${태그} class="${갈래}">${줄들.map((줄) => `<li>${줄}</li>`).join("")}</${태그}>`;

/** 화면에 적는 노선 이름. */
const 노선_이름 = (network, route) => 벗김(network.routeName(route));

/** 추정 좌표를 쓴 정류장이면 이름 옆에 표시를 붙인다 (CONTEXT 「추정 좌표」). */
function 정류장(stop) {
  const 표시 = stop.estimated ? ' <span class="estimated">추정 위치</span>' : "";
  return `<b>${벗김(stop.name)}</b>${표시}`;
}

/** 카드 머리의 상태 (CONTEXT 「상태」). 등급 넷은 여기서만 글자가 된다. */
const 상태 = (journey) => {
  if (!journey) return "경로 없음";
  return journey.transfers ? `환승 ${journey.transfers}회` : "직행";
};

/**
 * 노선망 하나의 카드. `journey`가 없으면 머리가 「경로 없음」이고 안이 한 줄이다.
 *
 * `key`는 이 경로의 경로 키, `geometry`는 경로 지도 좌표, `alternatives`는 다른 경로들의 키다.
 * 경로가 없으면 셋 다 없다.
 */
export function card(network, journey, { key, geometry, alternatives = [] } = {}) {
  const 안쪽 = journey
    ? 경로(network, journey) + 지표(network, journey) + 추정치
      + 지도_버튼(network) + 좌표(geometry) + 더_보기(network, alternatives)
    : `<p class="notice">이 노선망에서는 환승 ${MAX_TRANSFERS}회 안에 가는 길을 찾지 못했습니다.</p>`;
  return 카드("journey-card", network, journey, key, 안쪽);
}

/**
 * 다른 경로 카드 하나 — `/journey/{id}`가 돌려주는 조각 (CONTEXT 「다른 경로 카드」).
 *
 * 기본 카드와 같은 줄들을 적는다. 다른 것은 둘 — 「다른 경로 더 보기」가 없고(펼친 것이 또 펼치지
 * 않는다), 스스로 자리를 차지하지 않고 기본 카드 안의 자리에 끼워진다.
 */
export const alternative = (network, journey, { key, geometry } = {}) =>
  카드(
    "journey-card alternative", network, journey, key,
    경로(network, journey) + 지표(network, journey)
      + 지도_버튼(network) + 좌표(geometry),
  );

/** 키가 번들과 안 맞을 때. `/journey/{id}`가 404와 함께 돌려준다. */
export const brokenJourney = () => 안내("이 경로 주소는 더 볼 수 없습니다.");

/** 카드 하나의 껍데기. 경로 키를 카드에 적어 두면 `map`이 어느 경로인지 알아본다. */
const 카드 = (갈래, network, journey, key, 안쪽) =>
  `<article class="${갈래}" data-network="${network.key}"`
  + `${key ? ` data-journey="${key}"` : ""}>`
  + `<h3><span class="network">${network.label}</span>`
  + ` <span class="status">${상태(journey)}</span></h3>${안쪽}</article>`;

/**
 * 「지도에 표시」 — 카드당 경로 하나만 지도에 올린다(CONTEXT 「경로 지도」).
 *
 * 누르는 것을 `map`이 받는다. 조각을 새로 받아 오는 일이 아니라 이미 실린 좌표를 고르는 일이라
 * htmx가 아니라 브라우저 스크립트다.
 */
const 지도_버튼 = (network) =>
  `<button type="button" class="show-on-map" data-network="${network.key}">지도에 표시</button>`;

/**
 * 경로 지도 좌표. 그리는 것은 브라우저 `map`이다(ADR-0001).
 *
 * `<`를 `\u003c`로 바꾼다 — 정류장 이름은 CSV에서 온 남의 글자라, 언젠가 `</script`가 든 이름이
 * 들어오면 조각이 거기서 끊긴다. JSON은 그 자리에 유니코드 이스케이프를 그대로 받는다.
 */
const 좌표 = (geometry) =>
  geometry
    ? '<script type="application/json" class="geometry">'
      + JSON.stringify(geometry).replace(/</g, "\\u003c")
      + "</script>"
    : "";

/**
 * 「다른 경로 더 보기」와 그 자리 — 누르면 다른 경로 카드가 최대 둘 끼워진다.
 *
 * 조각 하나에 경로 하나이므로 자리도 둘이다. 단추 하나가 둘을 함께 부르도록 htmx의
 * `from:`을 쓴다 — 우리 스크립트를 하나도 더하지 않는다(ADR-0001). `once`라 두 번 부르지 않고,
 * 다 채워지면 단추는 CSS가 감춘다.
 */
function 더_보기(network, keys) {
  if (!keys.length) return "";
  const 단추 = `more-${network.key}`;
  const 자리 = keys
    .map(
      (key) =>
        `<div data-journey="${key}" hx-get="/journey/${key}"`
        + ` hx-trigger="click once from:#${단추}" hx-swap="outerHTML"></div>`,
    )
    .join("");
  return (
    `<button type="button" class="more" id="${단추}">다른 경로 더 보기</button>`
    + `<div class="alternatives">${자리}</div>`
  );
}

/**
 * 출발 지점 → 도보 → (승차 → 노선 → 하차 → 환승) … → 도보 → 도착 지점.
 *
 * 구간마다 세 줄이고 그 사이마다 환승 한 줄이 선다. 환승 줄에는 내리는 곳 → 타는 곳과 환승 도보가
 * 함께 있다 — 「어디서 내려 어디서 타는지」를 모르면 갈아탈 수가 없다.
 */
function 경로(network, journey) {
  const 구간 = journey.legs;
  const 줄 = [`출발 지점에서 ${미터(구간[0].board.walk)} 걷기`];
  구간.forEach((leg, i) => {
    줄.push(
      `승차 ${정류장(leg.board)}`,
      `${노선_이름(network, leg.route)} 타고 ${leg.stopsPassed}개 정류장`,
      `하차 ${정류장(leg.alight)}`,
    );
    if (i + 1 < 구간.length) 줄.push(환승(leg.alight, 구간[i + 1].board, journey.transferWalks[i]));
  });
  줄.push(`${미터(구간[구간.length - 1].alight.walk)} 걸어 도착 지점`);
  return 목록("ol", "legs", 줄);
}

/**
 * 환승 한 줄. 같은 줄에서 갈아타면 걸을 일이 없으므로 거리 대신 그렇다고 적는다 —
 * 「환승 도보 0m」는 값이 빠진 것처럼 보인다.
 *
 * 이름이 같은데 줄만 다른 자리(길 양쪽)라면 「A → A」로 보일 텐데, 번들의 환승 지점 7,250줄에
 * 그런 쌍은 **0줄**이다 — 두 노선이 같은 이름에 서면 같은 줄에도 서서 그쪽이 더 짧기 때문이다.
 * 생기면 그때 가르면 된다. 지금 가르면 검사도 못 쓰는 갈래가 하나 는다.
 */
const 환승 = (내리는_곳, 타는_곳, walk) =>
  내리는_곳.id === 타는_곳.id
    ? `<span class="transfer">${정류장(내리는_곳)}에서 환승 · 같은 정류장</span>`
    : `<span class="transfer">환승 도보 ${미터(walk)}`
      + ` · ${정류장(내리는_곳)} → ${정류장(타는_곳)}</span>`;

/** 시가 공표한 배차간격이 없을 때 그 자리에 서는 말 (CONTEXT 「지표」). */
const 배차_없음 = "정보 없음";
const 배차_값 = (v) => (v === null || v === undefined ? 배차_없음 : 벗김(v));

/** 카드 아래 수치 줄 (CONTEXT 「지표」). 배차간격은 값이 없으면 「정보 없음」이다. */
function 지표(network, journey) {
  const 노선 = journey.legs.map((leg) => leg.route);
  // 배차는 노선마다 따로다. 아직 어느 노선도 자료가 없어 한 줄로 합치고, 자료가 들어오면 갈린다
  const 배차 = 노선.map((route) => network.headway(route));
  const 줄 = [
    `예상 시간 ${분(journey.seconds)}`,
    `환승 ${journey.transfers ? `${journey.transfers}회` : "없음"}`,
    `노선 ${노선.map((route) => 노선_이름(network, route)).join(" · ")}`,
    `정류장 ${journey.stopsPassed}곳`,
    `도보 합계 ${도보_합계(journey)}`,
    `배차간격 ${배차.every((v) => 배차_값(v) === 배차_없음)
      ? 배차_없음
      : 배차.map(배차_값).join(" · ")}`,
  ];
  return 목록("ul", "metrics", 줄);
}

const 추정치 =
  `<p class="estimate-note">예상 시간은 정류장당 ${SECONDS_PER_STOP}초와` +
  ` 걷는 속도 ${WALK_SPEED_KMH}km/h로 잡은 추정치입니다. 배차 대기는 넣지 않았습니다.</p>`;
