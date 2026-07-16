# -*- coding: utf-8 -*-
import html
import json
from datetime import datetime, timezone
from xml.sax.saxutils import escape

SITE_NAME = "도파민 지도"
DEFAULT_DESCRIPTION = (
    "전국 짚라인·번지·패러글라이딩·제트보트·실탄사격·동굴탐험 등 "
    "하드코어 액티비티 스팟 정보, 스릴 지수, 생존 가이드, 지도 검색."
)
DEFAULT_KEYWORDS = (
    "도파민 지도,액티비티,짚라인,번지점프,패러글라이딩,제트보트,스피드보트,"
    "실탄사격,동굴탐험,행글라이더,스릴,레저,여행,전국 지도"
)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def publishable_spots(spots: list[dict]) -> list[dict]:
    """Same rule as sitemap / app exposure."""
    out = []
    for spot in spots:
        if not spot.get("approved", True):
            continue
        if not (spot.get("coordVerified") or spot.get("legacy")):
            continue
        if spot.get("id") is None:
            continue
        out.append(spot)
    return out


def _spot_label(spot: dict) -> str:
    return spot.get("categoryName") or spot.get("tl") or spot.get("type") or "액티비티"


def _rss_pub_date(spot: dict) -> str:
    raw = spot.get("updatedAt") or spot.get("createdAt") or ""
    if not raw:
        return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
    except ValueError:
        return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


def build_robots_txt(base_url: str) -> str:
    base = base_url.rstrip("/")
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /spot/\n"
        "Disallow: /admin.html\n"
        "Disallow: /api/\n"
        "Disallow: /auth/\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )


