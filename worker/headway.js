/**
 * 배차간격 답 하나 — 시민이 노선을 물었을 때 LLM이 읽을 순수 함수 (ADR-0009).
 *
 * 이 파일이 있는 까닭은 **같은 노선을 몇 번을 물어도 답이 한곳으로 모이게** 하기 위해서다.
 * 그냥 자료만 주면 LLM은 물을 때마다 다른 수를 짓는다. 그래서 여기서는 셋을 함께 준다.
 *
 * 1. **점 추정 하나** — `배차간격`. 빌드가 미리 계산해 `headway.json`에 박아 둔 값이라
 *    호출 때 계산하지 않는다. 난수도 시각도 없다.
 * 2. **흔들림의 크기** — `밴드`와 `확신`. 모형을 달리 골랐을 때 답이 어디까지 가는지다.
 *    확신이 「낮음」인 노선은 뼈대가 아예 점 추정을 안 읽고 범위로만 말한다.
 * 3. **답변 뼈대** — `뼈대`. 수치가 박힌 문장 몇 줄. LLM은 말투를 바꿔도 이 문장의 **내용**을
 *    바꿀 수 없다. 수렴하는 것은 문장이 아니라 이 뼈대다.
 *
 * `answer`는 **총함수**다. 무엇을 넣어도 던지지 않고 같은 모양의 기록을 돌려준다 —
 * 없는 번호에는 `찾음: false`와 그때 할 말이 든 뼈대가 온다. LLM이 예외를 만나 즉흥으로
 * 답하는 자리를 남기지 않기 위해서다.
 *
 * 표기는 흔들려도 좋다. 「간선18」「간선 18」「18」「018」「간선18(기본)」이 한 기록으로 모인다
 * (ADR-0006의 번호 잇기 규칙과 같은 규칙이다). 개편 전 번호(「문흥18」)로 물으면 대체 노선들을
 * 모아 답한다 — 시민은 오늘 타는 번호로 묻기 때문이다.
 */
import table from "./headway.json" with { type: "json" };

/** 이 답은 배포마다 한 번 정해지는 값이라 한참 캐시해도 된다. 한 시간으로 둔다. */
const CACHE_SECONDS = 60 * 60;

/** 노선 표기 → (종류, 번호). 앞자리 0은 뗀다. 방면 접미는 이미 떨어진 뒤에 온다. */
const NAME_RE = /^([^\d\s(]+)?(\d+(?:-\d+)?)$/;

/** 권고 등급과 확신 등급. 답에 나오는 값은 늘 이 안에 있다. */
export const VERDICTS = Object.freeze([...table.등급목록]);
export const CONFIDENCES = Object.freeze([...table.확신목록]);

/** 개편 후 노선 이름 → 그것을 대체 노선으로 적어 둔 개편 전 번호들. 비교표를 뒤집은 것이다. */
const PREDECESSORS = (() => {
  const back = new Map();
  for (const [before, row] of Object.entries(table.개편전)) {
    for (const after of row.대체노선) {
      if (!back.has(after)) back.set(after, []);
      back.get(after).push(before);
    }
  }
  return back;
})();

/** (종류, 번호) → 개편 후 노선 이름. 종류를 안 적으면 급행 아닌 것을 고른다(ADR-0006). */
const BY_DIGITS = (() => {
  const index = new Map();
  for (const [name, row] of Object.entries(table.노선)) {
    const m = NAME_RE.exec(name);
    if (!m) continue;
    const digits = trimZeros(m[2]);
    if (!index.has(digits)) index.set(digits, []);
    index.get(digits).push({ name, kind: row.종류 });
  }
  return index;
})();

/** 「01」 → 「1」, 「70-1」 → 「70-1」. 앞자리 0만 뗀다. */
function trimZeros(digits) {
  const [head, tail] = digits.split("-");
  return String(Number(head)) + (tail === undefined ? "" : `-${tail}`);
}

/**
 * 소수 자릿수를 끊는다. 답이 바이트 단위로 같아야 하므로 자릿수를 부동소수점이 아니라 코드가 정한다.
 * 표에 실린 값은 이미 세 자리로 끊겨 있고, 여기서 나눈 값(종류 대비 배수 같은 것)만 다시 끊는다.
 */
function round(x, digits) {
  const scale = 10 ** digits;
  return Math.round(x * scale) / scale;
}

const r1 = (x) => round(x, 1);
const r2 = (x) => round(x, 2);

/**
 * 무엇이 들어오든 노선 이름 후보로 다듬는다. 던지지 않는다.
 *
 * 공백을 다 떼고, 방면 접미 「(빛그린산단출근)」를 떼고, 「번」·「번버스」 같은 꼬리말을 뗀다.
 */
export function normalise(query) {
  const raw = typeof query === "string" ? query : query == null ? "" : String(query);
  return raw
    .replace(/\s+/g, "")
    .replace(/\([^)]*\)$/, "")
    .replace(/(번버스|번|버스)$/, "");
}

