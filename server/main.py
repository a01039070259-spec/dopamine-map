import base64
import json
import os
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from server.auth import (
    clear_auth_cookie,
    create_token,
    get_user_from_request,
    require_user,
    set_auth_cookie,
)
from server.seo import (
    build_robots_txt,
    build_sitemap_xml,
    build_spot_page_html,
    inject_home_seo,
)
from server.database import (
    clear_all_login_data,
    create_review,
    create_spot,
    delete_spot,
    get_admin_stats,
    get_persistence_info,
    get_spot,
    get_spot_detail,
    get_spot_image_data,
    get_venue_image_data,
    get_user_by_id,
    init_db,
    list_spots,
    record_visit,
    update_spot,
    update_user_diagnosis,
    update_venue,
    upsert_kakao_user,
)
from server.venues import get_venue, list_venues

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1111")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "")
KAKAO_REDIRECT_URI = os.getenv(
    "KAKAO_REDIRECT_URI",
    "https://dopamine-map.onrender.com/auth/kakao/callback",
)
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://dopamine-map.onrender.com")
# SEO: Search Console / 네이버 소유확인 — 코드 정리·리팩터 시 삭제 금지 (see .cursor/rules/seo-verification.mdc)
GOOGLE_SITE_VERIFICATION = os.getenv(
    "GOOGLE_SITE_VERIFICATION",
    "myCeWNY3QMXhBpvuo_WKHnf6qCDLOx6gBNb2iNnqEdw",
)
NAVER_SITE_VERIFICATION = os.getenv(
    "NAVER_SITE_VERIFICATION",
    "7b004530b3cb9a6352464fe49a6958b2a6916670",
)


def login_fail_redirect(reason: str) -> RedirectResponse:
    return RedirectResponse(
        f"{APP_BASE_URL}/index.html?login=fail&reason={urllib.parse.quote(reason)}"
    )

app = FastAPI(title="Dopamine Map API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


def verify_admin(
    x_admin_password: Optional[str] = Header(default=None, alias="X-Admin-Password"),
) -> None:
    if not x_admin_password or x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="관리자 인증 실패")


def is_admin(x_admin_password: Optional[str]) -> bool:
    return bool(x_admin_password and x_admin_password == ADMIN_PASSWORD)


def encode_oauth_state(next_path: str) -> str:
    raw = json.dumps({"next": next_path}, ensure_ascii=False)
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_oauth_state(state: str) -> str:
    try:
        data = json.loads(base64.urlsafe_b64decode(state.encode()).decode())
        nxt = data.get("next") or "/index.html"
        return nxt if nxt.startswith("/") else "/index.html"
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return "/index.html"


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    info = get_persistence_info()
    return {"ok": True, **info}


@app.post("/api/admin/verify")
def admin_verify(_: None = Depends(verify_admin)):
    return {"ok": True}


@app.get("/api/admin/stats")
def api_admin_stats(_: None = Depends(verify_admin)):
    return get_admin_stats()


@app.post("/api/admin/clear-login-data")
def api_admin_clear_login_data(_: None = Depends(verify_admin)):
    return clear_all_login_data()


@app.post("/api/admin/geocode")
def api_admin_geocode(payload: dict, _: None = Depends(verify_admin)):
    if not KAKAO_REST_API_KEY:
        raise HTTPException(status_code=500, detail="KAKAO_REST_API_KEY가 설정되지 않았습니다")

    raw_queries = payload.get("queries") or payload.get("query") or []
    if isinstance(raw_queries, str):
        raw_queries = [raw_queries]
    queries = [str(q).strip() for q in raw_queries if str(q).strip()]
    raw_keywords = payload.get("keywords") or []
    if isinstance(raw_keywords, str):
        raw_keywords = [raw_keywords]
    keywords = [str(k).strip() for k in raw_keywords if str(k).strip()]
    if not queries and not keywords:
        raise HTTPException(status_code=400, detail="queries가 필요합니다")

    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    with httpx.Client(timeout=12.0) as client:
        for query in queries:
            hit = _kakao_geocode_query(client, headers, query, "address")
            if hit:
                hit["query"] = query
                return hit
        for query in queries:
            hit = _kakao_geocode_query(client, headers, query, "keyword", size=3)
            if hit:
                hit["query"] = query
                return hit
        for keyword in keywords:
            hit = _kakao_geocode_query(client, headers, keyword, "keyword", size=5)
            if hit:
                hit["query"] = keyword
                hit["source"] = "keyword-name"
                return hit

    raise HTTPException(status_code=404, detail="주소를 찾을 수 없습니다")


