/**
 * 조각 만들기 — htmx가 결과 영역에 그대로 끼우는 HTML (ADR-0001).
 *
 * 화면에 나가는 말은 CONTEXT 「장소로 찾기」 절을 따른다. 카드 머리에 상태만 적고, 두 카드를
 * 합쳐 말하는 **판정 문장은 두지 않는다** — 견주는 일은 시민이 카드 둘을 보고 한다.
 *
 * 카드 안은 둘로 나뉜다(CONTEXT 「경로 줄」·「지표」). **노선마다 달라지는 값**(노선 이름 ·
 * 배차간격 · 지나는 정류장 수)은 경로 줄의 그 노선 자리에 있고, **경로 전체에 하나씩인 값**
 * (예상 시간 · 환승 · 도보 합계)만 아래 지표 표에 있다. 나누지 않으면 환승 2회 경로에서 같은
 * 값이 네 번까지 겹친다.
 *
 * 숫자를 문장에 적을 때도 상수는 `rules`에서 읽는다. 안내문에 500이라 적어 두면 도보권을 고칠 때
 * 규칙과 문구가 따로 낡는다.
 */
import { MAX_TRANSFERS, SECONDS_PER_STOP, WALK_RADIUS_M, WALK_SPEED_KMH } from "./rules.js";

const SECONDS_PER_MINUTE = 60;