/** 다듬은 표기 → 개편 후 노선 이름 또는 빈 문자열. 여기서만 표기 흔들림을 흡수한다. */
export function resolveAfter(text) {
  if (Object.hasOwn(table.노선, text)) return text;
  const m = NAME_RE.exec(text);
  if (!m) return "";
  const hits = BY_DIGITS.get(trimZeros(m[2])) ?? [];
  if (m[1]) {
    const exact = hits.find((h) => h.kind === m[1]);
    return exact ? exact.name : "";
  }
  if (hits.length === 0) return "";
  // 숫자만 적힌 것은 급행 아닌 것으로 읽는다 — 급행 03과 간선 03이 따로 있기 때문이다
  const plain = hits.filter((h) => h.kind !== "급행");
  return (plain.length > 0 ? plain : hits)[0].name;
}

/** 다듬은 표기 → 개편 전 번호 또는 빈 문자열. 「문흥18」처럼 앞말이 번호의 일부인 것들이다. */
export function resolveBefore(text) {
  if (Object.hasOwn(table.개편전, text)) return text;
  const m = NAME_RE.exec(text);
  if (!m || m[1]) return "";
  // 앞말이 다른 같은 숫자 — 「18」로 물으면 「문흥18」이 나온다. 이름 차례는 비교표 차례다
  const digits = trimZeros(m[2]);
  for (const name of Object.keys(table.개편전)) {
    const hit = NAME_RE.exec(name);
    if (hit && trimZeros(hit[2]) === digits) return name;
  }
  return "";
}

/** 망 전체 수지 — 노선을 못 찾아도 이것만은 늘 답에 붙는다. */
function networkFacts() {
  const n = table.망;
  return {
    운행횟수: [n.개편전운행횟수, n.개편후운행횟수],
    노선수: [n.개편전노선, n.개편후노선],
    중앙배차: [n.개편전중앙배차, n.개편후중앙배차],
    차량소요비: n.차량소요비,
    필요표정속도상승: n.필요표정속도상승,
    발표통행시간단축: n.발표통행시간단축,
    증차없이가능: n.발표통행시간단축 >= n.필요표정속도상승,
  };
}

/** 망 이야기 한 줄. 어느 노선을 묻든 같은 문장이라 답이 갈리지 않는다. */
function networkLine() {
  const n = table.망;
  const verdict =
    n.발표통행시간단축 >= n.필요표정속도상승
      ? "그 단축이 실제로 이뤄지면 증차 없이 채울 수 있다"
      : "그것만으로는 모자라 증차가 필요하다";
  return (
    `광주 전체로는 운행횟수가 ${n.개편전운행횟수}회에서 ${n.개편후운행횟수}회로 늘고` +
    ` 노선은 ${n.개편전노선}개에서 ${n.개편후노선}개로 는다.` +
    ` 차량을 안 늘리고 이 운행횟수를 채우려면 표정속도가 ${r1(n.필요표정속도상승)}% 올라야 한다.` +
    ` 시가 밝힌 통행시간 단축은 같은 눈금으로 ${r1(n.발표통행시간단축)}%이므로, ${verdict}.`
  );
}

