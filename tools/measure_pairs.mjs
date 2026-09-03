/**
 * 실측 스크립트 둘이 함께 쓰는 정류장 쌍 고르기.
 *
 * §6-3(상태 분포와 요청 시간)과 §6-4(요청당 CPU)는 **같은 쌍**을 봐야 나란히 읽힌다. 한쪽만
 * 다른 표본이면 「CPU가 큰 쌍이 원래 경로가 없는 쌍이었나」를 가릴 수가 없다. 따로 적으면
 * 씨앗 하나가 갈려도 조용히 갈리므로 여기 한 곳에 둔다.
 *
 * 씨앗을 고정한 난수라 다시 돌리면 같은 쌍이 나온다 — 두 §의 수치가 재현되는 근거다.
 */
import { NETWORKS } from "../worker/network.js";

/** 서로 이만큼(m)은 떨어진 쌍만 본다. 붙어 있는 쌍은 「걸어갈 수 있는 거리」라 경로를 안 찾는다. */
export const MIN_APART_M = 3000;

/** 난수의 씨앗. 이 값이 바뀌면 §6-3·§6-4의 표본이 통째로 바뀐다. */
export const 씨앗_처음 = 20260904;

/** 씨앗을 고정한 난수. 다시 돌리면 같은 쌍이 나온다. */
function 난수(씨앗) {
  let 값 = 씨앗;
  return () => {
    값 = (값 * 1103515245 + 12345) % 2147483648;
    return 값 / 2147483648;
  };
}

const 대략_미터 = (a, b) =>
  Math.hypot((a.lat - b.lat) * 111000, (a.lng - b.lng) * 91000);

/** 개편 전 노선망이 서는 정류장에서 `MIN_APART_M` 넘게 떨어진 쌍을 `쌍_수`개. */
export function 정류장_쌍(쌍_수) {
  const [before] = NETWORKS;
  const 다음 = 난수(씨앗_처음);
  const 쌍 = [];
  while (쌍.length < 쌍_수) {
    const a = before.served[Math.floor(다음() * before.served.length)];
    const b = before.served[Math.floor(다음() * before.served.length)];
    if (a && b && a.id !== b.id && 대략_미터(a, b) >= MIN_APART_M) 쌍.push([a, b]);
  }
  return 쌍;
}
