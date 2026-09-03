function selectedPlace(input) {
  const lat = input.dataset.lat;
  const lng = input.dataset.lng;
  return lat && lng ? { lat, lng } : undefined;
}

function compareWhenBothPlacesAreSelected() {
  const from = selectedPlace(document.querySelector("#from"));
  const to = selectedPlace(document.querySelector("#to"));
  if (!from || !to || !window.htmx) return;

  window.htmx.ajax(
    "GET",
    `/compare?from=${encodeURIComponent(`${from.lat},${from.lng}`)}&to=${encodeURIComponent(`${to.lat},${to.lng}`)}`,
    { target: "#place-result", swap: "innerHTML" },
  );
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

document.addEventListener("input", (event) => {
  const input = event.target.closest(".place input");
  if (!input) return;
  delete input.dataset.lat;
  delete input.dataset.lng;
});
