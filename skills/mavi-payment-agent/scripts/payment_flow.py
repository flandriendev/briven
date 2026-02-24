"""
mavi Payment Agent — Payment Flow Orchestrator

General-purpose, multi-user payment lifecycle manager:
  - Card linking / unlinking (per user, by last4 + email)
  - Balance check, loading, charging, refunds
  - Mock mode for MVP / testing (no live API needed)

All Wallester/mavi API calls are routed through this module so that
the SKILL.md agent logic stays declarative and the scripts stay
independently testable.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MOCK_MODE = os.getenv("MAVI_MOCK_MODE", "true").lower() in ("true", "1", "yes")
API_BASE = os.getenv("MAVI_API_BASE", "https://api.mavi-finans.com/v1")
API_KEY = os.getenv("MAVI_API_KEY", "")


# ---------------------------------------------------------------------------
# Enums & models
# ---------------------------------------------------------------------------

class CardStatus(str, Enum):
    NONE = "none"
    ORDERED = "ordered"
    ACTIVE = "active"
    BLOCKED = "blocked"


class PaymentStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    REFUNDED = "refunded"


@dataclass
class CardInfo:
    card_token: str
    status: CardStatus
    last4: str
    balance: float
    currency: str = "EUR"
    holder_email: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class LinkResult:
    success: bool
    card: Optional[CardInfo] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"success": self.success}
        if self.card:
            d["card"] = self.card.to_dict()
        if self.error:
            d["error"] = self.error
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class PaymentResult:
    transaction_id: str
    status: PaymentStatus
    amount: float
    currency: str
    card_last4: str
    description: str
    timestamp: str
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Mock registry (in-memory, per process — for testing only)
# ---------------------------------------------------------------------------

_MOCK_CARDS: dict[str, CardInfo] = {}


def _mock_link_card(last4: str, email: str) -> LinkResult:
    token = f"mavi_linked_{uuid.uuid4().hex[:8]}"
    card = CardInfo(
        card_token=token,
        status=CardStatus.ACTIVE,
        last4=last4,
        balance=100.00,
        holder_email=email,
    )
    _MOCK_CARDS[token] = card
    return LinkResult(success=True, card=card)


def _mock_unlink_card(card_token: str) -> dict:
    _MOCK_CARDS.pop(card_token, None)
    return {"status": "unlinked", "card_token": card_token}


def _mock_issue_card(email: str) -> CardInfo:
    token = f"mavi_test_card_{uuid.uuid4().hex[:8]}"
    card = CardInfo(
        card_token=token,
        status=CardStatus.ACTIVE,
        last4=str(hash(token) % 10000).zfill(4),
        balance=100.00,
        holder_email=email,
    )
    _MOCK_CARDS[token] = card
    return card


def _mock_get_balance(card_token: str) -> float:
    card = _MOCK_CARDS.get(card_token)
    return card.balance if card else 100.00


def _mock_charge(card_token: str, amount: float, description: str, metadata: dict) -> PaymentResult:
    card = _MOCK_CARDS.get(card_token)
    last4 = card.last4 if card else "0000"

    if card and card.balance < amount:
        return PaymentResult(
            transaction_id=f"tx_fail_{uuid.uuid4().hex[:8]}",
            status=PaymentStatus.FAILED,
            amount=amount,
            currency="EUR",
            card_last4=last4,
            description=description,
            timestamp=_now(),
            error="Insufficient balance",
            metadata=metadata,
        )

    if card:
        card.balance = round(card.balance - amount, 2)

    return PaymentResult(
        transaction_id=f"tx_{uuid.uuid4().hex[:12]}",
        status=PaymentStatus.SUCCESS,
        amount=amount,
        currency="EUR",
        card_last4=last4,
        description=description,
        timestamp=_now(),
        metadata=metadata,
    )


def _mock_load_card(card_token: str, amount: float) -> dict:
    card = _MOCK_CARDS.get(card_token)
    if card:
        card.balance = round(card.balance + amount, 2)
        return {"status": "success", "new_balance": card.balance}
    return {"status": "success", "new_balance": amount}


def _mock_refund(transaction_id: str) -> dict:
    return {
        "status": "refunded",
        "transaction_id": transaction_id,
        "refund_id": f"ref_{uuid.uuid4().hex[:8]}",
    }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Public API — Card Management
# ---------------------------------------------------------------------------

def link_card(last4: str, email: str, briven_user_id: str = "") -> LinkResult:  # noqa: ARG001
    """
    Link an existing mavi Card to a Briven user by last-4 digits + email.

    In live mode, calls POST /v1/cards/link to verify ownership and
    retrieve a secure card_token. In mock mode, simulates success.
    """
    if not last4 or not email:
        return LinkResult(success=False, error="Both last4 and email are required.")
    if len(last4) != 4 or not last4.isdigit():
        return LinkResult(success=False, error="last4 must be exactly 4 digits.")

    if MOCK_MODE:
        return _mock_link_card(last4, email)

    # Live API placeholder:
    # resp = requests.post(f"{API_BASE}/cards/link",
    #     headers={"Authorization": f"Bearer {API_KEY}"},
    #     json={"last4": last4, "email": email, "briven_user_id": briven_user_id})
    # data = resp.json()
    # return LinkResult(success=True, card=CardInfo(...))
    raise NotImplementedError("Live Wallester API not configured. Set MAVI_MOCK_MODE=true for testing.")


def unlink_card(card_token: str) -> dict:
    """Unlink a mavi Card from a Briven user. Preserves reward history."""
    if MOCK_MODE:
        return _mock_unlink_card(card_token)

    # Live API placeholder:
    # resp = requests.post(f"{API_BASE}/cards/{card_token}/unlink", ...)
    raise NotImplementedError("Live API not configured.")


def issue_card(email: str) -> CardInfo:
    """Issue a new mavi virtual card for a user."""
    if MOCK_MODE:
        return _mock_issue_card(email)

    raise NotImplementedError("Live API not configured.")


def get_balance(card_token: str) -> float:
    """Check mavi Card balance in EUR."""
    if MOCK_MODE:
        return _mock_get_balance(card_token)

    raise NotImplementedError("Live API not configured.")


def load_card(card_token: str, amount: float) -> dict:
    """Simulate or execute loading funds onto a mavi Card."""
    if MOCK_MODE:
        return _mock_load_card(card_token, amount)

    raise NotImplementedError("Live API not configured.")


# ---------------------------------------------------------------------------
# Public API — Payments
# ---------------------------------------------------------------------------

def charge_payment(
    card_token: str,
    amount: float,
    service_name: str,
    tier: str,
    user_id: str = "",
    first_payment_discount_applied: bool = False,
) -> PaymentResult:
    """
    Charge a payment against a linked mavi Card.

    Parameters
    ----------
    card_token : str
        The user's linked mavi Card token.
    amount : float
        Amount to charge in EUR (after any discounts).
    service_name : str
        The Briven service being purchased.
    tier : str
        The service tier.
    user_id : str
        Briven user identifier.
    first_payment_discount_applied : bool
        Whether this charge includes the first-payment discount.
    """
    description = f"Briven {service_name} - {tier}"
    metadata = {
        "briven_user_id": user_id,
        "service": service_name,
        "tier": tier,
        "cashback_eligible": True,
        "first_payment_discount_applied": first_payment_discount_applied,
    }

    if MOCK_MODE:
        return _mock_charge(card_token, amount, description, metadata)

    raise NotImplementedError("Live API not configured.")


def refund_payment(transaction_id: str) -> dict:
    """Initiate a refund for a previous transaction."""
    if MOCK_MODE:
        return _mock_refund(transaction_id)

    raise NotImplementedError("Live API not configured.")


def get_card_status(card_token: Optional[str]) -> CardStatus:
    """Determine card status from token."""
    if not card_token:
        return CardStatus.NONE
    if MOCK_MODE:
        card = _MOCK_CARDS.get(card_token)
        return card.status if card else CardStatus.NONE
    raise NotImplementedError("Live API not configured.")


# ---------------------------------------------------------------------------
# Full payment flow (orchestrator)
# ---------------------------------------------------------------------------

def execute_payment_flow(
    card_token: str,
    service: str,
    tier: str,
    amount: float,
    is_first_payment: bool = False,
    user_id: str = "",
    cumulative_spend: float = 0.0,
    cashback_balance: float = 0.0,
    config: Optional[dict[str, Any]] = None,
) -> dict:
    """
    End-to-end payment flow for any Briven user:
      1. Verify card balance
      2. Calculate rewards (using configurable rates)
      3. Process charge (discounted amount)
      4. Return consolidated result with reward breakdown

    Returns a dict ready for agent display.
    """
    from scripts.cashback import calculate_cashback

    # 1. Check balance
    balance = get_balance(card_token)
    if balance < amount:
        return {
            "success": False,
            "error": f"Insufficient balance: {balance:.2f} EUR available, {amount:.2f} EUR needed.",
            "suggestion": f"Load at least {amount - balance:.2f} EUR more onto your mavi Card.",
        }

    # 2. Compute effective amount with configurable rewards
    rewards = calculate_cashback(
        amount=amount,
        is_briven=True,
        is_first_payment=is_first_payment,
        cumulative_spend=cumulative_spend,
        cashback_balance=cashback_balance,
        config=config,
    )

    # 3. Charge the discounted amount
    result = charge_payment(
        card_token=card_token,
        amount=rewards.charged,
        service_name=service,
        tier=tier,
        user_id=user_id,
        first_payment_discount_applied=is_first_payment,
    )

    if result.status != PaymentStatus.SUCCESS:
        return {
            "success": False,
            "error": result.error or "Payment failed",
            "transaction_id": result.transaction_id,
        }

    # 4. Consolidated result
    return {
        "success": True,
        "transaction": result.to_dict(),
        "rewards": rewards.to_dict(),
        "memory_updates": {
            "mavi:first_payment_used": "true" if is_first_payment else None,
            "mavi:cumulative_spend": str(rewards.new_cumulative),
            "mavi:cashback_balance": str(rewards.new_cashback_balance),
            "mavi:tier": rewards.tier,
        },
        "summary": {
            "service": f"{service} {tier}",
            "original_price": rewards.original_amount,
            "discount_applied": rewards.discount,
            "amount_charged": rewards.charged,
            "cashback_earned": rewards.cashback,
            "milestone_bonus": rewards.milestone_bonus,
            "milestones_hit": rewards.milestones_hit,
            "new_cumulative_spend": rewards.new_cumulative,
            "new_cashback_balance": rewards.new_cashback_balance,
            "tier": rewards.tier,
        },
    }


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== mavi Payment Flow Test (Mock Mode, Multi-User) ===\n")

    # User A links an existing card
    print("--- User A: Link card ---")
    link_a = link_card("7842", "alice@example.com", briven_user_id="user_alice")
    print(link_a.to_json())

    # User B links a different card
    print("\n--- User B: Link card ---")
    link_b = link_card("3691", "bob@example.com", briven_user_id="user_bob")
    print(link_b.to_json())

    # User A loads and pays
    print("\n--- User A: Load + Pay ---")
    if link_a.card:
        load_card(link_a.card.card_token, 50.0)
        flow_a = execute_payment_flow(
            card_token=link_a.card.card_token,
            service="premium",
            tier="pro",
            amount=19.0,
            is_first_payment=True,
            user_id="user_alice",
            cumulative_spend=0.0,
            cashback_balance=0.0,
        )
        print(json.dumps(flow_a, indent=2))

    # User B pays with custom config (20% discount)
    print("\n--- User B: Pay with custom config ---")
    if link_b.card:
        custom_cfg = {"first_payment_discount": 0.20}
        flow_b = execute_payment_flow(
            card_token=link_b.card.card_token,
            service="sponsor",
            tier="growth",
            amount=10.0,
            is_first_payment=True,
            user_id="user_bob",
            cumulative_spend=450.0,
            cashback_balance=8.50,
            config=custom_cfg,
        )
        print(json.dumps(flow_b, indent=2))

    # User A unlinks
    print("\n--- User A: Unlink card ---")
    if link_a.card:
        unlink_result = unlink_card(link_a.card.card_token)
        print(json.dumps(unlink_result, indent=2))
