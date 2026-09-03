/**
 * 번들 JSON을 노선망 둘로 갈라 조회할 수 있는 모습으로 바꾼다 (ADR-0008).
 *
 * 경로는 늘 한 노선망 안에서만 찾으므로(CONTEXT 「노선망」), 아래 계산은 노선망 하나를 받는다.
 * 번들의 생김새를 아는 곳은 이 파일 하나이고, `candidates`·`search`·`render`는 여기가 만든
 * 모습만 본다.
 *
 * 표를 만드는 일은 **모듈이 처음 불릴 때 한 번**만 한다. 번들은 요청 중에 바뀌지 않으므로,
 * 요청마다 다시 만들면 무료 요금제의 요청당 CPU를 그 일에 다 쓴다.
 */
import bundle from "./data.json" with { type: "json" };

/** 노선망 하나를 만든다. `label`은 화면에 그대로 나가는 말이다(CONTEXT 「개편 전 / 개편 후」). */
function 노선망(key, label) {
  // 정류장 줄 하나 → 그 줄에서 탈 수 있는 (노선 · 방향 · 순번) 전부
  const rides = new Map();
  for (const [route, sides] of Object.entries(bundle.route_stops)) {
    if (bundle.routes[route].network !== key) continue;
    for (const [side, 차례] of Object.entries(sides)) {
      차례.forEach((자리, order) => {
        for (const id of 자리.stops) {
          const 목록 = rides.get(id);
          if (목록) 목록.push({ route, side, order });
          else rides.set(id, [{ route, side, order }]);
        }
      });
    }
  }
  // 도보권을 잴 때 도는 목록. 이 노선망의 노선이 지나는 줄만 담는다 —
  // 전남 정류장까지 다 재면 「가장 가까운 정류장」이 아무 버스도 안 서는 곳이 된다
  const served = [...rides.keys()].map((id) => ({ id, ...bundle.stops[id] }));
  return {
    key,
    label,
    rides,
    served,
    /** 노선 하나의 화면 이름. */
    routeName: (route) => bundle.routes[route].name,
    /** 배차간격. 개편 전 자료가 아직 없어 늘 `null`이다(스펙 Out of Scope). */
    headway: (route) => bundle.routes[route].headway,
  };
}

/** 개편 전 · 개편 후 순서. 화면의 카드 차례가 이 차례다. */
export const NETWORKS = [노선망("before", "개편 전"), 노선망("after", "개편 후")];
