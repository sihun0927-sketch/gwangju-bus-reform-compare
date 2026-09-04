/* 지도 — 조각에 실린 좌표를 Kakao JS SDK로 그린다 (CONTEXT 「경로 지도」·「노선 지도」, ADR-0001·0005).

   htmx는 지도를 못 그린다. Worker와 빌드는 좌표만 조각에 실어 보내고, 타일 위에 선과 점을 놓는
   일은 이 파일이 브라우저에서 한다.

   `window.busMap.draw(자리, 그림)`이 그 하나뿐인 그리는 함수다. **선과 점을 따로 받는다** —

       draw(자리, {
         paths:   [{ points: [{lat, lng}], color, weight, style }],
         markers: [{ lat, lng, colors: [색…], size: "small"|"normal", label }],
       })

   점을 선에 매달지 않고 따로 두는 까닭은 **점 하나가 색을 여럿 가질 수 있기 때문**이다. 개편 전
   경로와 개편 후 경로가 같은 정류장을 쓰면 점 하나를 반씩 나눠 두 색으로 칠한다(2026-09-04).
   점이 선에 매달려 있으면 그 정류장이 선 둘에 한 번씩, 곧 점 둘이 겹쳐 서서 색 하나만 보인다.

   점 크기는 둘이다 — 타고 내리는 곳은 큰 점(가운데가 흰 도넛), 지나가는 곳은 작은 점. 큰 점에는
   이름 라벨이 붙는다. 다 붙이면 정류장 이름이 지도를 덮는다.

   장소 탭이 넘기는 것은 카드마다 하나씩 고른 경로다(카드당 하나, CONTEXT). 개편 전은 점선,
   개편 후는 실선이고 색은 노선 지도와 같은 초록·파랑을 쓴다. 도보(출발 → 승차 · 환승 ·
   하차 → 도착)는 회색 점선으로 잇는다.

   노선번호 탭이 넘기는 것은 노선 변화 표 하나다 — 표 하나가 지도 하나다(§7-3 Q6). 표 조각의
   `.route-geometry` JSON을 읽어 개편 전·후 선 둘과 정류장 점을 카드의 `.route-map`에 그린다.
   점 색은 표의 상태 색 그대로이고(표와 지도가 따로 놀지 않는다), 바뀐 곳(경유 제외·경유 추가)만
   큰 점이다. 정류장이 100곳을 넘는 노선이 있어 라벨은 달지 않는다.

   Kakao JS 키가 없으면(로컬 빌드) SDK 태그가 아예 없다. 그때 장소 탭은 지도 자리를 감추고
   — 시민에게 키 이야기를 하지 않는다 — 노선번호 탭은 카드에 이미 자리가 있으므로 한 줄만 남긴다.

   `journey`와 `route`도 함께 내놓는다. 좌표 조각을 위 `그림` 모양으로 옮기기만 하는 순수 함수라,
   DOM도 SDK도 없이 검사할 수 있다(`map.test.js`). 그리는 일은 여전히 `draw` 하나가 한다. */

