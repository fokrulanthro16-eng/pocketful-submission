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
from app.store import current_time_rfc3339, derive_handle, hash_password, store, validate_amount, verify_password
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

def parse_int_query_param(val: Optional[str], name: str, min_val: int, max_val: Optional[int] = None) -> int:
    if val is None:
        return min_val
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

# 3.2 Health
@app.get("/health")
async def health():
    return {"status": "ok"}

# 3.3 Reset and seed
@app.post("/_test/reset", status_code=204)
async def test_reset(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "malformed_request", "Invalid JSON")
    async with store.lock:
        store.reset_fixture(body)
    return Response(status_code=204)

# 10. Export and import
@app.get("/_test/export")
async def test_export():
    async with store.lock:
        return store.export_state()

@app.post("/_test/import", status_code=204)
async def test_import(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "malformed_request", "Invalid JSON")
    async with store.lock:
        store.import_state(body)
    return Response(status_code=204)

# 6. Authentication
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
            "balance": 0
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

# 8. API
@app.get("/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    async with store.lock:
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
            "created_at": created_at
        }
        store.payments.append(payment_data)

        cache_key = (user["id"], "POST", "/payments", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": payment_data
        }

        return payment_data

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
            raise ApiError(403, "forbidden", "Only the payer may pay this request")
        if req_item["status"] != "pending":
            raise ApiError(409, "request_not_pending", "Request is not pending")

        amount = req_item["amount"]
        total, available, held = store.get_user_balances(user["id"])
        if available < amount:
            raise ApiError(409, "insufficient_funds", "Insufficient funds to pay request")

        recipient = store.find_user_by_id(req_item["requester_id"])
        if not recipient:
            raise ApiError(404, "not_found", "Requester user not found")

        # Atomic transfer
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
            "created_at": created_at
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
    handles = body.get("participant_handles")
    note = body.get("note", "")

    amount = validate_amount(amount_val)

    if not isinstance(handles, list) or len(handles) == 0:
        raise ApiError(422, "validation_failed", "participant_handles must be a non-empty array")
    if len(handles) != len(set(handles)):
        raise ApiError(422, "validation_failed", "Duplicate participant_handles not permitted")
    if not isinstance(note, str) or len(note) > 200:
        raise ApiError(422, "validation_failed", "note must be a string up to 200 characters")

    async with store.lock:
        for h in handles:
            if not store.find_user_by_handle(h):
                raise ApiError(404, "not_found", f"Participant handle '{h}' not found")

        n = len(handles)
        base = amount // n
        remainder = amount % n
        split_shares = []
        for i, h in enumerate(handles):
            share_amount = base + (1 if i < remainder else 0)
            split_shares.append({"handle": h, "amount": share_amount})

        split_id = store.next_id("sp")
        created_at = current_time_rfc3339()

        created_requests = []
        for share in split_shares:
            if share["handle"] == user["handle"]:
                continue
            payer = store.find_user_by_handle(share["handle"])
            req_id = store.next_id("rq")
            req_data = {
                "request_id": req_id,
                "requester_id": user["id"],
                "requester_handle": user["handle"],
                "payer_id": payer["id"],
                "payer_handle": payer["handle"],
                "amount": share["amount"],
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
            "shares": split_shares,
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

        # Net balance calculation across all affected wallets evaluated against available
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
                "created_at": committed_at
            }
            store.payments.append(p_data)
            created_payments.append(p_data)

        settlement_response = {
            "settlement_id": settlement_id,
            "committed_at": committed_at,
            "payments": created_payments
        }

        cache_key = (user["id"], "POST", "/settlements", key)
        store.idempotency_records[cache_key] = {
            "body": body,
            "status_code": 201,
            "response": settlement_response
        }

        return settlement_response

# ---- STAGE 2: AUTHORIZATIONS & CAPTURES ----------------------------------

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

        # Move money
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
            "created_at": created_at
        }
        store.payments.append(payment_data)

        auth["captured_amount"] += capture_amount
        auth["remaining_amount"] -= capture_amount
        auth["payment_id"] = payment_id
        auth["payment_ids"].append(payment_id)

        if final or auth["remaining_amount"] == 0:
            auth["status"] = "captured"
            auth["remaining_amount"] = 0
        else:
            auth["status"] = "open"

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

        auth["status"] = "voided"
        auth["remaining_amount"] = 0
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
