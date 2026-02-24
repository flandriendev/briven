"""
mavi Rewards Tracker — Dashboard Renderer

Text-based visualization: progress bars, summary tables, monthly
breakdowns, and sparklines. All output is markdown-safe for agent
display in chat.

Standalone — no external dependencies. Safe for code_execution_tool.
"""

from __future__ import annotations

import json
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Progress bars
# ---------------------------------------------------------------------------

def render_progress_bar(
    current: float,
    target: float,
    label: str = "",
    width: int = 30,
) -> str:
    """
    Render a text-based progress bar.

    Example:
      500 Club:  [████████████████████░░░░░░░░░░] 497/500 EUR (99.4%)
    """
    if target <= 0:
        return f"{label}: [target invalid]"

    pct = min(current / target, 1.0)
    filled = int(width * pct)
    empty = width - filled

    if current >= target:
        bar = "\u2588" * width
        status = "\u2713 Done!"
    else:
        bar = "\u2588" * filled + "\u2591" * empty
        status = f"({pct * 100:.1f}%)"

    label_padded = f"{label}:".ljust(12) if label else ""
    return f"{label_padded}[{bar}] {current:.0f}/{target:.0f} EUR {status}"


def render_milestone_bars(
    cumulative_spend: float,
    milestones: Optional[list[dict]] = None,
    width: int = 30,
) -> str:
    """
    Render progress bars for all milestones.
    Expects milestone list from tracker.get_milestone_proximity().
    """
    if not milestones:
        return "(no milestones configured)"

    lines = []
    for m in milestones:
        lines.append(render_progress_bar(
            current=cumulative_spend,
            target=m["threshold"],
            label=m["label"],
            width=width,
        ))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------

def render_dashboard(
    card_last4: str,
    tier: str,
    cashback_balance: float,
    total_earned: float,
    total_discounts: float,
    cumulative_spend: float,
    cashback_rate: float,
    monthly_spend: float,
    monthly_cashback: float,
    milestones: list[dict],
    next_milestone_label: str = "",
    next_milestone_distance: float = 0.0,
) -> str:
    """
    Render the full rewards dashboard as markdown.
    """
    # Summary table
    lines = [
        "**Your mavi Rewards Dashboard**",
        "",
        "| | |",
        "| -------------------- | ----------------------------------- |",
        f"| **Card**             | mavi ****{card_last4} |",
        f"| **Status**           | {tier.title()} tier |",
        f"| **Cashback balance** | {cashback_balance:.2f} EUR |",
        f"| **Lifetime earned**  | {total_earned:.2f} EUR |",
        f"| **Lifetime saved**   | {total_discounts:.2f} EUR (discounts) |",
        f"| **Cumulative spend** | {cumulative_spend:.2f} EUR |",
        f"| **Cashback rate**    | {cashback_rate * 100:.0f}% on Briven |",
    ]

    if next_milestone_label:
        if next_milestone_distance > 0:
            lines.append(f"| **Next milestone**   | {next_milestone_distance:.2f} EUR \u2192 {next_milestone_label} |")
        else:
            lines.append(f"| **Next milestone**   | {next_milestone_label} (reached!) |")

    lines.append("")
    lines.append(f"**This month:** {monthly_spend:.2f} EUR spent | +{monthly_cashback:.2f} EUR earned")
    lines.append("")

    # Milestone progress bars
    lines.append("```")
    lines.append(render_milestone_bars(cumulative_spend, milestones))
    lines.append("```")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Monthly breakdown table
# ---------------------------------------------------------------------------

