import {
  PLACE_CACHE_SECONDS,
  PLACE_CANDIDATES,
  PLACE_QUERY_MIN_LENGTH,
  PLACE_SEARCH_MARGIN_M,
} from "./rules.js";

const KAKAO_KEYWORD_SEARCH = "https://dapi.kakao.com/v2/local/search/keyword.json";
const METRES_PER_LATITUDE_DEGREE = 111_320;

export async function places(request, env, bundle) {
  const query = new URL(request.url).searchParams.get("q")?.trim() ?? "";
  if (Array.from(query).length < PLACE_QUERY_MIN_LENGTH) return "";

  const cache = globalThis.caches?.default;
  const cacheUrl = new URL(request.url);
  cacheUrl.search = new URLSearchParams({ q: query }).toString();
  const cacheKey = new Request(cacheUrl.toString());
  const cached = cache && await cache.match(cacheKey);
  if (cached) return cached.text();

  try {
    const response = await fetch(kakaoUrl(query, bundle.bbox), {
      headers: { Authorization: `KakaoAK ${env.KAKAO_REST_KEY}` },
    });
    if (!response.ok) throw new Error(`Kakao returned ${response.status}`);

    const { documents = [] } = await response.json();
    const html = render(documents);
    if (cache) {
      await cache.put(cacheKey, new Response(html, {
        headers: {
          "cache-control": `public, max-age=${PLACE_CACHE_SECONDS}`,
          "content-type": "text/html; charset=utf-8",
        },
      }));
    }
    return html;
  } catch {
    return '<p class="notice">장소 후보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</p>';
  }
}

function kakaoUrl(query, bbox) {
  const rect = expandedRect(bbox);
  const url = new URL(KAKAO_KEYWORD_SEARCH);
  url.searchParams.set("query", query);
  url.searchParams.set("rect", rect.join(","));
  url.searchParams.set("size", PLACE_CANDIDATES);
  return url;
}

function expandedRect(bbox) {
  const latitudeMargin = PLACE_SEARCH_MARGIN_M / METRES_PER_LATITUDE_DEGREE;
  const middleLatitude = (bbox.min_lat + bbox.max_lat) / 2;
  const longitudeMargin = latitudeMargin / Math.cos(middleLatitude * Math.PI / 180);
  return [
    bbox.min_lng - longitudeMargin,
    bbox.min_lat - latitudeMargin,
    bbox.max_lng + longitudeMargin,
    bbox.max_lat + latitudeMargin,
  ].map((value) => value.toFixed(6));
}

function render(documents) {
  const candidates = documents.slice(0, PLACE_CANDIDATES);
  if (!candidates.length) return '<p class="notice">찾는 장소가 없습니다.</p>';

  return `<ul class="place-candidates">${candidates.map((place) => `
    <li data-place-candidate data-lat="${escape(place.y)}" data-lng="${escape(place.x)}">
      <strong>${escape(place.place_name)}</strong>
      <span>${escape(place.road_address_name || place.address_name)}</span>
    </li>`).join("")}
  </ul>`;
}

function escape(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}
