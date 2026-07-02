import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import HTTPException, Request, Response

JWT_SECRET = os.getenv("JWT_SECRET", "dopamine-map-dev-secret-change-me")
JWT_ALG = "HS256"
JWT_DAYS = 30
COOKIE_NAME = "dopamine_session"


def create_token(user_id: int, kakao_id: str, nickname: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "kakao_id": kakao_id,
        "nickname": nickname,
        "iat": now,
        "exp": now + timedelta(days=JWT_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다") from exc


def get_user_from_request(request: Request) -> Optional[dict[str, Any]]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = decode_token(token)
    except HTTPException:
        return None
    return {
        "id": int(payload["sub"]),
        "kakao_id": payload.get("kakao_id", ""),
        "nickname": payload.get("nickname", ""),
    }


def require_user(request: Request) -> dict[str, Any]:
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    return user


def set_auth_cookie(response: Response, token: str) -> None:
    secure = os.getenv("APP_BASE_URL", "").startswith("https://")
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=JWT_DAYS * 24 * 3600,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    secure = os.getenv("APP_BASE_URL", "").startswith("https://")
    response.delete_cookie(key=COOKIE_NAME, path="/", secure=secure)
