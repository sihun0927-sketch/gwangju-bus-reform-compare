/**
 * workerd 인스펙터에 붙는 최소 CDP(Chrome DevTools Protocol) 클라이언트.
 *
 * `wrangler dev`는 Worker 아이솔레이트의 인스펙터를 `--inspector-port`에 연다. 거기에 붙으면
 * V8 CPU 프로파일러를 켜고 끌 수 있다 — 요청 하나가 **아이솔레이트 안에서** 얼마나 도는지를
 * 재는 유일한 길이고, 그것이 Cloudflare가 세는 CPU 시간이다(`wrangler dev`의 로컬 트레이스는
 * `cpu_time_ms`를 늘 0으로 준다).
 *
 * WebSocket을 손으로 짠 까닭: Node의 내장 `WebSocket`(undici)이 이 인스펙터와 악수하다 죽는다
 * (`Profiler.enable`을 보내기도 전에 close 1006). 라이브러리를 하나 더 들이는 대신, 우리가 쓰는
 * 만큼만 — 마스킹한 텍스트 프레임 보내기와, 나뉘어 오는 텍스트 프레임 잇기 — 여기 적는다.
 */
import crypto from "node:crypto";
import http from "node:http";

const FIN_TEXT = 0x81;
const FIN_BIT = 0x80;
const MASK_BIT = 0x80;
const 길이_2바이트 = 126;
const 길이_8바이트 = 127;

/** `http://127.0.0.1:9229/json`이 알려 주는 디버거 주소. 아직 안 열렸으면 `null`. */
export async function 인스펙터_주소(포트) {
  try {
    const 목록 = await (await fetch(`http://127.0.0.1:${포트}/json`)).json();
    return 목록[0]?.webSocketDebuggerUrl ?? null;
  } catch {
    return null;
  }
}

/** 인스펙터에 붙어 `부른다(method, params)` 하나만 내놓는다. */
export async function 붙는다(디버거_주소) {
  const { hostname, port, pathname } = new URL(디버거_주소);
  const 소켓 = await new Promise((풀림, 깨짐) => {
    const 요청 = http.request({
      host: hostname,
      port,
      path: pathname,
      headers: {
        Connection: "Upgrade",
        Upgrade: "websocket",
        "Sec-WebSocket-Key": crypto.randomBytes(16).toString("base64"),
        "Sec-WebSocket-Version": "13",
      },
    });
    요청.on("upgrade", (_응답, 소켓) => 풀림(소켓));
    요청.on("response", (응답) => 깨짐(new Error(`인스펙터가 업그레이드를 거절했다(${응답.statusCode})`)));
    요청.on("error", 깨짐);
    요청.end();
  });
  소켓.setNoDelay(true);

  const 기다림 = new Map();
  let 번호 = 0;

  // 프로파일 하나가 수백 KB라 프레임이 나뉘어 온다. FIN이 설 때까지 모았다가 한 번에 읽는다
  let 남은 = Buffer.alloc(0);
  let 조각 = [];
  소켓.on("data", (칸) => {
    남은 = Buffer.concat([남은, 칸]);
    for (;;) {
      if (남은.length < 2) return;
      const 끝인가 = (남은[0] & FIN_BIT) !== 0;
      const 종류 = 남은[0] & 0x0f;
      let 길이 = 남은[1] & 0x7f;
      let 앞 = 2;
      if (길이 === 길이_2바이트) {
        if (남은.length < 4) return;
        길이 = 남은.readUInt16BE(2);
        앞 = 4;
      } else if (길이 === 길이_8바이트) {
        if (남은.length < 10) return;
        길이 = Number(남은.readBigUInt64BE(2));
        앞 = 10;
      }
      if (남은.length < 앞 + 길이) return;
      const 몸 = 남은.subarray(앞, 앞 + 길이);
      남은 = 남은.subarray(앞 + 길이);
      if (종류 === 0x8) return 소켓.destroy();
      if (종류 !== 0x1 && 종류 !== 0x0) continue;
      조각.push(몸);
      if (!끝인가) continue;
      const 답 = JSON.parse(Buffer.concat(조각).toString("utf8"));
      조각 = [];
      if (답.id && 기다림.has(답.id)) {
        기다림.get(답.id)(답.result ?? {});
        기다림.delete(답.id);
      }
    }
  });

  function 보낸다(글) {
    const 몸 = Buffer.from(글, "utf8");
    let 머리;
    if (몸.length < 길이_2바이트) {
      머리 = Buffer.from([FIN_TEXT, MASK_BIT | 몸.length]);
    } else if (몸.length < 65536) {
      머리 = Buffer.alloc(4);
      머리.writeUInt16BE(몸.length, 2);
      머리[0] = FIN_TEXT;
      머리[1] = MASK_BIT | 길이_2바이트;
    } else {
      머리 = Buffer.alloc(10);
      머리.writeBigUInt64BE(BigInt(몸.length), 2);
      머리[0] = FIN_TEXT;
      머리[1] = MASK_BIT | 길이_8바이트;
    }
    const 가림쇠 = crypto.randomBytes(4);
    const 가린 = Buffer.from(몸);
    for (let i = 0; i < 가린.length; i++) 가린[i] ^= 가림쇠[i & 3];
    소켓.write(Buffer.concat([머리, 가림쇠, 가린]));
  }

  return {
    부른다: (method, params = {}) =>
      new Promise((풀림) => {
        const n = ++번호;
        기다림.set(n, 풀림);
        보낸다(JSON.stringify({ id: n, method, params }));
      }),
    끊는다: () => 소켓.destroy(),
  };
}
