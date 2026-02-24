"""
mavi Payment Agent — Cashback & Rewards Calculator

General-purpose, user-configurable reward engine. All rates are defaults
that can be overridden via a config dict (loaded from user settings,
operator config, or skill-level overrides).

Standalone — no external dependencies. Safe for code_execution_tool
sandboxed runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Default configuration (overridable per user / per operator)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "first_payment_discount": 0.15,     # 15% off first payment
    "base_cashback_rate": 0.01,         # 1% on all transactions
    "briven_boost_rate": 0.01,          # +1% extra for Briven services
    "gold_cashback_rate": 0.03,         # 3% after Gold milestone
    "gold_threshold": 1000.0,           # EUR cumulative spend for Gold
    "milestones": {
        500:  {"bonus": 10.0, "label": "500 Milestone Bonus"},
        1000: {"bonus": 0.0,  "label": "Gold Status Unlock"},
    },
    "partner_offers": {
        "cyclingtravel": {
            "discount": 0.15,
            "label": "15% off Cyprus cycling holidays",
            "opt_in_required": True,
        },
    },
}

# Briven service pricing (EUR) — canonical reference
PRICING: dict[str, dict[str, float]] = {
    "sponsor": {
        "seed":   5.0,
        "growth": 10.0,
        "scale":  25.0,
    },
    "premium": {
        "starter": 9.0,
        "pro":     19.0,
        "team":    29.0,
    },
    "skill": {
        "min": 5.0,
        "max": 50.0,
    },
}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config(overrides: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Merge user/operator overrides on top of defaults."""
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        for key, val in overrides.items():
            if key in cfg and isinstance(cfg[key], dict) and isinstance(val, dict):
                cfg[key] = {**cfg[key], **val}
            else:
                cfg[key] = val
    return cfg


def _get(cfg: dict[str, Any], key: str, fallback: Any = None) -> Any:
    return cfg.get(key, DEFAULT_CONFIG.get(key, fallback))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CashbackResult:
    original_amount: float
    discount: float
    charged: float
    cashback: float
    milestone_bonus: float
    milestones_hit: list
    new_cumulative: float
    new_cashback_balance: float
    tier: str  # "standard" | "gold"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def get_cashback_rate(
    cumulative_spend: float,
    is_briven: bool = True,
    config: Optional[dict[str, Any]] = None,
) -> float:
    """Return the effective cashback rate."""
    cfg = config or DEFAULT_CONFIG
    gold_threshold = _get(cfg, "gold_threshold", 1000.0)

    if cumulative_spend >= gold_threshold:
        return _get(cfg, "gold_cashback_rate", 0.03)
    if is_briven:
        return _get(cfg, "base_cashback_rate", 0.01) + _get(cfg, "briven_boost_rate", 0.01)
    return _get(cfg, "base_cashback_rate", 0.01)


def get_tier(
    cumulative_spend: float,
    config: Optional[dict[str, Any]] = None,
) -> str:
    cfg = config or DEFAULT_CONFIG
    threshold = _get(cfg, "gold_threshold", 1000.0)
    return "gold" if cumulative_spend >= threshold else "standard"


def calculate_cashback(
    amount: float,
    *,
    is_briven: bool = True,
    is_first_payment: bool = False,
    cumulative_spend: float = 0.0,
    cashback_balance: float = 0.0,
    config: Optional[dict[str, Any]] = None,
) -> CashbackResult:
    """
    Compute the full rewards breakdown for a single payment.

    Parameters
    ----------
    amount : float
        Original price of the service (EUR).
    is_briven : bool
        Whether this is a Briven-service transaction (enables boost).
    is_first_payment : bool
        Whether the user qualifies for the first-payment discount.
    cumulative_spend : float
        Total historical spend before this transaction.
    cashback_balance : float
        Current cashback wallet balance.
    config : dict, optional
        Reward configuration overrides. If None, uses DEFAULT_CONFIG.

    Returns
    -------
    CashbackResult with full breakdown.
    """
    cfg = load_config(config)

    # --- discount ---
    discount_rate = _get(cfg, "first_payment_discount", 0.15)
    discount = round(amount * discount_rate, 2) if is_first_payment else 0.0
    charged = round(amount - discount, 2)

    # --- cashback ---
    rate = get_cashback_rate(cumulative_spend, is_briven=is_briven, config=cfg)
    cashback = round(charged * rate, 2)

    # --- milestones ---
    new_cumulative = round(cumulative_spend + charged, 2)
    milestone_bonus = 0.0
    milestones_hit: list[str] = []

    milestones = _get(cfg, "milestones", {})
    for threshold_str, info in sorted(milestones.items(), key=lambda kv: float(kv[0])):
        threshold = float(threshold_str)
        if cumulative_spend < threshold <= new_cumulative:
            milestone_bonus += info.get("bonus", 0.0)
            milestones_hit.append(info.get("label", f"Milestone {threshold}"))

    milestone_bonus = round(milestone_bonus, 2)

    # --- new balance ---
    new_balance = round(cashback_balance + cashback + milestone_bonus, 2)

    return CashbackResult(
        original_amount=amount,
        discount=discount,
        charged=charged,
        cashback=cashback,
        milestone_bonus=milestone_bonus,
        milestones_hit=milestones_hit,
        new_cumulative=new_cumulative,
        new_cashback_balance=new_balance,
        tier=get_tier(new_cumulative, config=cfg),
    )


