// 노선 지도 · 경로 지도 — 조각에 실린 좌표 JSON을 Kakao JS SDK로 그린다 (ADR-0005, §7-3 Q6·Q7).
//
// 두 탭 공용이다. 노선번호 탭은 노선 변화 표 조각의 `.route-geometry`를 읽고, 장소 탭도 나중에
// 같은 함수에 입력만 다르게 준다. htmx가 조각을 끼운 뒤에만 돌며 HTML은 만들지 않는다.
//
// Kakao SDK 태그는 빌드가 `KAKAO_JS_KEY`를 읽었을 때만 껍데기에 들어간다. 키가 없으면
// `window.kakao`가 없고, 그때는 지도 자리에 한 줄만 남기고 조용히 끝난다.

// 색은 `site.css`의 토큰이 정본이다. 여기 적힌 값은 스타일시트를 못 읽었을 때의 대비책일 뿐이라,
// 색을 바꿀 일이 있으면 CSS만 고치면 된다 — 표와 지도가 따로 놀지 않는다
const MAP_LINE_BEFORE = { token: "--before-line", fallback: "#0e6b5c", weight: 8, zIndex: 1 };
const MAP_LINE_AFTER = { token: "--after-line", fallback: "#1d4ed8", weight: 4, zIndex: 2 };
const MAP_DOT = {
  유지: { token: "--kept-dot", fallback: "#5a6b67" },
  "경유 제외": { token: "--dropped-dot", fallback: "#b2402f" },
  "경유 추가": { token: "--added-dot", fallback: "#1d4ed8" },
};
const MAP_UNAVAILABLE = "지도를 불러오지 못했습니다";

// 카드 하나에 지도 하나. 표가 바뀌면 같은 지도 위에 다시 그린다
const drawnMaps = new WeakMap();

function mapColour(style) {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(style.token)
    .trim();
  return value || style.fallback;
}

function routeGeometry(root) {
  const carrier = root.matches?.(".route-geometry")
    ? root
    : root.querySelector?.(".route-geometry");
  if (!carrier) return undefined;
  try {
    return JSON.parse(carrier.textContent);
  } catch {
    return undefined;
  }
}

function mapSlot(root) {
  // 표만 바뀌었으면 카드는 위에 있고, 카드째 바뀌었으면 아래에 있다
  const card = root.closest?.(".route-card") ?? root.querySelector?.(".route-card");
  return card?.querySelector(".route-map") ?? undefined;
}

function mapNote(slot, text) {
  const note = document.createElement("p");
  note.className = "map-note";
  note.textContent = text;
  // 지도가 있었다면 그 DOM째 버리는 것이라 기억도 함께 버린다. 안 그러면 다음에 그릴 때
  // 이미 있다고 여겨 빈 자리 위에 선을 얹고, 카드가 이 문구에 갇힌다
  drawnMaps.delete(slot);
  slot.replaceChildren(note);
}

function mapLine(map, path, style) {
  return new kakao.maps.Polyline({
    map,
    path,
    strokeWeight: style.weight,
    strokeColor: mapColour(style),
    strokeOpacity: 0.9,
    strokeStyle: "solid",
    zIndex: style.zIndex,
  });
}

function mapDot(map, stop) {
  const mark = document.createElement("span");
  mark.className = "route-stop-dot";
  mark.style.background = mapColour(MAP_DOT[stop.state] ?? MAP_DOT["유지"]);
  mark.title = `${stop.name} · ${stop.state}`;
  return new kakao.maps.CustomOverlay({
    map,
    position: new kakao.maps.LatLng(stop.lat, stop.lng),
    content: mark,
    zIndex: 3,
  });
}

function drawRouteMap(slot, geometry) {
  const bounds = new kakao.maps.LatLngBounds();
  const path = (points) =>
    points.map(([lat, lng]) => {
      const at = new kakao.maps.LatLng(lat, lng);
      bounds.extend(at);
      return at;
    });
  const before = path(geometry.before ?? []);
  const after = path(geometry.after ?? []);
  if (!before.length && !after.length) {
    mapNote(slot, MAP_UNAVAILABLE);
    return;
  }

  let drawn = drawnMaps.get(slot);
  if (!drawn) {
    slot.replaceChildren();
    drawn = { map: new kakao.maps.Map(slot, { center: before[0] ?? after[0], level: 6 }), shapes: [] };
    drawnMaps.set(slot, drawn);
  }
  drawn.shapes.forEach((shape) => shape.setMap(null));
  // 한쪽 선이 비어 있으면(그 노선의 정류장을 하나도 못 이었으면) 그 선은 긋지 않는다
  drawn.shapes = [
    ...(before.length ? [mapLine(drawn.map, before, MAP_LINE_BEFORE)] : []),
    ...(after.length ? [mapLine(drawn.map, after, MAP_LINE_AFTER)] : []),
    ...(geometry.stops ?? []).map((stop) => mapDot(drawn.map, stop)),
  ];
  // 카드가 막 끼워진 참이면 자리의 크기를 지도가 아직 모른다
  drawn.map.relayout();
  drawn.map.setBounds(bounds);
}

function showRouteMap(slot, geometry) {
  if (!window.kakao?.maps) {
    mapNote(slot, MAP_UNAVAILABLE);
    return;
  }
  // SDK를 `autoload=false`로 불렀으므로 쓰기 전에 한 번 깨운다. 두 번째부터는 바로 돌아온다
  window.kakao.maps.load(() => drawRouteMap(slot, geometry));
}

document.body.addEventListener("htmx:afterSwap", (event) => {
  const geometry = routeGeometry(event.target);
  const slot = mapSlot(event.target);
  if (geometry && slot) showRouteMap(slot, geometry);
});
