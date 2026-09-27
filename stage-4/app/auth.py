from __future__ import annotations
from typing import Optional
from fastapi import Request

from app.models import ApiError
from app.store import store

async def get_current_user_optional(request: Request) -> Optional[dict]:
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    if not token:
        cookie_token = request.cookies.get("token")
        if cookie_token:
            token = cookie_token
    if not token:
        return None
    user_id = store.tokens.get(token)
    if not user_id:
        return None
    return store.find_user_by_id(user_id)

async def get_current_user(request: Request) -> dict:
    user = await get_current_user_optional(request)
    if not user:
        raise ApiError(401, "unauthenticated", "Invalid or missing token")
    return user
