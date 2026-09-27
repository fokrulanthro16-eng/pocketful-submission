from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message or code

class ErrorDetail(BaseModel):
    code: str
    message: str

class ErrorResponse(BaseModel):
    error: ErrorDetail

class UserSignupRequest(BaseModel):
    email: str
    password: str
    display_name: str

class UserLoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    user_id: str
    display_name: str
    token: str

class MeResponse(BaseModel):
    user_id: str
    display_name: str
    handle: str
    balance: int
    total: int
    available: int
    held: int
    currency: str
    minor_units: int
    as_of: Optional[str] = None
    known_at: Optional[str] = None

class PaymentCreateRequest(BaseModel):
    to_handle: str
    amount: Any
    note: Optional[str] = ""
    visibility: Optional[str] = "public"

class PaymentResponse(BaseModel):
    payment_id: str
    from_user_id: str
    from_handle: str
    to_user_id: str
    to_handle: str
    amount: int
    currency: str
    note: str
    visibility: str
    request_id: Optional[str] = None
    authorization_id: Optional[str] = None
    settlement_id: Optional[str] = None
    refund_of: Optional[str] = None
    created_at: str

class RequestCreateRequest(BaseModel):
    payer_handle: str
    amount: Any
    note: Optional[str] = ""

class RequestPayRequest(BaseModel):
    visibility: Optional[str] = "public"

class RequestResponse(BaseModel):
    request_id: str
    requester_id: str
    requester_handle: str
    payer_id: str
    payer_handle: str
    amount: int
    currency: str
    note: str
    status: Literal["pending", "paid", "declined", "cancelled"]
    payment_id: Optional[str] = None
    created_at: str

class SplitCreateRequest(BaseModel):
    amount: Any
    participant_handles: List[str]
    note: Optional[str] = ""

class SplitShare(BaseModel):
    handle: str
    amount: int

class SplitResponse(BaseModel):
    split_id: str
    amount: int
    currency: str
    note: str
    shares: List[SplitShare]
    requests: List[RequestResponse]
    created_at: str

class SettlementTransfer(BaseModel):
    from_handle: str
    to_handle: str
    amount: Any
    note: Optional[str] = ""
    visibility: Optional[str] = "public"

class SettlementCreateRequest(BaseModel):
    transfers: List[SettlementTransfer]

class SettlementResponse(BaseModel):
    settlement_id: str
    committed_at: str
    payments: List[PaymentResponse]

class AuthorizationCreateRequest(BaseModel):
    to_handle: str
    amount: Any
    note: Optional[str] = ""
    visibility: Optional[str] = "public"

class AuthorizationCaptureRequest(BaseModel):
    amount: Optional[Any] = None
    final: Optional[bool] = True

class AuthorizationResponse(BaseModel):
    authorization_id: str
    from_user_id: str
    from_handle: str
    to_user_id: str
    to_handle: str
    amount: int
    captured_amount: int
    remaining_amount: int
    currency: str
    note: str
    visibility: str
    status: Literal["open", "captured", "voided", "expired"]
    expires_at: str
    closed_at: Optional[str] = None
    payment_id: Optional[str] = None
    payment_ids: List[str] = []
    created_at: str

class PaymentCorrectionRequest(BaseModel):
    expected_revision: int
    amount: Any
    effective_at: str
    reason: str

class PaymentCorrectionResponse(BaseModel):
    payment_id: str
    revision: int
    amount: int
    effective_at: str
    recorded_at: str
    reason: str
    correction_batch_id: Optional[str] = None

class RevisionItem(BaseModel):
    payment_id: str
    revision: int
    amount: int
    effective_at: str
    recorded_at: str
    reason: str
    correction_batch_id: Optional[str] = None

class RevisionsListResponse(BaseModel):
    revisions: List[RevisionItem]

class StatementEntry(BaseModel):
    payment: Dict[str, Any]
    delta: int
    balance_after: int
    revision: int
    effective_at: str
    recorded_at: str

class StatementResponse(BaseModel):
    opening_balance: int
    entries: List[StatementEntry]
    closing_balance: int
    has_more: bool
    snapshot: str
    known_at: Optional[str] = None

class RefundCreateRequest(BaseModel):
    amount: Any

class BatchCorrectionItem(BaseModel):
    payment_id: str
    expected_revision: int
    amount: Any
    effective_at: str
    reason: str

class BatchCorrectionRequest(BaseModel):
    corrections: List[BatchCorrectionItem]

class BatchCorrectionResponse(BaseModel):
    correction_batch_id: str
    recorded_at: str
    revisions: List[RevisionItem]

