/* 지도 — 조각에 실린 좌표를 Kakao JS SDK로 그린다 (CONTEXT 「경로 지도」·「노선 지도」, ADR-0001·0005).

   htmx는 지도를 못 그린다. Worker와 빌드는 좌표만 조각에 실어 보내고, 타일 위에 선과 점을 놓는
   일은 이 파일이 브라우저에서 한다.

   `window.busMap.draw(자리, 선들)`이 그 하나뿐인 그리는 함수다. **좌표 배열만 받는다** — 경로도
   노선도 모르므로 두 탭이 같은 함수를 부르고 입력만 다르게 준다.

       draw(자리, [{ points: [{lat, lng}], dots: [{lat, lng, name}], color, weight, style }])

   장소 탭이 넘기는 것은 카드마다 하나씩 고른 경로다(카드당 하나, CONTEXT). 개편 전은 점선,
   개편 후는 실선이고 색은 노선 지도와 같은 초록·파랑을 쓴다. 도보(출발 → 승차 · 환승 ·
   하차 → 도착)는 회색 점선으로 잇는다.

   노선번호 탭이 넘기는 것은 노선 변화 표 하나다 — 표 하나가 지도 하나다(§7-3 Q6). 표 조각의
   `.route-geometry` JSON을 읽어 개편 전·후 선 둘과 정류장 점을 카드의 `.route-map`에 그린다.
   카드에 지도는 하나뿐이라 표가 바뀌면 같은 자리에 다시 그린다.

   Kakao JS 키가 없으면(로컬 빌드) SDK 태그가 아예 없다. 그때 장소 탭은 지도 자리를 감추고
   — 시민에게 키 이야기를 하지 않는다 — 노선번호 탭은 카드에 이미 자리가 있으므로 한 줄만 남긴다. */