(function () {
  "use strict";

  var 지도_자리 = "#journey-map-canvas";
  /* 선 셋의 생김새. 색은 `site.css`의 `--map-*`에서 읽는다 — 팔레트가 두 곳에 살면 갈린다 */
  var 모습 = {
    before: { 색: "--map-before", weight: 6, style: "shortdash" },
    after: { 색: "--map-after", weight: 4, style: "solid" },
    walk: { 색: "--map-walk", weight: 3, style: "shortdot" },
  };

  /* 점 지름(px). 큰 점만 가운데가 비고, 그 흰 속은 이만큼 작다 */
  var 점_지름 = { small: 8, normal: 15 };
  var 속_여백 = 6;

  function 토큰(이름) {
    var 뿌리 = document.documentElement;
    var 값 = window.getComputedStyle ? window.getComputedStyle(뿌리).getPropertyValue(이름) : "";
    return (값 || "").trim();
  }

  function 색(갈래) {
    return 토큰(모습[갈래].색);
  }

  /** 선 하나의 생김새를 점 목록에 입힌다. */
  function 선(갈래, points) {
    return {
      points: points,
      color: 색(갈래),
      weight: 모습[갈래].weight,
      style: 모습[갈래].style,
    };
  }

  /** 점 하나. 색이 여럿이면 반씩 나눠 칠하고, 이름이 있으면 라벨이 붙는다. */
  function 점(위치, 색들, 크기, 이름) {
    return {
      lat: 위치.lat,
      lng: 위치.lng,
      colors: 색들,
      size: 크기,
      label: 이름 || "",
    };
  }

  /** 같은 자리에 선 점들을 하나로 겹친다 — 색은 이어 붙이고, 큰 점과 라벨이 이긴다. */
  function 겹친다(점들) {
    var 자리별 = [];
    var 찾기 = {};
    점들.forEach(function (하나) {
      var 열쇠 = 하나.lat.toFixed(6) + "," + 하나.lng.toFixed(6);
      var 있던것 = 찾기[열쇠];
      if (!있던것) {
        찾기[열쇠] = { lat: 하나.lat, lng: 하나.lng, colors: 하나.colors.slice(),
          size: 하나.size, label: 하나.label };
        자리별.push(찾기[열쇠]);
        return;
      }
      하나.colors.forEach(function (칠) {
        if (있던것.colors.indexOf(칠) === -1) 있던것.colors.push(칠);
      });
      if (하나.size === "normal") 있던것.size = "normal";
      if (!있던것.label) 있던것.label = 하나.label;
    });
    return 자리별;
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

  /** 색 하나면 그 색, 여럿이면 반씩 나눈 부채꼴. 「개편 전후가 함께 쓰는 곳」이 이 모양이다. */
  function 칠(색들) {
    if (!색들.length) return "transparent";
    if (색들.length === 1) return 안전한_색(색들[0]);
    var 몫 = 100 / 색들.length;
    var 칸 = 색들.map(function (하나, 차례) {
      return 안전한_색(하나) + " " + (차례 * 몫).toFixed(4) + "% " + ((차례 + 1) * 몫).toFixed(4) + "%";
    });
    return "conic-gradient(from 180deg," + 칸.join(",") + ")";
  }

  /* 색 값은 CSS 토큰에서 온 남의 글자다. 인라인 스타일에 그대로 넣으면 `;`로 선언을 끊을 수 있다 */
  function 안전한_색(값) {
    return String(값).replace(/[;"'<>]/g, "");
  }

  /** 점 하나의 DOM. 지름과 색만 인라인이고 나머지 모양은 `site.css`가 맡는다. */
  function 점_조각(하나) {
    var 지름 = 점_지름[하나.size] || 점_지름.small;
    var 감쌈 = document.createElement("div");
    감쌈.className = "map-pin";
    감쌈.style.transform = "translateX(-" + 지름 / 2 + "px)";

    var 동그라미 = document.createElement("span");
    동그라미.className = "map-dot map-dot--" + 하나.size;
    동그라미.style.width = 지름 + "px";
    동그라미.style.height = 지름 + "px";
    동그라미.style.background = 칠(하나.colors);
    if (하나.size === "normal") {
      var 속 = document.createElement("span");
      속.className = "map-dot__core";
      속.style.width = (지름 - 속_여백) + "px";
      속.style.height = (지름 - 속_여백) + "px";
      동그라미.append(속);
    }
    감쌈.append(동그라미);

    if (하나.label) {
      var 라벨 = document.createElement("span");
      라벨.className = "map-label";
      라벨.textContent = 하나.label;
      var 글자색 = 하나.colors.length === 1 ? 안전한_색(하나.colors[0]) : "";
      if (글자색) {
        라벨.style.color = 글자색;
        라벨.style.borderColor = 글자색;
      }
      감쌈.append(라벨);
    }
    return 감쌈;
  }

  /**
   * 그림 하나를 타일 위에 놓는다. 선은 선대로, 점은 점대로 얹는다.
   * 지도는 자리마다 한 번만 만들고 다시 부를 때는 얹은 것만 갈아 끼운다.
   */
  function draw(자리, 그림) {
    if (!준비됨 || !자리 || !그림) return;
    var paths = 그림.paths || [];
    var markers = 그림.markers || [];
    if (!paths.length && !markers.length) return;

    var maps = window.kakao.maps;
    var 좌표 = function (점) { return new maps.LatLng(점.lat, 점.lng); };
    var 놓인것 = 판.get(자리);
    if (!놓인것) {
      자리.replaceChildren();
      var 첫점 = paths.length ? paths[0].points[0] : markers[0];
      놓인것 = { 지도: new maps.Map(자리, { center: 좌표(첫점), level: 6 }), 얹은것: [] };
      /* 카드가 접혔다 펴지거나 창이 바뀌면 타일이 반쪽만 남는다. 가운데를 붙잡고 다시 맞춘다 */
      if (typeof ResizeObserver === "function") {
        놓인것.지켜봄 = new ResizeObserver(function () {
          try {
            var 가운데 = 놓인것.지도.getCenter();
            놓인것.지도.relayout();
            놓인것.지도.setCenter(가운데);
          } catch (e) { /* 자리가 사라지는 중이면 아무것도 안 한다 */ }
        });
        놓인것.지켜봄.observe(자리);
      }
      판.set(자리, 놓인것);
    }
    // 얹은 것을 다 걷어 낸다. 다시 그릴 때마다 판을 비운다
    놓인것.얹은것.forEach(function (것) { 것.setMap(null); });
    놓인것.얹은것 = [];

    var 테두리 = new maps.LatLngBounds();
    paths.forEach(function (선) {
      var 길 = 선.points.map(좌표);
      길.forEach(function (점) { 테두리.extend(점); });
      if (길.length < 2) return;
      놓인것.얹은것.push(new maps.Polyline({
        map: 놓인것.지도,
        path: 길,
        strokeColor: 선.color,
        strokeWeight: 선.weight,
        strokeStyle: 선.style,
        strokeOpacity: 0.9,
      }));
    });
    markers.forEach(function (하나) {
      var 자리점 = 좌표(하나);
      테두리.extend(자리점);
      놓인것.얹은것.push(new maps.CustomOverlay({
        map: 놓인것.지도,
        position: 자리점,
        content: 점_조각(하나),
        xAnchor: 0,
        yAnchor: 0.5,
        // 작은 점이 큰 점의 라벨을 가리지 않게 큰 점을 위에 둔다
        zIndex: 하나.size === "small" ? 1 : 3,
      }));
    });
    // 카드가 막 끼워진 참이면 자리의 크기를 지도가 아직 모른다
    놓인것.지도.relayout();
    놓인것.지도.setBounds(테두리, 28, 28, 28, 28);
  }


  /* ── 노선 형상 ────────────────────────────────────────────────────
     선은 정류장 직선이 아니라 차도 경로다(ADR-0009). 형상은 노선마다 파일 하나이고 조각에는
     열쇠만 실린다 — 카드 하나가 받는 양이 33KB쯤이라 번들에 싣지 않는다.
     받은 것은 그대로 들고 있는다. 같은 노선을 두 번 그릴 일이 잦다(다른 경로를 펼칠 때) */
  var 형상_기억 = {};

  /** 열쇠 하나 → 점 목록. 못 받으면 `null`이고 그 구간은 정류장 직선으로 돌아간다. */
  function 형상_받기(열쇠) {
    if (Object.prototype.hasOwnProperty.call(형상_기억, 열쇠)) {
      return Promise.resolve(형상_기억[열쇠]);
    }
    /* 파일 이름에서 `|`는 `~`다(빌드의 `SHAPE_SEP`). 나머지 글자는 인코딩이 알아서 한다 */
    return fetch("shape/" + encodeURIComponent(열쇠.replace(/\|/g, "~")) + ".json")
      .then(function (답) { return 답.ok ? 답.json() : null; })
      .then(function (점들) {
        var 값 = Array.isArray(점들) && 점들.length > 1
          ? 점들.map(function (점) { return { lat: 점[0], lng: 점[1] }; })
          : null;
        형상_기억[열쇠] = 값;
        return 값;
      })
      .catch(function () { 형상_기억[열쇠] = null; return null; });
  }

  /** 열쇠 여럿을 한꺼번에. 하나가 없어도 나머지는 그린다. */
  function 형상들_받기(열쇠들) {
    var 고른것 = 열쇠들.filter(function (열쇠) { return !!열쇠; });
    if (!고른것.length || typeof fetch !== "function") return Promise.resolve({});
    return Promise.all(고른것.map(형상_받기)).then(function (것들) {
      var 표 = {};
      고른것.forEach(function (열쇠, i) { if (것들[i]) 표[열쇠] = 것들[i]; });
      return 표;
    });
  }

  /** 두 점 사이 거리의 제곱. 어느 점이 더 가까운지만 가리면 되므로 제곱근을 안 씌운다. */
  function 거리제곱(a, b) {
    var dy = a.lat - b.lat;
    var dx = (a.lng - b.lng) * 0.82;   // 광주 위도에서 경도 1도는 위도 1도의 0.82배쯤이다
    return dy * dy + dx * dx;
  }

  /** 형상에서 점 하나에 가장 가까운 자리. */
  function 가장가까운(형상, 점) {
    var 고른 = 0;
    var 가장 = Infinity;
    형상.forEach(function (자리, i) {
      var 잼 = 거리제곱(자리, 점);
      if (잼 < 가장) { 가장 = 잼; 고른 = i; }
    });
    return 고른;
  }

  /**
   * 노선 전체 형상에서 **승차부터 하차까지**만 자른다.
   *
   * 형상은 노선 한 바퀴이고 우리가 그릴 것은 그 가운데 한 토막이다. 자르는 자리는 승차·하차
   * 정류장에 가장 가까운 점이다 — 형상이 정류장을 지나가되 정확히 밟지는 않기 때문이다.
   * 양 끝에 정류장 좌표를 덧대어 선이 점에서 시작하고 점에서 끝나게 한다.
   */
  function 잘라낸다(형상, 승차, 하차) {
    if (!형상 || 형상.length < 2 || !승차 || !하차) return null;
    var 처음 = 가장가까운(형상, 승차);
    var 끝 = 가장가까운(형상, 하차);
    if (처음 === 끝) return null;
    var 토막 = 처음 < 끝 ? 형상.slice(처음, 끝 + 1) : 형상.slice(끝, 처음 + 1).reverse();
    return [승차].concat(토막, [하차]);
  }

  /* ── 장소 탭 · 경로 지도 ─────────────────────────────────────────── */

  /**
   * 고른 경로들(카드마다 하나) → `draw`가 받는 그림.
   *
   * 선은 구간마다 하나에 도보 선을 사이사이 끼우고, 점은 구간의 **양 끝만 큰 점**이다 —
   * 거기가 타고 내리는 곳이다. 사이 정류장은 지나갈 뿐이라 작은 점에 라벨이 없다.
   * 마지막에 자리로 겹치므로, 개편 전·후가 같은 정류장을 쓰면 점 하나에 색 둘이 남는다.
   */
  function journey(경로들, 형상표) {
    var 받은것 = 형상표 || {};
    var paths = [];
    var markers = [];
    경로들.forEach(function (geometry) {
      var 노선망 = geometry.network;
      var 칠하기 = 색(노선망);
      var 열쇠들 = geometry.shapes || [];
      // 좌표가 하나도 없는 구간은 뺀다 — 점 없는 선을 얹으면 테두리 계산이 어긋난다
      var 구간들 = [];
      (geometry.legs || []).forEach(function (leg, 차례) {
        if (leg.length) 구간들.push({ 점들: leg, 형상: 받은것[열쇠들[차례]] });
      });
      if (!구간들.length) return;

      var 앞 = geometry.from;
      구간들.forEach(function (구간) {
        var leg = 구간.점들;
        paths.push(선(노선망, 잘라낸다(구간.형상, leg[0], leg[leg.length - 1]) || leg));
        paths.push(선("walk", [앞, leg[0]]));
        앞 = leg[leg.length - 1];
        leg.forEach(function (정류장, 차례) {
          var 끝 = 차례 === 0 || 차례 === leg.length - 1;
          var 역할 = 차례 === 0 ? " 승차" : " 하차";
          markers.push(점(정류장, [칠하기], 끝 ? "normal" : "small",
            끝 ? (정류장.name || "") + 역할 : ""));
        });
      });
      paths.push(선("walk", [앞, geometry.to]));
    });
    return { paths: paths, markers: 겹친다(markers) };
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
    var 좌표들 = 고른것.map(function (하나) { return 하나.geometry; });
    // 키가 없으면 SDK도 없다. 그릴 수 없는 자리는 비워 두지 않고 감춘다
    감쌈.hidden = !준비됨 || !journey(좌표들).paths.length;
    if (감쌈.hidden) return;
    /* 형상을 받는 동안 정류장 직선으로 먼저 그린다 — 지도가 빈 채로 기다리지 않는다.
       받아 오면 같은 자리에 다시 그리고, 못 받으면 먼저 그린 것이 그대로 남는다 */
    준비되면(function () { draw(자리, journey(좌표들)); });
    var 열쇠들 = 좌표들.reduce(function (모두, 하나) {
      return 모두.concat(하나.shapes || []);
    }, []);
    형상들_받기(열쇠들).then(function (형상표) {
      if (!Object.keys(형상표).length) return;
      준비되면(function () { draw(자리, journey(좌표들, 형상표)); });
    });
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

  /**
   * 표 하나의 좌표 JSON → `draw`가 받는 그림.
   *
   * 점 색은 표의 상태 색 그대로다. 크기만 갈린다 — **바뀐 곳**(경유 제외 · 경유 추가)이 큰 점이고
   * 유지는 작은 점이라, 지도를 처음 볼 때 눈이 달라진 자리에 먼저 간다. 라벨은 달지 않는다:
   * 정류장이 100곳을 넘는 노선이 있어 이름을 다 붙이면 지도가 글자로 덮인다.
   */
  function route(geometry) {
    var paths = ["before", "after"]
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
    if (!paths.length) return { paths: [], markers: [] };

    var markers = (geometry.stops || []).map(function (정류장) {
      var 상태 = 노선_점색[정류장.state] ? 정류장.state : "유지";
      return 점(정류장, [노선색(노선_점색[상태])], 상태 === "유지" ? "small" : "normal", "");
    });
    return { paths: paths, markers: 겹친다(markers) };
  }

  function 노선_그린다(조각) {
    var geometry = 노선_좌표(조각);
    var 자리 = 노선_자리(조각);
    if (!geometry || !자리) return;

    var 그림 = route(geometry);
    // 키가 없어 SDK가 안 실렸거나 이을 좌표가 없으면 카드의 빈 자리에 까닭을 한 줄 남긴다
    if (!그림.paths.length || !(window.kakao && window.kakao.maps)) {
      노선_문구(자리, 노선_지도_없음);
      return;
    }
    준비되면(function () { draw(자리, 그림); });
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

  /* 그리는 함수 하나와, 좌표 조각을 그림으로 옮기는 순수 함수 둘(CONTEXT 「map」).
     두 탭의 지도가 `draw` 하나를 함께 부른다 — `journey`·`route`는 그 입력을 만드는 자리다 */
  window.busMap = { draw: draw, journey: journey, route: route };
})();
