function selectedPlace(input) {
  const lat = input.dataset.lat;
  const lng = input.dataset.lng;
  return lat && lng ? { lat, lng, name: input.value } : undefined;
}

function compareWhenBothPlacesAreSelected() {
  const from = selectedPlace(document.querySelector("#from"));
  const to = selectedPlace(document.querySelector("#to"));
  if (!from || !to || !window.htmx) return;

  // 이름도 함께 보낸다 — 카드 경로 줄의 양 끝이 「출발 지점」이 아니라 시민이 고른 곳이 되게
  // (CONTEXT 「경로 줄」). 좌표와 달리 이름은 경로 키에 없으므로 매개변수로만 간다
  const 칸 = new URLSearchParams({
    from: `${from.lat},${from.lng}`,
    to: `${to.lat},${to.lng}`,
    fromName: from.name,
    toName: to.name,
  });
  window.htmx.ajax("GET", `/compare?${칸}`, { target: "#place-result", swap: "innerHTML" });
}

document.addEventListener("click", (event) => {
  const candidate = event.target.closest("[data-place-candidate]");
  if (!candidate) return;

  const candidates = candidate.closest(".place-candidate-list");
  const input = candidates.previousElementSibling?.querySelector("input");
  if (!input) return;

  input.value = candidate.querySelector("strong")?.textContent ?? "";
  input.dataset.lat = candidate.dataset.lat;
  input.dataset.lng = candidate.dataset.lng;
  candidates.replaceChildren();
  compareWhenBothPlacesAreSelected();
});

/** 예시 검색 하나 → 두 입력칸을 채운다. 시민이 후보를 고른 것과 같은 상태로 만든다. */
function fillPlace(selector, point, name) {
  const input = document.querySelector(selector);
  const [lat, lng] = String(point).split(",");
  if (!input || !lat || !lng) return;
  input.value = name;
  input.dataset.lat = lat;
  input.dataset.lng = lng;
  // 열려 있던 후보 목록은 닫는다 — 채워 넣은 값 위에 옛 후보가 덮여 있으면 고른 것처럼 보인다
  document.querySelector(`${selector}-candidates`)?.replaceChildren();
}

document.addEventListener("click", (event) => {
  const example = event.target.closest(".example");
  if (!example) return;
  fillPlace("#from", example.dataset.from, example.dataset.fromName);
  fillPlace("#to", example.dataset.to, example.dataset.toName);
  compareWhenBothPlacesAreSelected();
});

document.addEventListener("input", (event) => {
  const input = event.target.closest(".place input");
  if (!input) return;
  delete input.dataset.lat;
  delete input.dataset.lng;
});