/** 등급마다 붙는 한 줄. 등급이 유한하므로 이 문장도 유한하다. */
const VERDICT_LINE = Object.freeze({
  "증차 필요":
    "같은 종류 노선의 가운데보다 배차가 길고, 이 노선이 지나는 길의 버스 총량도 개편으로 평균만큼 늘지 못한다. 차량을 더 넣지 않으면 배차가 안 줄어든다.",
  "재배치 검토":
    "배차는 길지만 이 노선이 지나는 길의 버스 총량은 평균만큼 늘었다. 노선이 갈라진 몫이므로, 증차보다 여력 있는 노선에서 차량을 옮기는 쪽을 먼저 본다.",
  "현행 적정":
    "같은 종류 노선의 가운데와 비슷한 배차다. 이 노선만 놓고 증차를 말할 근거는 약하다.",
  "여력 있음":
    "같은 종류 노선의 가운데보다 배차가 촘촘하다. 다른 노선이 차량을 필요로 할 때 내줄 수 있는 쪽이다.",
});

/** 노선 하나의 답. `answer`가 부르는 곳은 여기 하나다. */
function forRoute(name, asked) {
  const row = table.노선[name];
  const before = PREDECESSORS.get(name) ?? [];
  const 점 = row.확신 === "낮음" ? null : r1(row.배차간격);
  const 밴드 = [r1(row.밴드[0]), r1(row.밴드[1])];
  const 첫줄 =
    점 === null
      ? `${name}의 개편 후 배차간격은 ${밴드[0]}~${밴드[1]}분으로 추정된다.` +
        " 어느 방식으로 나누느냐에 따라 답이 크게 갈리는 노선이라 한 값으로 말하지 않는다."
      : `${name}의 개편 후 배차간격은 ${점}분으로 추정된다(범위 ${밴드[0]}~${밴드[1]}분).`;
  return {
    물음: asked,
    노선: name,
    찾음: true,
    갈래: "개편후",
    종류: row.종류,
    배차간격: 점,
    밴드,
    확신: row.확신,
    등급: row.등급,
    대체한노선: before,
    근거: {
      운행횟수: r1(row.운행횟수),
      방향칸: row.방향칸,
      노선길이: r2(row.노선길이),
      왕복시간: r1(row.왕복시간),
      종류중앙배차: r1(row.종류중앙배차),
      종류대비: r2(row.배차간격 / row.종류중앙배차),
      회랑변화: r2(row.회랑변화),
    },
    차량: {
      지금: r2(row.차량),
      한대더: r1(row.차량더[0]),
      두대더: r1(row.차량더[1]),
      세대더: r1(row.차량더[2]),
    },
    // 같은 차량을 대기시간 총합이 가장 작아지도록 다시 나눈 것(ADR-0009 제곱근 법칙).
    // 「지금 대수」와의 차이가 곧 다른 노선에서 옮겨 와야 할 대수다
    적합: { 배차: r1(row.적합배차), 대수: r2(row.적합차량) },
    망: networkFacts(),
    뼈대: [
      첫줄,
      before.length > 0
        ? `개편 전 ${before.join(" · ")}의 자리를 이어받는다.`
        : "비교표가 대응하는 개편 전 노선을 안 적어 둔, 새로 생긴 노선이다.",
      VERDICT_LINE[row.등급],
      `차량을 하나도 안 늘리고 대기시간 총합이 가장 작아지게 다시 나누면 이 노선은` +
        ` ${r1(row.적합배차)}분에 버스 ${r2(row.적합차량)}대가 된다(지금 ${r2(row.차량)}대).`,
      `${점 === null ? "밴드 한가운데를 기준으로, 차량" : "차량"}을 한 대 더 넣으면 ${r1(row.차량더[0])}분,` +
        ` 두 대면 ${r1(row.차량더[1])}분, 세 대면 ${r1(row.차량더[2])}분이 된다.`,
      networkLine(),
      "이 값은 시가 공표한 총량(운행횟수·노선 수·증차 없음)을 노선별로 나눈 추정이지 시가 발표한 노선별 배차간격이 아니다.",
    ],
  };
}

