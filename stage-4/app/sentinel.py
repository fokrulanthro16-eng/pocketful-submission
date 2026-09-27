from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
import logging
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("pocketful.sentinel")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "sentinel": "%(name)s", "level": "%(levelname)s", "payload": %(message)s}'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class SentinelEngine:
    """Enterprise-grade real-time AML (Anti-Money Laundering) and Fraud Sentinel.
    
    Evaluates transaction velocities, smurfing patterns, and high-value anomalies
    in real time without disrupting low-latency transaction processing pipelines.
    """
    def __init__(self):
        # user_id -> deque of (timestamp_dt, amount)
        self.user_transfer_history: Dict[str, Deque[tuple[datetime, int]]] = {}
        self.alerts: Deque[dict] = deque(maxlen=200)

    def record_and_evaluate(
        self,
        event_type: str,
        user_id: str,
        user_handle: str,
        counterparty_id: Optional[str],
        counterparty_handle: Optional[str],
        amount: int,
        currency: str = "EUR"
    ) -> List[dict]:
        """Evaluates an outgoing transaction against real-time AML rules."""
        now = datetime.now(timezone.utc)
        triggered_alerts = []

        if user_id not in self.user_transfer_history:
            self.user_transfer_history[user_id] = deque(maxlen=100)
        history = self.user_transfer_history[user_id]
        history.append((now, amount))

        # Rule 1: High-Value Anomaly (> 100,000 minor units = 1,000.00 EUR or equivalent)
        if amount >= 100_000:
            alert = {
                "rule": "AML-001-HIGH-VALUE-TRANSFER",
                "severity": "ELEVATED",
                "user_id": user_id,
                "user_handle": user_handle,
                "counterparty": counterparty_handle or "N/A",
                "amount": amount,
                "currency": currency,
                "details": f"High value transfer exceeding standard threshold: {amount} {currency}",
                "timestamp": now.isoformat()
            }
            triggered_alerts.append(alert)
            self.alerts.append(alert)
            logger.warning(str(alert))

        # Rule 2: Smurfing / Rapid Micro-Transfer Velocity (>= 5 transfers in <= 60 seconds)
        recent_window = [t for t in history if (now - t[0]).total_seconds() <= 60]
        if len(recent_window) >= 5:
            alert = {
                "rule": "AML-002-RAPID-VELOCITY-BURST",
                "severity": "WARNING",
                "user_id": user_id,
                "user_handle": user_handle,
                "counterparty": counterparty_handle or "N/A",
                "amount": amount,
                "currency": currency,
                "details": f"Rapid velocity burst: {len(recent_window)} transactions executed in < 60s",
                "timestamp": now.isoformat()
            }
            triggered_alerts.append(alert)
            self.alerts.append(alert)
            logger.warning(str(alert))

        return triggered_alerts

    def get_recent_alerts(self, limit: int = 50) -> List[dict]:
        return list(self.alerts)[-limit:]

    def get_stats(self) -> dict:
        return {
            "total_alerts_recorded": len(self.alerts),
            "monitored_wallets": len(self.user_transfer_history),
            "status": "ONLINE_ACTIVE"
        }

    def reset(self):
        self.user_transfer_history.clear()
        self.alerts.clear()

sentinel = SentinelEngine()
