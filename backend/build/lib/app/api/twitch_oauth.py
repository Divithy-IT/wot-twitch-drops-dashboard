import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, mutation_admin
from app.config import get_settings
from app.database import get_db
from app.models import Admin, EventLog, TwitchConnection
from app.security import decrypt_token, encrypt_token, serializer
from app.services.twitch import TwitchClient, TwitchError, oauth_expiry

router = APIRouter(prefix="/oauth/twitch", tags=["twitch"])
client = TwitchClient()


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    conn = await db.scalar(select(TwitchConnection))
    if not conn: return {"connected": False, "api_limitation": True}
    return {"connected": True, "login": conn.login, "scopes": conn.scopes,
            "expires_at": conn.expires_at, "last_synced_at": conn.last_synced_at, "api_limitation": True}


@router.get("/connect")
async def connect(_: Admin = Depends(current_admin)):
    if not get_settings().twitch_client_id: raise HTTPException(503, "Najpierw skonfiguruj Twitch Client ID")
    nonce = secrets.token_urlsafe(24)
    state = serializer().dumps({"nonce": nonce}, salt="twitch-oauth")
    response = RedirectResponse(client.authorization_url(state))
    response.set_cookie("wot_oauth_state", nonce, httponly=True, secure=get_settings().secure_cookies,
                        samesite="lax", path=get_settings().base_path or "/", max_age=600)
    return response


@router.get("/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = "",
                   db: AsyncSession = Depends(get_db)):
    if error: return RedirectResponse(f"{get_settings().base_path}/settings?oauth=denied")
    try: decoded = serializer().loads(state, salt="twitch-oauth", max_age=600)
    except Exception as exc: raise HTTPException(400, "Nieprawidłowy stan OAuth") from exc
    if not secrets.compare_digest(decoded.get("nonce", ""), request.cookies.get("wot_oauth_state", "")):
        raise HTTPException(400, "Nieprawidłowy stan OAuth")
    try:
        token = await client.exchange(code); profile = await client.user(token["access_token"])
    except TwitchError as exc: raise HTTPException(502, str(exc)) from exc
    await db.execute(delete(TwitchConnection))
    db.add(TwitchConnection(id=1, twitch_user_id=profile["id"], login=profile["login"],
        access_token_encrypted=encrypt_token(token["access_token"]),
        refresh_token_encrypted=encrypt_token(token.get("refresh_token", "")),
        scopes=token.get("scope", []), expires_at=oauth_expiry(token), last_synced_at=datetime.now(UTC)))
    db.add(EventLog(event_type="twitch_connected", message=f"Połączono konto Twitch: {profile['login']}"))
    await db.commit()
    return RedirectResponse(f"{get_settings().base_path}/settings?oauth=connected")


@router.post("/disconnect")
async def disconnect(db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    await db.execute(delete(TwitchConnection)); db.add(EventLog(event_type="twitch_disconnected", level="warning", message="Odłączono konto Twitch")); await db.commit(); return {"ok": True}


@router.post("/sync")
async def sync(db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    conn = await db.scalar(select(TwitchConnection))
    if not conn: raise HTTPException(409, "Konto Twitch nie jest połączone")
    try:
        data = await client.validate(decrypt_token(conn.access_token_encrypted)); conn.scopes = data.get("scopes", [])
        conn.last_synced_at = datetime.now(UTC); await db.commit()
    except TwitchError as exc:
        db.add(EventLog(event_type="twitch_sync_error", level="error", message=str(exc))); await db.commit()
        raise HTTPException(502, str(exc)) from exc
    return {"ok": True, "note": "Twitch nie udostępnia widzowi postępu Drops przez Helix API."}
