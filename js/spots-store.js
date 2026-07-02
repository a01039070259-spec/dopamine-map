/**
 * 도파민 지도 — 공통 스팟 저장소 (index ↔ admin 공유)
 */
(function (global) {
  const CUSTOM_SPOTS_KEY = "dopamine_map_custom_spots";
  /** 기본 스팟 id(0~5)와 겹치지 않도록 커스텀 id는 100부터 */
  const CUSTOM_ID_START = 100;

  const TYPE_META = {
    roller: { tl: "롤러코스터", bg: "#1a0a2e" },
    swing: { tl: "바이킹", bg: "#0a0a1f" },
    bungee: { tl: "번지점프", bg: "#0a001f" },
    zipline: { tl: "짚라인", bg: "#0a0a1f" },
    luge: { tl: "루지", bg: "#1f1a0a" },
    coaster: { tl: "마운틴코스터", bg: "#0a1f1a" },
    sky: { tl: "스카이다이빙", bg: "#1f0a1f" },
  };

  /** 관리자 등록 · 리뷰 등에서 선택하는 공통 태그 */
  const PRESET_TAGS = [
    "#목꺾임주의",
    "#안전바들썩",
    "#안전바덜렁",
    "#낙하각도77도",
    "#첫드롭지옥",
    "#뒷자리금지구역",
    "#재탑승각",
    "#재방문의사있음",
    "#도파민폭발",
    "#심장마비급",
    "#기저귀필수",
    "#대기2시간각오",
    "#대기지옥",
    "#점심후탑승금지",
    "#멀미주의",
    "#소화불량보장",
    "#다음날파스",
    "#눈못뜸",
    "#비명금지불가",
    "#척추각도이상",
    "#입문자주의",
    "#커플코스",
    "#가족추천",
    "#로컬추천",
    "#국내원탑",
    "#바다배경뒤집힘",
    "#역방향끝자리각",
    "#해상공포체험",
    "#북한강뷰낙하",
    "#60m자유낙하",
    "#발목밧줄신뢰게임",
    "#다리풀림100%보장",
    "#1인탑승직접조작",
    "#레버로속도조절",
    "#직접조작",
    "#1300m급경사커브",
    "#대관령전망",
    "#국내최고속120km",
    "#병방산정상출발",
    "#325m낙차",
    "#한반도지형뷰",
    "#4트랙3.8km",
    "#카트직접운전",
    "#통영앞바다뷰",
    "#360도회전코스",
    "#GoPro필수",
    "#지포스최강",
    "#속도미쳤음",
    "#직접등록",
    "#NEW",
  ];

  const PRESET_EMOJIS = ["🔥", "💀", "⚡", "🎢"];

  function loadCustomSpots() {
    try {
      const raw = localStorage.getItem(CUSTOM_SPOTS_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (_) {
      return [];
    }
  }

  function saveCustomSpots(list) {
    try {
      localStorage.setItem(CUSTOM_SPOTS_KEY, JSON.stringify(list));
    } catch (_) {
      throw new Error("STORAGE_FULL");
    }
  }

  function mergeSpots(defaultSpots) {
    const defaults = defaultSpots || [];
    return [...defaults, ...ensureCustomSpotIds(defaults)];
  }

  /** id가 기본 스팟과 겹치면 자동으로 100+ 번호 재부여 */
  function ensureCustomSpotIds(defaultSpots) {
    const reserved = new Set((defaultSpots || []).map((s) => Number(s.id)));
    let custom = loadCustomSpots();
    let maxId = CUSTOM_ID_START - 1;

    custom.forEach((s) => {
      const id = Number(s.id);
      if (id >= CUSTOM_ID_START && !reserved.has(id)) {
        maxId = Math.max(maxId, id);
      }
    });

    const used = new Set([...reserved]);
    custom.forEach((s) => used.add(Number(s.id)));

    let changed = false;
    custom = custom.map((s) => {
      const id = Number(s.id);
      if (id >= CUSTOM_ID_START && !reserved.has(id)) {
        return s;
      }
      changed = true;
      do {
        maxId += 1;
      } while (used.has(maxId));
      used.add(maxId);
      return { ...s, id: maxId };
    });

    if (changed) saveCustomSpots(custom);
    return custom;
  }

  function thrillStars(n) {
    const v = Math.max(1, Math.min(5, Math.round(Number(n) || 3)));
    return "🔥".repeat(v);
  }

  function parseRegisterTags(text) {
    return String(text || "")
      .split(/[,，]/)
      .map((t) => t.trim())
      .filter(Boolean)
      .map((t) => (t.startsWith("#") ? t : `#${t}`));
  }

  function parseRegisterWarns(text) {
    const lines = String(text || "")
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (!lines.length) {
      return [
        {
          t: "y",
          i: "💡",
          tx: "탑승 전 안전 수칙과 제한 사항을 현장에서 꼭 확인하세요.",
        },
      ];
    }
    return lines.map((line) => {
      if (line.startsWith("💡")) {
        return { t: "y", i: "💡", tx: line.replace(/^💡\s*/, "") };
      }
      if (line.startsWith("✅")) {
        return { t: "g", i: "✅", tx: line.replace(/^✅\s*/, "") };
      }
      return { t: "r", i: "⚠️", tx: line.replace(/^⚠️\s*/, "") };
    });
  }

  function nextSpotId(allSpots) {
    let max = CUSTOM_ID_START - 1;
    (allSpots || []).forEach((s) => {
      max = Math.max(max, Number(s.id) || 0);
    });
    return max + 1;
  }

  function hasSpotImage(spot) {
    return !!(spot && spot.img && String(spot.img).indexOf("data:image") === 0);
  }

  function compressImageFile(file, maxW, maxH, quality) {
    maxW = maxW || 800;
    maxH = maxH || 600;
    quality = quality || 0.78;
    return new Promise((resolve, reject) => {
      if (!file || !String(file.type).startsWith("image/")) {
        reject(new Error("NOT_IMAGE"));
        return;
      }
      if (file.size > 8 * 1024 * 1024) {
        reject(new Error("TOO_LARGE"));
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => {
          let w = img.width;
          let h = img.height;
          const ratio = Math.min(maxW / w, maxH / h, 1);
          w = Math.round(w * ratio);
          h = Math.round(h * ratio);
          const canvas = document.createElement("canvas");
          canvas.width = w;
          canvas.height = h;
          const ctx = canvas.getContext("2d");
          if (!ctx) {
            reject(new Error("CANVAS_FAIL"));
            return;
          }
          ctx.drawImage(img, 0, 0, w, h);
          resolve(canvas.toDataURL("image/jpeg", quality));
        };
        img.onerror = () => reject(new Error("LOAD_FAIL"));
        img.src = reader.result;
      };
      reader.onerror = () => reject(new Error("READ_FAIL"));
      reader.readAsDataURL(file);
    });
  }

  function normalizeTypeLabel(raw) {
    const label = String(raw || "").trim();
    return label || "액티비티";
  }

  function resolveTypeInfo(raw) {
    const tl = normalizeTypeLabel(raw);
    const compact = tl.toLowerCase().replace(/\s+/g, "");

    for (const [key, meta] of Object.entries(TYPE_META)) {
      const metaCompact = meta.tl.replace(/\s+/g, "").toLowerCase();
      if (key === compact || meta.tl === tl || metaCompact === compact) {
        return { type: key, tl: meta.tl, bg: meta.bg };
      }
    }

    const palettes = ["#1a0a2e", "#0a0a1f", "#0a001f", "#1f1a0a", "#0a1f1a", "#1f0a1f"];
    let h = 0;
    for (let i = 0; i < tl.length; i++) h = (h + tl.charCodeAt(i) * (i + 1)) % palettes.length;
    return { type: compact || "custom", tl, bg: palettes[h] };
  }

  function spotSearchHaystack(spot) {
    return [
      spot.name,
      spot.addr,
      spot.tl,
      spot.type,
      spot.rank,
      spot.br,
      ...(spot.tags || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
  }

  function matchSpotSearch(spot, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return true;
    const hay = spotSearchHaystack(spot);
    const hayCompact = hay.replace(/\s+/g, "");
    const qCompact = q.replace(/\s+/g, "");
    if (hay.includes(q) || hayCompact.includes(qCompact)) return true;
    const tokens = q.split(/\s+/).filter(Boolean);
    if (tokens.length > 1) {
      return tokens.every(
        (t) => hay.includes(t) || hayCompact.includes(t.replace(/\s+/g, ""))
      );
    }
    return false;
  }

  const CHIP_CLASS_MAP = {
    roller: "t-roller",
    swing: "t-swing",
    bungee: "t-bungee",
    zipline: "t-zipline",
    luge: "t-luge",
    coaster: "t-coaster",
    sky: "t-sky",
    롤러코스터: "t-roller",
    바이킹: "t-swing",
    번지점프: "t-bungee",
    짚라인: "t-zipline",
    루지: "t-luge",
    마운틴코스터: "t-coaster",
    스카이다이빙: "t-sky",
  };

  function chipClassForSpot(spot) {
    const tl = spot && spot.tl ? String(spot.tl).trim() : "";
    const type = spot && spot.type ? String(spot.type).trim() : "";
    return CHIP_CLASS_MAP[type] || CHIP_CLASS_MAP[tl] || "t-custom";
  }

  function buildSpotFromForm(data, allSpots, existingSpot) {
    const typeInfo = resolveTypeInfo(data.type);
    const th = Math.max(1, Math.min(5, parseInt(data.th, 10) || 3));
    const fp = Math.max(0, Math.min(100, parseInt(data.fp, 10) || 50));
    const sp2 = Math.max(0, Math.min(100, parseInt(data.sp2, 10) || 50));
    const ap = Math.max(0, Math.min(100, parseInt(data.ap, 10) || 50));
    const sp = Math.max(0, parseInt(data.sp, 10) || 0);
    const tags = parseRegisterTags(data.tags);
    const now = new Date().toISOString();

    const spot = {
      id: existingSpot ? existingSpot.id : nextSpotId(allSpots),
      name: data.name,
      addr: data.addr,
      type: typeInfo.type,
      tl: typeInfo.tl,
      em: data.em || "🔥",
      bg: typeInfo.bg,
      img: Object.prototype.hasOwnProperty.call(data, "img")
        ? data.img
        : (existingSpot && existingSpot.img) || "",
      lat: Number(data.lat),
      lng: Number(data.lng),
      th,
      fe: Math.max(1, Math.min(5, Math.round(th * (fp / 100)))),
      sp,
      fp,
      sp2,
      ap,
      rank: data.rank || "NEW SPOT",
      markerType: th >= 4 ? "skull" : "fire",
      tags: tags.length ? tags : ["#직접등록", "#NEW"],
      br: data.br || "직접 등록한 매운맛 스팟. 생존 후기를 남겨주세요.",
      ts: thrillStars(th),
      warns: parseRegisterWarns(data.warns),
      reviews: existingSpot && existingSpot.reviews ? existingSpot.reviews : [],
      custom: true,
      approved: true,
      createdAt: existingSpot && existingSpot.createdAt ? existingSpot.createdAt : now,
      updatedAt: now,
    };

    return spot;
  }

  function formatTagsForInput(tags) {
    return (tags || [])
      .map((t) => String(t).trim())
      .filter(Boolean)
      .map((t) => (t.startsWith("#") ? t : `#${t}`))
      .join(", ");
  }

  function formatWarnsForInput(warns) {
    return (warns || [])
      .map((w) => {
        const icon = w.i || "⚠️";
        const text = w.tx || "";
        return text.startsWith(icon) ? text : `${icon} ${text}`;
      })
      .join("\n");
  }

  function getCustomSpot(id) {
    const num = Number(id);
    return loadCustomSpots().find((s) => s.id === num) || null;
  }

  function upsertCustomSpot(spot) {
    const list = loadCustomSpots();
    const idx = list.findIndex((s) => s.id === spot.id);
    if (idx >= 0) list[idx] = spot;
    else list.push(spot);
    saveCustomSpots(list);
    return spot;
  }

  function deleteCustomSpot(id) {
    const num = Number(id);
    saveCustomSpots(loadCustomSpots().filter((s) => s.id !== num));
  }

  const API_BASE = "";

  async function apiFetch(path, options) {
    const opts = options || {};
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    const res = await fetch(
      API_BASE + path,
      Object.assign({ credentials: "include" }, opts, { headers })
    );
    if (!res.ok) {
      const err = new Error("API_ERROR");
      err.status = res.status;
      try {
        err.body = await res.json();
      } catch (_) {
        err.body = null;
      }
      throw err;
    }
    if (res.status === 204) return null;
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  }

  async function fetchAllSpots() {
    return apiFetch("/api/spots");
  }

  async function verifyAdminPassword(adminPassword) {
    await apiFetch("/api/admin/verify", {
      method: "POST",
      headers: { "X-Admin-Password": adminPassword || "" },
      body: "{}",
    });
    return true;
  }

  async function fetchSpotById(id, adminPassword) {
    const headers = adminPassword ? { "X-Admin-Password": adminPassword } : {};
    return apiFetch("/api/spots/" + Number(id), { headers: headers });
  }

  async function fetchAuthMe() {
    return apiFetch("/api/auth/me");
  }

  async function recordVisit() {
    return apiFetch("/api/visits", { method: "POST", body: "{}" });
  }

  async function submitReview(payload) {
    return apiFetch("/api/reviews", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async function saveDiagnosis(result) {
    return apiFetch("/api/diagnosis", {
      method: "POST",
      body: JSON.stringify({ result: result }),
    });
  }

  async function fetchDiagnosis() {
    return apiFetch("/api/diagnosis");
  }

  async function logoutAuth() {
    return apiFetch("/auth/logout", { method: "POST", body: "{}" });
  }

  async function fetchAdminStats(adminPassword) {
    return apiFetch("/api/admin/stats", {
      headers: { "X-Admin-Password": adminPassword || "" },
    });
  }

  async function adminGeocode(queries, adminPassword, keywords) {
    const list = Array.isArray(queries) ? queries : [queries];
    const kw = Array.isArray(keywords) ? keywords : keywords ? [keywords] : [];
    return apiFetch("/api/admin/geocode", {
      method: "POST",
      headers: { "X-Admin-Password": adminPassword || "" },
      body: JSON.stringify({ queries: list.filter(Boolean), keywords: kw.filter(Boolean) }),
    });
  }

  function kakaoLoginUrl(nextPath) {
    const next = nextPath || "/index.html";
    return "/auth/kakao/login?next=" + encodeURIComponent(next);
  }

  async function saveSpotToApi(spot, adminPassword) {
    const headers = { "X-Admin-Password": adminPassword || "" };
    if (spot.id) {
      return apiFetch("/api/spots/" + spot.id, {
        method: "PUT",
        headers,
        body: JSON.stringify(spot),
      });
    }
    const payload = Object.assign({}, spot);
    delete payload.id;
    return apiFetch("/api/spots", {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
  }

  async function deleteSpotFromApi(id, adminPassword) {
    return apiFetch("/api/spots/" + Number(id), {
      method: "DELETE",
      headers: { "X-Admin-Password": adminPassword || "" },
    });
  }

  global.DopamineStore = {
    CUSTOM_SPOTS_KEY,
    CUSTOM_ID_START,
    TYPE_META,
    PRESET_TAGS,
    PRESET_EMOJIS,
    loadCustomSpots,
    saveCustomSpots,
    mergeSpots,
    thrillStars,
    parseRegisterTags,
    parseRegisterWarns,
    nextSpotId,
    hasSpotImage,
    compressImageFile,
    normalizeTypeLabel,
    resolveTypeInfo,
    matchSpotSearch,
    chipClassForSpot,
    buildSpotFromForm,
    formatTagsForInput,
    formatWarnsForInput,
    getCustomSpot,
    upsertCustomSpot,
    deleteCustomSpot,
    fetchAllSpots,
    fetchSpotById,
    fetchAuthMe,
    recordVisit,
    submitReview,
    saveDiagnosis,
    fetchDiagnosis,
    logoutAuth,
    fetchAdminStats,
    adminGeocode,
    kakaoLoginUrl,
    verifyAdminPassword,
    saveSpotToApi,
    deleteSpotFromApi,
  };
})(window);
