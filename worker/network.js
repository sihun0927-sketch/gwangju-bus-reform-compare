/**
 * 번들 JSON을 노선망 둘로 갈라 조회할 수 있는 모습으로 바꾼다 (ADR-0008).
 *
 * 경로는 늘 한 노선망 안에서만 찾으므로(CONTEXT 「노선망」), 아래 계산은 노선망 하나를 받는다.
 * 번들의 생김새를 아는 곳은 이 파일 하나이고, `candidates`·`search`·`render`는 여기가 만든
 * 모습만 본다.
 *
 * 표를 만드는 일은 **모듈이 처음 불릴 때 한 번**만 한다. 번들은 요청 중에 바뀌지 않으므로,
 * 요청마다 다시 만들면 무료 요금제의 요청당 CPU를 그 일에 다 쓴다.
 *
 * 환승은 번들의 `route_links`가 이미 정해 준다 — 노선 쌍마다 가장 가까운 환승 지점 하나(ADR-0008).
 * 번들은 쌍을 한 줄로만 적으므로(`a < b`) 여기서 양쪽으로 펴 둔다. 요청 때 「이 노선에서 갈아탈 수
 * 있는 노선」을 바로 꺼내려면 두 방향이 다 있어야 한다.
 */
import bundle from "./data.json" with { type: "json" };

/** 노선망 하나를 만든다. `label`은 화면에 그대로 나가는 말이다(CONTEXT 「개편 전 / 개편 후」). */
function 노선망(key, label) {
  // 정류장 줄 하나 → 그 줄에서 탈 수 있는 (노선 · 방향 · 순번) 전부
  //
  // `lane`(노선|방향)과 `spot`(노선|방향|순번)은 탐색이 표를 찾을 때 쓰는 열쇠다. 값이 번들에서
  // 정해지므로 여기서 한 번 만든다 — 요청 때 만들면 갈아타기 한 바퀴에 글자 수만 개를 새로 잇게 되고,
  // 그 이음이 요청당 CPU의 대부분이었다
  const rides = new Map();
  for (const [route, sides] of Object.entries(bundle.route_stops)) {
    if (bundle.routes[route].network !== key) continue;
    for (const [side, 차례] of Object.entries(sides)) {
      const lane = `${route}|${side}`;
      차례.forEach((자리, order) => {
        const spot = `${lane}|${order}`;
        for (const id of 자리.stops) {
          const 탈것 = { route, side, order, lane, spot };
          const 목록 = rides.get(id);
          if (목록) 목록.push(탈것);
          else rides.set(id, [탈것]);
        }
      });
    }
  }
  // 도보권을 잴 때 도는 목록. 이 노선망의 노선이 지나는 줄만 담는다 —
  // 전남 정류장까지 다 재면 「가장 가까운 정류장」이 아무 버스도 안 서는 곳이 된다
  const served = [...rides.keys()].map((id) => ({ id, ...bundle.stops[id] }));

  // 줄 하나에 대상 하나. 환승 정류장은 요청마다 같은 것을 가리키므로 새로 만들지 않는다
  const byId = new Map(served.map((s) => [s.id, s]));

  // 노선 → 갈아탈 수 있는 노선 → 그 쌍의 환승 지점 한 자리(`here`는 내리는 줄, `there`는 타는 줄)
  const links = new Map();
  const rideOn = (id, route) => (rides.get(id) ?? []).filter((r) => r.route === route);
  for (const [a, b, here, there, walk] of bundle.route_links) {
    if (bundle.routes[a].network !== key) continue;   // 번들은 한 노선망 안에서만 잇는다
    // 「이 줄에서 이 노선을 몇 번째로 지나는가」는 번들이 정해 둔 것이라 요청마다 다시 고를 것이 없다.
    // 여기서 한 번 붙여 두면 탐색은 순번 비교만 한다 — 요청당 CPU가 여기서 갈렸다
    잇는다(links, a, b, byId.get(here), byId.get(there), walk, rideOn(here, a), rideOn(there, b));
    잇는다(links, b, a, byId.get(there), byId.get(here), walk, rideOn(there, b), rideOn(here, a));
  }

  return {
    key,
    label,
    rides,
    served,
    links,
    /** 줄 하나의 이름·좌표. 환승 정류장처럼 도보권 후보가 아닌 줄을 화면에 적을 때 쓴다. */
    stop: (id) => byId.get(id),
    /** 노선 하나의 화면 이름. */
    routeName: (route) => bundle.routes[route].name,
    /** 화면 이름 → 이 노선망의 노선. 없는 이름이면 `null`(경로 키를 풀 때 쓴다). */
    route: (name) => (bundle.routes[`${key}:${name}`] ? `${key}:${name}` : null),
    /**
     * 한 구간이 지나는 자리들 — 순번 `from`부터 `to`까지, 자리마다 그 자리에 선 줄 목록.
     *
     * 경로 지도가 승차와 하차 **사이**의 정류장을 그리려면 이것이 있어야 한다. 자리 하나에
     * 줄이 여럿인 것은 길 양쪽이 따로이기 때문이고, 어느 쪽을 그릴지는 `geometry`가 고른다.
     */
    along: (route, side, from, to) =>
      (bundle.route_stops[route]?.[side] ?? []).slice(from, to + 1),
    /** 배차간격(분). 시가 공표한 값이 있는 개편 전 110개만 숫자이고 나머지는 `null`이다. */
    // 값과 함께 **어디서 온 값인지**를 준다. 개편 전은 시가 공표한 것, 개편 후는 우리가
    // 나눈 추정이다(ADR-0010) — 화면이 그것을 밝혀야 시민이 둘을 안 헷갈린다
    headway: (route) => bundle.routes[route].headway,
    headwayEstimated: (route) => bundle.routes[route].estimated === true,
  };
}

/**
 * `from`에서 `to`로 갈아타는 자리를 한 칸 적는다.
 *
 * `hereRides`·`thereRides`는 그 줄에서 각 노선을 지나는 (방향 · 순번)이다. 한 노선이 한 줄을
 * 두 번 지나기도 해서 목록이다.
 */
function 잇는다(links, from, to, here, there, walk, hereRides, thereRides) {
  const 이음 = { here, there, walk, hereRides, thereRides };
  const 묶음 = links.get(from);
  if (묶음) 묶음.set(to, 이음);
  else links.set(from, new Map([[to, 이음]]));
}

/** 개편 전 · 개편 후 순서. 화면의 카드 차례가 이 차례다. */
export const NETWORKS = [노선망("before", "개편 전"), 노선망("after", "개편 후")];
