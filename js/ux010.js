/**
 * UX 010 — categories home + 3-tier map markers + bottom sheet
 * Depends on globals from index.html: SPOTS, VENUES, kakaoMap, getVenue, getSpot, ...
 */
(function (global) {
  const MAP_LEVEL_L1 = 10; // level >= 10 → region bubbles
  const MAP_LEVEL_L3 = 6; // level <= 6 → neighborhood (selected emphasis)

  let CATEGORY_GROUPS = [];
  let CATEGORIES = [];
  let homeMode = "home"; // home | group
  let selectedGroupSlug = null;
  let selectedCategoryId = null; // null = all in group
  let groupSortMode = "region"; // region | thrill
  let flatCategoryMode = false;
  let mapBoundsFilter = null; // {swLat,swLng,neLat,neLng} or null
  let mapClusterOverlays = [];
  let mapPinOverlays = [];
  let mapMiniClusters = [];

  function spotLabel(s) {
    if (!s) return "액티비티";
    return s.categoryName || s.tl || s.type || "액티비티";
  }

  function spotIcon(s) {
    if (!s) return "📍";
    return s.categoryIcon || s.em || "📍";
  }

  function venueMaxGrade(v) {
    const members = typeof getVenueMemberSpots === "function" ? getVenueMemberSpots(v) : [];
    let max = 0;
    members.forEach((s) => {
      const g = Number(s.thrillGrade);
      if (Number.isFinite(g) && g > max) max = g;
    });
    if (!max && v.primarySpotId) {
      const s = getSpot(v.primarySpotId);
      max = Number(s && s.thrillGrade) || 0;
    }
    return max;
  }

  function venueGroupSlug(v) {
    const members = typeof getVenueMemberSpots === "function" ? getVenueMemberSpots(v) : [];
    const s = members[0] || (v.primarySpotId ? getSpot(v.primarySpotId) : null);
    return (s && s.groupSlug) || v.groupSlug || null;
  }

  function venueCategoryId(v) {
    const members = typeof getVenueMemberSpots === "function" ? getVenueMemberSpots(v) : [];
    const s = members[0] || (v.primarySpotId ? getSpot(v.primarySpotId) : null);
    return s && s.categoryId != null ? s.categoryId : null;
  }

  function isSpotPublishable(s) {
    if (!s) return false;
    return !!(s.coordVerified || s.legacy);
  }

  function venueIsPublishable(v) {
    const members = typeof getVenueMemberSpots === "function" ? getVenueMemberSpots(v) : [];
    if (members.length) return members.some((s) => isSpotPublishable(s));
    const s = v.primarySpotId ? getSpot(v.primarySpotId) : null;
    return isSpotPublishable(s);
  }

  function venueMatchesCategoryFilters(v) {
    if (!venueIsPublishable(v)) return false;
    if (selectedGroupSlug) {
      if (venueGroupSlug(v) !== selectedGroupSlug) return false;
    }
    if (selectedCategoryId != null) {
      const members = typeof getVenueMemberSpots === "function" ? getVenueMemberSpots(v) : [];
      if (!members.length) {
        return venueCategoryId(v) === selectedCategoryId;
      }
      return members.some(
        (s) => s.categoryId === selectedCategoryId && isSpotPublishable(s)
      );
    }
    return true;
  }

  function venueInMapBounds(v) {
    if (!mapBoundsFilter) return true;
    const c = getVenueMapCoords(v);
    if (!c) return false;
    const b = mapBoundsFilter;
    return c.lat >= b.swLat && c.lat <= b.neLat && c.lng >= b.swLng && c.lng <= b.neLng;
  }

  async function loadCategoryGroups() {
    try {
      const [gRes, cRes] = await Promise.all([
        fetch("/api/categories/groups?withSpotsOnly=true"),
        fetch("/api/categories?withSpotsOnly=true"),
      ]);
      CATEGORY_GROUPS = gRes.ok ? await gRes.json() : [];
      CATEGORIES = cRes.ok ? await cRes.json() : [];
      CATEGORIES = (CATEGORIES || [])
        .filter((c) => c.spotCount > 0)
        .slice()
        .sort((a, b) => b.spotCount - a.spotCount || a.sortOrder - b.sortOrder);
    } catch (_) {
      CATEGORY_GROUPS = [];
      CATEGORIES = [];
    }
    return CATEGORY_GROUPS;
  }

  /** 홈 아이콘 그리드용 짧은 표기 — 생소한 영문/은어는 쉬운 말로 */
  function shortCatName(name) {
    const n = String(name || "");
    const aliases = {
      실내스카이다이빙: "실내스카이",
      "자연 암벽등반": "암벽등반",
      "서바이벌 게임": "서바이벌",
      "MTB 다운힐": "산악자전거",
      MTB: "산악자전거",
      산악자전거: "산악자전거",
      SUV오프로드: "SUV체험",
      SUV체험: "SUV체험",
      "급류 카약": "급류카약",
      급류카약: "급류카약",
      카약: "급류카약",
      알파인코스터: "롤러코스터",
      롤러코스터: "롤러코스터",
      스카이바이크: "공중자전거",
      공중자전거: "공중자전거",
      캐녀닝: "계곡탐험",
      계곡탐험: "계곡탐험",
      하이로프: "숲속모험",
      숲속모험: "숲속모험",
      씨워킹: "바닷속걷기",
      바닷속걷기: "바닷속걷기",
      케이브보트: "동굴보트",
      동굴보트: "동굴보트",
      동물라이딩: "승마",
      동물타기: "승마",
      승마: "승마",
      수륙양용차: "수륙양용",
    };
    if (aliases[n]) return aliases[n];
    if (n.length <= 6) return n;
    return n.length > 7 ? n.slice(0, 6) + "…" : n;
  }

  /** slug 기준 아이콘 — DB가 구버전 시드여도 홈은 즉시 통일 */
  const CAT_ICON_BY_SLUG = {
    paragliding: "🪂",
    bungee: "🔻",
    zipline: "➰",
    "indoor-skydiving": "💨",
    balloon: "🎈",
    "big-swing": "🌀",
    "light-aircraft": "✈️",
    "hang-glider": "🪁",
    rafting: "🛶",
    "whitewater-kayak": "🛶",
    jetboat: "🚤",
    parasailing: "🪂",
    seawalk: "🤿",
    "cave-boat": "🚤",
    luge: "🛷",
    "alpine-coaster": "🎢",
    skybike: "🚲",
    monorail: "🚋",
    canyoning: "🏔️",
    "rock-climbing": "🧗",
    "high-ropes": "🪜",
    "survival-game": "🪖",
    shooting: "🎯",
    "animal-riding": "🐴",
    skywalk: "🌉",
    slide: "🛝",
    "cave-explore": "🦇",
    kart: "🏎️",
    atv: "🏍️",
    offroad: "🚙",
    "suv-offroad": "🚙",
    "mtb-downhill": "🚵",
    amphibious: "🚢",
  };

  function catIcon(c) {
    if (!c) return "📍";
    return CAT_ICON_BY_SLUG[c.slug] || c.icon || "📍";
  }

  function isSeasonOpenLocal(spot, month) {
    if (typeof isSeasonOpen === "function") return isSeasonOpen(spot, month);
    return true;
  }

  function getSeasonNowSpots(limit) {
    const month = new Date().getMonth() + 1;
    const list = (SPOTS || [])
      .filter((s) => isSpotPublishable(s))
      .filter((s) => isSeasonOpenLocal(s, month))
      .sort((a, b) => (Number(b.thrillGrade) || 0) - (Number(a.thrillGrade) || 0));
    return list.slice(0, limit || 10);
  }

  function thrillBadge(grade) {
    if (typeof thrillGradeBadgeHtml === "function") return thrillGradeBadgeHtml(grade);
    const n = Number(grade);
    if (!Number.isFinite(n) || n < 1) return "";
    return `<span class="mc-thrill-grade">${"⚡".repeat(n)}</span>`;
  }

  function renderHomeHome() {
    homeMode = "home";
    flatCategoryMode = false;
    selectedGroupSlug = null;
    selectedCategoryId = null;
    const grid = document.getElementById("homeGroupGrid");
    const season = document.getElementById("homeSeasonRow");
    const listWrap = document.getElementById("homeGroupList");
    const sortSec = document.getElementById("homeSortSec");
    if (listWrap) listWrap.classList.add("is-hidden");
    if (sortSec) sortSec.classList.add("is-hidden");
    if (grid) {
      grid.classList.remove("is-hidden");
      grid.classList.add("home-cat-grid");
      if (!(CATEGORIES || []).length) {
        grid.classList.add("is-loading");
        grid.innerHTML = [0, 1, 2, 3, 4, 5, 6, 7]
          .map(() => `<button type="button" class="home-cat-btn" tabindex="-1" aria-hidden="true"><span class="home-cat-ico">·</span><span class="home-cat-name">·</span></button>`)
          .join("");
      } else {
        grid.classList.remove("is-loading");
        grid.innerHTML = (CATEGORIES || [])
          .map(
            (c) => `
        <button type="button" class="home-cat-btn" data-cid="${c.id}" onclick="Ux010.openCategory(${c.id})">
          <span class="home-cat-ico" aria-hidden="true">${catIcon(c)}</span>
          <span class="home-cat-name">${shortCatName(c.name)}</span>
        </button>`
          )
          .join("");
      }
    }
    if (season) {
      season.classList.remove("is-hidden");
      const spots = getSeasonNowSpots(10);
      const track = document.getElementById("homeSeasonTrack");
      if (track) {
        if (!(SPOTS || []).length) {
          track.classList.add("is-loading");
          track.innerHTML = [0, 1, 2]
            .map(() => `<button type="button" class="home-season-card" tabindex="-1" aria-hidden="true">.</button>`)
            .join("");
        } else {
          track.classList.remove("is-loading");
          track.innerHTML = spots.length
            ? spots
                .map((s) => {
                  return `<button type="button" class="home-season-card" onclick="Ux010.openSpotFromHome(${s.id})">
              <span class="hsc-ico">${spotIcon(s)}</span>
              <span class="hsc-cat">${spotLabel(s)}</span>
              <span class="hsc-name">${s.name}</span>
              ${thrillBadge(s.thrillGrade)}
              <span class="hsc-season">지금 가능</span>
            </button>`;
                })
                .join("")
            : `<p class="home-season-empty">현재 시즌 스팟이 없어요</p>`;
        }
      }
    }
    const quiz = document.getElementById("homeQuizBanner");
    if (quiz) quiz.classList.remove("is-hidden");
    const nearby = document.getElementById("homeNearbyBtn");
    if (nearby) nearby.classList.remove("is-hidden");
    const legacyCards = document.getElementById("cardList");
    if (legacyCards) legacyCards.classList.add("is-hidden");
    const rh = document.querySelector(".m-rh");
    if (rh) rh.classList.add("is-hidden");
  }

  function showListShell(titleText) {
    const grid = document.getElementById("homeGroupGrid");
    const season = document.getElementById("homeSeasonRow");
    const quiz = document.getElementById("homeQuizBanner");
    const nearby = document.getElementById("homeNearbyBtn");
    const listWrap = document.getElementById("homeGroupList");
    const sortSec = document.getElementById("homeSortSec");
    if (grid) grid.classList.add("is-hidden");
    if (season) season.classList.add("is-hidden");
    if (quiz) quiz.classList.add("is-hidden");
    if (nearby) nearby.classList.add("is-hidden");
    if (listWrap) listWrap.classList.remove("is-hidden");
    if (sortSec) sortSec.classList.remove("is-hidden");
    const title = document.getElementById("homeGroupTitle");
    if (title) title.textContent = titleText || "액티비티";
  }

  /** 배달의민족식: 소분류 아이콘 탭 → 해당 카테고리 리스트 */
  function openCategory(categoryId) {
    homeMode = "group";
    flatCategoryMode = true;
    const cat = (CATEGORIES || []).find((c) => Number(c.id) === Number(categoryId));
    if (!cat) return;
    selectedCategoryId = Number(categoryId);
    // 리스트는 카테고리만 필터 (대분류 하늘/땅 노출 안 함). 지도 전환 시에만 group 사용.
    selectedGroupSlug = null;
    showListShell(shortCatName(cat.name));

    const chips = document.getElementById("homeSubChips");
    if (chips) {
      chips.innerHTML = "";
      chips.classList.add("is-hidden");
    }
    // stash for map
    openCategory._groupSlug = cat.groupSlug || null;
    renderGroupList();
  }

  function openGroupMap() {
    if (flatCategoryMode && openCategory._groupSlug) {
      selectedGroupSlug = openCategory._groupSlug;
    }
    if (typeof goMap === "function") goMap({ keepFilters: true });
  }

  function openGroup(groupSlug) {
    homeMode = "group";
    flatCategoryMode = false;
    selectedGroupSlug = groupSlug;
    selectedCategoryId = null;
    const g = (CATEGORY_GROUPS || []).find((x) => x.groupSlug === groupSlug);
    showListShell((g && g.groupName) || groupSlug);

    const chips = document.getElementById("homeSubChips");
    if (chips && g) {
      chips.classList.remove("is-hidden");
      const cats = (g.categories || [])
        .filter((c) => c.spotCount > 0)
        .slice()
        .sort((a, b) => b.spotCount - a.spotCount || a.sortOrder - b.sortOrder);
      chips.innerHTML =
        `<button type="button" class="sub-chip active" data-cid="" onclick="Ux010.setCategoryFilter(null, this)">전체</button>` +
        cats
          .map(
            (c) =>
              `<button type="button" class="sub-chip" data-cid="${c.id}" onclick="Ux010.setCategoryFilter(${c.id}, this)">${c.icon || ""} ${c.name} <em>${c.spotCount}</em></button>`
          )
          .join("");
    }
    renderGroupList();
  }

  function setCategoryFilter(cid, btn) {
    selectedCategoryId = cid;
    document.querySelectorAll("#homeSubChips .sub-chip").forEach((el) => el.classList.remove("active"));
    if (btn) btn.classList.add("active");
    renderGroupList();
  }

  function setGroupSort(mode, btn) {
    groupSortMode = mode;
    document.querySelectorAll("#homeSortSec .mfb").forEach((el) => el.classList.remove("active"));
    if (btn) btn.classList.add("active");
    renderGroupList();
  }

  function renderGroupList() {
    let list = (VENUES || []).filter((v) => venueMatchesCategoryFilters(v));
    if (typeof seasonNowOnly !== "undefined" && seasonNowOnly && typeof venueHasInSeasonSpot === "function") {
      list = list.filter((v) => venueHasInSeasonSpot(v));
    }
    const q = typeof getSpotSearchQuery === "function" ? getSpotSearchQuery() : "";
    if (q && typeof matchVenueSearch === "function") {
      list = list.filter((v) => matchVenueSearch(v, q));
    }
    if (groupSortMode === "thrill") {
      list = list.slice().sort((a, b) => venueMaxGrade(b) - venueMaxGrade(a) || String(a.name).localeCompare(String(b.name), "ko"));
    } else {
      list = list.slice().sort((a, b) => {
        const ra = (a.region || (a.address || "").split(" ")[0] || "").toString();
        const rb = (b.region || (b.address || "").split(" ")[0] || "").toString();
        return ra.localeCompare(rb, "ko") || String(a.name || "").localeCompare(String(b.name || ""), "ko");
      });
    }
    const host = document.getElementById("homeGroupCards");
    const countEl = document.getElementById("homeGroupCount");
    if (countEl) countEl.textContent = String(list.length);
    if (host) {
      if (!list.length) {
        host.innerHTML = `<div class="empty"><div class="empty-icon">🔍</div><p class="empty-t">조건에 맞는 장소가 없습니다</p></div>`;
      } else if (typeof renderVenueCardHtml === "function") {
        host.innerHTML = list.map((v) => renderVenueCardHtml(v)).join("");
      }
    }
  }

  function openSpotFromHome(spotId) {
    const spot = getSpot(spotId);
    if (!spot) return;
    if (typeof goDetail === "function") goDetail(spotId);
  }

  function backToHome() {
    renderHomeHome();
  }

  /* ───── Bottom sheet ───── */
  function ensureBottomSheet() {
    let el = document.getElementById("mapBottomSheet");
    if (el) return el;
    el = document.createElement("div");
    el.id = "mapBottomSheet";
    el.className = "map-bottom-sheet is-hidden";
    el.innerHTML = `
      <div class="mbs-handle" id="mbsHandle"></div>
      <div class="mbs-body" id="mbsBody"></div>
    `;
    const mapScreen = document.getElementById("mapScreen");
    if (mapScreen) mapScreen.appendChild(el);
    let startY = 0;
    el.addEventListener(
      "touchstart",
      (e) => {
        startY = e.touches[0].clientY;
      },
      { passive: true }
    );
    el.addEventListener(
      "touchend",
      (e) => {
        const dy = e.changedTouches[0].clientY - startY;
        if (dy > 60) closeBottomSheet();
      },
      { passive: true }
    );
    return el;
  }

  function closeBottomSheet() {
    const el = document.getElementById("mapBottomSheet");
    if (el) el.classList.add("is-hidden");
    selectedMapVenueId = null;
    if (kakaoMap && typeof renderKakaoMarkersUx === "function") {
      renderKakaoMarkersUx(currentFilter || "all");
    }
  }

  function openMapBottomSheet(venueId) {
    const v = getVenue(venueId);
    if (!v) return;
    const el = ensureBottomSheet();
    const body = document.getElementById("mbsBody");
    const members = typeof getVenueMemberSpots === "function" ? getVenueMemberSpots(v) : [];
    const isComposite = v.spotCount > 1 && !v.virtual;

    if (isComposite) {
      body.innerHTML = `
        <p class="mbs-title">${v.name}</p>
        <p class="mbs-sub">${v.spotCount}개 체험 · 항목을 고르세요</p>
        <div class="mbs-list">
          ${members
            .map(
              (s) => `
            <button type="button" class="mbs-item" onclick="Ux010.openSpotDetail(${s.id})">
              <span class="mbs-ico">${spotIcon(s)}</span>
              <span class="mbs-meta">
                <span class="mbs-cat">${spotLabel(s)}</span>
                <span class="mbs-name">${s.name}</span>
              </span>
              ${thrillBadge(s.thrillGrade)}
            </button>`
            )
            .join("")}
        </div>`;
    } else {
      const s = members[0] || (v.primarySpotId ? getSpot(v.primarySpotId) : null);
      if (!s) return;
      const seasonOn = isSeasonOpenLocal(s);
      body.innerHTML = `
        <div class="mbs-card" role="button" tabindex="0" onclick="Ux010.openSpotDetail(${s.id})">
          <div class="mbs-card-top">
            <span class="mbs-ico lg">${spotIcon(s)}</span>
            <div>
              <span class="chip t-earth">${spotLabel(s)}</span>
              ${thrillBadge(s.thrillGrade)}
            </div>
          </div>
          <p class="mbs-title">${s.name}</p>
          <p class="mbs-addr">📍 ${s.addr || v.address || ""}</p>
          <p class="mbs-season ${seasonOn ? "on" : "off"}">${seasonOn ? "⏱ 지금 가능" : "🚫 시즌 외"}</p>
          <button type="button" class="mbs-cta" onclick="event.stopPropagation();Ux010.openSpotDetail(${s.id})">상세 보기</button>
        </div>`;
    }
    el.classList.remove("is-hidden");
  }

  function openSpotDetail(spotId) {
    closeBottomSheet();
    if (typeof goDetail === "function") goDetail(spotId, false, "mapScreen");
  }

  /* ───── Map markers 3-level ───── */
  function clearMapOverlays() {
    mapClusterOverlays.forEach((o) => o.setMap && o.setMap(null));
    mapPinOverlays.forEach((o) => o.setMap && o.setMap(null));
    mapClusterOverlays = [];
    mapPinOverlays = [];
    if (typeof kakaoMarkers !== "undefined") {
      kakaoMarkers.forEach((m) => m.setMap && m.setMap(null));
      kakaoMarkers.length = 0;
    }
  }

  function mapLevel() {
    return kakaoMap && kakaoMap.getLevel ? kakaoMap.getLevel() : MAP_LEVEL_L1;
  }

  function makeMiniPinHTML(v) {
    const grade = venueMaxGrade(v);
    const hot = grade >= 4;
    const selected = selectedMapVenueId === v.id ? " selected" : "";
    const hotClass = hot ? " hot" : "";
    const spot = v.primarySpotId ? getSpot(v.primarySpotId) : null;
    const ico =
      v.spotCount > 1
        ? "📍"
        : spotIcon(spot) || "📍";
    return `<div class="map-mini-pin${selected}${hotClass}" onclick="Ux010.selectMapVenue(${v.id}, event)"><span>${ico}</span></div>`;
  }

  function makeRegionBubbleHTML(cluster) {
    const label = `${cluster.region} ${cluster.count}`;
    return `<div class="map-region-bubble" onclick="Ux010.zoomToRegion(${cluster.lat}, ${cluster.lng}, event)"><span>${label}</span></div>`;
  }

  function clusterNearby(venues, cellDeg) {
    const cells = new Map();
    venues.forEach((v) => {
      const c = getVenueMapCoords(v);
      if (!c) return;
      const key = `${Math.round(c.lat / cellDeg)}_${Math.round(c.lng / cellDeg)}`;
      if (!cells.has(key)) cells.set(key, []);
      cells.get(key).push({ v, c });
    });
    const out = [];
    cells.forEach((items) => {
      if (items.length === 1) {
        out.push({ type: "pin", venue: items[0].v, lat: items[0].c.lat, lng: items[0].c.lng });
      } else {
        const lat = items.reduce((s, i) => s + i.c.lat, 0) / items.length;
        const lng = items.reduce((s, i) => s + i.c.lng, 0) / items.length;
        out.push({ type: "cluster", count: items.length, venues: items.map((i) => i.v), lat, lng });
      }
    });
    return out;
  }

  async function fetchRegionClusters() {
    const params = new URLSearchParams();
    if (selectedGroupSlug) params.set("group", selectedGroupSlug);
    if (selectedCategoryId != null) params.set("categoryId", String(selectedCategoryId));
    if (typeof seasonNowOnly !== "undefined" && seasonNowOnly) {
      params.set("seasonMonth", String(new Date().getMonth() + 1));
    }
    try {
      const res = await fetch("/api/map/clusters?" + params.toString());
      if (!res.ok) return [];
      return await res.json();
    } catch (_) {
      return [];
    }
  }

  function getFilteredMapVenues(filter) {
    let visible =
      typeof getMapVisibleVenues === "function"
        ? getMapVisibleVenues(filter || "all")
        : VENUES || [];
    visible = visible.filter(venueMatchesCategoryFilters).filter(venueInMapBounds);
    return visible;
  }

  async function renderKakaoMarkersUx(filter) {
    if (!kakaoMap || typeof kakao === "undefined") return;
    clearMapOverlays();
    const level = mapLevel();
    const counter = document.getElementById("mapCounter");

    if (level >= MAP_LEVEL_L1) {
      const clusters = await fetchRegionClusters();
      clusters.forEach((cl) => {
        const overlay = new kakao.maps.CustomOverlay({
          position: new kakao.maps.LatLng(cl.lat, cl.lng),
          content: makeRegionBubbleHTML(cl),
          yAnchor: 0.5,
          xAnchor: 0.5,
        });
        overlay.setMap(kakaoMap);
        mapClusterOverlays.push(overlay);
        if (typeof kakaoMarkers !== "undefined") kakaoMarkers.push(overlay);
      });
      if (counter) counter.innerHTML = `<b>${clusters.reduce((s, c) => s + c.count, 0)}</b> 장소`;
      return;
    }

    const visible = getFilteredMapVenues(filter);
    if (counter) counter.innerHTML = `<b>${visible.length}</b> 장소`;

    const cell = level <= MAP_LEVEL_L3 ? 0.008 : 0.02;
    const items = clusterNearby(visible, cell);
    items.forEach((item) => {
      let html;
      if (item.type === "cluster") {
        html = `<div class="map-mini-cluster" onclick="Ux010.zoomIntoMiniCluster(${item.lat}, ${item.lng}, event)"><span>${item.count}</span></div>`;
      } else {
        html = makeMiniPinHTML(item.venue);
      }
      const overlay = new kakao.maps.CustomOverlay({
        position: new kakao.maps.LatLng(item.lat, item.lng),
        content: html,
        yAnchor: 1.1,
      });
      overlay.setMap(kakaoMap);
      mapPinOverlays.push(overlay);
      if (typeof kakaoMarkers !== "undefined") kakaoMarkers.push(overlay);
    });
  }

  function zoomToRegion(lat, lng, ev) {
    if (ev) {
      ev.stopPropagation();
      ev.preventDefault && ev.preventDefault();
    }
    if (!kakaoMap) return;
    kakaoMap.setLevel(8);
    kakaoMap.panTo(new kakao.maps.LatLng(lat, lng));
    setTimeout(() => renderKakaoMarkersUx(currentFilter || "all"), 200);
  }

  function zoomIntoMiniCluster(lat, lng, ev) {
    if (ev) {
      ev.stopPropagation();
      ev.preventDefault && ev.preventDefault();
    }
    if (!kakaoMap) return;
    const next = Math.max(mapLevel() - 2, 5);
    kakaoMap.setLevel(next);
    kakaoMap.panTo(new kakao.maps.LatLng(lat, lng));
    setTimeout(() => renderKakaoMarkersUx(currentFilter || "all"), 200);
  }

  function selectMapVenue(venueId, ev) {
    if (ev) {
      ev.stopPropagation();
      ev.preventDefault && ev.preventDefault();
    }
    selectedMapVenueId = venueId;
    const v = getVenue(venueId);
    if (v) {
      const coords = getVenueMapCoords(v);
      if (coords && kakaoMap) {
        kakaoMap.panTo(new kakao.maps.LatLng(coords.lat, coords.lng));
      }
      if (v.primarySpotId) currentId = v.primarySpotId;
    }
    renderKakaoMarkersUx(currentFilter || "all");
    openMapBottomSheet(venueId);
  }

  function researchThisArea() {
    if (!kakaoMap) return;
    const b = kakaoMap.getBounds();
    const sw = b.getSouthWest();
    const ne = b.getNorthEast();
    mapBoundsFilter = {
      swLat: sw.getLat(),
      swLng: sw.getLng(),
      neLat: ne.getLat(),
      neLng: ne.getLng(),
    };
    const btn = document.getElementById("mapResearchBtn");
    if (btn) btn.classList.add("is-hidden");
    renderKakaoMarkersUx(currentFilter || "all");
  }

  function onMapIdleForResearch() {
    const btn = document.getElementById("mapResearchBtn");
    if (btn) btn.classList.remove("is-hidden");
  }

  function clearBoundsFilter() {
    mapBoundsFilter = null;
  }

  function startMapAtUserLocation() {
    const fallback = () => {
      if (!kakaoMap) return;
      kakaoMap.setCenter(new kakao.maps.LatLng(37.5665, 126.978));
      kakaoMap.setLevel(MAP_LEVEL_L1);
      renderKakaoMarkersUx(currentFilter || "all");
    };
    if (!navigator.geolocation) {
      fallback();
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (!kakaoMap) return;
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        kakaoMap.setCenter(new kakao.maps.LatLng(lat, lng));
        kakaoMap.setLevel(8); // L2
        clearBoundsFilter();
        renderKakaoMarkersUx(currentFilter || "all");
      },
      () => fallback(),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 }
    );
  }

  function syncMapCategoryChips() {
    const row = document.getElementById("mapSubChips");
    if (!row) return;
    if (!selectedGroupSlug) {
      row.innerHTML = "";
      row.classList.add("is-hidden");
      return;
    }
    const g = (CATEGORY_GROUPS || []).find((x) => x.groupSlug === selectedGroupSlug);
    if (!g) return;
    row.classList.remove("is-hidden");
    const cats = (g.categories || []).filter((c) => c.spotCount > 0);
    row.innerHTML =
      `<button type="button" class="sub-chip ${selectedCategoryId == null ? "active" : ""}" onclick="Ux010.setMapCategory(null, this)">전체</button>` +
      cats
        .map(
          (c) =>
            `<button type="button" class="sub-chip ${selectedCategoryId === c.id ? "active" : ""}" onclick="Ux010.setMapCategory(${c.id}, this)">${c.name}</button>`
        )
        .join("");
  }

  function setMapCategory(cid, btn) {
    selectedCategoryId = cid;
    document.querySelectorAll("#mapSubChips .sub-chip").forEach((el) => el.classList.remove("active"));
    if (btn) btn.classList.add("active");
    renderKakaoMarkersUx(currentFilter || "all");
  }

  global.Ux010 = {
    MAP_LEVEL_L1,
    MAP_LEVEL_L3,
    loadCategoryGroups,
    renderHomeHome,
    openGroup,
    openCategory,
    setCategoryFilter,
    setGroupSort,
    renderGroupList,
    openSpotFromHome,
    backToHome,
    openGroupMap,
    selectMapVenue,
    openSpotDetail,
    closeBottomSheet,
    renderKakaoMarkersUx,
    zoomToRegion,
    zoomIntoMiniCluster,
    researchThisArea,
    onMapIdleForResearch,
    startMapAtUserLocation,
    syncMapCategoryChips,
    setMapCategory,
    venueMatchesCategoryFilters,
    get selectedGroupSlug() {
      return selectedGroupSlug;
    },
    get selectedCategoryId() {
      return selectedCategoryId;
    },
    get isListMode() {
      return homeMode === "group";
    },
    isSpotPublishable,
    venueIsPublishable,
    openSpotOnMap,
  };

  function openSpotOnMap(spotId) {
    const spot = typeof getSpot === "function" ? getSpot(spotId) : null;
    if (!spot) return;
    const lat = Number(spot.lat);
    const lng = Number(spot.lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || (lat === 0 && lng === 0)) {
      return;
    }
    const venueId = spot.venueId != null ? spot.venueId : -Number(spotId);
    if (typeof goMap === "function") goMap();
    const tryFocus = () => {
      if (!kakaoMap) {
        setTimeout(tryFocus, 200);
        return;
      }
      mapBoundsFilter = null;
      kakaoMap.setLevel(MAP_LEVEL_L3);
      kakaoMap.setCenter(new kakao.maps.LatLng(lat, lng));
      selectedMapVenueId = venueId;
      if (spot.id) currentId = spot.id;
      renderKakaoMarkersUx(currentFilter || "all");
      openMapBottomSheet(venueId);
      const btn = document.getElementById("mapResearchBtn");
      if (btn) btn.classList.remove("is-hidden");
    };
    setTimeout(tryFocus, 250);
  }
})(window);
