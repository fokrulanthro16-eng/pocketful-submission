from __future__ import annotations
import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import os
import re
import secrets
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

def parse_rfc3339_with_offset(val: Any) -> datetime:
    if not isinstance(val, str) or not val.strip():
        raise ApiError(422, "validation_failed", "Timestamp must be a non-empty RFC 3339 string with offset")
    if "T" not in val and "t" not in val:
        raise ApiError(422, "validation_failed", "Timestamp must contain a time component")
    s = val.replace("Z", "+00:00").replace("z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            raise ApiError(422, "validation_failed", "Timestamp must include timezone offset")
        return dt
    except Exception:
        raise ApiError(422, "validation_failed", "Invalid RFC 3339 timestamp")

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
        self.authorization_ttl_seconds: int = 600
        self.users: Dict[str, dict] = {}               # user_id -> user dict
        self.tokens: Dict[str, str] = {}              # token -> user_id
        self.payments: List[dict] = []                # list of payment dicts
        self.requests: Dict[str, dict] = {}           # request_id -> request dict
        self.splits: Dict[str, dict] = {}             # split_id -> split dict
        self.authorizations: Dict[str, dict] = {}     # authorization_id -> auth dict
        self.settlement_operator_ids: Set[str] = set()
        self.idempotency_records: Dict[Tuple[str, str, str, str], dict] = {}
        self.statement_snapshots: Dict[str, dict] = {} # token -> snapshot dict
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

    def get_auth_status(self, auth: dict) -> str:
        status = auth.get("status", "open")
        if status == "open":
            exp_str = auth.get("expires_at")
            if exp_str:
                exp = parse_rfc3339_with_offset(exp_str)
                now = datetime.now(timezone.utc)
                if exp <= now:
                    return "expired"
        return status

    def get_user_balances(self, user_id: str) -> tuple[int, int, int]:
        user = self.users.get(user_id)
        if not user:
            return 0, 0, 0
        total = user["balance"]
        held = 0
        for a in self.authorizations.values():
            if a["from_user_id"] == user_id and self.get_auth_status(a) == "open":
                held += a.get("remaining_amount", a["amount"] - a.get("captured_amount", 0))
        available = max(0, total - held)
        return total, available, held

    def compute_user_balance_at(self, user_id: str, as_of_dt: datetime, known_at_dt: datetime) -> int:
        user = self.users.get(user_id)
        if not user:
            return 0
        balance = user.get("opening_balance", 0)
        for p in self.payments:
            if p["from_user_id"] != user_id and p["to_user_id"] != user_id:
                continue
            revisions = p.get("revisions", [])
            active_rev = None
            for rev in revisions:
                rec_dt = parse_rfc3339_with_offset(rev["recorded_at"])
                if rec_dt <= known_at_dt:
                    active_rev = rev
            if not active_rev:
                continue
            eff_dt = parse_rfc3339_with_offset(active_rev["effective_at"])
            if eff_dt <= as_of_dt:
                amt = active_rev["amount"]
                if p["from_user_id"] == user_id:
                    balance -= amt
                if p["to_user_id"] == user_id:
                    balance += amt
        return balance

    def compute_user_held_at(self, user_id: str, as_of_dt: datetime, known_at_dt: datetime) -> int:
        total_held = 0
        for a in self.authorizations.values():
            if a["from_user_id"] != user_id:
                continue
            created_dt = parse_rfc3339_with_offset(a["created_at"])
            if created_dt > known_at_dt or created_dt > as_of_dt:
                continue
            exp_str = a.get("expires_at")
            if exp_str:
                exp_dt = parse_rfc3339_with_offset(exp_str)
                if as_of_dt >= exp_dt:
                    continue
            rem = a["amount"]
            events = a.get("events", [])
            if not events:
                closed_at_str = a.get("closed_at")
                if closed_at_str:
                    closed_dt = parse_rfc3339_with_offset(closed_at_str)
                    if closed_dt <= known_at_dt and closed_dt <= as_of_dt:
                        rem = 0
                    else:
                        rem = a.get("remaining_amount", a["amount"] - a.get("captured_amount", 0))
                else:
                    rem = a.get("remaining_amount", a["amount"] - a.get("captured_amount", 0))
            else:
                for ev in events:
                    ev_dt = parse_rfc3339_with_offset(ev["time"])
                    if ev_dt <= known_at_dt and ev_dt <= as_of_dt:
                        if ev["type"] == "captured":
                            if ev.get("final", True):
                                rem = 0
                            else:
                                rem = max(0, rem - ev["captured"])
                        elif ev["type"] == "voided":
                            rem = 0
            total_held += rem
        return total_held

    def check_historical_overdraft(
        self,
        sender_id: str,
        receiver_id: str,
        target_payment: dict,
        tentative_rev: dict
    ):
        now_dt = datetime.now(timezone.utc)
        target_payment["revisions"].append(tentative_rev)
        try:
            boundaries: Set[datetime] = set()
            boundaries.add(now_dt)
            boundaries.add(parse_rfc3339_with_offset(tentative_rev["effective_at"]))
            
            for u_id in (sender_id, receiver_id):
                user = self.users.get(u_id)
                if not user:
                    continue
                for p in self.payments:
                    if p["from_user_id"] == u_id or p["to_user_id"] == u_id:
                        for rev in p.get("revisions", []):
                            eff_dt = parse_rfc3339_with_offset(rev["effective_at"])
                            if eff_dt <= now_dt:
                                boundaries.add(eff_dt)
                for a in self.authorizations.values():
                    if a["from_user_id"] == u_id:
                        c_dt = parse_rfc3339_with_offset(a["created_at"])
                        if c_dt <= now_dt:
                            boundaries.add(c_dt)
                        if a.get("expires_at"):
                            exp_dt = parse_rfc3339_with_offset(a["expires_at"])
                            if exp_dt <= now_dt:
                                boundaries.add(exp_dt)
                        if a.get("closed_at"):
                            cl_dt = parse_rfc3339_with_offset(a["closed_at"])
                            if cl_dt <= now_dt:
                                boundaries.add(cl_dt)
                        for ev in a.get("events", []):
                            ev_dt = parse_rfc3339_with_offset(ev["time"])
                            if ev_dt <= now_dt:
                                boundaries.add(ev_dt)

            sorted_boundaries = sorted(list(boundaries))
            for b_dt in sorted_boundaries:
                for u_id in (sender_id, receiver_id):
                    tot = self.compute_user_balance_at(u_id, as_of_dt=b_dt, known_at_dt=now_dt)
                    hld = self.compute_user_held_at(u_id, as_of_dt=b_dt, known_at_dt=now_dt)
                    avail = tot - hld
                    if tot < 0 or avail < 0:
                        raise ApiError(409, "historical_overdraft", f"Correction would cause historical overdraft for user {u_id}")
        finally:
            target_payment["revisions"].pop()

    def reset_fixture(self, fixture: dict):
        if not isinstance(fixture, dict):
            raise ApiError(400, "malformed_request", "Fixture must be an object")
        
        currency = fixture.get("currency", "EUR")
        minor_units = fixture.get("minor_units", 2)
        ttl = fixture.get("authorization_ttl_seconds", 600)
        users_list = fixture.get("users", [])
        payments_list = fixture.get("payments", [])
        requests_list = fixture.get("requests", [])
        authorizations_list = fixture.get("authorizations", [])
        operator_ids = fixture.get("settlement_operator_ids", [])

        # Validate users balances
        for u in users_list:
            if u.get("balance", 0) < 0:
                raise ApiError(422, "validation_failed", "User balance cannot be negative")

        # Validate seeded payments created_at not in future
        reset_now = datetime.now(timezone.utc)
        reset_now_str = reset_now.isoformat()
        for p in payments_list:
            cat = p.get("created_at")
            if cat:
                p_dt = parse_rfc3339_with_offset(cat)
                if p_dt > reset_now:
                    raise ApiError(422, "validation_failed", "Seeded payment created_at cannot be in the future")

        self.currency = currency
        self.minor_units = minor_units
        self.authorization_ttl_seconds = ttl
        self.users.clear()
        self.tokens.clear()
        self.payments.clear()
        self.requests.clear()
        self.splits.clear()
        self.authorizations.clear()
        self.settlement_operator_ids = set(operator_ids)
        self.idempotency_records.clear()
        self.statement_snapshots.clear()
        self.id_counter = 0

        # Compute net seeded payments per user
        net_seeded: Dict[str, int] = {u["id"]: 0 for u in users_list}
        for p in payments_list:
            amt = p["amount"]
            f_id = p.get("from_user_id")
            t_id = p.get("to_user_id")
            if f_id in net_seeded:
                net_seeded[f_id] -= amt
            if t_id in net_seeded:
                net_seeded[t_id] += amt

        for u in users_list:
            user_id = u["id"]
            pwd = u["password"]
            hashed_pwd = hash_password(pwd)
            opening_bal = u["balance"] - net_seeded.get(user_id, 0)
            self.users[user_id] = {
                "id": user_id,
                "email": u["email"],
                "password_hash": hashed_pwd,
                "display_name": u.get("display_name", u["handle"].title()),
                "handle": u["handle"],
                "balance": u["balance"],
                "opening_balance": opening_bal
            }
            token = f"tok_{user_id}_{secrets.token_hex(16)}"
            self.tokens[token] = user_id

        for p in payments_list:
            from_u = self.users.get(p.get("from_user_id"))
            to_u = self.users.get(p.get("to_user_id"))
            cat = p.get("created_at") or reset_now_str
            payment_id = p["id"]
            revs = p.get("revisions")
            if not revs:
                revs = [{
                    "payment_id": payment_id,
                    "revision": 1,
                    "amount": p["amount"],
                    "effective_at": cat,
                    "recorded_at": cat,
                    "reason": ""
                }]
            payment = {
                "payment_id": payment_id,
                "from_user_id": p["from_user_id"],
                "from_handle": from_u["handle"] if from_u else "",
                "to_user_id": p["to_user_id"],
                "to_handle": to_u["handle"] if to_u else "",
                "amount": p["amount"],
                "currency": self.currency,
                "note": p.get("note", ""),
                "visibility": p.get("visibility", "public"),
                "request_id": p.get("request_id"),
                "authorization_id": p.get("authorization_id"),
                "settlement_id": p.get("settlement_id"),
                "created_at": cat,
                "revisions": revs
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
                "created_at": r.get("created_at") or reset_now_str
            }

        # Load authorizations
        for a in authorizations_list:
            from_u = self.users.get(a.get("from_user_id"))
            to_u = self.users.get(a.get("to_user_id"))
            a_id = a["id"]
            captured = a.get("captured_amount", 0)
            amt = a["amount"]
            rem = a.get("remaining_amount", amt - captured)
            created_at = a.get("created_at") or reset_now_str
            closed_at = a.get("closed_at")
            if a.get("status") in ("captured", "voided") and not closed_at:
                closed_at = created_at
            events = a.get("events")
            if not events:
                events = [{"type": "created", "time": created_at, "amount": amt}]
                if a.get("status") == "voided":
                    events.append({"type": "voided", "time": closed_at or created_at})
                elif a.get("status") == "captured":
                    events.append({"type": "captured", "time": closed_at or created_at, "captured": captured, "final": True, "remaining_after": 0})
            self.authorizations[a_id] = {
                "authorization_id": a_id,
                "from_user_id": a["from_user_id"],
                "from_handle": from_u["handle"] if from_u else "",
                "to_user_id": a["to_user_id"],
                "to_handle": to_u["handle"] if to_u else "",
                "amount": amt,
                "captured_amount": captured,
                "remaining_amount": rem if a.get("status") == "open" else 0,
                "currency": self.currency,
                "note": a.get("note", ""),
                "visibility": a.get("visibility", "public"),
                "status": a.get("status", "open"),
                "expires_at": a.get("expires_at"),
                "closed_at": closed_at,
                "events": events,
                "payment_id": a.get("payment_id"),
                "payment_ids": a.get("payment_ids", ([a["payment_id"]] if a.get("payment_id") else [])),
                "created_at": created_at
            }

        # Check seeded open holds do not exceed user balance
        for u_id, user in self.users.items():
            user_held = sum(
                auth["remaining_amount"]
                for auth in self.authorizations.values()
                if auth["from_user_id"] == u_id and self.get_auth_status(auth) == "open"
            )
            if user_held > user["balance"]:
                raise ApiError(422, "validation_failed", "Seeded unexpired open holds exceed user balance")

    def export_state(self) -> dict:
        return {
            "track": "pocketful",
            "format_version": 1,
            "state": {
                "currency": self.currency,
                "minor_units": self.minor_units,
                "authorization_ttl_seconds": self.authorization_ttl_seconds,
                "users": list(self.users.values()),
                "tokens": self.tokens,
                "payments": self.payments,
                "requests": self.requests,
                "splits": self.splits,
                "authorizations": self.authorizations,
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
                "statement_snapshots": self.statement_snapshots,
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
        self.authorization_ttl_seconds = state.get("authorization_ttl_seconds", 600)
        self.tokens = copy.deepcopy(state.get("tokens", {}))
        self.requests = copy.deepcopy(state.get("requests", {}))
        self.splits = copy.deepcopy(state.get("splits", {}))
        self.settlement_operator_ids = set(state.get("settlement_operator_ids", []))
        self.id_counter = state.get("id_counter", 0)
        self.idempotency_records.clear()
        for item in state.get("idempotency_records", []):
            k = (item["user_id"], item["method"], item["path"], item["key"])
            self.idempotency_records[k] = item["record"]

        self.statement_snapshots = copy.deepcopy(state.get("statement_snapshots", {}))

        # Import payments and ensure revisions exist
        raw_payments = copy.deepcopy(state.get("payments", []))
        self.payments = []
        for p in raw_payments:
            cat = p.get("created_at") or current_time_rfc3339()
            p["created_at"] = cat
            if "revisions" not in p:
                p["revisions"] = [{
                    "payment_id": p["payment_id"],
                    "revision": 1,
                    "amount": p["amount"],
                    "effective_at": cat,
                    "recorded_at": cat,
                    "reason": ""
                }]
            self.payments.append(p)

        # Import users and ensure opening_balance exists
        raw_users = state.get("users", [])
        self.users = {}
        for u in raw_users:
            u_dict = copy.deepcopy(u)
            if "opening_balance" not in u_dict:
                # Compute opening balance from imported payments
                net = 0
                for p in self.payments:
                    amt = p["revisions"][0]["amount"] if p.get("revisions") else p["amount"]
                    if p["from_user_id"] == u_dict["id"]:
                        net -= amt
                    if p["to_user_id"] == u_dict["id"]:
                        net += amt
                u_dict["opening_balance"] = u_dict["balance"] - net
            self.users[u_dict["id"]] = u_dict

        # Import authorizations and ensure closed_at / events exist
        raw_auths = copy.deepcopy(state.get("authorizations", {}))
        self.authorizations = {}
        for a_id, a in raw_auths.items():
            if "closed_at" not in a:
                if a.get("status") in ("captured", "voided"):
                    a["closed_at"] = a.get("created_at") or current_time_rfc3339()
                else:
                    a["closed_at"] = None
            if "events" not in a:
                created_at = a.get("created_at") or current_time_rfc3339()
                amt = a["amount"]
                captured = a.get("captured_amount", 0)
                events = [{"type": "created", "time": created_at, "amount": amt}]
                if a.get("status") == "voided":
                    events.append({"type": "voided", "time": a["closed_at"] or created_at})
                elif a.get("status") == "captured":
                    events.append({"type": "captured", "time": a["closed_at"] or created_at, "captured": captured, "final": True, "remaining_after": 0})
                a["events"] = events
            self.authorizations[a_id] = a

store = DataStore()
