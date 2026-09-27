from __future__ import annotations
import copy
from datetime import datetime, timedelta, timezone
import json
import re
import secrets
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

from app.auth import get_current_user, get_current_user_optional
from app.models import ApiError
from app.sentinel import sentinel
from app.store import (
    current_time_rfc3339,
    derive_handle,
    hash_password,
    parse_rfc3339_with_offset,
    store,
    validate_amount,
    verify_password
)
from app.ui import HTML_TEMPLATE

app = FastAPI(title="Pocketful Service", docs_url=None, redoc_url=None)

@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}}
    )

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    code = "validation_failed"
    status_code = 422
    for err in errors:
        err_type = err.get("type", "")
        if "type_error" in err_type or "json_invalid" in err_type:
            code = "malformed_request"
            status_code = 400
            break
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": "Validation failed"}}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": str(exc)}}
    )

def parse_int_query_param(val: Optional[str], name: str, min_val: int, max_val: Optional[int] = None, default: Optional[int] = None) -> int:
    if val is None:
        return default if default is not None else min_val
    if not re.fullmatch(r"^[0-9]+$", val):
        raise ApiError(422, "validation_failed", f"Query parameter {name} must be plain decimal digits")
    num = int(val)
    if num < min_val or (max_val is not None and num > max_val):
        raise ApiError(422, "validation_failed", f"Query parameter {name} out of range")
    return num

async def parse_and_validate_idempotency(request: Request, user: dict) -> tuple[str, dict]:
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise ApiError(400, "missing_idempotency_key", "Missing required Idempotency-Key header")
    if len(key) < 1 or len(key) > 255:
        raise ApiError(422, "validation_failed", "Idempotency-Key must be 1 to 255 characters")
    
    try:
        raw_body = await request.body()
        body = json.loads(raw_body) if raw_body else {}
        if not isinstance(body, dict):
            raise ApiError(400, "malformed_request", "Body must be a JSON object")
    except json.JSONDecodeError:
        raise ApiError(400, "malformed_request", "Malformed JSON body")

    method = request.method
    path = request.url.path
    cache_key = (user["id"], method, path, key)

    if cache_key in store.idempotency_records:
        rec = store.idempotency_records[cache_key]
        if rec["body"] == body:
            return key, {"replay": True, "status_code": 200, "response": rec["response"]}
        else:
            raise ApiError(409, "idempotency_key_reuse", "Idempotency key already used with different request body")

    return key, {"replay": False, "body": body}

# UI HTML Routes
@app.get("/", response_class=HTMLResponse)
async def serve_home():
    return HTMLResponse(HTML_TEMPLATE)

@app.get("/login", response_class=HTMLResponse)
async def serve_login():
    return HTMLResponse(HTML_TEMPLATE)

@app.get("/signup", response_class=HTMLResponse)
async def serve_signup():
    return HTMLResponse(HTML_TEMPLATE)

@app.get("/split", response_class=HTMLResponse)
async def serve_split():
    return HTMLResponse(HTML_TEMPLATE)

@app.get("/audit", response_class=HTMLResponse)
async def serve_audit():
    return HTMLResponse(HTML_TEMPLATE)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/_test/reset")
async def test_reset(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "malformed_request", "Invalid JSON")
    async with store.lock:
        store.reset_fixture(body)
        sentinel.reset()
    return Response(status_code=204)

@app.get("/_test/export")
async def test_export():
    async with store.lock:
        return store.export_state()

@app.post("/_test/import")
async def test_import(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "malformed_request", "Invalid JSON")
    async with store.lock:
        store.import_state(body)
    return Response(status_code=204)

# Authentication
@app.post("/auth/signup", status_code=201)
async def auth_signup(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "malformed_request", "Invalid JSON")
    
    email = body.get("email")
    password = body.get("password")
    display_name = body.get("display_name")

    if not isinstance(email, str) or "@" not in email:
        raise ApiError(422, "validation_failed", "Invalid email format")
    parts = email.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ApiError(422, "validation_failed", "Invalid email format")
    if not isinstance(password, str) or len(password) < 8:
        raise ApiError(422, "validation_failed", "Password must be at least 8 characters")
    if not isinstance(display_name, str):
        raise ApiError(422, "validation_failed", "Invalid display_name")

    async with store.lock:
        if store.find_user_by_email(email):
            raise ApiError(409, "email_taken", "Email already registered")
        
        handle = derive_handle(email)
        if store.find_user_by_handle(handle):
            raise ApiError(409, "handle_taken", f"Handle '{handle}' derived from email is already taken")

        user_id = store.next_id("u")
        token = f"tok_{secrets.token_hex(16)}"
        user = {
            "id": user_id,
            "email": email,
            "password_hash": hash_password(password),
            "display_name": display_name,
            "handle": handle,
            "balance": 0,
            "opening_balance": 0
        }
        store.users[user_id] = user
        store.tokens[token] = user_id

        return {"user_id": user_id, "display_name": display_name, "token": token}

@app.post("/auth/login")
async def auth_login(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "malformed_request", "Invalid JSON")
    
    email = body.get("email")
    password = body.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        raise ApiError(422, "validation_failed", "Invalid credentials payload")

    async with store.lock:
        user = store.find_user_by_email(email)
        if not user or not verify_password(password, user["password_hash"]):
            raise ApiError(401, "unauthenticated", "Invalid email or password")

        token = f"tok_{secrets.token_hex(16)}"
        store.tokens[token] = user["id"]
        return {"user_id": user["id"], "display_name": user["display_name"], "token": token}