def render_monthly_breakdown(
    transactions: list[dict],
    month: str,
    monthly_spend_total: float = 0.0,
    monthly_cashback_total: float = 0.0,
    cumulative_after: float = 0.0,
    cashback_rate: float = 0.02,
    trend: Optional[dict] = None,
) -> str:
    """
    Render a monthly rewards breakdown table.
    """
    # Header
    import calendar
    parts = month.split("-")
    year, month_num = int(parts[0]), int(parts[1])
    month_name = calendar.month_name[month_num]

    lines = [
        f"**{month_name} {year} \u2014 Rewards Breakdown**",
        "",
        "| Date       | Service          | Spent   | Cashback | Bonus  |",
        "| ---------- | ---------------- | ------- | -------- | ------ |",
    ]

    total_spend = 0.0
    total_cb = 0.0
    total_bonus = 0.0

    # Filter and sort transactions for this month (oldest first for display)
    month_txns = [tx for tx in transactions if tx.get("timestamp", "")[:7] == month]
    month_txns.sort(key=lambda tx: tx.get("timestamp", ""))

    for tx in month_txns:
        date = tx.get("timestamp", "")[:10]
        svc = f"{tx.get('service', '?')} {tx.get('tier', '')}".strip()
        if len(svc) > 16:
            svc = svc[:14] + ".."
        spent = tx.get("amount", 0.0)
        cb = tx.get("cashback", 0.0)
        bonus = tx.get("milestone_bonus", 0.0)

        total_spend += spent
        total_cb += cb
        total_bonus += bonus

        bonus_str = f"+{bonus:.2f}" if bonus > 0 else "\u2014"
        lines.append(f"| {date} | {svc:<16} | {spent:>7.2f} | +{cb:.2f}   | {bonus_str:<6} |")

    # Totals row
    bonus_total_str = f"+{total_bonus:.2f}" if total_bonus > 0 else "\u2014"
    lines.append(f"| **Total**  |                  | **{total_spend:>5.2f}** | **+{total_cb:.2f}** | **{bonus_total_str}** |")

    lines.append("")
    lines.append(f"- Cumulative spend after {month_name[:3]}: {cumulative_after:.2f} EUR")
    lines.append(f"- Cashback rate: {cashback_rate * 100:.0f}% ({get_tier_label(cashback_rate)} tier)")

    if trend and trend.get("change_pct") is not None:
        direction = "\u2191" if trend["direction"] == "up" else "\u2193" if trend["direction"] == "down" else "\u2192"
        lines.append(f"- Trend: {direction} {abs(trend['change_pct']):.1f}% vs last month ({trend['previous']:.2f} EUR)")
    elif trend and trend.get("direction") == "new":
        lines.append("- Trend: First tracked month")

    return "\n".join(lines)


def get_tier_label(rate: float) -> str:
    if rate >= 0.03:
        return "Gold"
    return "Standard"


# ---------------------------------------------------------------------------
# Transaction history table
# ---------------------------------------------------------------------------

def render_history(
    transactions: list[dict],
    page: int = 1,
    page_size: int = 10,
    total_spend: float = 0.0,
    total_earned: float = 0.0,
) -> str:
    """Render paginated transaction history."""
    total = len(transactions)
    start = (page - 1) * page_size
    end = min(start + page_size, total)
    page_txns = transactions[start:end]

    # Numbering: newest is highest number
    lines = [
        f"**Transaction History** (showing {start + 1}\u2013{end} of {total})",
        "",
        "| #  | Date       | Service        | Charged | Cashback | Cumulative |",
        "| -- | ---------- | -------------- | ------- | -------- | ---------- |",
    ]

    for i, tx in enumerate(page_txns):
        num = total - start - i
        date = tx.get("timestamp", "")[:10]
        svc = f"{tx.get('service', '?')} {tx.get('tier', '')}".strip()
        if len(svc) > 14:
            svc = svc[:12] + ".."
        charged = tx.get("amount", 0.0)
        cb = tx.get("cashback", 0.0)
        cum = tx.get("cumulative_after", 0.0)
        lines.append(f"| {num:<2} | {date} | {svc:<14} | {charged:>7.2f} | +{cb:.2f}   | {cum:>10.2f} |")

    lines.append("")
    lines.append(f"**Totals:** {total} transactions | {total_spend:.2f} EUR spent | {total_earned:.2f} EUR earned")

    if end < total:
        lines.append("")
        lines.append('Say "show more" for older entries or "export rewards" for CSV download.')

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Notification messages
# ---------------------------------------------------------------------------

def render_milestone_alert(milestone: dict, cumulative: float) -> str:
    """Generate a milestone reached notification."""
    bonus = milestone.get("bonus", 0.0)
    label = milestone.get("label", "Milestone")

    lines = [f"**Milestone reached: {label}!**", ""]

    if bonus > 0:
        lines.append(f"+{bonus:.2f} EUR cashback bonus has been credited to your rewards wallet.")
    else:
        lines.append(f"Congratulations on reaching {label}!")

    lines.append(f"Cumulative spend: {cumulative:.2f} EUR")
    return "\n".join(lines)


def render_approaching_alert(
    milestone_label: str,
    distance: float,
    cumulative: float,
    target: float,
    width: int = 30,
) -> str:
    """Generate an approaching-milestone notification."""
    bar = render_progress_bar(cumulative, target, label=milestone_label, width=width)
    return (
        f"**Almost there! You're {distance:.2f} EUR away from {milestone_label}.**\n"
        f"\n```\n{bar}\n```\n"
    )