def _kakao_geocode_query(
    client: httpx.Client,
    headers: dict[str, str],
    query: str,
    mode: str,
    size: int = 1,
) -> Optional[dict]:
    path = "search/address.json" if mode == "address" else "search/keyword.json"
    params = {"query": query}
    if mode == "keyword":
        params["size"] = str(size)
    try:
        res = client.get(
            f"https://dapi.kakao.com/v2/local/{path}",
            params=params,
            headers=headers,
        )
        if res.status_code >= 400:
            return None
        docs = res.json().get("documents") or []
        if not docs:
            return None
        doc = docs[0]
        return {
            "lat": float(doc["y"]),
            "lng": float(doc["x"]),
            "source": path,
            "label": doc.get("place_name") or doc.get("address_name") or query,
        }
    except (httpx.HTTPError, ValueError, KeyError):
        return None


@app.get("/api/auth/me")
def api_auth_me(request: Request):
    user = get_user_from_request(request)
    if not user:
        return {"loggedIn": False, "user": None}
    db_user = get_user_by_id(user["id"])
    if db_user:
        return {
            "loggedIn": True,
            "user": {
                "id": db_user["id"],
                "nickname": db_user["nickname"],
                "diagnosisResult": db_user.get("diagnosisResult"),
            },
        }
    return {"loggedIn": True, "user": user}


@app.get("/api/auth/status")
def api_auth_status():
    key = KAKAO_REST_API_KEY or ""
    return {
        "kakaoConfigured": bool(key),
        "redirectUri": KAKAO_REDIRECT_URI,
        "clientSecretConfigured": bool(KAKAO_CLIENT_SECRET),
        "restKeySuffix": key[-4:] if len(key) >= 4 else "",
    }


@app.get("/auth/kakao/login")
def kakao_login(next: str = "/index.html"):
    if not KAKAO_REST_API_KEY:
        return login_fail_redirect("KAKAO_REST_API_KEY_missing")
    safe_next = next if next.startswith("/") else "/index.html"
    state = encode_oauth_state(safe_next)
    oauth_params = {
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "response_type": "code",
        "state": state,
    }
    # KOE205 방지: 카카오 콘솔 [동의항목]에서 닉네임 활성화 후에만 scope 요청
    if os.getenv("KAKAO_NICKNAME_SCOPE", "").lower() in ("1", "true", "yes"):
        oauth_params["scope"] = "profile_nickname"
    params = urllib.parse.urlencode(oauth_params)
    return RedirectResponse(f"https://kauth.kakao.com/oauth/authorize?{params}")


@app.get("/auth/kakao/callback")
def kakao_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error:
        return login_fail_redirect(error)
    if not code:
        return login_fail_redirect("no_code")
    if not KAKAO_REST_API_KEY:
        raise HTTPException(status_code=500, detail="KAKAO_REST_API_KEY가 설정되지 않았습니다")

    token_data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
    }
    if KAKAO_CLIENT_SECRET:
        token_data["client_secret"] = KAKAO_CLIENT_SECRET

    with httpx.Client(timeout=15.0) as client:
        token_res = client.post(
            "https://kauth.kakao.com/oauth/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_res.status_code >= 400:
            detail = token_res.text[:120] if token_res.text else "token_error"
            return login_fail_redirect(detail)
        token_json = token_res.json()
        access_token = token_json.get("access_token")
        if not access_token:
            return login_fail_redirect("no_access_token")

        user_res = client.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_res.status_code >= 400:
            return login_fail_redirect("user_info_error")
        profile = user_res.json()

    kakao_id = str(profile.get("id"))
    props = profile.get("properties") or {}
    kakao_account = profile.get("kakao_account") or {}
    kakao_profile = kakao_account.get("profile") or {}
    nickname = (
        (kakao_profile.get("nickname") or props.get("nickname") or "").strip()
    )
    if not nickname:
        nickname = f"유저{kakao_id[-4:]}"
    user = upsert_kakao_user(kakao_id, nickname)
    token = create_token(user["id"], kakao_id, user["nickname"])
    record_visit(user["id"])

    next_path = decode_oauth_state(state or "")
    response = RedirectResponse(f"{APP_BASE_URL}{next_path}{'&' if '?' in next_path else '?'}login=ok")
    set_auth_cookie(response, token)
    return response


@app.post("/auth/logout")
def auth_logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}


@app.post("/api/visits")
def api_record_visit(request: Request):
    user = get_user_from_request(request)
    record_visit(user["id"] if user else None)
    return {"ok": True}


@app.get("/api/spots")
def api_list_spots():
    return list_spots()


@app.get("/api/venues")
def api_list_venues():
    return list_venues()