(function () {
  "use strict";

  var 지도_자리 = "#journey-map-canvas";
  /* 선 셋의 생김새. 색은 `site.css`의 `--map-*`에서 읽는다 — 팔레트가 두 곳에 살면 갈린다 */
  var 모습 = {
    before: { 색: "--map-before", weight: 6, style: "shortdash" },
    after: { 색: "--map-after", weight: 4, style: "solid" },
    walk: { 색: "--map-walk", weight: 3, style: "shortdot" },
  };

  function 토큰(이름) {
    return getComputedStyle(document.documentElement).getPropertyValue(이름).trim();
  }

  function 색(갈래) {
    return 토큰(모습[갈래].색);
  }

  /** 선 하나의 생김새를 점 목록에 입힌다. */
  function 선(갈래, points, dots) {
    return {
      points: points,
      dots: dots,
      color: 색(갈래),
      weight: 모습[갈래].weight,
      style: 모습[갈래].style,
    };
  }

  var 준비됨 = false;
  var 기다리는 = [];
  /* 자리마다 지도 하나. 두 탭이 한 껍데기 안에 있으므로 지도를 변수 하나에 묶어 두면 다른 탭이
     그릴 때 엉뚱한 자리에 얹힌다. 자리째 갈린 지도는 WeakMap이 알아서 놓는다 */
  var 판 = new WeakMap();
  /** 노선망마다 지도에 올린 경로 하나. 카드당 하나만 올라간다(CONTEXT 「경로 지도」). */
  var 선택 = { before: null, after: null };

  function 준비되면(할일) {
    if (준비됨) return 할일();
    기다리는.push(할일);
  }

  if (window.kakao && window.kakao.maps && window.kakao.maps.load) {
    window.kakao.maps.load(function () {
      준비됨 = true;
      기다리는.splice(0).forEach(function (할일) { 할일(); });
    });
  }

  /**
   * 좌표 배열들을 타일 위에 놓는다. 선 하나에 점 목록 하나이고, 점은 있으면 그린다.
   * 지도는 자리마다 한 번만 만들고 다시 부를 때는 얹은 것만 갈아 끼운다.
   */
  function draw(자리, 선들) {
    if (!준비됨 || !자리) return;
    var maps = window.kakao.maps;
    var 좌표 = function (점) { return new maps.LatLng(점.lat,점.lng); };

    var 놓인것 = 판.get(자리);
    if (!놓인것) {
      자리.replaceChildren();
      놓인것 = {
        지도: new maps.Map(자리, { center: 좌표(선들[0].points[0]), level: 6 }),
        얹은것: [],
      };
      판.set(자리, 놓인것);
    }
    // 얹은 것을 다 걷어 낸다. 다시 그릴 때마다 판을 비운다
    놓인것.얹은것.forEach(function (것) { 것.setMap(null); });
    놓인것.얹은것 = [];

    var 테두리 = new maps.LatLngBounds();
    선들.forEach(function (선) {
      var 길 = 선.points.map(좌표);
      길.forEach(function (점) { 테두리.extend(점); });
      if (길.length > 1) {
        놓인것.얹은것.push(new maps.Polyline({
          map: 놓인것.지도,
          path: 길,
          strokeColor: 선.color,
          strokeWeight: 선.weight,
          strokeStyle: 선.style,
          strokeOpacity: 0.9,
        }));
      }
      (선.dots || []).forEach(function (점) {
        놓인것.얹은것.push(new maps.CustomOverlay({
          map: 놓인것.지도,
          position: 좌표(점),
          content: '<i class="map-dot" style="background:' + 선.color + '" title="'
            + String(점.name || "").replace(/"/g, "&quot;") + '"></i>',
        }));
      });
    });
    // 카드가 막 끼워진 참이면 자리의 크기를 지도가 아직 모른다
    놓인것.지도.relayout();
    놓인것.지도.setBounds(테두리, 24, 24, 24, 24);
  }

  /* ── 장소 탭 · 경로 지도 ─────────────────────────────────────────── */

  /** 경로 하나(조각의 좌표 JSON) → `draw`가 받는 선 목록. 버스 구간과 도보를 가른다. */
  function 선으로(geometry) {
    var 노선망 = geometry.network;
    // 좌표가 하나도 없는 구간은 뺀다 — 점 없는 선을 얹으면 테두리 계산이 어긋난다
    var 구간들 = geometry.legs.filter(function (leg) { return leg.length; });
    var 선들 = 구간들.map(function (leg) { return 선(노선망, leg, leg); });

    // 도보는 출발 지점 → 첫 승차, 구간 사이(환승), 마지막 하차 → 도착 지점이다
    var 앞 = geometry.from;
    구간들.forEach(function (leg) {
      선들.push(선("walk", [앞, leg[0]]));
      앞 = leg[leg.length - 1];
    });
    선들.push(선("walk", [앞, geometry.to]));
    return 선들;
  }

  /** 카드 하나에서 경로 키와 좌표를 읽는다. 카드가 자기 것만 내놓도록 바로 밑 자식만 본다. */
  function 읽는다(카드) {
    var 좌표글 = 카드.querySelector(":scope > script.geometry");
    if (!좌표글) return null;
    try {
      return { key: 카드.dataset.journey, geometry: JSON.parse(좌표글.textContent) };
    } catch (e) {
      return null;
    }
  }

  /** 고른 경로가 화면에서 사라졌으면(카드가 갈렸으면) 그 노선망의 기본 경로로 되돌린다. */
  function 되짚는다() {
    ["before", "after"].forEach(function (갈래) {
      var 고른 = 선택[갈래];
      if (고른 && document.querySelector('[data-journey="' + 고른.key + '"]')) return;
      var 기본 = document.querySelector(
        'article.journey-card[data-network="' + 갈래 + '"]:not(.alternative)',
      );
      선택[갈래] = 기본 ? 읽는다(기본) : null;
    });
  }

  /** 지금 지도에 올라 있는 경로의 단추에 표시를 남긴다 — 어느 것을 보고 있는지 알 수 있게. */
  function 표시한다() {
    document.querySelectorAll(".show-on-map").forEach(function (단추) {
      var 카드 = 단추.closest("article.journey-card");
      var 고른 = 선택[단추.dataset.network];
      var 올라감 = !!(카드 && 고른 && 카드.dataset.journey === 고른.key);
      단추.classList.toggle("on", 올라감);
      단추.setAttribute("aria-pressed", 올라감 ? "true" : "false");
      // 색만으로 알리면 색을 못 가리는 눈에는 아무 표시가 없는 것과 같다 — 글자도 바꾼다
      단추.textContent = 올라감 ? "지도에 표시 중" : "지도에 표시";
    });
  }

  function 그린다() {
    var 자리 = document.querySelector(지도_자리);
    if (!자리) return;
    var 감쌈 = 자리.closest(".journey-map");
    var 고른것 = [선택.before, 선택.after].filter(Boolean);
    var 선들 = 고른것.reduce(function (모두, 하나) {
      return 모두.concat(선으로(하나.geometry));
    }, []);
    // 키가 없으면 SDK도 없다. 그릴 수 없는 자리는 비워 두지 않고 감춘다
    감쌈.hidden = !준비됨 || !선들.length;
    if (감쌈.hidden) return;
    준비되면(function () { draw(자리, 선들); });
  }

  function 다시() {
    되짚는다();
    표시한다();
    그린다();
  }

  /* ── 노선번호 탭 · 노선 지도 ──────────────────────────────────────── */

  /* 노선 지도의 색은 표의 색이다. `site.css` 토큰이 정본이고 여기 적힌 값은 스타일시트를 못
     읽었을 때의 대비책일 뿐이라, 색을 바꿀 일이 있으면 CSS만 고치면 된다 — 표와 지도가 따로 놀지 않는다 */
  var 노선_모습 = {
    before: { 색: "--before-line", 대비책: "#0e6b5c", weight: 8 },
    after: { 색: "--after-line", 대비책: "#1d4ed8", weight: 4 },
  };
  var 노선_점색 = {
    "유지": { 색: "--kept-dot", 대비책: "#5a6b67" },
    "경유 제외": { 색: "--dropped-dot", 대비책: "#b2402f" },
    "경유 추가": { 색: "--added-dot", 대비책: "#1d4ed8" },
  };
  var 노선_지도_없음 = "지도를 불러오지 못했습니다";

  function 노선색(꼴) {
    return 토큰(꼴.색) || 꼴.대비책;
  }

  /** 표 조각에 실린 좌표 JSON. 조각 자체일 수도 있고 조각 안에 있을 수도 있다. */
  function 노선_좌표(조각) {
    var 실린것 = 조각.matches && 조각.matches(".route-geometry")
      ? 조각
      : 조각.querySelector && 조각.querySelector(".route-geometry");
    if (!실린것) return null;
    try {
      return JSON.parse(실린것.textContent);
    } catch (e) {
      return null;
    }
  }

  /** 지도 자리는 카드에 있다 — 표만 바뀌었으면 위에, 카드째 바뀌었으면 안에 있다. */
  function 노선_자리(조각) {
    var 카드 = (조각.closest && 조각.closest(".route-card"))
      || (조각.querySelector && 조각.querySelector(".route-card"));
    return 카드 ? 카드.querySelector(".route-map") : null;
  }

  /** 지도 대신 한 줄만 남긴다. 지도가 있었다면 그 DOM째 버리므로 기억도 함께 버린다 —
      안 그러면 다음에 그릴 때 이미 있다고 여겨 빈 자리 위에 선을 얹고 카드가 이 문구에 갇힌다. */
  function 노선_문구(자리, 글) {
    var 줄 = document.createElement("p");
    줄.className = "map-note";
    줄.textContent = 글;
    판.delete(자리);
    자리.replaceChildren(줄);
  }

  /** `[[lat, lng]]` → `draw`가 받는 점 목록. 좌표 JSON은 표가 실어 보낸 그대로다. */
  function 노선_점들(좌표들) {
    return (좌표들 || []).map(function (점) { return { lat: 점[0], lng: 점[1] }; });
  }

  /** 표 하나의 좌표 JSON → `draw`가 받는 선 목록. 선 둘이 먼저, 상태별 점 묶음이 그 위에 온다. */
  function 노선_선으로(geometry) {
    var 선들 = ["before", "after"]
      .map(function (갈래) {
        var 꼴 = 노선_모습[갈래];
        return {
          points: 노선_점들(geometry[갈래]),
          color: 노선색(꼴),
          weight: 꼴.weight,
          style: "solid",
        };
      })
      // 한쪽 선이 비어 있으면(그 노선의 정류장을 하나도 못 이었으면) 그 선은 긋지 않는다
      .filter(function (선) { return 선.points.length; });
    if (!선들.length) return [];

    // 점은 상태마다 색이 다르다. `draw`는 선 하나에 색 하나이므로 상태별로 묶어 넘긴다
    var 묶음 = {};
    (geometry.stops || []).forEach(function (정류장) {
      var 상태 = 노선_점색[정류장.state] ? 정류장.state : "유지";
      (묶음[상태] = 묶음[상태] || []).push({
        lat: 정류장.lat,
        lng: 정류장.lng,
        name: 정류장.name + " · " + 정류장.state,
      });
    });
    Object.keys(묶음).forEach(function (상태) {
      선들.push({ points: [], dots: 묶음[상태], color: 노선색(노선_점색[상태]) });
    });
    return 선들;
  }

  function 노선_그린다(조각) {
    var geometry = 노선_좌표(조각);
    var 자리 = 노선_자리(조각);
    if (!geometry || !자리) return;

    var 선들 = 노선_선으로(geometry);
    // 키가 없어 SDK가 안 실렸거나 이을 좌표가 없으면 카드의 빈 자리에 까닭을 한 줄 남긴다
    if (!선들.length || !(window.kakao && window.kakao.maps)) {
      노선_문구(자리, 노선_지도_없음);
      return;
    }
    준비되면(function () { draw(자리, 선들); });
  }

  document.addEventListener("htmx:afterSwap", function (event) {
    다시();
    노선_그린다(event.target);
  });

  document.addEventListener("click", function (event) {
    var 단추 = event.target.closest(".show-on-map");
    if (!단추) return;
    var 고른 = 읽는다(단추.closest("article.journey-card"));
    if (!고른) return;
    선택[단추.dataset.network] = 고른;
    표시한다();
    그린다();
  });

  // 그리는 함수 하나만 내놓는다(CONTEXT 「map」). 두 탭의 지도가 이것을 함께 부른다
  window.busMap = { draw: draw };
})();
