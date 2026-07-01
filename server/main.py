import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.database import (
    create_spot,
    delete_spot,
    get_spot,
    init_db,
    list_spots,
    update_spot,
)

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1111")

app = FastAPI(title="Dopamine Map API", version="1.0.0")

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


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/admin/verify")
def admin_verify(_: None = Depends(verify_admin)):
    return {"ok": True}


@app.get("/api/spots")
def api_list_spots():
    return list_spots()


@app.get("/api/spots/{spot_id}")
def api_get_spot(spot_id: int):
    spot = get_spot(spot_id)
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


app.mount("/", StaticFiles(directory=str(ROOT), html=True), name="site")
