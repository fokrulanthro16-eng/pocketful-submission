from __future__ import annotations
import asyncio
import copy
import hashlib
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models import ApiError

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ":" + key.hex()

def verify_password(password: str, hashed: str) -> bool:
    try:
        parts = hashed.split(":")
        if len(parts) != 2:
            return False
        salt = bytes.fromhex(parts[0])
        key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
        return secrets.compare_digest(key.hex(), parts[1])
    except Exception:
        return False

def current_time_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat()

def derive_handle(email: str) -> str:
    local_part = email.split("@")[0].lower()
    clean = re.sub(r"[^a-z0-9_]", "_", local_part)
    return clean[:20]

def validate_amount(val: Any) -> int:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ApiError(422, "validation_failed", "amount must be an integral number")
    if isinstance(val, float):
        if not val.is_integer():
            raise ApiError(422, "validation_failed", "amount must be an integer count of minor units")
        val = int(val)
    if val < 1 or val > 1_000_000_000:
        raise ApiError(422, "validation_failed", "amount out of range")
    return val

class DataStore:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.currency: str = "EUR"
        self.minor_units: int = 2
        self.users: Dict[str, dict] = {}               # user_id -> user dict
        self.tokens: Dict[str, str] = {}              # token -> user_id
        self.payments: List[dict] = []                # list of payment dicts
        self.requests: Dict[str, dict] = {}           # request_id -> request dict
        self.splits: Dict[str, dict] = {}             # split_id -> split dict
        self.settlement_operator_ids: Set[str] = set()
        # (user_id, method, path, key) -> {"body": ..., "status_code": ..., "response": ...}
        self.idempotency_records: Dict[Tuple[str, str, str, str], dict] = {}
        self.id_counter: int = 0

    def next_id(self, prefix: str) -> str:
        self.id_counter += 1
        return f"{prefix}_{secrets.token_hex(6)}"

    def find_user_by_id(self, user_id: str) -> Optional[dict]:
        return self.users.get(user_id)

    def find_user_by_handle(self, handle: str) -> Optional[dict]:
        for u in self.users.values():
            if u["handle"] == handle:
                return u
        return None

    def find_user_by_email(self, email: str) -> Optional[dict]:
        email_lower = email.lower()
        for u in self.users.values():
            if u["email"].lower() == email_lower:
                return u
        return None

    def reset_fixture(self, fixture: dict):
        if not isinstance(fixture, dict):
            raise ApiError(400, "malformed_request", "Fixture must be an object")
        
        currency = fixture.get("currency", "EUR")
        minor_units = fixture.get("minor_units", 2)
        users_list = fixture.get("users", [])
        payments_list = fixture.get("payments", [])
        requests_list = fixture.get("requests", [])
        operator_ids = fixture.get("settlement_operator_ids", [])

        # Validate users balances
        for u in users_list:
            if u.get("balance", 0) < 0:
                raise ApiError(422, "validation_failed", "User balance cannot be negative")

        self.currency = currency
        self.minor_units = minor_units
        self.users.clear()
        self.tokens.clear()
        self.payments.clear()
        self.requests.clear()
        self.splits.clear()
        self.settlement_operator_ids = set(operator_ids)
        self.idempotency_records.clear()
        self.id_counter = 0

        for u in users_list:
            user_id = u["id"]
            pwd = u["password"]
            hashed_pwd = hash_password(pwd)
            self.users[user_id] = {
                "id": user_id,
                "email": u["email"],
                "password_hash": hashed_pwd,
                "display_name": u.get("display_name", u["handle"].title()),
                "handle": u["handle"],
                "balance": u["balance"]
            }
            # Pre-generate a token for convenience
            token = f"tok_{user_id}_{secrets.token_hex(16)}"
            self.tokens[token] = user_id

        for p in payments_list:
            from_u = self.users.get(p.get("from_user_id"))
            to_u = self.users.get(p.get("to_user_id"))
            payment = {
                "payment_id": p["id"],
                "from_user_id": p["from_user_id"],
                "from_handle": from_u["handle"] if from_u else "",
                "to_user_id": p["to_user_id"],
                "to_handle": to_u["handle"] if to_u else "",
                "amount": p["amount"],
                "currency": self.currency,
                "note": p.get("note", ""),
                "visibility": p.get("visibility", "public"),
                "request_id": p.get("request_id"),
                "settlement_id": p.get("settlement_id"),
                "created_at": p.get("created_at") or current_time_rfc3339()
            }
            self.payments.append(payment)

        for r in requests_list:
            req_u = self.users.get(r.get("requester_id"))
            pay_u = self.users.get(r.get("payer_id"))
            req_id = r["id"]
            self.requests[req_id] = {
                "request_id": req_id,
                "requester_id": r["requester_id"],
                "requester_handle": req_u["handle"] if req_u else "",
                "payer_id": r["payer_id"],
                "payer_handle": pay_u["handle"] if pay_u else "",
                "amount": r["amount"],
                "currency": self.currency,
                "note": r.get("note", ""),
                "status": r.get("status", "pending"),
                "payment_id": r.get("payment_id"),
                "created_at": r.get("created_at") or current_time_rfc3339()
            }

    def export_state(self) -> dict:
        return {
            "track": "pocketful",
            "format_version": 1,
            "state": {
                "currency": self.currency,
                "minor_units": self.minor_units,
                "users": list(self.users.values()),
                "tokens": self.tokens,
                "payments": self.payments,
                "requests": self.requests,
                "splits": self.splits,
                "settlement_operator_ids": list(self.settlement_operator_ids),
                "idempotency_records": [
                    {
                        "user_id": k[0],
                        "method": k[1],
                        "path": k[2],
                        "key": k[3],
                        "record": v
                    }
                    for k, v in self.idempotency_records.items()
                ],
                "id_counter": self.id_counter
            }
        }

    def import_state(self, data: dict):
        if not isinstance(data, dict):
            raise ApiError(422, "validation_failed", "Import data must be a JSON object")
        if data.get("track") != "pocketful" or data.get("format_version") != 1:
            raise ApiError(422, "validation_failed", "Unsupported track or format version")
        state = data.get("state")
        if not isinstance(state, dict):
            raise ApiError(422, "validation_failed", "Invalid state format")

        self.currency = state["currency"]
        self.minor_units = state["minor_units"]
        self.users = {u["id"]: u for u in state.get("users", [])}
        self.tokens = copy.deepcopy(state.get("tokens", {}))
        self.payments = copy.deepcopy(state.get("payments", []))
        self.requests = copy.deepcopy(state.get("requests", {}))
        self.splits = copy.deepcopy(state.get("splits", {}))
        self.settlement_operator_ids = set(state.get("settlement_operator_ids", []))
        self.id_counter = state.get("id_counter", 0)
        self.idempotency_records.clear()
        for item in state.get("idempotency_records", []):
            k = (item["user_id"], item["method"], item["path"], item["key"])
            self.idempotency_records[k] = item["record"]

store = DataStore()
