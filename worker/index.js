/**
 * 장소 탭 Worker — 정적 자산과 같은 Worker에서 세 경로만 코드가 받는다 (ADR-0001 · 0008).
 *
 * `wrangler.jsonc`의 `run_worker_first`가 `/places` · `/compare` · `/journey/…`만 이리로 보내고,
 * 나머지(`index.html`, `route/…` 조각, `site.css`)는 정적 자산 그대로 나간다. 노선번호 탭은
 * 이 파일이 없어도 돌던 그대로 돈다.
 *
 * 데이터는 빌드가 만든 번들 JSON 하나뿐이다 — D1은 없다. 요청 때 하는 일은 조회·순위·렌더뿐이다.
 *
 * 세 경로 모두 조각을 돌려준다 — `/places`는 Kakao 자동완성 후보, `/compare`는 카드 한 쌍,
 * `/journey/{id}`는 다른 경로 카드 하나다.
 * 번들을 여기서도 import해 두는 까닭은, 배포에 실린 번들의 크기를 응답 머리로 보이기 위해서다.
 */
import bundle from "./data.json" with { type: "json" };
import { places } from "./places.js";

import { compare } from "./compare.js";
import { journey } from "./journey.js";

/** `/journey/` 뒤에 오는 경로 키가 시작하는 자리. */
const JOURNEY_PREFIX = "/journey/";

/** 번들이 실제로 배포에 실렸는지 한 줄로 보이게 한다 — 코드와 데이터가 따로 낡는 것을 잡는 표식. */
const BUNDLE_HEALTH =
  `stops=${Object.keys(bundle.stops).length}` +
  ` routes=${Object.keys(bundle.routes).length}`;

/** 조각 하나를 응답으로 감싼다. 조각(HTML 토막) 자체를 만드는 것은 `render`다(CONTEXT 「조각」). */
function htmlResponse(html, status = 200) {
  return new Response(html, {
    status,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "x-bundle": BUNDLE_HEALTH,
    },
  });
}

export default {
  async fetch(request, env) {
    const { pathname, searchParams } = new URL(request.url);
    if (pathname === "/places") return htmlResponse(await places(request, env, bundle));
    if (pathname === "/compare") return htmlResponse(compare(searchParams));
    if (pathname.startsWith(JOURNEY_PREFIX)) {
      // 키가 번들과 안 맞으면 `journey`가 404와 한 줄 문구를 준다. htmx는 200이 아닌 응답을
      // 끼우지 않으므로 그 문구는 **주소를 그대로 연 사람**이 본다 — 키는 남에게 보낼 수 있는 링크다
      const { html, status } = journey(pathname.slice(JOURNEY_PREFIX.length), searchParams);
      return htmlResponse(html, status);
    }
    return env.ASSETS.fetch(request);
  },
};
