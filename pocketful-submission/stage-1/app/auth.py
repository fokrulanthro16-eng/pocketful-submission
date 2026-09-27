from __future__ import annotations
from typing import Optional
from fastapi import Request

from app.models import ApiError
from app.store import store

async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise ApiError(401, "unauthenticated", "Missing Authorization header")
    parts = auth_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise ApiError(401, "unauthenticated", "Invalid Authorization header format")
    token = parts[1]
    user_id = store.tokens.get(token)
    if not user_id:
        raise ApiError(401, "unauthenticated", "Invalid or unknown token")
    user = store.find_user_by_id(user_id)
    if not user:
        raise ApiError(401, "unauthenticated", "User not found")
    return user