/** 개편 전 번호로 물었을 때. 대체 노선들의 답을 모아 준다. */
function forBefore(name, asked) {
  const row = table.개편전[name];
  const parts = row.대체노선.filter((n) => Object.hasOwn(table.노선, n));
  return {
    물음: asked,
    노선: name,
    찾음: true,
    갈래: "개편전",
    종류: "",
    배차간격: row.배차간격,
    밴드: [row.배차간격, row.배차간격],
    확신: "높음",
    등급: "",
    대체노선: parts,
    근거: { 개편전배차간격: row.배차간격 },
    대체: parts.map((n) => forRoute(n, n)),
    망: networkFacts(),
    뼈대: [
      `${name}은 개편 전 노선이고 지금 배차간격은 ${row.배차간격}분이다.`,
      parts.length > 0
        ? `개편 후 대체 노선은 ${parts.join(" · ")}이다.`
        : "개편 후 대체 노선이 비교표에 적혀 있지 않다.",
      ...parts.map(
        (n) =>
          `${n}: ${
            table.노선[n].확신 === "낮음"
              ? `${r1(table.노선[n].밴드[0])}~${r1(table.노선[n].밴드[1])}분(갈림)`
              : `${r1(table.노선[n].배차간격)}분`
          } · ${table.노선[n].등급}`,
      ),
      networkLine(),
    ],
  };
}

/** 못 찾았을 때. 던지지 않고, 그때 할 말까지 뼈대에 담아 준다. */
function notFound(asked) {
  return {
    물음: asked,
    노선: null,
    찾음: false,
    갈래: "없음",
    종류: "",
    배차간격: null,
    밴드: null,
    확신: "낮음",
    등급: "",
    근거: {},
    망: networkFacts(),
    뼈대: [
      `「${asked}」에 맞는 노선을 못 찾았다. 없는 번호를 두고 배차간격을 말하지 않는다.`,
      `개편 후 노선은 ${table.망.개편후노선}개이고 종류는 직행 · 급행 · 간선 · 지선이다.` +
        " 급행03과 간선03은 다른 노선이라 숫자만으로는 갈리지 않는다.",
      networkLine(),
    ],
  };
}

/**
 * 노선 하나에 대한 답. 같은 물음이면 늘 같은 답이 나오고, 무엇을 넣어도 던지지 않는다.
 *
 * 답이 한곳으로 모이는 까닭은 이 함수가 계산을 안 하기 때문이다 — 계산은 빌드가 한 번 했고,
 * 여기서는 미리 박힌 값을 읽어 문장에 끼울 뿐이다.
 */
export function answer(query) {
  const asked = typeof query === "string" ? query : query == null ? "" : String(query);
  const text = normalise(query);
  if (text === "") return notFound(asked);
  const after = resolveAfter(text);
  if (after) return forRoute(after, asked);
  const before = resolveBefore(text);
  if (before) return forBefore(before, asked);
  return notFound(asked);
}

/** 망 전체만 물었을 때 — 노선을 안 주고 `/headway`만 부른 경우다. */
export function overview() {
  return {
    망: { ...table.망 },
    등급목록: VERDICTS,
    확신목록: CONFIDENCES,
    노선수: Object.keys(table.노선).length,
    여력노선: [...table.여력노선],
    뼈대: [
      networkLine(),
      `노선 ${Object.keys(table.노선).length}개의 배차간격 추정이 있다. 번호를 주면 그 노선의 값을 답한다.`,
      `차량을 내줄 여력이 있다고 본 노선은 ${table.여력노선.length}개다.`,
    ],
  };
}

/**
 * `/headway` — 자료 경로다. 다른 세 경로와 달리 조각(HTML)이 아니라 JSON을 준다.
 *
 * 읽는 쪽이 화면이 아니라 LLM이기 때문이다(ADR-0009 결정 4). `?route=`가 없으면 망 전체를 준다.
 */
export function respond(searchParams) {
  const route = searchParams.get("route");
  const body = route === null ? overview() : answer(route);
  return new Response(JSON.stringify(body, null, 2) + "\n", {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": `public, max-age=${CACHE_SECONDS}`,
    },
  });
}
