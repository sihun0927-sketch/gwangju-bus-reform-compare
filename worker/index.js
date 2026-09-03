/**
 * 장소 탭 Worker — 정적 자산과 같은 Worker에서 세 경로만 코드가 받는다 (ADR-0001 · 0008).
 *
 * `wrangler.jsonc`의 `run_worker_first`가 `/places` · `/compare` · `/journey/…`만 이리로 보내고,
 * 나머지(`index.html`, `route/…` 조각, `site.css`)는 정적 자산 그대로 나간다. 노선번호 탭은
 * 이 파일이 없어도 돌던 그대로 돈다.
 *
 * 데이터는 빌드가 만든 번들 JSON 하나뿐이다 — D1은 없다. 요청 때 하는 일은 조회·순위·렌더뿐이다.
 *
 * `/compare`는 `compare` 모듈이 채웠다. `/places`와 `/journey`는 아직 「준비 중」 조각이다.
 * 번들을 여기서도 import해 두는 까닭은, 배포에 실린 번들의 크기를 응답 머리로 보이기 위해서다.
 */
import bundle from "./data.json" with { type: "json" };

import { compare } from "./compare.js";

/** 아직 준비 중인 경로가 돌려주는 조각. htmx가 결과 영역에 그대로 끼운다. */
const NOT_READY = '<p class="notice">장소로 찾기는 준비 중입니다.</p>';

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
    if (pathname === "/compare") return htmlResponse(compare(searchParams));
    if (pathname === "/places" || pathname.startsWith("/journey/")) {
      return htmlResponse(NOT_READY);
    }
    return env.ASSETS.fetch(request);
  },
};