const 문자 = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** 정류장·노선·장소 이름은 CSV와 Kakao에서 온 남의 글자다. 그대로 붙이지 않는다. */
const 벗김 = (글) => String(글).replace(/[&<>"']/g, (c) => 문자[c]);

const 미터 = (m) => `${Math.round(m)}m`;

/**
 * 카드에 적는 도보 합계. `rank`가 붙인 걷는 구간 목록을 **구간마다 반올림해서** 더한다 —
 * 시민이 눈으로 줄마다의 값을 더한 것과 합계가 1m 어긋나 보이지 않게. 환승 도보도 그 목록에 있다.
 */
const 도보_합계 = (journey) =>
  미터(journey.walks.reduce((합, m) => 합 + Math.round(m), 0));
const 분 = (초) => `${Math.round(초 / SECONDS_PER_MINUTE)}분`;

/** 줄 목록을 `<ul>` 하나로. */
const 목록 = (갈래, 줄들) =>
  `<ul class="${갈래}">${줄들.map((줄) => `<li>${줄}</li>`).join("")}</ul>`;

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

/** 지도의 선 둘이 무엇인지 한 줄로 (CONTEXT 「경로 지도」). */
const 지도_범례 = "개편 전 경로는 점선, 개편 후 경로는 실선입니다. 회색 점선은 걷는 구간입니다.";

/**
 * 카드 한 쌍 아래 각주 한 벌 (CONTEXT 「개편 전 카드 / 개편 후 카드」).
 *
 * 카드 **안**에 두면 같은 문장이 두 번 서고, 카드 높이도 먹어 지표 표가 어긋난다. 뒤 두 줄은
 * 시민이 걸려 넘어지는 자리다 — 「왜 내가 아는 정류장이 아니지」와 「왜 개편 후만 정보 없음이지」.
 */
const 각주 = 목록("notes", [
  `예상 시간은 정류장당 ${SECONDS_PER_STOP}초와 걷는 속도 ${WALK_SPEED_KMH}km/h로 잡은`
    + " 추정치입니다. 배차 대기는 넣지 않았습니다.",
  `승차·하차 정류장은 고른 지점의 도보권 ${WALK_RADIUS_M}m 안에서 엔진이 고릅니다.`,
  "배차간격 공표값은 개편 전 노선에만 있습니다. 예상 시간 계산에 쓰지 않았습니다.",
]);

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
  + `<div class="compare">${조각들.join("")}</div>`
  + 각주;

/** 화면에 적는 노선 이름. */
const 노선_이름 = (network, route) => 벗김(network.routeName(route));

/** 추정 좌표를 쓴 정류장이면 이름 옆에 표시를 붙인다 (CONTEXT 「추정 좌표」). */
function 정류장(stop) {
  const 표시 = stop.estimated ? ' <span class="estimated">추정 위치</span>' : "";
  return `<b>${벗김(stop.name)}</b>${표시}`;
}

/**
 * 카드 머리의 상태 (CONTEXT 「상태」). 등급 넷은 여기서만 글자가 된다.
 *
 * 넷이 모두 환승 횟수 한 축의 말이다 — 「직행」이라 적으면 하나만 다른 축이 되어, 두 카드를
 * 나란히 놓았을 때 몇 단계 달라졌는지를 눈으로 세야 한다.
 */
const 상태 = (journey) => {
  if (!journey) return "경로 없음";
  return journey.transfers ? `환승 ${journey.transfers}회` : "환승 없음";
};

/**
 * 배차간격 한 줄. 번들에는 **분 단위 숫자**가 있고 단위는 여기서 붙인다 (CONTEXT 「경로 줄」).
 *
 * 시가 공표한 값이 없으면 「정보 없음」이다 — 개편 후 노선 전부와 개편 전 순환01이 그렇다.
 */
const 배차_없음 = "정보 없음";
const 배차_값 = (v) => (typeof v === "number" ? `${v}분` : 배차_없음);

/**
 * 노선망 하나의 카드. `journey`가 없으면 머리가 「경로 없음」이고 안이 한 줄이다.
 *
 * `key`는 이 경로의 경로 키, `geometry`는 경로 지도 좌표, `alternatives`는 다른 경로들의 키다.
 * 경로가 없으면 셋 다 없다. `places`는 시민이 고른 두 장소의 이름이다 — 없으면 경로 줄 양 끝이
 * 「출발 지점」·「도착 지점」이다.
 */
export function card(network, journey, { key, geometry, alternatives = [], places = {} } = {}) {
  const 안쪽 = journey
    ? 경로(network, journey, places) + 지표(journey) + 지도_버튼(network) + 좌표(geometry)
    : `<p class="notice">이 노선망에서는 환승 ${MAX_TRANSFERS}회 안에 가는 길을 찾지 못했습니다.</p>`;
  return 카드("journey-card", network, journey, key, 안쪽)
    + (journey ? 다른_경로(network, alternatives, places) : "");
}

/**
 * 다른 경로 카드 하나 — `/journey/{id}`가 돌려주는 조각 (CONTEXT 「다른 경로 카드」).
 *
 * 기본 카드와 같은 줄들을 적는다. 다른 것은 둘 — 「다른 경로 더 보기」가 없고(펼친 것이 또 펼치지
 * 않는다), 스스로 자리를 차지하지 않고 기본 카드 안의 자리에 끼워진다.
 */
export const alternative = (network, journey, { key, geometry, places = {} } = {}) =>
  카드(
    "journey-card alternative", network, journey, key,
    경로(network, journey, places) + 지표(journey)
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
 * htmx가 아니라 브라우저 스크립트다. 올라간 뒤 글자를 「지도에 표시 중」으로 바꾸는 것도 `map`이
 * 한다 — 색만으로 알리면 색을 못 가리는 눈에는 아무 표시가 없는 것과 같다.
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
 * 장소 이름을 조각 주소에 싣는다 — 펼친 다른 경로 카드도 같은 이름을 적게.
 *
 * 좌표는 경로 키 안에 있지만 이름은 없다. 이름까지 키에 넣으면 같은 경로가 시민이 무엇을
 * 검색했는지에 따라 다른 키가 되고, 키는 남에게 보내는 링크다(`journey.js` 머리말). 그래서
 * 이름만 매개변수로 간다 — 키 하나만 받은 사람에게는 이름이 없고, 그때 양 끝이 「출발 지점」이다.
 * 조각은 HTML이므로 `&`는 `&amp;`로 적는다.
 */
function 이름_매개변수({ from, to } = {}) {
  const 칸 = [];
  if (from) 칸.push(`fromName=${encodeURIComponent(from)}`);
  if (to) 칸.push(`toName=${encodeURIComponent(to)}`);
  return 칸.length ? `?${칸.join("&amp;")}` : "";
}

/**
 * 「다른 경로 더 보기 (2)」 — 펴고 접는 `<details>` 하나. 안에 다른 경로 카드가 최대 둘 온다.
 *
 * **카드 밖에 선다.** 카드 한 쌍은 지표를 맞추려고 서로 늘어나므로(CONTEXT 「개편 전 카드 /
 * 개편 후 카드」), 펼친 것이 카드 **안**에 있으면 한쪽만 펼쳐도 격자 줄이 커져 옆 카드가 빈 채로
 * 따라 늘어난다. 카드는 첫 줄, 이것은 둘째 줄이라 서로 키를 안 건드린다.
 *
 * 펴고 접는 일을 `<details>`가 한다 — 우리 스크립트를 하나도 더하지 않는다(ADR-0001). 조각을
 * 부르는 것은 처음 펼 때 한 번뿐이고(`toggle once`), 그 뒤로 접었다 펴는 것은 브라우저 몫이라
 * 다시 받아 오지 않는다. `toggle`은 위로 오르지 않는 사건이지만 htmx의 `from:`이 그 자리에
 * 직접 듣게 하므로 상관없다.
 *
 * 개수를 적는 까닭은 펴기 전에 볼 것이 몇 개인지 알리기 위해서다. 0개면 이 자리가 아예 없으므로
 * 적는 값은 1과 2를 가른다.
 */
function 다른_경로(network, keys, places) {
  if (!keys.length) return "";
  const 상자 = `more-${network.key}`;
  const 꼬리 = 이름_매개변수(places);
  const 자리 = keys
    .map(
      (key) =>
        `<div data-journey="${key}" hx-get="/journey/${key}${꼬리}"`
        + ` hx-trigger="toggle once from:#${상자}" hx-swap="outerHTML"></div>`,
    )
    .join("");
  return (
    `<details class="alternatives" id="${상자}" data-network="${network.key}">`
    + '<summary class="more">'
    + `<span class="shut">다른 경로 더 보기 (${keys.length})</span>`
    + '<span class="open">다른 경로 접기</span></summary>'
    + `${자리}</details>`
  );
}

/**
 * 경로 줄의 핀 목록 (CONTEXT 「경로 줄」).
 *
 * 핀 하나가 자리 하나다 — 양 끝은 시민이 고른 **장소**, 사이는 **정류장**. 정류장 핀에 노선이
 * 붙어 있으면 거기서 버스를 타는 것이고, 그 핀 아래 선이 실선이 된다.
 *
 * 같은 정류장에서 갈아탈 때는 하차 핀과 승차 핀을 **하나로 겹친다**. 같은 이름의 핀이 둘 서면
 * 「내렸다가 또 어딘가로 갔나」로 읽힌다. 줄이 다르면 겹치지 않고 그 사이에 환승 도보를 적는다.
 */
function 핀들(journey, places) {
  const 구간 = journey.legs;
  const 핀 = [
    { 갈래: "place", 이름: places.from, 기본: "출발 지점", 도보: 구간[0].board.walk },
  ];
  구간.forEach((leg, i) => {
    const 앞 = 구간[i - 1];
    const 끝 = () => 핀[핀.length - 1];
    if (앞 && 앞.alight.id === leg.board.id) Object.assign(끝(), { 역할: "하차 · 승차", leg });
    else {
      if (앞) 끝().환승도보 = journey.transferWalks[i - 1];
      핀.push({ 갈래: "stop", stop: leg.board, 역할: "승차", leg });
    }
    핀.push({ 갈래: "stop", stop: leg.alight, 역할: "하차" });
  });
  const 마지막 = 구간[구간.length - 1];
  핀.push({ 갈래: "place", 이름: places.to, 기본: "도착 지점", 도보: 마지막.alight.walk });
  return 핀;
}

/** 핀 하나. `ride`면 아래로 내려가는 선이 버스 구간(실선)이고, 아니면 걷는 구간(점선)이다. */
function 핀_조각(network, 핀) {
  if (핀.갈래 === "place") {
    const 이름 = 핀.이름 ? 벗김(핀.이름) : 핀.기본;
    return `<li class="walk"><b>${이름}</b>`
      + `<span class="sub">도보 ${미터(핀.도보)}</span></li>`;
  }
  const 아래 = 핀.leg
    ? `<span class="route"><b class="chip">${노선_이름(network, 핀.leg.route)}</b></span>`
      + `<span class="sub">배차간격 ${배차_값(network.headway(핀.leg.route))}`
      + ` · ${핀.leg.stopsPassed}개 정류장</span>`
    : 핀.환승도보 === undefined
      ? ""
      : `<span class="sub">환승 도보 ${미터(핀.환승도보)}</span>`;
  return `<li class="${핀.leg ? "ride" : "walk"}">`
    + `<span class="at">${정류장(핀.stop)} ${핀.역할}</span>${아래}</li>`;
}

/** 출발 장소 → 승차 → (하차 · 승차 …) → 하차 → 도착 장소. */
const 경로 = (network, journey, places) =>
  `<ol class="steps">`
  + 핀들(journey, places).map((핀) => 핀_조각(network, 핀)).join("")
  + "</ol>";

/**
 * 카드 아래 지표 표 (CONTEXT 「지표」) — 경로 전체에 하나씩인 값 셋뿐이다.
 *
 * 레이블을 왼쪽, 값을 오른쪽에 두는 정의 목록이라 개편 전·후 두 카드의 행이 늘 맞는다. 알약을
 * 줄바꿈으로 흘리면 항목 글자 길이에 따라 카드마다 접히는 자리가 갈려 나란히 놓아도 견줄 수 없다.
 */
function 지표(journey) {
  const 줄 = [
    ["예상 시간", 분(journey.seconds)],
    ["환승", journey.transfers ? `${journey.transfers}회` : "없음"],
    ["도보 합계", 도보_합계(journey)],
  ];
  return '<dl class="metrics">'
    + 줄.map(([이름, 값]) => `<dt>${이름}</dt><dd>${값}</dd>`).join("")
    + "</dl>";
}