@app.get("/api/venues/{venue_id}")
def api_get_venue(venue_id: int):
    venue = get_venue(venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="장소를 찾을 수 없습니다")
    return venue


@app.get("/api/venues/{venue_id}/image")
def api_venue_image(venue_id: int):
    data = get_venue_image_data(venue_id)
    if not data:
        raise HTTPException(status_code=404, detail="이미지가 없습니다")
    content, media_type = data
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


@app.put("/api/venues/{venue_id}")
def api_update_venue(venue_id: int, payload: dict, _: None = Depends(verify_admin)):
    venue = update_venue(venue_id, payload)
    if not venue:
        raise HTTPException(status_code=404, detail="장소를 찾을 수 없습니다")
    return venue


@app.get("/api/spots/{spot_id}/image")
def api_spot_image(spot_id: int):
    data = get_spot_image_data(spot_id)
    if not data:
        raise HTTPException(status_code=404, detail="이미지가 없습니다")
    content, media_type = data
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


@app.get("/api/spots/{spot_id}")
def api_get_spot(
    spot_id: int,
    request: Request,
    x_admin_password: Optional[str] = Header(default=None, alias="X-Admin-Password"),
):
    if not is_admin(x_admin_password):
        require_user(request)
    spot = get_spot_detail(spot_id)
    if not spot:
        raise HTTPException(status_code=404, detail="스팟을 찾을 수 없습니다")
    return spot


@app.post("/api/spots")
def api_create_spot(payload: dict, _: None = Depends(verify_admin)):
    required = ("name", "addr", "lat", "lng")
    for key in required:
        if payload.get(key) in (None, ""):
            raise HTTPException(status_code=400, detail=f"필수 항목 누락: {key}")
    return create_spot(payload)


@app.put("/api/spots/{spot_id}")
def api_update_spot(spot_id: int, payload: dict, _: None = Depends(verify_admin)):
    spot = update_spot(spot_id, payload)
    if not spot:
        raise HTTPException(status_code=404, detail="스팟을 찾을 수 없습니다")
    return spot


@app.delete("/api/spots/{spot_id}")
def api_delete_spot(spot_id: int, _: None = Depends(verify_admin)):
    if not delete_spot(spot_id):
        raise HTTPException(status_code=404, detail="스팟을 찾을 수 없습니다")
    return {"ok": True}


@app.post("/api/reviews")
def api_create_review(payload: dict, request: Request):
    user = require_user(request)
    spot_id = payload.get("spot_id")
    content = (payload.get("content") or payload.get("text") or "").strip()
    if not spot_id:
        raise HTTPException(status_code=400, detail="spot_id가 필요합니다")
    if len(content) < 10:
        raise HTTPException(status_code=400, detail="리뷰는 10자 이상 입력해 주세요")
    if not get_spot(int(spot_id)):
        raise HTTPException(status_code=404, detail="스팟을 찾을 수 없습니다")
    review = create_review(payload, user["id"], user["nickname"])
    return review


@app.post("/api/diagnosis")
def api_save_diagnosis(payload: dict, request: Request):
    user = require_user(request)
    result = (payload.get("result") or "").strip()
    if not result:
        raise HTTPException(status_code=400, detail="result가 필요합니다")
    updated = update_user_diagnosis(user["id"], result)
    return {"ok": True, "result": updated["diagnosisResult"] if updated else result}


@app.get("/api/diagnosis")
def api_get_diagnosis(request: Request):
    user = require_user(request)
    db_user = get_user_by_id(user["id"])
    if not db_user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    return {"result": db_user.get("diagnosisResult")}


def _home_html() -> str:
    index_path = ROOT / "index.html"
    html_text = index_path.read_text(encoding="utf-8")
    return inject_home_seo(
        html_text,
        APP_BASE_URL,
        GOOGLE_SITE_VERIFICATION,
        NAVER_SITE_VERIFICATION,
    )


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return PlainTextResponse(
        build_robots_txt(APP_BASE_URL),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/sitemap.xml", response_class=PlainTextResponse)
def sitemap_xml():
    spots = list_spots()
    return PlainTextResponse(
        build_sitemap_xml(APP_BASE_URL, spots),
        media_type="application/xml; charset=utf-8",
    )


@app.get("/spot/{spot_id}", response_class=HTMLResponse)
def spot_landing(spot_id: int):
    spot = get_spot(spot_id)
    if not spot or not spot.get("approved", True):
        raise HTTPException(status_code=404, detail="스팟을 찾을 수 없습니다")
    return HTMLResponse(build_spot_page_html(spot, APP_BASE_URL))


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def serve_home():
    return HTMLResponse(_home_html())


app.mount("/", StaticFiles(directory=str(ROOT), html=True), name="site")
