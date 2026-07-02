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
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from server.auth import (
    clear_auth_cookie,
    create_token,
    get_user_from_request,
    require_user,
    set_auth_cookie,
)
from server.database import (
    create_review,
    create_spot,
    delete_spot,
    get_admin_stats,
    get_spot,
    get_spot_detail,
    get_user_by_id,
    init_db,
    list_spots,
    record_visit,
    update_spot,
    update_user_diagnosis,
    upsert_kakao_user,
)

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
    return {"ok": True}


@app.post("/api/admin/verify")
def admin_verify(_: None = Depends(verify_admin)):
    return {"ok": True}


@app.get("/api/admin/stats")
def api_admin_stats(_: None = Depends(verify_admin)):
    return get_admin_stats()


@app.get("/api/auth/me")
def api_auth_me(request: Request):
    user = get_user_from_request(request)
    if not user:
        return {"loggedIn": False, "user": None}
    return {"loggedIn": True, "user": user}


@app.get("/api/auth/status")
def api_auth_status():
    return {
        "kakaoConfigured": bool(KAKAO_REST_API_KEY),
        "redirectUri": KAKAO_REDIRECT_URI,
    }


@app.get("/auth/kakao/login")
def kakao_login(next: str = "/index.html"):
    if not KAKAO_REST_API_KEY:
        return login_fail_redirect("KAKAO_REST_API_KEY_missing")
    safe_next = next if next.startswith("/") else "/index.html"
    state = encode_oauth_state(safe_next)
    params = urllib.parse.urlencode(
        {
            "client_id": KAKAO_REST_API_KEY,
            "redirect_uri": KAKAO_REDIRECT_URI,
            "response_type": "code",
            "state": state,
        }
    )
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
    nickname = props.get("nickname") or "카카오유저"
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


app.mount("/", StaticFiles(directory=str(ROOT), html=True), name="site")