def suggest_load_amount(
    service: str,
    tier: str,
    is_first_payment: bool = True,
    buffer: float = 1.0,
    config: Optional[dict[str, Any]] = None,
) -> dict:
    """
    Suggest how much to load on the mavi Card for a given service.

    Returns dict with suggested amount and breakdown.
    """
    cfg = load_config(config)
    discount_rate = _get(cfg, "first_payment_discount", 0.15)

    category = PRICING.get(service, {})
    if isinstance(category, dict) and tier in category:
        base_price = category[tier]
    else:
        base_price = 0.0

    if is_first_payment:
        effective = round(base_price * (1 - discount_rate), 2)
    else:
        effective = base_price

    suggested = round(effective + buffer, 0)

    return {
        "service": service,
        "tier": tier,
        "base_price": base_price,
        "effective_price": effective,
        "buffer": buffer,
        "suggested_load": suggested,
        "note": f"Load {suggested:.0f} EUR to cover {service} {tier}"
               + (" (first-payment discount applied)" if is_first_payment else ""),
    }


def format_rewards_summary(
    cashback_balance: float,
    cumulative_spend: float,
    config: Optional[dict[str, Any]] = None,
) -> str:
    """Render a markdown rewards summary table."""
    cfg = load_config(config)
    tier = get_tier(cumulative_spend, config=cfg)
    rate = get_cashback_rate(cumulative_spend, is_briven=True, config=cfg)
    gold_threshold = _get(cfg, "gold_threshold", 1000.0)

    if tier == "gold":
        next_milestone = "You've reached Gold status!"
    elif cumulative_spend < 500:
        distance = round(500 - cumulative_spend, 2)
        next_milestone = f"{distance:.2f} EUR until +10 milestone bonus"
    else:
        distance = round(gold_threshold - cumulative_spend, 2)
        next_milestone = f"{distance:.2f} EUR until Gold status ({_get(cfg, 'gold_cashback_rate', 0.03) * 100:.0f}% cashback)"

    return (
        "| Metric | Value |\n"
        "|---|---|\n"
        f"| Cashback balance | {cashback_balance:.2f} EUR |\n"
        f"| Cumulative spend | {cumulative_spend:.2f} EUR |\n"
        f"| Current cashback rate | {rate * 100:.0f}% on Briven |\n"
        f"| Next milestone | {next_milestone} |\n"
        f"| Status | {tier.title()} |"
    )


def get_partner_offer(
    partner_code: str,
    opted_in_promos: str = "",
    config: Optional[dict[str, Any]] = None,
) -> Optional[dict]:
    """
    Check if a partner offer is available and the user has opted in.

    Returns offer dict if available and opted-in, else None.
    """
    cfg = load_config(config)
    offers = _get(cfg, "partner_offers", {})
    offer = offers.get(partner_code)
    if not offer:
        return None

    if offer.get("opt_in_required") and partner_code not in opted_in_promos:
        return None

    return offer


# ---------------------------------------------------------------------------
# CLI / standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Cashback Calculation Test (default config) ===\n")

    result = calculate_cashback(
        amount=19.0,
        is_briven=True,
        is_first_payment=True,
        cumulative_spend=481.0,
        cashback_balance=4.20,
    )
    print(result.to_json())

    print("\n=== With custom config (20% first discount, 5% gold) ===\n")

    custom = {"first_payment_discount": 0.20, "gold_cashback_rate": 0.05}
    result2 = calculate_cashback(
        amount=19.0,
        is_briven=True,
        is_first_payment=True,
        cumulative_spend=481.0,
        cashback_balance=4.20,
        config=custom,
    )
    print(result2.to_json())

    print("\n=== Suggested Load Amount ===\n")
    suggestion = suggest_load_amount("premium", "pro", is_first_payment=True)
    print(json.dumps(suggestion, indent=2))

    print("\n=== Rewards Summary ===\n")
    print(format_rewards_summary(
        cashback_balance=result.new_cashback_balance,
        cumulative_spend=result.new_cumulative,
    ))

    print("\n=== Partner Offer (cycling, opted in) ===\n")
    offer = get_partner_offer("cyclingtravel", opted_in_promos="cycling,cyclingtravel")
    print(json.dumps(offer, indent=2))

    print("\n=== Partner Offer (cycling, NOT opted in) ===\n")
    offer2 = get_partner_offer("cyclingtravel", opted_in_promos="")
    print(f"Result: {offer2}")