def build_sitemap_xml(base_url: str, spots: list[dict]) -> str:
    base = base_url.rstrip("/")
    urls = [
        (f"{base}/", "daily", "1.0"),
        (f"{base}/index.html", "daily", "1.0"),
        (f"{base}/spots", "daily", "0.9"),
        (f"{base}/diagnosis.html", "monthly", "0.6"),
    ]
    for spot in publishable_spots(spots):
        urls.append((f"{base}/spot/{spot['id']}", "weekly", "0.8"))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    lastmod = _today()
    for loc, changefreq, priority in urls:
        lines.extend(
            [
                "  <url>",
                f"    <loc>{escape(loc)}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                f"    <changefreq>{changefreq}</changefreq>",
                f"    <priority>{priority}</priority>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def build_rss_xml(base_url: str, spots: list[dict], *, limit: int = 200) -> str:
    """RSS 2.0 — 네이버 서치어드바이저 RSS 제출용."""
    base = base_url.rstrip("/")
    items = sorted(
        publishable_spots(spots),
        key=lambda s: int(s.get("id") or 0),
        reverse=True,
    )[:limit]
    now = _rss_pub_date({})
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        f"    <title>{escape(SITE_NAME)}</title>",
        f"    <link>{escape(base + '/')}</link>",
        f"    <description>{escape(DEFAULT_DESCRIPTION)}</description>",
        "    <language>ko</language>",
        f"    <lastBuildDate>{now}</lastBuildDate>",
        f'    <atom:link href="{escape(base + "/rss.xml")}" rel="self" type="application/rss+xml"/>',
    ]
    for spot in items:
        sid = spot["id"]
        name = spot.get("name") or "액티비티 스팟"
        tl = _spot_label(spot)
        addr = spot.get("addr") or ""
        br = spot.get("br") or f"{addr} — {tl}"
        link = f"{base}/spot/{sid}"
        title = f"{name} · {tl}"
        desc = html.escape((br or title)[:300])
        lines.extend(
            [
                "    <item>",
                f"      <title>{escape(title)}</title>",
                f"      <link>{escape(link)}</link>",
                f"      <guid isPermaLink=\"true\">{escape(link)}</guid>",
                f"      <description>{desc}</description>",
                f"      <pubDate>{_rss_pub_date(spot)}</pubDate>",
                "    </item>",
            ]
        )
    lines.extend(["  </channel>", "</rss>", ""])
    return "\n".join(lines)


def build_spots_index_html(base_url: str, spots: list[dict]) -> str:
    """크롤러용 정적 HTML — 네이버·구글 봇이 JS 없이 스팟 링크를 읽도록."""
    base = base_url.rstrip("/")
    items = sorted(
        publishable_spots(spots),
        key=lambda s: (
            str(s.get("categoryName") or s.get("tl") or ""),
            str(s.get("name") or ""),
        ),
    )
    by_cat: dict[str, list[dict]] = {}
    for spot in items:
        cat = _spot_label(spot)
        by_cat.setdefault(cat, []).append(spot)

    sections = []
    for cat in sorted(by_cat.keys(), key=lambda x: x):
        links = []
        for spot in by_cat[cat]:
            sid = spot["id"]
            name = spot.get("name") or "스팟"
            addr = spot.get("addr") or ""
            links.append(
                f'<li><a href="{html.escape(base + "/spot/" + str(sid))}">'
                f"{html.escape(name)}</a>"
                f' <span class="addr">{html.escape(addr)}</span></li>'
            )
        sections.append(
            f"<section><h2>{html.escape(cat)}</h2><ul>{''.join(links)}</ul></section>"
        )

    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>전국 액티비티 스팟 목록 | {html.escape(SITE_NAME)}</title>
<meta name="description" content="{html.escape(DEFAULT_DESCRIPTION)}"/>
<meta name="robots" content="index,follow"/>
<link rel="canonical" href="{html.escape(base + "/spots")}"/>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{min-height:100vh;background:#0a0a0a;color:#f0f0f0;font-family:'Noto Sans KR',sans-serif;line-height:1.65}}
.wrap{{max-width:900px;margin:0 auto;padding:28px 20px 48px}}
h1{{font-size:24px;font-weight:900;color:#39ff14;margin-bottom:8px}}
.lead{{font-size:14px;color:#aaa;margin-bottom:24px}}
section{{margin-bottom:28px}}
h2{{font-size:16px;font-weight:800;color:#39ff14;margin-bottom:10px;border-bottom:1px solid #2a2a2a;padding-bottom:6px}}
ul{{list-style:none}}
li{{margin:8px 0;font-size:14px}}
a{{color:#f0f0f0;text-decoration:none;font-weight:700}}
a:hover{{color:#39ff14}}
.addr{{display:block;font-size:12px;color:#888;font-weight:400;margin-top:2px}}
footer{{margin-top:32px;font-size:12px;color:#666}}
footer a{{color:#39ff14}}
</style>
</head>
<body>
<div class="wrap">
  <h1>{html.escape(SITE_NAME)} — 전국 스팟 목록</h1>
  <p class="lead">짚라인·번지·패러세일링·제트보트·루지·동굴탐험 등 {len(items)}곳. 각 링크에서 스릴 지수·생존 가이드를 확인할 수 있습니다.</p>
  {body}
  <footer>
    <p><a href="{html.escape(base + '/')}">← 홈으로</a> · <a href="{html.escape(base + '/sitemap.xml')}">사이트맵</a> · <a href="{html.escape(base + '/rss.xml')}">RSS</a></p>
  </footer>
</div>
</body>
</html>"""


def build_spot_page_html(spot: dict, base_url: str) -> str:
    base = base_url.rstrip("/")
    name = spot.get("name") or "액티비티 스팟"
    tl = spot.get("tl") or spot.get("type") or "액티비티"
    addr = spot.get("addr") or ""
    br = spot.get("br") or ""
    th = spot.get("th") or 3
    tags = spot.get("tags") or []
    sid = spot.get("id")
    page_url = f"{base}/spot/{sid}"
    app_url = f"{base}/index.html?spot={sid}"
    title = f"{name} · {tl} | {SITE_NAME}"
    desc = br or f"{addr} — {tl} 스릴 지수 {th}. {SITE_NAME}에서 생존 가이드 확인."
    desc = desc[:180]
    tag_text = " ".join(str(t).replace("#", "") for t in tags[:6])
    keywords = f"{name},{tl},{tag_text},{DEFAULT_KEYWORDS}"

    json_ld = {
        "@context": "https://schema.org",
        "@type": "TouristAttraction",
        "name": name,
        "description": desc,
        "url": page_url,
        "address": addr,
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": spot.get("lat"),
            "longitude": spot.get("lng"),
        },
    }

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}"/>
<meta name="robots" content="index,follow"/>
<meta name="keywords" content="{html.escape(keywords)}"/>
<link rel="canonical" href="{html.escape(page_url)}"/>
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="{html.escape(SITE_NAME)}"/>
<meta property="og:title" content="{html.escape(title)}"/>
<meta property="og:description" content="{html.escape(desc)}"/>
<meta property="og:url" content="{html.escape(page_url)}"/>
<meta property="og:image" content="{html.escape(base + "/assets/og-default.jpg")}"/>
<meta property="og:locale" content="ko_KR"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{html.escape(title)}"/>
<meta name="twitter:description" content="{html.escape(desc)}"/>
<meta name="twitter:image" content="{html.escape(base + "/assets/og-default.jpg")}"/>
<!-- TODO(011): 스팟별 동적 og:image — spot.cover 주입 -->
<script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{min-height:100vh;background:#0a0a0a;color:#f0f0f0;font-family:'Noto Sans KR',sans-serif;line-height:1.65}}
.wrap{{max-width:640px;margin:0 auto;padding:28px 20px 48px}}
.badge{{display:inline-block;font-size:11px;font-weight:700;color:#39ff14;border:1px solid #39ff1444;background:#39ff1414;padding:4px 10px;border-radius:999px;margin-bottom:12px}}
h1{{font-size:24px;font-weight:900;margin-bottom:10px;letter-spacing:-.3px}}
.addr{{font-size:13px;color:#888;margin-bottom:14px}}
.desc{{font-size:15px;color:#ccc;margin-bottom:18px}}
.meta{{font-size:13px;color:#aaa;margin-bottom:24px}}
.tags{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:28px}}
.tag{{font-size:11px;color:#aaa;border:1px solid #2a2a2a;border-radius:6px;padding:4px 8px}}
.btn{{display:block;text-align:center;background:#39ff14;color:#0a0a0a;text-decoration:none;font-weight:900;padding:14px;border-radius:10px;margin-bottom:10px}}
.btn-ghost{{background:transparent;border:1px solid #2a2a2a;color:#aaa;font-weight:600}}
footer{{margin-top:32px;font-size:12px;color:#666}}
footer a{{color:#39ff14}}
</style>
</head>
<body>
<div class="wrap">
  <span class="badge">{html.escape(tl)}</span>
  <h1>{html.escape(name)}</h1>
  <p class="addr">📍 {html.escape(addr)}</p>
  <p class="desc">{html.escape(br or desc)}</p>
  <p class="meta">종합 스릴 지수 {html.escape(str(th))}.0 · {html.escape(SITE_NAME)}</p>
  <div class="tags">{''.join(f'<span class="tag">{html.escape(str(t))}</span>' for t in tags[:8])}</div>
  <a class="btn" href="{html.escape(app_url)}">상세 보기 · 생존 가이드</a>
  <a class="btn btn-ghost" href="{html.escape(base + '/')}">← {html.escape(SITE_NAME)} 홈</a>
  <footer>
    <p>{html.escape(SITE_NAME)} — 전국 하드코어 액티비티 스팟 지도</p>
    <p><a href="{html.escape(base + '/sitemap.xml')}">사이트맵</a></p>
  </footer>
</div>
</body>
</html>"""


def inject_home_seo(html_text: str, base_url: str, google_verification: str = "", naver_verification: str = "") -> str:
    # DO NOT REMOVE: google-site-verification / naver-site-verification meta tags (Search Console)
    base = base_url.rstrip("/")
    extra = []
    if google_verification:
        extra.append(
            f'<meta name="google-site-verification" content="{html.escape(google_verification)}"/>'
        )
    if naver_verification:
        extra.append(
            f'<meta name="naver-site-verification" content="{html.escape(naver_verification)}"/>'
        )
    block = "\n".join(
        [
            '<meta name="robots" content="index,follow,max-image-preview:large"/>',
            f'<meta name="description" content="{html.escape(DEFAULT_DESCRIPTION)}"/>',
            f'<meta name="keywords" content="{html.escape(DEFAULT_KEYWORDS)}"/>',
            f'<link rel="canonical" href="{html.escape(base + "/")}"/>',
            f'<link rel="alternate" type="application/rss+xml" title="{html.escape(SITE_NAME)}" href="{html.escape(base + "/rss.xml")}"/>',
            '<meta property="og:type" content="website"/>',
            f'<meta property="og:site_name" content="{html.escape(SITE_NAME)}"/>',
            f'<meta property="og:title" content="{html.escape(SITE_NAME)} ⚡"/>',
            f'<meta property="og:description" content="{html.escape(DEFAULT_DESCRIPTION)}"/>',
            f'<meta property="og:url" content="{html.escape(base + "/")}"/>',
            f'<meta property="og:image" content="{html.escape(base + "/assets/og-default.jpg")}"/>',
            '<meta property="og:image:width" content="1200"/>',
            '<meta property="og:image:height" content="630"/>',
            '<meta property="og:locale" content="ko_KR"/>',
            '<meta name="twitter:card" content="summary_large_image"/>',
            f'<meta name="twitter:title" content="{html.escape(SITE_NAME)}"/>',
            f'<meta name="twitter:description" content="{html.escape(DEFAULT_DESCRIPTION)}"/>',
            f'<meta name="twitter:image" content="{html.escape(base + "/assets/og-default.jpg")}"/>',
            # TODO(011): 스팟별 동적 og:image — 백엔드 spot 페이지 렌더에서 커버 이미지 주입 필요
            *extra,
            f"""<script type="application/ld+json">{json.dumps({
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": SITE_NAME,
                "url": base + "/",
                "description": DEFAULT_DESCRIPTION,
                "inLanguage": "ko-KR",
            }, ensure_ascii=False)}</script>""",
        ]
    )
    marker = "<title>"
    if marker not in html_text:
        return html_text
    return html_text.replace(marker, block + "\n" + marker, 1)
