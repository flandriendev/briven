"""
mavi Rewards Tracker — Transaction Ledger & Analytics

Manages the reward transaction log, monthly aggregations, milestone
tracking, and reward claiming. All data is stored as JSON strings
in Briven memory (mavi:tracker:* namespace).

Standalone — no external dependencies. Safe for code_execution_tool.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, asdict, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Config defaults (same rates as mavi-payment-agent cashback.py)
# ---------------------------------------------------------------------------

DEFAULT_TRACKER_CONFIG: dict[str, Any] = {
    "base_cashback_rate": 0.01,
    "briven_boost_rate": 0.01,
    "gold_cashback_rate": 0.03,
    "gold_threshold": 1000.0,
    "milestones": {
        500: {"bonus": 10.0, "label": "500 Club"},
        1000: {"bonus": 0.0, "label": "Gold Status"},
    },
    "history_limit": 100,
    "currency": "EUR",
    "claim_threshold": 5.0,
    "approaching_threshold": 50.0,
}


def _cfg(config: Optional[dict[str, Any]], key: str, fallback: Any = None) -> Any:
    if config and key in config:
        return config[key]
    return DEFAULT_TRACKER_CONFIG.get(key, fallback)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Transaction:
    id: str
    timestamp: str
    amount: float
    original_amount: float
    discount: float
    cashback: float
    service: str
    tier: str
    category: str  # "briven" | "partner" | "other"
    rate_applied: float
    milestone_bonus: float
    cumulative_after: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClaimResult:
    success: bool
    amount: float
    destination: str  # "card_balance" | "next_payment"
    reference: str
    timestamp: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class MonthlyStats:
    month: str  # "YYYY-MM"
    spend: float
    cashback: float
    bonus: float
    tx_count: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TrackerState:
    """Consolidated tracker state for dashboard rendering."""
    card_last4: str
    card_status: str
    tier: str
    cumulative_spend: float
    cashback_balance: float
    total_earned: float
    total_discounts: float
    tx_log: list[dict]
    monthly_spend: dict[str, float]
    monthly_cashback: dict[str, float]
    milestones_log: list[dict]
    claims_log: list[dict]
    last_synced: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Transaction recording
# ---------------------------------------------------------------------------

def record_transaction(
    tx_log: list[dict],
    monthly_spend: dict[str, float],
    monthly_cashback: dict[str, float],
    milestones_log: list[dict],
    *,
    amount: float,
    original_amount: float = 0.0,
    discount: float = 0.0,
    service: str = "",
    tier: str = "",
    category: str = "briven",
    cumulative_before: float = 0.0,
    cashback_balance: float = 0.0,
    total_earned: float = 0.0,
    total_discounts: float = 0.0,
    tx_id: str = "",
    timestamp: str = "",
    config: Optional[dict[str, Any]] = None,
    history_limit: int = 100,
) -> dict:
    """
    Record a new transaction and update all tracker aggregations.

    Parameters
    ----------
    tx_log : list
        Current transaction log (mutable, will be updated in place).
    monthly_spend / monthly_cashback : dict
        Monthly aggregation dicts (mutable).
    milestones_log : list
        Milestone events log (mutable).
    amount : float
        Charged amount (after discount).
    original_amount : float
        Original price before discount.
    discount : float
        Discount applied.
    service, tier, category : str
        Transaction metadata.
    cumulative_before : float
        Cumulative spend before this transaction.
    cashback_balance, total_earned, total_discounts : float
        Current running totals.
    config : dict, optional
        Rate overrides.

    Returns
    -------
    dict with updated totals and the new transaction record.
    """
    ts = timestamp or _now()
    tid = tx_id or f"tx_{uuid.uuid4().hex[:12]}"
    orig = original_amount if original_amount > 0 else amount + discount

    # Cashback rate
    gold_threshold = _cfg(config, "gold_threshold", 1000.0)
    if cumulative_before >= gold_threshold:
        rate = _cfg(config, "gold_cashback_rate", 0.03)
    elif category == "briven":
        rate = _cfg(config, "base_cashback_rate", 0.01) + _cfg(config, "briven_boost_rate", 0.01)
    else:
        rate = _cfg(config, "base_cashback_rate", 0.01)

    cashback = round(amount * rate, 2)
    new_cumulative = round(cumulative_before + amount, 2)

    # Milestones
    milestone_bonus = 0.0
    milestones = _cfg(config, "milestones", {})
    for thr_key, info in sorted(milestones.items(), key=lambda kv: float(kv[0])):
        thr = float(thr_key)
        if cumulative_before < thr <= new_cumulative:
            bonus = info.get("bonus", 0.0)
            milestone_bonus += bonus
            milestones_log.append({
                "timestamp": ts,
                "milestone": thr,
                "label": info.get("label", f"Milestone {thr}"),
                "bonus": bonus,
                "cumulative_at": new_cumulative,
            })
    milestone_bonus = round(milestone_bonus, 2)

    # Transaction entry
    tx = Transaction(
        id=tid,
        timestamp=ts,
        amount=amount,
        original_amount=orig,
        discount=discount,
        cashback=cashback,
        service=service,
        tier=tier,
        category=category,
        rate_applied=rate,
        milestone_bonus=milestone_bonus,
        cumulative_after=new_cumulative,
    )

    # Update log (newest first, enforce limit)
    tx_log.insert(0, tx.to_dict())
    limit = _cfg(config, "history_limit", history_limit)
    while len(tx_log) > limit:
        tx_log.pop()

    # Monthly aggregation
    month_key = ts[:7]  # "YYYY-MM"
    monthly_spend[month_key] = round(monthly_spend.get(month_key, 0.0) + amount, 2)
    monthly_cashback[month_key] = round(monthly_cashback.get(month_key, 0.0) + cashback + milestone_bonus, 2)

    # Running totals
    new_total_earned = round(total_earned + cashback + milestone_bonus, 2)
    new_total_discounts = round(total_discounts + discount, 2)
    new_cashback_balance = round(cashback_balance + cashback + milestone_bonus, 2)

    return {
        "transaction": tx.to_dict(),
        "updated_totals": {
            "cumulative_spend": new_cumulative,
            "cashback_balance": new_cashback_balance,
            "total_earned": new_total_earned,
            "total_discounts": new_total_discounts,
            "tier": "gold" if new_cumulative >= gold_threshold else "standard",
        },
        "milestones_triggered": [m for m in milestones_log if m["timestamp"] == ts],
        "memory_updates": {
            "mavi:cumulative_spend": str(new_cumulative),
            "mavi:cashback_balance": str(new_cashback_balance),
            "mavi:tier": "gold" if new_cumulative >= gold_threshold else "standard",
            "mavi:tracker:tx_log": json.dumps(tx_log),
            "mavi:tracker:monthly_spend": json.dumps(monthly_spend),
            "mavi:tracker:monthly_cashback": json.dumps(monthly_cashback),
            "mavi:tracker:milestones_log": json.dumps(milestones_log),
            "mavi:tracker:total_earned": str(new_total_earned),
            "mavi:tracker:total_discounts": str(new_total_discounts),
            "mavi:tracker:last_synced": ts,
        },
    }


# ---------------------------------------------------------------------------
# Reward claiming
# ---------------------------------------------------------------------------

def claim_rewards(
    amount: float,
    destination: str = "card_balance",
    cashback_balance: float = 0.0,
    claims_log: Optional[list[dict]] = None,
) -> ClaimResult:
    """
    Claim rewards — transfer to card balance or apply to next payment.

    In mock mode, always succeeds. In production, calls POST /v1/rewards/claim.
    """
    if claims_log is None:
        claims_log = []

    ts = _now()
    ref = f"claim_{uuid.uuid4().hex[:6]}"

    if amount <= 0:
        return ClaimResult(
            success=False, amount=0, destination=destination,
            reference="", timestamp=ts, error="Claim amount must be > 0.",
        )

    if amount > cashback_balance:
        return ClaimResult(
            success=False, amount=amount, destination=destination,
            reference="", timestamp=ts,
            error=f"Insufficient balance: {cashback_balance:.2f} EUR available.",
        )

    # Mock: always succeeds
    result = ClaimResult(
        success=True, amount=amount, destination=destination,
        reference=ref, timestamp=ts,
    )

    claims_log.append(result.to_dict())
    return result


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------

def get_monthly_stats(
    tx_log: list[dict],
    month: str,  # "YYYY-MM"
) -> MonthlyStats:
    """Compute stats for a specific month from the transaction log."""
    spend = 0.0
    cashback = 0.0
    bonus = 0.0
    count = 0

    for tx in tx_log:
        if tx.get("timestamp", "")[:7] == month:
            spend += tx.get("amount", 0.0)
            cashback += tx.get("cashback", 0.0)
            bonus += tx.get("milestone_bonus", 0.0)
            count += 1

    return MonthlyStats(
        month=month,
        spend=round(spend, 2),
        cashback=round(cashback, 2),
        bonus=round(bonus, 2),
        tx_count=count,
    )


def get_milestone_proximity(
    cumulative_spend: float,
    config: Optional[dict[str, Any]] = None,
) -> list[dict]:
    """
    Return a list of milestones with distance and completion percentage.
    """
    milestones = _cfg(config, "milestones", {})
    results = []
    for thr_key, info in sorted(milestones.items(), key=lambda kv: float(kv[0])):
        thr = float(thr_key)
        distance = max(0.0, round(thr - cumulative_spend, 2))
        pct = min(100.0, round((cumulative_spend / thr) * 100, 1)) if thr > 0 else 100.0
        results.append({
            "threshold": thr,
            "label": info.get("label", f"Milestone {thr}"),
            "bonus": info.get("bonus", 0.0),
            "distance": distance,
            "percent": pct,
            "reached": cumulative_spend >= thr,
        })
    return results


def get_trend(
    monthly_spend: dict[str, float],
    current_month: str,
) -> Optional[dict]:
    """
    Compare current month spend vs previous month.
    Returns trend dict or None if not enough data.
    """
    parts = current_month.split("-")
    year, month_num = int(parts[0]), int(parts[1])
    if month_num == 1:
        prev_month = f"{year - 1}-12"
    else:
        prev_month = f"{year}-{month_num - 1:02d}"

    current = monthly_spend.get(current_month, 0.0)
    previous = monthly_spend.get(prev_month, 0.0)

    if previous == 0:
        return {"current": current, "previous": previous, "change_pct": None, "direction": "new"}

    change_pct = round(((current - previous) / previous) * 100, 1)
    direction = "up" if change_pct > 0 else "down" if change_pct < 0 else "flat"

    return {
        "current": current,
        "previous": previous,
        "change_pct": change_pct,
        "direction": direction,
    }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== mavi Rewards Tracker Test ===\n")

    tx_log: list[dict] = []
    monthly_spend: dict[str, float] = {}
    monthly_cashback: dict[str, float] = {}
    milestones_log: list[dict] = []
    claims_log: list[dict] = []

    # Record 3 transactions
    txns = [
        {"amount": 16.15, "original_amount": 19.0, "discount": 2.85, "service": "premium", "tier": "pro", "cumulative_before": 480.0, "cashback_balance": 9.50, "total_earned": 9.50, "total_discounts": 2.85, "timestamp": "2026-02-03T10:00:00Z"},
        {"amount": 10.0, "original_amount": 10.0, "discount": 0.0, "service": "sponsor", "tier": "growth", "cumulative_before": 496.15, "cashback_balance": 9.82, "total_earned": 9.82, "total_discounts": 2.85, "timestamp": "2026-02-14T12:00:00Z"},
        {"amount": 15.0, "original_amount": 15.0, "discount": 0.0, "service": "skill", "tier": "deploy-ai", "cumulative_before": 506.15, "cashback_balance": 20.02, "total_earned": 20.02, "total_discounts": 2.85, "timestamp": "2026-02-18T14:00:00Z"},
    ]

    for i, t in enumerate(txns):
        result = record_transaction(
            tx_log, monthly_spend, monthly_cashback, milestones_log, **t
        )
        print(f"--- Transaction {i + 1} ---")
        print(f"  Charged: {t['amount']} | Cashback: {result['transaction']['cashback']}")
        print(f"  Milestones: {result['milestones_triggered']}")
        print(f"  Cumulative: {result['updated_totals']['cumulative_spend']}")
        print()

    print(f"TX log entries: {len(tx_log)}")
    print(f"Monthly spend: {json.dumps(monthly_spend, indent=2)}")
    print(f"Monthly cashback: {json.dumps(monthly_cashback, indent=2)}")
    print(f"Milestones log: {json.dumps(milestones_log, indent=2)}")

    print("\n--- Monthly Stats (Feb 2026) ---")
    feb = get_monthly_stats(tx_log, "2026-02")
    print(json.dumps(feb.to_dict(), indent=2))

    print("\n--- Milestone Proximity ---")
    proximity = get_milestone_proximity(521.15)
    print(json.dumps(proximity, indent=2))

    print("\n--- Trend ---")
    monthly_spend["2026-01"] = 31.50
    trend = get_trend(monthly_spend, "2026-02")
    print(json.dumps(trend, indent=2))

    print("\n--- Claim Rewards ---")
    claim = claim_rewards(10.0, "card_balance", cashback_balance=20.32, claims_log=claims_log)
    print(claim.to_json())
    print(f"Claims log: {json.dumps(claims_log, indent=2)}")
