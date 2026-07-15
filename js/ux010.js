/**
 * UX 010 — categories home + 3-tier map markers + bottom sheet
 * Depends on globals from index.html: SPOTS, VENUES, kakaoMap, getVenue, getSpot, ...
 */
(function (global) {
  const MAP_LEVEL_L1 = 10; // level >= 10 → 도/광역시 버블
  const MAP_LEVEL_CITY = 8; // level >= 8 && < L1 → 시/군/구 버블
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
      const want = Number(selectedCategoryId);
      const members = typeof getVenueMemberSpots === "function" ? getVenueMemberSpots(v) : [];
      if (!members.length) {
        return Number(venueCategoryId(v)) === want;
      }
      return members.some(
        (s) => Number(s.categoryId) === want && isSpotPublishable(s)
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

  let categoriesReady = false;

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
      categoriesReady = true;
    } catch (_) {
      CATEGORY_GROUPS = [];
      CATEGORIES = [];
      categoriesReady = false;
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
    amphibious: "🚢",
  };

  function catIcon(c) {
    if (!c) return "📍";
    return CAT_ICON_BY_SLUG[c.slug] || c.icon || "📍";
  }

  /** 홈 4대 카테고리 섹션 — 클릭 없이 그룹별로 한눈에 */
  const MACRO_SECTIONS = [
    { key: "thrill", title: "스릴/익스트림", color: "#ff4d4d", emoji: "🎢" },
    { key: "riding", title: "탈것/라이딩", color: "#ff9124", emoji: "🏎️" },
    { key: "water", title: "수상 레저", color: "#3aa0ff", emoji: "🚤" },
    { key: "adventure", title: "어드벤처/탐험", color: "#37d67a", emoji: "🗺️" },
  ];
  const CAT_MACRO_BY_SLUG = {
    // 스릴/익스트림 — 고소·공중·낙하 계열
    paragliding: "thrill", bungee: "thrill", zipline: "thrill", "indoor-skydiving": "thrill",
    balloon: "thrill", "big-swing": "thrill", "light-aircraft": "thrill", "hang-glider": "thrill",
    "alpine-coaster": "thrill", slide: "thrill",
    // 탈것/라이딩 — 운전·탑승·페달
    kart: "riding", atv: "riding", offroad: "riding", "suv-offroad": "riding", amphibious: "riding",
    luge: "riding", skybike: "riding", railbike: "riding", "animal-riding": "riding",
    // 수상 레저 — 물놀이 계열
    jetboat: "water", "whitewater-kayak": "water", seawalk: "water", rafting: "water", parasailing: "water",
    // 어드벤처/탐험 — 체험·탐험 계열
    monorail: "adventure", "rock-climbing": "adventure", "high-ropes": "adventure",
    "survival-game": "adventure", shooting: "adventure", skywalk: "adventure",
    "cave-explore": "adventure", "cave-boat": "adventure",
  };
  const GROUP_MACRO_FALLBACK = { sky: "thrill", speed: "riding", water: "water", land: "adventure" };
  function macroOfCat(c) {
    if (!c) return "adventure";
    return CAT_MACRO_BY_SLUG[c.slug] || GROUP_MACRO_FALLBACK[c.groupSlug] || "adventure";
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

  let homeCatsExpanded = false;
  const HOME_CAT_PRIMARY = 8;

  function catBtnHtml(c, idx) {
    const tone = `t${idx % 8}`;
    return `
        <button type="button" class="home-cat-btn" data-cid="${c.id}" onclick="Ux010.openCategory(${c.id})">
          <span class="home-cat-ico ${tone}" aria-hidden="true">${catIcon(c)}</span>
          <span class="home-cat-name">${shortCatName(c.name)}</span>
        </button>`;
  }

  // 홈: 24개 아이콘 대신 4개 대형 카테고리 버튼 + 아코디언(세부 종목)
  let homeMacroOpen = null;

  function macroCardHtml(sec, list, open) {
    const total = list.reduce((n, c) => n + (Number(c.spotCount) || 0), 0);
    return `
        <button type="button" class="home-macro-card${open ? " is-open" : ""}" style="--macro:${sec.color}" aria-expanded="${open}" onclick="Ux010.toggleMacro('${sec.key}')">
          <span class="hmc-emoji" aria-hidden="true">${sec.emoji}</span>
          <span class="hmc-text">
            <span class="hmc-title">${sec.title}</span>
            <span class="hmc-meta">${list.length}종 · ${total}곳</span>
          </span>
          <span class="hmc-caret" aria-hidden="true">${open ? "▾" : "▸"}</span>
        </button>`;
  }

  function renderHomeMacroGrid() {
    const grid = document.getElementById("homeGroupGrid");
    if (!grid) return;
    grid.classList.remove("is-hidden", "home-cat-grid", "home-group-grid", "home-cat-sections");
    grid.classList.add("home-macro-wrap");
    const cats = CATEGORIES || [];
    if (!cats.length) {
      grid.classList.add("is-loading");
      grid.innerHTML =
        `<div class="home-macro-grid">` +
        [0, 1, 2, 3]
          .map(() => `<div class="home-macro-card" aria-hidden="true"><span class="hmc-emoji">·</span></div>`)
          .join("") +
        `</div>`;
      return;
    }
    grid.classList.remove("is-loading");
    const sections = MACRO_SECTIONS.map((sec) => ({
      sec,
      list: cats.filter((c) => macroOfCat(c) === sec.key),
    })).filter((x) => x.list.length);
    const cards = sections
      .map(({ sec, list }) => macroCardHtml(sec, list, homeMacroOpen === sec.key))
      .join("");
    let panel = "";
    const openEntry = sections.find((x) => x.sec.key === homeMacroOpen);
    if (openEntry) {
      const subBtns = openEntry.list.map((c, i) => catBtnHtml(c, i)).join("");
      panel = `
        <div class="home-macro-panel" style="--macro:${openEntry.sec.color}">
          <div class="home-macro-panel-head">
            <span class="hmp-title">${openEntry.sec.emoji} ${openEntry.sec.title}</span>
            <span class="hmp-hint">세부 종목을 눌러보세요</span>
          </div>
          <div class="home-cat-grid-sec">${subBtns}</div>
        </div>`;
    }
    grid.innerHTML = `<div class="home-macro-grid">${cards}</div>${panel}`;
  }

  function toggleMacro(key) {
    homeMacroOpen = homeMacroOpen === key ? null : key;
    renderHomeMacroGrid();
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
    renderHomeMacroGrid();
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

  function toggleHomeCats() {
    homeCatsExpanded = !homeCatsExpanded;
    const extra = document.getElementById("homeCatExtra");
    const btn = document.getElementById("homeCatMoreBtn");
    const rest = Math.max(0, (CATEGORIES || []).length - HOME_CAT_PRIMARY);
    if (extra) extra.classList.toggle("is-collapsed", !homeCatsExpanded);
    if (btn) {
      btn.textContent = homeCatsExpanded
        ? "인기 카테고리만 보기 ↑"
        : `전체 카테고리 ${rest}개 더보기 ↓`;
    }
  }

  /** 홈 검색창 — 카테고리 대신 전국 검색 결과 */
  function onHomeSearch(query) {
    const q = String(query || "").trim();
    if (!q) {
      if (homeMode === "search" || homeMode === "group") renderHomeHome();
      return;
    }
    homeMode = "search";
    flatCategoryMode = false;
    selectedGroupSlug = null;
    selectedCategoryId = null;
    showListShell(`‘${q}’ 검색`);
    const chips = document.getElementById("homeSubChips");
    if (chips) {
      chips.innerHTML = "";
      chips.classList.add("is-hidden");
    }
    renderSearchList(q);
  }

  function renderSearchList(q) {
    let list = (VENUES || []).filter((v) => venueIsPublishable(v));
    if (typeof seasonNowOnly !== "undefined" && seasonNowOnly && typeof venueHasInSeasonSpot === "function") {
      list = list.filter((v) => venueHasInSeasonSpot(v));
    }
    if (typeof matchVenueSearch === "function") {
      list = list.filter((v) => matchVenueSearch(v, q));
    }
    list = list.slice().sort((a, b) => venueMaxGrade(b) - venueMaxGrade(a) || String(a.name).localeCompare(String(b.name), "ko"));

    const countEl = document.getElementById("homeGroupCount");
    if (countEl) countEl.textContent = String(list.length);
    const cards = document.getElementById("homeGroupCards");
    if (!cards) return;
    if (!list.length) {
      cards.innerHTML = `<p class="home-search-empty">‘${q}’에 맞는 스팟이 없어요.<br>지역명이나 액티비티명으로 다시 검색해 보세요.</p>`;
      return;
    }
    if (typeof renderVenueCardHtml === "function") {
      cards.innerHTML = list.map((v) => renderVenueCardHtml(v)).join("");
    } else {
      cards.innerHTML = list
        .map(
          (v) =>
            `<button type="button" class="mc" onclick="Ux010.openSpotFromHome(${v.primarySpotId || ""})">${v.name}</button>`
        )
        .join("");
    }
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
    homeCatsExpanded = false;
    try {
      const main = document.getElementById("searchInput");
      const map = document.getElementById("mapSearchInput");
      if (main) main.value = "";
      if (map) map.value = "";
    } catch (_) {}
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
    const sheet = document.getElementById("mapBottomSheet");
    if (sheet) sheet.classList.add("is-hidden");
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

  /** 단독 핀: 카테고리만 (이름·사진 카드 X) */
  function makeMiniPinHTML(v) {
    const grade = venueMaxGrade(v);
    const hot = grade >= 4;
    const selected = selectedMapVenueId === v.id ? " selected" : "";
    const hotClass = hot ? " hot" : "";
    const spot = v.primarySpotId ? getSpot(v.primarySpotId) : null;
    const members = typeof getVenueMemberSpots === "function" ? getVenueMemberSpots(v) : [];
    const primary = spot || members[0] || null;
    const ico = spotIcon(primary) || "📍";
    const cat = shortCatName(
      primary ? spotLabel(primary) : (v && (v.tl || v.categoryName)) || "액티비티"
    );
    return `<div class="map-cat-pin${selected}${hotClass}" onclick="Ux010.selectMapVenue(${v.id}, event)">
      <div class="map-mini-pin${hotClass}"><span>${ico}</span></div>
      <span class="map-cat-label">${cat}</span>
    </div>`;
  }

  function makeCountBubbleHTML(count, lat, lng, zoomFn) {
    const n = Number(count) || 0;
    const fn = zoomFn || "zoomToRegion";
    return `<div class="map-mini-cluster" onclick="Ux010.${fn}(${lat}, ${lng}, event)"><span>${n}</span></div>`;
  }

  /** 같은 좌표(또는 극근접) 핀을 살짝 펼쳐 겹침 해소 */
  function spiderfySameCoords(entries) {
    if (entries.length <= 1) {
      const e = entries[0];
      return e
        ? [{ type: "pin", venue: e.v, lat: e.c.lat, lng: e.c.lng }]
        : [];
    }
    const lat0 = entries.reduce((s, e) => s + e.c.lat, 0) / entries.length;
    const lng0 = entries.reduce((s, e) => s + e.c.lng, 0) / entries.length;
    const r = 0.00028; // ~30m
    return entries.map((e, i) => {
      const a = (2 * Math.PI * i) / entries.length - Math.PI / 2;
      return {
        type: "pin",
        venue: e.v,
        lat: lat0 + r * Math.cos(a),
        lng: lng0 + r * Math.sin(a),
      };
    });
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

  /** 고배율: 격자 클러스터 끄고, 동일좌표만 펼침.
   * 줌아웃할수록 셀이 커져 2→5→15처럼 숫자가 합쳐짐. */
  function buildPinItems(venues, level) {
    if (level <= 3) {
      const buckets = new Map();
      venues.forEach((v) => {
        const c = getVenueMapCoords(v);
        if (!c) return;
        const key = `${c.lat.toFixed(5)}_${c.lng.toFixed(5)}`;
        if (!buckets.has(key)) buckets.set(key, []);
        buckets.get(key).push({ v, c });
      });
      const out = [];
      buckets.forEach((entries) => {
        spiderfySameCoords(entries).forEach((p) => out.push(p));
      });
      return out;
    }
    // Kakao level 작을수록 확대. 확대로 갈수록 셀을 줄여 숫자 클러스터가 풀리게.
    const cell =
      level <= 4 ? 0.0018 :
      level <= 5 ? 0.004 :
      level <= 6 ? 0.01 :
      level <= 7 ? 0.022 :
      0.04;
    return clusterNearby(venues, cell);
  }

  function openClusterVenueSheet(venues) {
    const el = ensureBottomSheet();
    const body = document.getElementById("mbsBody");
    const list = (venues || []).filter(Boolean);
    if (!list.length) return;
    body.innerHTML = `
      <p class="mbs-title">이 위치 ${list.length}곳</p>
      <p class="mbs-sub">겹친 장소를 골라 주세요</p>
      <div class="mbs-list">
        ${list
          .map((v) => {
            const s =
              (typeof getVenueMemberSpots === "function" ? getVenueMemberSpots(v)[0] : null) ||
              (v.primarySpotId ? getSpot(v.primarySpotId) : null);
            const title = (s && s.name) || v.name || "장소";
            const cat = s ? spotLabel(s) : v.tl || "";
            const sid = s && s.id != null ? s.id : v.primarySpotId;
            const click =
              sid != null
                ? `Ux010.openSpotDetail(${sid})`
                : `Ux010.selectMapVenue(${v.id}, event)`;
            return `
            <button type="button" class="mbs-item" onclick="${click}">
              <span class="mbs-ico">${s ? spotIcon(s) : "📍"}</span>
              <span class="mbs-meta">
                <span class="mbs-cat">${cat}</span>
                <span class="mbs-name">${title}</span>
              </span>
              ${s ? thrillBadge(s.thrillGrade || s.th) : ""}
            </button>`;
          })
          .join("")}
      </div>`;
    el.classList.remove("is-hidden");
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

    // 멀리: 도/광역시 묶음 — 숫자만 (용인 4 X → 4)
    if (level >= MAP_LEVEL_L1) {
      const clusters = await fetchRegionClusters();
      clusters.forEach((cl) => {
        const overlay = new kakao.maps.CustomOverlay({
          position: new kakao.maps.LatLng(cl.lat, cl.lng),
          content: makeCountBubbleHTML(cl.count, cl.lat, cl.lng, "zoomToRegion"),
          yAnchor: 0.5,
          xAnchor: 0.5,
          clickable: true,
          zIndex: 2,
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

    // 중간·가까운 줌: 격자 숫자 클러스터 → 1개면 카테고리 핀
    const items = buildPinItems(visible, level);
    mapMiniClusters = items.filter((it) => it.type === "cluster");
    items.forEach((item) => {
      let html;
      let yAnchor = 1.05;
      if (item.type === "cluster") {
        const idx = mapMiniClusters.indexOf(item);
        html = `<div class="map-mini-cluster" onclick="Ux010.openMiniCluster(${idx}, ${item.lat}, ${item.lng}, event)"><span>${item.count}</span></div>`;
        yAnchor = 0.5;
      } else {
        html = makeMiniPinHTML(item.venue);
      }
      const overlay = new kakao.maps.CustomOverlay({
        position: new kakao.maps.LatLng(item.lat, item.lng),
        content: html,
        yAnchor,
        clickable: true,
        zIndex: 3,
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
    kakaoMap.setLevel(7);
    kakaoMap.panTo(new kakao.maps.LatLng(lat, lng));
    setTimeout(() => renderKakaoMarkersUx(currentFilter || "all"), 200);
  }

  function zoomToCity(lat, lng, ev) {
    if (ev) {
      ev.stopPropagation();
      ev.preventDefault && ev.preventDefault();
    }
    if (!kakaoMap) return;
    kakaoMap.setLevel(6);
    kakaoMap.panTo(new kakao.maps.LatLng(lat, lng));
    setTimeout(() => renderKakaoMarkersUx(currentFilter || "all"), 200);
  }

  function openMiniCluster(idx, lat, lng, ev) {
    if (ev) {
      ev.stopPropagation();
      ev.preventDefault && ev.preventDefault();
    }
    if (!kakaoMap) return;
    const cl = mapMiniClusters[idx];
    const level = mapLevel();
    // 이미 크게 확대됐으면 숫자 대신 목록
    if (level <= 4 && cl && cl.venues && cl.venues.length) {
      openClusterVenueSheet(cl.venues);
      return;
    }
    const next = Math.max(level - 2, 1);
    kakaoMap.setLevel(next);
    kakaoMap.panTo(new kakao.maps.LatLng(lat, lng));
    setTimeout(() => {
      renderKakaoMarkersUx(currentFilter || "all");
      // 줌인 후에도 같은 위치에 묶이면 목록
      const still = (mapMiniClusters || []).find(
        (c) => Math.abs(c.lat - lat) < 0.0008 && Math.abs(c.lng - lng) < 0.0008
      );
      if (still && still.venues && still.venues.length && mapLevel() <= 3) {
        openClusterVenueSheet(still.venues);
      }
    }, 240);
  }

  function zoomIntoMiniCluster(lat, lng, ev) {
    openMiniCluster(0, lat, lng, ev);
  }

  function selectMapVenue(venueId, ev) {
    if (ev) {
      ev.stopPropagation();
      ev.preventDefault && ev.preventDefault();
    }
    selectedMapVenueId = venueId;
    const v = typeof getVenue === "function" ? getVenue(venueId) : null;
    if (!v) return;
    const coords = typeof getVenueMapCoords === "function" ? getVenueMapCoords(v) : null;
    if (coords && kakaoMap) {
      kakaoMap.panTo(new kakao.maps.LatLng(coords.lat, coords.lng));
    }
    const members = typeof getVenueMemberSpots === "function" ? getVenueMemberSpots(v) : [];
    const isComposite = v.spotCount > 1 && !v.virtual;
    if (!isComposite) {
      const s = members[0] || (v.primarySpotId ? getSpot(v.primarySpotId) : null);
      if (s && s.id) {
        if (s.id) currentId = s.id;
        openSpotDetail(s.id);
        return;
      }
    }
    if (v.primarySpotId) currentId = v.primarySpotId;
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
        // 멀리서 도 단위부터 보이도록 (확대하면 시→숫자→사진)
        kakaoMap.setLevel(Math.max(MAP_LEVEL_L1, 11));
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
    MAP_LEVEL_CITY,
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
    zoomToCity,
    zoomIntoMiniCluster,
    openMiniCluster,
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
      return homeMode === "group" || homeMode === "search";
    },
    isSpotPublishable,
    venueIsPublishable,
    openSpotOnMap,
    onHomeSearch,
    toggleHomeCats,
    toggleMacro,
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
