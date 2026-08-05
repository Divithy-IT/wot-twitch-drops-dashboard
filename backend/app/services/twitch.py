from datetime import UTC, datetime

import httpx

from app.config import get_settings


class TwitchError(RuntimeError):
    pass


class TwitchClient:
    authorize_url = "https://id.twitch.tv/oauth2/authorize"
    token_url = "https://id.twitch.tv/oauth2/token"
    validate_url = "https://id.twitch.tv/oauth2/validate"
    api_url = "https://api.twitch.tv/helix"

    def authorization_url(self, state: str) -> str:
        s = get_settings()
        return str(httpx.URL(self.authorize_url, params={
            "client_id": s.twitch_client_id, "redirect_uri": s.twitch_redirect_uri,
            "response_type": "code", "scope": "", "state": state,
        }))

    async def exchange(self, code: str) -> dict:
        s = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(self.token_url, params={
                "client_id": s.twitch_client_id, "client_secret": s.twitch_client_secret,
                "code": code, "grant_type": "authorization_code", "redirect_uri": s.twitch_redirect_uri,
            })
        if response.is_error:
            raise TwitchError(f"Wymiana kodu OAuth nie powiodła się ({response.status_code})")
        return response.json()

    async def refresh(self, refresh_token: str) -> dict:
        s = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(self.token_url, params={
                "client_id": s.twitch_client_id, "client_secret": s.twitch_client_secret,
                "grant_type": "refresh_token", "refresh_token": refresh_token,
            })
        if response.is_error:
            raise TwitchError(f"Odświeżenie tokenu nie powiodło się ({response.status_code})")
        return response.json()

    async def validate(self, access_token: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(self.validate_url, headers={"Authorization": f"OAuth {access_token}"})
        if response.is_error:
            raise TwitchError("Token Twitch jest nieważny lub został cofnięty")
        return response.json()

    async def user(self, access_token: str) -> dict:
        s = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{self.api_url}/users", headers={
                "Authorization": f"Bearer {access_token}", "Client-Id": s.twitch_client_id,
            })
        if response.is_error or not response.json().get("data"):
            raise TwitchError("Nie udało się pobrać profilu Twitch")
        return response.json()["data"][0]

    async def stream(self, access_token: str, channel: str) -> dict | None:
        s = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{self.api_url}/streams", params={"user_login": channel}, headers={
                "Authorization": f"Bearer {access_token}", "Client-Id": s.twitch_client_id,
            })
        if response.is_error:
            raise TwitchError(f"Sprawdzenie kanału nie powiodło się ({response.status_code})")
        rows = response.json().get("data", [])
        return rows[0] if rows else None


def oauth_expiry(payload: dict) -> datetime:
    return datetime.fromtimestamp(datetime.now(UTC).timestamp() + payload["expires_in"], UTC)