# API Endpoints
@app.get("/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    params = request.query_params
    as_of_param = params.get("as_of")
    known_at_param = params.get("known_at")

    as_of_dt = None
    if as_of_param is not None:
        as_of_dt = parse_rfc3339_with_offset(as_of_param)

    known_at_dt = None
    if known_at_param is not None:
        known_at_dt = parse_rfc3339_with_offset(known_at_param)

    async with store.lock:
        if as_of_param is None and known_at_param is None:
            total, available, held = store.get_user_balances(user["id"])
            return {
                "user_id": user["id"],
                "display_name": user["display_name"],
                "handle": user["handle"],
                "balance": total,
                "total": total,
                "available": available,
                "held": held,
                "currency": store.currency,
                "minor_units": store.minor_units
            }

        now_dt = datetime.now(timezone.utc)
        effective_known_at = known_at_dt if known_at_dt is not None else now_dt
        effective_as_of = as_of_dt if as_of_dt is not None else now_dt

        total = store.compute_user_balance_at(user["id"], effective_as_of, effective_known_at)
        held = store.compute_user_held_at(user["id"], effective_as_of, effective_known_at)
        available = max(0, total - held)

        res = {
            "user_id": user["id"],
            "display_name": user["display_name"],
            "handle": user["handle"],
            "balance": total,
            "total": total,
            "available": available,
            "held": held,
            "currency": store.currency,
            "minor_units": store.minor_units
        }
        if as_of_param is not None:
            res["as_of"] = as_of_param
        if known_at_param is not None:
            res["known_at"] = known_at_param
        return res

@app.post("/payments", status_code=201)
async def create_payment(request: Request):
    user = await get_current_user(request)
    key, idem_info = await parse_and_validate_idempotency(request, user)
    if idem_info.get("replay"):
        return JSONResponse(status_code=200, content=idem_info["response"])

    body = idem_info["body"]
    to_handle = body.get("to_handle")
    amount_val = body.get("amount")
    note = body.get("note", "")
    visibility = body.get("visibility", "public")

    if not isinstance(to_handle, str):
        raise ApiError(422, "validation_failed", "Invalid to_handle")
    if to_handle == user["handle"]:
        raise ApiError(422, "self_payment", "Cannot pay yourself")
    
    amount = validate_amount(amount_val)

    if not isinstance(note, str) or len(note) > 200:
        raise ApiError(422, "validation_failed", "note must be a string up to 200 characters")
    if visibility not in ("public", "private"):
        raise ApiError(422, "validation_failed", "visibility must be public or private")

    async with store.lock:
        recipient = store.find_user_by_handle(to_handle)
        if not recipient:
            raise ApiError(404, "not_found", f"User with handle '{to_handle}' not found")

        total, available, held = store.get_user_balances(user["id"])
        if available < amount:
            raise ApiError(409, "insufficient_funds", "Insufficient funds for payment")

        # Atomic debit and credit
        user["balance"] -= amount
        recipient["balance"] += amount

        payment_id = store.next_id("p")
        created_at = current_time_rfc3339()

        payment_data = {
            "payment_id": payment_id,
            "from_user_id": user["id"],
            "from_handle": user["handle"],
            "to_user_id": recipient["id"],
            "to_handle": recipient["handle"],
            "amount": amount,
            "currency": store.currency,
            "note": note,
            "visibility": visibility,
            "request_id": None,
            "authorization_id": None,
            "settlement_id": None,
            "refund_of": None,
            "created_at": created_at,
            "revisions": [{
                "payment_id": payment_id,
                "revision": 1,
                "amount": amount,
                "effective_at": created_at,
                "recorded_at": created_at,
                "reason": ""
            }]
        }
        store.payments.append(payment_data)

        store.record_audit_event("PAYMENT_TRANSFER", {
            "payment_id": payment_id,
            "from_user_id": user["id"],
            "to_user_id": recipient["id"],
            "amount": amount,
            "currency": store.currency
        })
        sentinel.record_and_evaluate(
            "PAYMENT", user["id"], user["handle"], recipient["id"], recipient["handle"], amount, store.currency
        )

        cache_key = (user["id"], "POST", "/payments", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": payment_data
        }

        return payment_data

@app.post("/payments/{payment_id}/corrections", status_code=201)
async def correct_payment(payment_id: str, request: Request):
    user = await get_current_user(request)
    key, idem_info = await parse_and_validate_idempotency(request, user)
    if idem_info.get("replay"):
        return JSONResponse(status_code=200, content=idem_info["response"])

    body = idem_info["body"]
    expected_revision = body.get("expected_revision")
    amount_val = body.get("amount")
    effective_at_str = body.get("effective_at")
    reason = body.get("reason")

    if not isinstance(expected_revision, int) or isinstance(expected_revision, bool) or expected_revision < 1:
        raise ApiError(422, "validation_failed", "expected_revision must be a positive integer")

    if isinstance(amount_val, bool) or not isinstance(amount_val, (int, float)):
        raise ApiError(422, "validation_failed", "amount must be an integral number")
    if isinstance(amount_val, float):
        if not amount_val.is_integer():
            raise ApiError(422, "validation_failed", "amount must be an integer count of minor units")
        amount_val = int(amount_val)
    if amount_val < 0 or amount_val > 1_000_000_000:
        raise ApiError(422, "validation_failed", "amount must be between 0 and 1,000,000,000")

    if not isinstance(reason, str) or len(reason) < 1 or len(reason) > 200:
        raise ApiError(422, "validation_failed", "reason must be 1 to 200 characters")

    eff_dt = parse_rfc3339_with_offset(effective_at_str)
    now_dt = datetime.now(timezone.utc)
    if eff_dt > now_dt:
        raise ApiError(422, "validation_failed", "effective_at cannot be in the future")

    async with store.lock:
        target_payment = None
        for p in store.payments:
            if p["payment_id"] == payment_id:
                target_payment = p
                break
        if not target_payment:
            raise ApiError(404, "not_found", "Payment not found")

        if target_payment["from_user_id"] != user["id"]:
            raise ApiError(403, "forbidden", "Only original sender can correct payment")

        if target_payment.get("settlement_id") or target_payment.get("authorization_id") or target_payment.get("refund_of"):
            raise ApiError(422, "linked_payment_immutable", "Linked payments and refunds are immutable")

        # Check already refunded amount
        refunded_sum = sum(rf["amount"] for rf in store.payments if rf.get("refund_of") == payment_id)
        if amount_val < refunded_sum:
            raise ApiError(422, "refund_exceeds_payment", "Correction cannot reduce payment below refunded amount")

        revisions = target_payment.get("revisions", [])
        if not revisions:
            revisions = [{
                "payment_id": payment_id,
                "revision": 1,
                "amount": target_payment["amount"],
                "effective_at": target_payment["created_at"],
                "recorded_at": target_payment["created_at"],
                "reason": ""
            }]
            target_payment["revisions"] = revisions

        latest_rev = revisions[-1]
        if expected_revision != latest_rev["revision"]:
            raise ApiError(409, "stale_revision", "Stale expected revision")

        old_amount = latest_rev["amount"]
        diff = amount_val - old_amount

        sender = store.users.get(target_payment["from_user_id"])
        receiver = store.users.get(target_payment["to_user_id"])
        if not sender or not receiver:
            raise ApiError(404, "not_found", "Parties not found")

        # Check current affordability (insufficient_funds takes precedence)
        if diff > 0:
            s_tot, s_avail, s_hld = store.get_user_balances(sender["id"])
            if s_avail < diff:
                raise ApiError(409, "insufficient_funds", "Sender has insufficient available funds")
        elif diff < 0:
            r_tot, r_avail, r_hld = store.get_user_balances(receiver["id"])
            if r_avail < -diff:
                raise ApiError(409, "insufficient_funds", "Receiver has insufficient available funds")

        # Strictly increasing recorded_at
        now_dt = datetime.now(timezone.utc)
        prev_rec_dt = parse_rfc3339_with_offset(latest_rev["recorded_at"])
        if now_dt <= prev_rec_dt:
            now_dt = prev_rec_dt + timedelta(microseconds=1)
        rec_str = now_dt.isoformat()

        new_rev_num = expected_revision + 1
        tentative_rev = {
            "payment_id": payment_id,
            "revision": new_rev_num,
            "amount": amount_val,
            "effective_at": eff_dt.isoformat(),
            "recorded_at": rec_str,
            "reason": reason
        }

        # Check historical overdraft across all boundary instants
        store.check_historical_overdraft(sender["id"], receiver["id"], target_payment, tentative_rev)

        # Apply atomic balance update
        sender["balance"] -= diff
        receiver["balance"] += diff
        target_payment["revisions"].append(tentative_rev)

        store.record_audit_event("PAYMENT_CORRECTION", {
            "payment_id": payment_id,
            "revision": new_rev_num,
            "amount": amount_val,
            "diff": diff,
            "sender_id": sender["id"],
            "receiver_id": receiver["id"]
        })
        sentinel.record_and_evaluate(
            "CORRECTION", user["id"], user["handle"], receiver["id"], receiver["handle"], abs(diff), store.currency
        )

        cache_key = (user["id"], "POST", f"/payments/{payment_id}/corrections", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": tentative_rev
        }

        return tentative_rev

@app.post("/payments/{payment_id}/refunds", status_code=201)
async def refund_payment(payment_id: str, request: Request):
    user = await get_current_user(request)
    key, idem_info = await parse_and_validate_idempotency(request, user)
    if idem_info.get("replay"):
        return JSONResponse(status_code=200, content=idem_info["response"])

    body = idem_info["body"]
    amount_val = body.get("amount")
    amount = validate_amount(amount_val)

    async with store.lock:
        target_payment = None
        for p in store.payments:
            if p["payment_id"] == payment_id:
                target_payment = p
                break
        if not target_payment:
            raise ApiError(404, "not_found", "Payment not found")

        if target_payment["to_user_id"] != user["id"]:
            raise ApiError(403, "forbidden", "Only original receiver may refund payment")

        if target_payment.get("refund_of") is not None:
            raise ApiError(422, "invalid_refund_target", "Cannot refund a refund payment")

        # Current corrected amount of target payment
        target_revs = target_payment.get("revisions", [])
        current_amount = target_revs[-1]["amount"] if target_revs else target_payment["amount"]
        already_refunded = sum(p["amount"] for p in store.payments if p.get("refund_of") == payment_id)

        if already_refunded + amount > current_amount:
            raise ApiError(422, "refund_exceeds_payment", "Refund exceeds payment amount")

        tot, avail, hld = store.get_user_balances(user["id"])
        if avail < amount:
            raise ApiError(409, "insufficient_funds", "Insufficient available funds for refund")

        orig_sender = store.users.get(target_payment["from_user_id"])
        if not orig_sender:
            raise ApiError(404, "not_found", "Original sender not found")

        # Atomic debit and credit
        user["balance"] -= amount
        orig_sender["balance"] += amount

        refund_id = store.next_id("p")
        created_at = current_time_rfc3339()

        refund_data = {
            "payment_id": refund_id,
            "from_user_id": user["id"],
            "from_handle": user["handle"],
            "to_user_id": orig_sender["id"],
            "to_handle": orig_sender["handle"],
            "amount": amount,
            "currency": store.currency,
            "note": target_payment["note"],
            "visibility": target_payment["visibility"],
            "request_id": None,
            "authorization_id": None,
            "settlement_id": None,
            "refund_of": payment_id,
            "created_at": created_at,
            "revisions": [{
                "payment_id": refund_id,
                "revision": 1,
                "amount": amount,
                "effective_at": created_at,
                "recorded_at": created_at,
                "reason": ""
            }]
        }
        store.payments.append(refund_data)

        store.record_audit_event("PAYMENT_REFUND", {
            "payment_id": refund_id,
            "refund_of": payment_id,
            "from_user_id": user["id"],
            "to_user_id": orig_sender["id"],
            "amount": amount,
            "currency": store.currency
        })
        sentinel.record_and_evaluate(
            "REFUND", user["id"], user["handle"], orig_sender["id"], orig_sender["handle"], amount, store.currency
        )

        cache_key = (user["id"], "POST", f"/payments/{payment_id}/refunds", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": refund_data
        }

        return refund_data

@app.post("/correction-batches", status_code=201)
async def create_correction_batch(request: Request):
    user = await get_current_user(request)
    async with store.lock:
        if user["id"] not in store.settlement_operator_ids:
            raise ApiError(403, "forbidden", "Only settlement operators can create correction batches")

    key, idem_info = await parse_and_validate_idempotency(request, user)
    if idem_info.get("replay"):
        return JSONResponse(status_code=200, content=idem_info["response"])

    body = idem_info["body"]
    corrections = body.get("corrections")
    if not isinstance(corrections, list) or len(corrections) < 1 or len(corrections) > 32:
        raise ApiError(422, "validation_failed", "corrections must contain 1 to 32 items")

    seen_ids = set()
    for item in corrections:
        if not isinstance(item, dict):
            raise ApiError(422, "validation_failed", "Correction item must be an object")
        pid = item.get("payment_id")
        if not isinstance(pid, str) or not pid:
            raise ApiError(422, "validation_failed", "Invalid payment_id")
        if pid in seen_ids:
            raise ApiError(422, "validation_failed", f"Duplicate payment_id {pid} in batch")
        seen_ids.add(pid)

    async with store.lock:
        now_dt = datetime.now(timezone.utc)
        batch_pairs = []

        # Error precedence 1: item errors in input order
        for item in corrections:
            pid = item.get("payment_id")
            exp_rev = item.get("expected_revision")
            amt_val = item.get("amount")
            eff_str = item.get("effective_at")
            reason = item.get("reason")

            if not isinstance(exp_rev, int) or isinstance(exp_rev, bool) or exp_rev < 1:
                raise ApiError(422, "validation_failed", "expected_revision must be a positive integer")

            if isinstance(amt_val, bool) or not isinstance(amt_val, (int, float)):
                raise ApiError(422, "validation_failed", "amount must be an integral number")
            if isinstance(amt_val, float):
                if not amt_val.is_integer():
                    raise ApiError(422, "validation_failed", "amount must be an integer count of minor units")
                amt_val = int(amt_val)
            if amt_val < 0 or amt_val > 1_000_000_000:
                raise ApiError(422, "validation_failed", "amount out of range")

            if not isinstance(reason, str) or len(reason) < 1 or len(reason) > 200:
                raise ApiError(422, "validation_failed", "reason must be 1 to 200 characters")

            eff_dt = parse_rfc3339_with_offset(eff_str)
            if eff_dt > now_dt:
                raise ApiError(422, "validation_failed", "effective_at cannot be in the future")

            target_p = None
            for p in store.payments:
                if p["payment_id"] == pid:
                    target_p = p
                    break
            if not target_p:
                raise ApiError(404, "not_found", f"Payment {pid} not found")

            # Check stale expected revision
            latest_rev = target_p["revisions"][-1]["revision"]
            if exp_rev != latest_rev:
                raise ApiError(409, "stale_revision", f"Stale expected revision for payment {pid}")

            # Immutability: captures and refunds remain immutable
            if target_p.get("authorization_id") or target_p.get("refund_of"):
                raise ApiError(422, "linked_payment_immutable", "Captures and refunds are immutable")

            # Check already refunded amount
            refunded_sum = sum(rf["amount"] for rf in store.payments if rf.get("refund_of") == pid)
            if amt_val < refunded_sum:
                raise ApiError(422, "refund_exceeds_payment", "Correction cannot reduce payment below refunded amount")

            batch_pairs.append((item, target_p, eff_dt, amt_val))

        # Error precedence 2 & 3: settlement completeness and identical effective instant
        batch_pids = {p["payment_id"] for _, p, _, _ in batch_pairs}
        settlement_groups: Dict[str, List[tuple]] = {}
        for item, p, eff_dt, amt in batch_pairs:
            stl_id = p.get("settlement_id")
            if stl_id:
                if stl_id not in settlement_groups:
                    settlement_groups[stl_id] = []
                settlement_groups[stl_id].append((item, p, eff_dt))

        for stl_id, members in settlement_groups.items():
            all_stl_payments = [p for p in store.payments if p.get("settlement_id") == stl_id]
            for ap in all_stl_payments:
                if ap["payment_id"] not in batch_pids:
                    raise ApiError(422, "incomplete_settlement", f"Settlement {stl_id} incomplete in batch")

            # Check identical effective instants
            first_eff_utc = members[0][2].astimezone(timezone.utc)
            for _, _, eff_dt in members:
                if eff_dt.astimezone(timezone.utc) != first_eff_utc:
                    raise ApiError(422, "validation_failed", "Settlement members must have identical effective instants")

        # Error precedence 4: resulting current available funds
        net_deltas: Dict[str, int] = {}
        for item, p, eff_dt, amt in batch_pairs:
            old_amt = p["revisions"][-1]["amount"]
            diff = amt - old_amt
            net_deltas[p["from_user_id"]] = net_deltas.get(p["from_user_id"], 0) - diff
            net_deltas[p["to_user_id"]] = net_deltas.get(p["to_user_id"], 0) + diff

        for u_id, delta in net_deltas.items():
            if delta < 0:
                tot, avail, hld = store.get_user_balances(u_id)
                if avail + delta < 0:
                    raise ApiError(409, "insufficient_funds", "Batch causes insufficient available funds")

        # Error precedence 5: historical total and available funds at every effective/event boundary
        batch_id = store.next_id("cb")
        max_prev_rec = max(parse_rfc3339_with_offset(p["revisions"][-1]["recorded_at"]) for _, p, _, _ in batch_pairs)
        if now_dt <= max_prev_rec:
            now_dt = max_prev_rec + timedelta(microseconds=1)
        batch_recorded_at = now_dt.isoformat()

        modifications = []
        for item, p, eff_dt, amt in batch_pairs:
            new_rev_num = p["revisions"][-1]["revision"] + 1
            new_rev = {
                "payment_id": p["payment_id"],
                "revision": new_rev_num,
                "amount": amt,
                "effective_at": eff_dt.isoformat(),
                "recorded_at": batch_recorded_at,
                "reason": item["reason"],
                "correction_batch_id": batch_id
            }
            modifications.append((p, new_rev))

        store.check_batch_historical_overdraft(set(net_deltas.keys()), modifications)

        # Apply
        for p, new_rev in modifications:
            p["revisions"].append(new_rev)

        for u_id, delta in net_deltas.items():
            store.users[u_id]["balance"] += delta

        created_revs = [m[1] for m in modifications]
        batch_resp = {
            "correction_batch_id": batch_id,
            "recorded_at": batch_recorded_at,
            "revisions": created_revs
        }

        store.record_audit_event("CORRECTION_BATCH", {
            "correction_batch_id": batch_id,
            "revisions_count": len(created_revs),
            "operator_id": user["id"]
        })

        cache_key = (user["id"], "POST", "/correction-batches", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": batch_resp
        }

        return batch_resp

@app.get("/payments/{payment_id}/revisions")
async def list_payment_revisions(payment_id: str, request: Request):
    user = await get_current_user(request)
    async with store.lock:
        target_payment = None
        for p in store.payments:
            if p["payment_id"] == payment_id:
                target_payment = p
                break
        if not target_payment:
            raise ApiError(404, "not_found", "Payment not found")

        if user["id"] != target_payment["from_user_id"] and user["id"] != target_payment["to_user_id"]:
            raise ApiError(404, "not_found", "Payment not found")

        revisions = target_payment.get("revisions", [])
        if not revisions:
            revisions = [{
                "payment_id": payment_id,
                "revision": 1,
                "amount": target_payment["amount"],
                "effective_at": target_payment["created_at"],
                "recorded_at": target_payment["created_at"],
                "reason": "",
                "correction_batch_id": None
            }]
        return {"revisions": revisions}

@app.get("/statement")
async def get_statement(request: Request):
    user = await get_current_user(request)
    params = request.query_params
    snapshot_param = params.get("snapshot")
    from_param = params.get("from")
    to_param = params.get("to")
    known_at_param = params.get("known_at")
    limit_param = params.get("limit")
    offset_param = params.get("offset")

    limit = parse_int_query_param(limit_param, "limit", 1, 100, default=50)
    offset = parse_int_query_param(offset_param, "offset", 0, default=0)

    async with store.lock:
        if snapshot_param is not None:
            if from_param is not None or to_param is not None or known_at_param is not None:
                raise ApiError(422, "validation_failed", "from, to, known_at not allowed with snapshot")

            snap = store.statement_snapshots.get(snapshot_param)
            if not snap or snap["user_id"] != user["id"]:
                raise ApiError(404, "not_found", "Statement snapshot not found")

            entries = snap["entries"]
            page_entries = entries[offset : offset + limit]
            has_more = (offset + limit < len(entries))
            res = {
                "opening_balance": snap["opening_balance"],
                "entries": page_entries,
                "closing_balance": snap["closing_balance"],
                "has_more": has_more,
                "snapshot": snapshot_param
            }
            if snap.get("known_at") is not None:
                res["known_at"] = snap["known_at"]
            return res

        now_dt = datetime.now(timezone.utc)
        from_dt = parse_rfc3339_with_offset(from_param) if from_param is not None else datetime.min.replace(tzinfo=timezone.utc)
        to_dt = parse_rfc3339_with_offset(to_param) if to_param is not None else now_dt
        known_at_dt = parse_rfc3339_with_offset(known_at_param) if known_at_param is not None else now_dt

        selected_payments = []
        for p in store.payments:
            if p["from_user_id"] != user["id"] and p["to_user_id"] != user["id"]:
                continue
            active_rev = None
            for rev in p.get("revisions", []):
                r_dt = parse_rfc3339_with_offset(rev["recorded_at"])
                if r_dt <= known_at_dt:
                    active_rev = rev
            if active_rev:
                eff_dt = parse_rfc3339_with_offset(active_rev["effective_at"])
                selected_payments.append((eff_dt, p["payment_id"], p, active_rev))

        selected_payments.sort(key=lambda x: (x[0], x[1]))

        opening_balance = user.get("opening_balance", 0)
        running_balance = opening_balance
        window_entries = []

        for eff_dt, pid, p, rev in selected_payments:
            amt = rev["amount"]
            delta = -amt if p["from_user_id"] == user["id"] else amt
            if eff_dt < from_dt:
                opening_balance += delta
                running_balance = opening_balance
            elif eff_dt < to_dt:
                running_balance += delta
                p_copy = {
                    "payment_id": p["payment_id"],
                    "from_user_id": p["from_user_id"],
                    "from_handle": p["from_handle"],
                    "to_user_id": p["to_user_id"],
                    "to_handle": p["to_handle"],
                    "amount": amt,
                    "currency": p["currency"],
                    "note": p["note"],
                    "visibility": p["visibility"],
                    "request_id": p.get("request_id"),
                    "authorization_id": p.get("authorization_id"),
                    "settlement_id": p.get("settlement_id"),
                    "refund_of": p.get("refund_of"),
                    "created_at": p["created_at"]
                }
                entry = {
                    "payment": p_copy,
                    "delta": delta,
                    "balance_after": running_balance,
                    "revision": rev["revision"],
                    "effective_at": rev["effective_at"],
                    "recorded_at": rev["recorded_at"]
                }
                window_entries.append(entry)

        closing_balance = running_balance
        snapshot_token = f"snap_{secrets.token_hex(16)}"
        store.statement_snapshots[snapshot_token] = {
            "user_id": user["id"],
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
            "entries": window_entries,
            "known_at": known_at_param
        }

        page_entries = window_entries[offset : offset + limit]
        has_more = (offset + limit < len(window_entries))

        res = {
            "opening_balance": opening_balance,
            "entries": page_entries,
            "closing_balance": closing_balance,
            "has_more": has_more,
            "snapshot": snapshot_token
        }
        if known_at_param is not None:
            res["known_at"] = known_at_param
        return res

@app.post("/requests", status_code=201)
async def create_request(request: Request):
    user = await get_current_user(request)
    key, idem_info = await parse_and_validate_idempotency(request, user)
    if idem_info.get("replay"):
        return JSONResponse(status_code=200, content=idem_info["response"])

    body = idem_info["body"]
    payer_handle = body.get("payer_handle")
    amount_val = body.get("amount")
    note = body.get("note", "")

    if not isinstance(payer_handle, str):
        raise ApiError(422, "validation_failed", "Invalid payer_handle")
    if payer_handle == user["handle"]:
        raise ApiError(422, "self_request", "Cannot request from yourself")

    amount = validate_amount(amount_val)

    if not isinstance(note, str) or len(note) > 200:
        raise ApiError(422, "validation_failed", "note must be a string up to 200 characters")

    async with store.lock:
        payer = store.find_user_by_handle(payer_handle)
        if not payer:
            raise ApiError(404, "not_found", f"User with handle '{payer_handle}' not found")

        req_id = store.next_id("rq")
        created_at = current_time_rfc3339()

        req_data = {
            "request_id": req_id,
            "requester_id": user["id"],
            "requester_handle": user["handle"],
            "payer_id": payer["id"],
            "payer_handle": payer["handle"],
            "amount": amount,
            "currency": store.currency,
            "note": note,
            "status": "pending",
            "payment_id": None,
            "created_at": created_at
        }
        store.requests[req_id] = req_data

        cache_key = (user["id"], "POST", "/requests", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": req_data
        }

        return req_data

@app.post("/requests/{req_id}/pay", status_code=201)
async def pay_request(req_id: str, request: Request):
    user = await get_current_user(request)
    key, idem_info = await parse_and_validate_idempotency(request, user)
    if idem_info.get("replay"):
        return JSONResponse(status_code=200, content=idem_info["response"])

    body = idem_info["body"]
    visibility = body.get("visibility", "public")
    if visibility not in ("public", "private"):
        raise ApiError(422, "validation_failed", "visibility must be public or private")

    async with store.lock:
        req_item = store.requests.get(req_id)
        if not req_item:
            raise ApiError(404, "not_found", "Request not found")
        if req_item["payer_id"] != user["id"]:
            raise ApiError(403, "forbidden", "Only the specified payer may pay this request")
        if req_item["status"] == "paid":
            raise ApiError(409, "request_already_paid", "Request has already been paid")
        if req_item["status"] in ("declined", "cancelled"):
            raise ApiError(409, "request_not_pending", "Request is no longer pending")

        recipient = store.users.get(req_item["requester_id"])
        if not recipient:
            raise ApiError(404, "not_found", "Requester not found")

        amount = req_item["amount"]
        total, available, held = store.get_user_balances(user["id"])
        if available < amount:
            raise ApiError(409, "insufficient_funds", "Insufficient funds to pay request")

        user["balance"] -= amount
        recipient["balance"] += amount

        payment_id = store.next_id("p")
        created_at = current_time_rfc3339()

        payment_data = {
            "payment_id": payment_id,
            "from_user_id": user["id"],
            "from_handle": user["handle"],
            "to_user_id": recipient["id"],
            "to_handle": recipient["handle"],
            "amount": amount,
            "currency": store.currency,
            "note": req_item["note"],
            "visibility": visibility,
            "request_id": req_id,
            "authorization_id": None,
            "settlement_id": None,
            "refund_of": None,
            "created_at": created_at,
            "revisions": [{
                "payment_id": payment_id,
                "revision": 1,
                "amount": amount,
                "effective_at": created_at,
                "recorded_at": created_at,
                "reason": ""
            }]
        }
        store.payments.append(payment_data)

        req_item["status"] = "paid"
        req_item["payment_id"] = payment_id

        cache_key = (user["id"], "POST", f"/requests/{req_id}/pay", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": payment_data
        }

        return payment_data

@app.post("/requests/{req_id}/decline")
async def decline_request(req_id: str, request: Request):
    user = await get_current_user(request)
    async with store.lock:
        req_item = store.requests.get(req_id)
        if not req_item:
            raise ApiError(404, "not_found", "Request not found")
        if req_item["payer_id"] != user["id"]:
            raise ApiError(403, "forbidden", "Only the payer may decline this request")
        if req_item["status"] == "declined":
            return req_item
        if req_item["status"] in ("paid", "cancelled"):
            raise ApiError(409, "request_not_pending", "Request is not pending")

        req_item["status"] = "declined"
        return req_item

@app.post("/requests/{req_id}/cancel")
async def cancel_request(req_id: str, request: Request):
    user = await get_current_user(request)
    async with store.lock:
        req_item = store.requests.get(req_id)
        if not req_item:
            raise ApiError(404, "not_found", "Request not found")
        if req_item["requester_id"] != user["id"]:
            raise ApiError(403, "forbidden", "Only the requester may cancel this request")
        if req_item["status"] == "cancelled":
            return req_item
        if req_item["status"] in ("paid", "declined"):
            raise ApiError(409, "request_not_pending", "Request is not pending")

        req_item["status"] = "cancelled"
        return req_item

@app.get("/requests")
async def list_requests(request: Request):
    if request.headers.get("accept", "").startswith("text/html"):
        return HTMLResponse(HTML_TEMPLATE)

    user = await get_current_user(request)
    params = request.query_params
    direction = params.get("direction")
    status = params.get("status")
    limit_str = params.get("limit", "50")
    offset_str = params.get("offset", "0")

    if direction is not None and direction not in ("incoming", "outgoing"):
        raise ApiError(422, "validation_failed", "Invalid direction")
    if status is not None and status not in ("pending", "paid", "declined", "cancelled"):
        raise ApiError(422, "validation_failed", "Invalid status")

    limit = parse_int_query_param(limit_str, "limit", 1, 200)
    offset = parse_int_query_param(offset_str, "offset", 0)

    async with store.lock:
        filtered = []
        for r in store.requests.values():
            is_incoming = (r["payer_id"] == user["id"])
            is_outgoing = (r["requester_id"] == user["id"])
            if not is_incoming and not is_outgoing:
                continue
            if direction == "incoming" and not is_incoming:
                continue
            if direction == "outgoing" and not is_outgoing:
                continue
            if status and r["status"] != status:
                continue
            filtered.append(r)

        filtered.sort(key=lambda x: x["created_at"], reverse=True)
        items = filtered[offset : offset + limit]
        has_more = (offset + limit) < len(filtered)
        return {"requests": items, "has_more": has_more}

@app.post("/splits", status_code=201)
async def create_split(request: Request):
    user = await get_current_user(request)
    key, idem_info = await parse_and_validate_idempotency(request, user)
    if idem_info.get("replay"):
        return JSONResponse(status_code=200, content=idem_info["response"])

    body = idem_info["body"]
    amount_val = body.get("amount")
    participants = body.get("participant_handles")
    note = body.get("note", "")

    amount = validate_amount(amount_val)

    if not isinstance(participants, list) or len(participants) < 1:
        raise ApiError(422, "validation_failed", "participant_handles must be a non-empty array")
    if len(set(participants)) != len(participants):
        raise ApiError(422, "validation_failed", "Duplicate participant handles")
    for h in participants:
        if not isinstance(h, str):
            raise ApiError(422, "validation_failed", "Participant handles must be strings")
    if not isinstance(note, str) or len(note) > 200:
        raise ApiError(422, "validation_failed", "note must be a string up to 200 characters")

    async with store.lock:
        for h in participants:
            if not store.find_user_by_handle(h):
                raise ApiError(404, "not_found", f"Participant handle '{h}' not found")

        n = len(participants)
        base = amount // n
        remainder = amount % n
        shares = []
        for i, h in enumerate(participants):
            share_amt = base + (1 if i < remainder else 0)
            shares.append({"handle": h, "amount": share_amt})

        split_id = store.next_id("sp")
        created_at = current_time_rfc3339()
        created_requests = []

        for item in shares:
            h = item["handle"]
            share_amt = item["amount"]
            if h == user["handle"]:
                continue
            payer_u = store.find_user_by_handle(h)
            req_id = store.next_id("rq")
            req_data = {
                "request_id": req_id,
                "requester_id": user["id"],
                "requester_handle": user["handle"],
                "payer_id": payer_u["id"],
                "payer_handle": payer_u["handle"],
                "amount": share_amt,
                "currency": store.currency,
                "note": note,
                "status": "pending",
                "payment_id": None,
                "created_at": created_at
            }
            store.requests[req_id] = req_data
            created_requests.append(req_data)

        split_response = {
            "split_id": split_id,
            "amount": amount,
            "currency": store.currency,
            "note": note,
            "shares": shares,
            "requests": created_requests,
            "created_at": created_at
        }
        store.splits[split_id] = split_response

        cache_key = (user["id"], "POST", "/splits", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": split_response
        }

        return split_response

@app.get("/activity")
async def list_activity(request: Request):
    user = await get_current_user(request)
    params = request.query_params
    limit_str = params.get("limit", "50")
    offset_str = params.get("offset", "0")

    limit = parse_int_query_param(limit_str, "limit", 1, 200)
    offset = parse_int_query_param(offset_str, "offset", 0)

    async with store.lock:
        visible = []
        for p in store.payments:
            if p["visibility"] == "public" or p["from_user_id"] == user["id"] or p["to_user_id"] == user["id"]:
                visible.append(p)

        visible.sort(key=lambda x: x["created_at"], reverse=True)
        items = visible[offset : offset + limit]
        has_more = (offset + limit) < len(visible)
        return {"payments": items, "has_more": has_more}

@app.post("/settlements", status_code=201)
async def create_settlement(request: Request):
    user = await get_current_user(request)
    async with store.lock:
        if user["id"] not in store.settlement_operator_ids:
            raise ApiError(403, "forbidden", "Only settlement operators can create settlements")

    key, idem_info = await parse_and_validate_idempotency(request, user)
    if idem_info.get("replay"):
        return JSONResponse(status_code=200, content=idem_info["response"])

    body = idem_info["body"]
    transfers = body.get("transfers")
    if not isinstance(transfers, list) or len(transfers) < 1 or len(transfers) > 32:
        raise ApiError(422, "validation_failed", "transfers must contain 1 to 32 items")

    validated_transfers = []
    async with store.lock:
        for t in transfers:
            if not isinstance(t, dict):
                raise ApiError(422, "validation_failed", "Transfer must be an object")
            from_h = t.get("from_handle")
            to_h = t.get("to_handle")
            amt_val = t.get("amount")
            note = t.get("note", "")
            visibility = t.get("visibility", "public")

            if not isinstance(from_h, str) or not isinstance(to_h, str):
                raise ApiError(422, "validation_failed", "Invalid handles")
            from_u = store.find_user_by_handle(from_h)
            if not from_u:
                raise ApiError(404, "not_found", f"from_handle '{from_h}' not found")
            to_u = store.find_user_by_handle(to_h)
            if not to_u:
                raise ApiError(404, "not_found", f"to_handle '{to_h}' not found")
            if from_h == to_h:
                raise ApiError(422, "self_payment", "Self-transfer is not permitted in settlement")

            amt = validate_amount(amt_val)
            if not isinstance(note, str) or len(note) > 200:
                raise ApiError(422, "validation_failed", "note must be a string up to 200 characters")
            if visibility not in ("public", "private"):
                raise ApiError(422, "validation_failed", "visibility must be public or private")

            validated_transfers.append({
                "from_user": from_u,
                "to_user": to_u,
                "amount": amt,
                "note": note,
                "visibility": visibility
            })

        delta_balances: Dict[str, int] = {}
        for vt in validated_transfers:
            f_id = vt["from_user"]["id"]
            t_id = vt["to_user"]["id"]
            delta_balances[f_id] = delta_balances.get(f_id, 0) - vt["amount"]
            delta_balances[t_id] = delta_balances.get(t_id, 0) + vt["amount"]

        for u_id, delta in delta_balances.items():
            u = store.users[u_id]
            tot, avail, hld = store.get_user_balances(u_id)
            if avail + delta < 0:
                raise ApiError(409, "insufficient_funds", f"Wallet '{u['handle']}' would overdraw available funds")

        settlement_id = store.next_id("stl")
        committed_at = current_time_rfc3339()
        created_payments = []

        for vt in validated_transfers:
            from_u = vt["from_user"]
            to_u = vt["to_user"]
            amt = vt["amount"]
            from_u["balance"] -= amt
            to_u["balance"] += amt

            payment_id = store.next_id("p")
            p_data = {
                "payment_id": payment_id,
                "from_user_id": from_u["id"],
                "from_handle": from_u["handle"],
                "to_user_id": to_u["id"],
                "to_handle": to_u["handle"],
                "amount": amt,
                "currency": store.currency,
                "note": vt["note"],
                "visibility": vt["visibility"],
                "request_id": None,
                "authorization_id": None,
                "settlement_id": settlement_id,
                "refund_of": None,
                "created_at": committed_at,
                "revisions": [{
                    "payment_id": payment_id,
                    "revision": 1,
                    "amount": amt,
                    "effective_at": committed_at,
                    "recorded_at": committed_at,
                    "reason": "",
                    "correction_batch_id": None
                }]
            }
            store.payments.append(p_data)
            created_payments.append(p_data)

        settlement_response = {
            "settlement_id": settlement_id,
            "committed_at": committed_at,
            "payments": created_payments
        }

        store.record_audit_event("SETTLEMENT_COMMITTED", {
            "settlement_id": settlement_id,
            "transfers_count": len(validated_transfers),
            "operator_id": user["id"]
        })
        for vt in validated_transfers:
            sentinel.record_and_evaluate(
                "SETTLEMENT_TRANSFER",
                vt["from_user"]["id"],
                vt["from_user"]["handle"],
                vt["to_user"]["id"],
                vt["to_user"]["handle"],
                vt["amount"],
                store.currency
            )

        cache_key = (user["id"], "POST", "/settlements", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": settlement_response
        }

        return settlement_response

# Authorizations & Holds
@app.post("/authorizations", status_code=201)
async def create_authorization(request: Request):
    user = await get_current_user(request)
    key, idem_info = await parse_and_validate_idempotency(request, user)
    if idem_info.get("replay"):
        return JSONResponse(status_code=200, content=idem_info["response"])

    body = idem_info["body"]
    to_handle = body.get("to_handle")
    amount_val = body.get("amount")
    note = body.get("note", "")
    visibility = body.get("visibility", "public")

    if not isinstance(to_handle, str):
        raise ApiError(422, "validation_failed", "Invalid to_handle")
    if to_handle == user["handle"]:
        raise ApiError(422, "self_payment", "Cannot authorize hold for yourself")

    amount = validate_amount(amount_val)

    if not isinstance(note, str) or len(note) > 200:
        raise ApiError(422, "validation_failed", "note must be a string up to 200 characters")
    if visibility not in ("public", "private"):
        raise ApiError(422, "validation_failed", "visibility must be public or private")

    async with store.lock:
        recipient = store.find_user_by_handle(to_handle)
        if not recipient:
            raise ApiError(404, "not_found", f"User with handle '{to_handle}' not found")

        total, available, held = store.get_user_balances(user["id"])
        if available < amount:
            raise ApiError(409, "insufficient_funds", "Insufficient available funds for authorization")

        auth_id = store.next_id("a")
        created_at_dt = datetime.now(timezone.utc)
        created_at = created_at_dt.isoformat()
        expires_at = (created_at_dt + timedelta(seconds=store.authorization_ttl_seconds)).isoformat()

        auth_data = {
            "authorization_id": auth_id,
            "from_user_id": user["id"],
            "from_handle": user["handle"],
            "to_user_id": recipient["id"],
            "to_handle": recipient["handle"],
            "amount": amount,
            "captured_amount": 0,
            "remaining_amount": amount,
            "currency": store.currency,
            "note": note,
            "visibility": visibility,
            "status": "open",
            "expires_at": expires_at,
            "closed_at": None,
            "events": [{"type": "created", "time": created_at, "amount": amount}],
            "payment_id": None,
            "payment_ids": [],
            "created_at": created_at
        }
        store.authorizations[auth_id] = auth_data

        cache_key = (user["id"], "POST", "/authorizations", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": auth_data
        }

        return auth_data

@app.post("/authorizations/{auth_id}/capture", status_code=201)
async def capture_authorization(auth_id: str, request: Request):
    user = await get_current_user(request)
    key, idem_info = await parse_and_validate_idempotency(request, user)
    if idem_info.get("replay"):
        return JSONResponse(status_code=200, content=idem_info["response"])

    body = idem_info["body"]
    amount_val = body.get("amount")
    final = body.get("final", True)
    if not isinstance(final, bool):
        raise ApiError(422, "validation_failed", "final must be a boolean")

    async with store.lock:
        auth = store.authorizations.get(auth_id)
        if not auth:
            raise ApiError(404, "not_found", "Authorization not found")
        if auth["to_user_id"] != user["id"]:
            raise ApiError(403, "forbidden", "Only the receiver may capture this authorization")

        current_status = store.get_auth_status(auth)
        if current_status == "expired":
            raise ApiError(409, "authorization_expired", "Authorization has expired")
        if current_status != "open":
            raise ApiError(409, "authorization_not_open", "Authorization is not open")

        if amount_val is None:
            capture_amount = auth["remaining_amount"]
        else:
            capture_amount = validate_amount(amount_val)

        if capture_amount > auth["remaining_amount"]:
            raise ApiError(422, "capture_exceeds_authorization", "Capture amount exceeds remaining authorization")

        payer = store.users.get(auth["from_user_id"])
        receiver = store.users.get(auth["to_user_id"])
        if not payer or not receiver:
            raise ApiError(404, "not_found", "Parties not found")

        payer["balance"] -= capture_amount
        receiver["balance"] += capture_amount

        payment_id = store.next_id("p")
        created_at = current_time_rfc3339()

        payment_data = {
            "payment_id": payment_id,
            "from_user_id": payer["id"],
            "from_handle": payer["handle"],
            "to_user_id": receiver["id"],
            "to_handle": receiver["handle"],
            "amount": capture_amount,
            "currency": store.currency,
            "note": auth["note"],
            "visibility": auth["visibility"],
            "request_id": None,
            "authorization_id": auth_id,
            "settlement_id": None,
            "refund_of": None,
            "created_at": created_at,
            "revisions": [{
                "payment_id": payment_id,
                "revision": 1,
                "amount": capture_amount,
                "effective_at": created_at,
                "recorded_at": created_at,
                "reason": "",
                "correction_batch_id": None
            }]
        }
        store.payments.append(payment_data)

        store.record_audit_event("AUTHORIZATION_CAPTURED", {
            "auth_id": auth_id,
            "payment_id": payment_id,
            "from_user_id": payer["id"],
            "to_user_id": receiver["id"],
            "amount": capture_amount,
            "currency": store.currency
        })
        sentinel.record_and_evaluate(
            "AUTH_CAPTURE",
            payer["id"],
            payer["handle"],
            receiver["id"],
            receiver["handle"],
            capture_amount,
            store.currency
        )

        auth["captured_amount"] += capture_amount
        auth["remaining_amount"] -= capture_amount
        auth["payment_id"] = payment_id
        auth["payment_ids"].append(payment_id)

        if final or auth["remaining_amount"] == 0:
            auth["status"] = "captured"
            auth["remaining_amount"] = 0
            auth["closed_at"] = created_at
            auth["events"].append({"type": "captured", "time": created_at, "captured": capture_amount, "final": True, "remaining_after": 0})
        else:
            auth["status"] = "open"
            auth["events"].append({"type": "captured", "time": created_at, "captured": capture_amount, "final": False, "remaining_after": auth["remaining_amount"]})

        cache_key = (user["id"], "POST", f"/authorizations/{auth_id}/capture", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": payment_data
        }

        return payment_data

@app.post("/authorizations/{auth_id}/void")
async def void_authorization(auth_id: str, request: Request):
    user = await get_current_user(request)
    async with store.lock:
        auth = store.authorizations.get(auth_id)
        if not auth:
            raise ApiError(404, "not_found", "Authorization not found")
        if auth["from_user_id"] != user["id"]:
            raise ApiError(403, "forbidden", "Only the payer may void this authorization")

        if auth["status"] == "voided":
            return auth

        current_status = store.get_auth_status(auth)
        if current_status in ("captured", "expired"):
            raise ApiError(409, "authorization_not_open", "Authorization is not open")

        now_str = current_time_rfc3339()
        auth["status"] = "voided"
        auth["remaining_amount"] = 0
        auth["closed_at"] = now_str
        auth["events"].append({"type": "voided", "time": now_str})
        return auth

@app.get("/authorizations")
async def list_authorizations(request: Request):
    if request.headers.get("accept", "").startswith("text/html"):
        return HTMLResponse(HTML_TEMPLATE)

    user = await get_current_user(request)
    params = request.query_params
    direction = params.get("direction")
    status = params.get("status")
    limit_str = params.get("limit", "50")
    offset_str = params.get("offset", "0")

    if direction is not None and direction not in ("incoming", "outgoing"):
        raise ApiError(422, "validation_failed", "Invalid direction")
    if status is not None and status not in ("open", "captured", "voided", "expired"):
        raise ApiError(422, "validation_failed", "Invalid status")

    limit = parse_int_query_param(limit_str, "limit", 1, 200)
    offset = parse_int_query_param(offset_str, "offset", 0)

    async with store.lock:
        filtered = []
        for a in store.authorizations.values():
            is_incoming = (a["to_user_id"] == user["id"])
            is_outgoing = (a["from_user_id"] == user["id"])
            if not is_incoming and not is_outgoing:
                continue
            if direction == "incoming" and not is_incoming:
                continue
            if direction == "outgoing" and not is_outgoing:
                continue
            curr_status = store.get_auth_status(a)
            if status and curr_status != status:
                continue
            item = copy.copy(a)
            item["status"] = curr_status
            if curr_status != "open":
                item["remaining_amount"] = 0
            filtered.append(item)

        filtered.sort(key=lambda x: x["created_at"], reverse=True)
        items = filtered[offset : offset + limit]
        has_more = (offset + limit) < len(filtered)
        return {"authorizations": items, "has_more": has_more}

# Enterprise Audit & Sentinel Endpoints
@app.get("/audit/verify")
async def get_audit_verify():
    async with store.lock:
        return store.verify_audit_chain()

@app.get("/audit/zero-sum")
async def get_zero_sum_status():
    async with store.lock:
        return store.verify_zero_sum_invariant()

@app.get("/audit/sentinel")
async def get_sentinel_status():
    return {
        "stats": sentinel.get_stats(),
        "alerts": sentinel.get_recent_alerts(50)
    }

@app.get("/audit/chain")
async def get_audit_chain(limit: int = 20):
    async with store.lock:
        return {
            "total_blocks": len(store.audit_chain),
            "recent_blocks": store.audit_chain[-limit:] if store.audit_chain else []
        }

