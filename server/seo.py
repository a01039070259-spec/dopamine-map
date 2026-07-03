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
        (f"{base}/diagnosis.html", "monthly", "0.6"),
    ]
    for spot in spots:
        if not spot.get("approved", True):
            continue
        sid = spot.get("id")
        if not sid:
            continue
        urls.append((f"{base}/spot/{sid}", "weekly", "0.8"))

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
<meta name="keywords" content="{html.escape(keywords)}"/>
<link rel="canonical" href="{html.escape(page_url)}"/>
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="{html.escape(SITE_NAME)}"/>
<meta property="og:title" content="{html.escape(title)}"/>
<meta property="og:description" content="{html.escape(desc)}"/>
<meta property="og:url" content="{html.escape(page_url)}"/>
<meta property="og:locale" content="ko_KR"/>
<meta name="twitter:card" content="summary"/>
<meta name="twitter:title" content="{html.escape(title)}"/>
<meta name="twitter:description" content="{html.escape(desc)}"/>
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
            f'<meta name="description" content="{html.escape(DEFAULT_DESCRIPTION)}"/>',
            f'<meta name="keywords" content="{html.escape(DEFAULT_KEYWORDS)}"/>',
            f'<link rel="canonical" href="{html.escape(base + "/")}"/>',
            '<meta property="og:type" content="website"/>',
            f'<meta property="og:site_name" content="{html.escape(SITE_NAME)}"/>',
            f'<meta property="og:title" content="{html.escape(SITE_NAME)} ⚡"/>',
            f'<meta property="og:description" content="{html.escape(DEFAULT_DESCRIPTION)}"/>',
            f'<meta property="og:url" content="{html.escape(base + "/")}"/>',
            '<meta property="og:locale" content="ko_KR"/>',
            '<meta name="twitter:card" content="summary_large_image"/>',
            f'<meta name="twitter:title" content="{html.escape(SITE_NAME)}"/>',
            f'<meta name="twitter:description" content="{html.escape(DEFAULT_DESCRIPTION)}"/>',
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