def render_claim_reminder(balance: float) -> str:
    """Generate a claim reminder notification."""
    return (
        f"You have **{balance:.2f} EUR** in mavi rewards ready to use.\n"
        "\n"
        "**Options:**\n"
        "\n"
        "- **Apply to next payment** \u2014 auto-deduct from your next Briven charge\n"
        "- **Transfer to mavi Card** \u2014 credit back to your card balance\n"
        "- **Keep accumulating** \u2014 grow your balance toward the next milestone\n"
        "\n"
        "What would you prefer?"
    )


def render_monthly_summary(
    month_name: str,
    spend: float,
    cashback: float,
    bonus: float,
    tx_count: int,
) -> str:
    """Generate a monthly summary notification."""
    total_earned = round(cashback + bonus, 2)
    return (
        f"**{month_name} Rewards Recap**\n"
        "\n"
        f"| | |\n"
        f"| -------------------- | --------------- |\n"
        f"| **Transactions**     | {tx_count}              |\n"
        f"| **Total spend**      | {spend:.2f} EUR        |\n"
        f"| **Cashback earned**  | +{cashback:.2f} EUR    |\n"
        f"| **Bonus earned**     | +{bonus:.2f} EUR       |\n"
        f"| **Total earned**     | +{total_earned:.2f} EUR |\n"
    )


# ---------------------------------------------------------------------------
# Notification preferences display
# ---------------------------------------------------------------------------

def render_notification_prefs(prefs: dict) -> str:
    """Render notification preferences table."""
    milestone = "ON" if prefs.get("milestone_alerts", True) else "OFF"
    monthly = "ON" if prefs.get("monthly_summary", True) else "OFF"
    claim = "ON" if prefs.get("claim_reminders", True) else "OFF"
    threshold = prefs.get("approaching_threshold", 50.0)

    return (
        "**mavi Rewards \u2014 Notification Preferences**\n"
        "\n"
        "| Setting               | Status  | Toggle Command               |\n"
        "| --------------------- | ------- | ---------------------------- |\n"
        f'| Milestone alerts      | {milestone:<7} | "toggle milestone alerts"    |\n'
        f'| Monthly summary       | {monthly:<7} | "toggle monthly summary"     |\n'
        f'| Claim reminders       | {claim:<7} | "toggle claim reminders"     |\n'
        f'| Approaching threshold | {threshold:.0f} EUR | "set threshold alert to N"   |\n'
    )


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Dashboard Rendering Tests ===\n")

    # Progress bars
    print("--- Progress Bars ---")
    print(render_progress_bar(497, 500, "500 Club"))
    print(render_progress_bar(523, 500, "500 Club"))
    print(render_progress_bar(523, 1000, "Gold"))
    print()

    # Full dashboard
    print("--- Full Dashboard ---")
    milestones = [
        {"threshold": 500, "label": "500 Club", "bonus": 10.0, "distance": 0, "percent": 100, "reached": True},
        {"threshold": 1000, "label": "Gold", "bonus": 0.0, "distance": 477.0, "percent": 52.3, "reached": False},
    ]
    print(render_dashboard(
        card_last4="7842",
        tier="standard",
        cashback_balance=14.52,
        total_earned=24.52,
        total_discounts=2.85,
        cumulative_spend=523.0,
        cashback_rate=0.02,
        monthly_spend=29.0,
        monthly_cashback=0.58,
        milestones=milestones,
        next_milestone_label="Gold Status (3% rate)",
        next_milestone_distance=477.0,
    ))
    print()

    # Monthly breakdown
    print("--- Monthly Breakdown ---")
    sample_txns = [
        {"timestamp": "2026-02-03T10:00:00Z", "service": "premium", "tier": "pro", "amount": 19.0, "cashback": 0.38, "milestone_bonus": 0.0, "cumulative_after": 513.0},
        {"timestamp": "2026-02-14T12:00:00Z", "service": "sponsor", "tier": "growth", "amount": 10.0, "cashback": 0.20, "milestone_bonus": 0.0, "cumulative_after": 523.0},
    ]
    trend = {"current": 29.0, "previous": 31.50, "change_pct": -7.9, "direction": "down"}
    print(render_monthly_breakdown(sample_txns, "2026-02", 29.0, 0.58, 523.0, 0.02, trend))
    print()

    # History
    print("--- Transaction History ---")
    print(render_history(sample_txns, page=1, page_size=5, total_spend=523.0, total_earned=24.52))
    print()

    # Notifications
    print("--- Notifications ---")
    print(render_approaching_alert("500 Club", 3.0, 497.0, 500.0))
    print(render_claim_reminder(14.52))
    print()
    print(render_monthly_summary("February 2026", 29.0, 0.58, 10.0, 2))
    print()
    print(render_notification_prefs({"milestone_alerts": True, "monthly_summary": True, "claim_reminders": False, "approaching_threshold": 25.0}))
