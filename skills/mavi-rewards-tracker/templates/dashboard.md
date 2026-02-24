# mavi Rewards Tracker — Display Templates

Used by the Dashboard Renderer subagent. Variables in `{braces}` are replaced at runtime.

---

## Template: Quick Dashboard

**Your mavi Rewards Dashboard**

| | |
| -------------------- | ----------------------------------- |
| **Card**             | mavi ****{last4}                    |
| **Status**           | {tier} tier                         |
| **Cashback balance** | {cashback_balance} EUR              |
| **Lifetime earned**  | {total_earned} EUR                  |
| **Lifetime saved**   | {total_discounts} EUR (discounts)   |
| **Cumulative spend** | {cumulative_spend} EUR              |
| **Cashback rate**    | {rate}% on Briven                   |
| **Next milestone**   | {distance} EUR -> {milestone_label} |

**This month:** {monthly_spend} EUR spent | +{monthly_cashback} EUR earned

```
{milestone_progress_bars}
```

---

## Template: Monthly Breakdown Header

**{month_name} {year} -- Rewards Breakdown**

| Date       | Service          | Spent   | Cashback | Bonus  |
| ---------- | ---------------- | ------- | -------- | ------ |
{transaction_rows}

| **Total**  |                  | **{total_spend}** | **+{total_cashback}** | **{total_bonus}** |

- Cumulative spend after {month_abbr}: {cumulative_after} EUR
- Cashback rate: {rate}% ({tier} tier)
- Trend: {trend_arrow} {trend_pct}% vs last month ({prev_spend} EUR)

---

## Template: Transaction History

**Transaction History** (showing {range_start}--{range_end} of {total})

| #  | Date       | Service        | Charged | Cashback | Cumulative |
| -- | ---------- | -------------- | ------- | -------- | ---------- |
{history_rows}

**Totals:** {total_count} transactions | {total_spend} EUR spent | {total_earned} EUR earned

---

## Template: Claim Options

You have **{balance} EUR** in mavi rewards.

**Claim options:**

1. **Apply to next payment** -- auto-deduct from your next Briven charge
2. **Transfer to mavi Card** -- credit {balance} EUR back to your card balance
3. **Partial claim** -- choose a specific amount

Which would you prefer?

---

## Template: Claim Confirmation

**Claim Successful!**

| | |
| ---------------------- | -------------------- |
| **Amount claimed**     | {claim_amount} EUR   |
| **Destination**        | {destination}        |
| **Reference**          | {reference}          |
| **New balance**        | {new_balance} EUR    |
| **Cumulative earned**  | {total_earned} EUR   |

Your card balance has been updated. You'll continue earning {rate}% on future payments.

---

## Template: Milestone Reached

**Milestone reached: {milestone_label}!**

{bonus_message}

Cumulative spend: {cumulative_spend} EUR

---

## Template: Approaching Milestone

**Almost there! You're {distance} EUR away from {milestone_label}.**

```
{progress_bar}
```

{suggestion_message}

---

## Template: Monthly Summary Notification

**{month_name} Rewards Recap**

| | |
| -------------------- | --------------- |
| **Transactions**     | {tx_count}      |
| **Total spend**      | {spend} EUR     |
| **Cashback earned**  | +{cashback} EUR |
| **Bonus earned**     | +{bonus} EUR    |
| **Total earned**     | +{total} EUR    |

---

## Template: Notification Preferences

**mavi Rewards -- Notification Preferences**

| Setting               | Status  | Toggle Command               |
| --------------------- | ------- | ---------------------------- |
| Milestone alerts      | {milestone_status} | "toggle milestone alerts"    |
| Monthly summary       | {monthly_status}   | "toggle monthly summary"     |
| Claim reminders       | {claim_status}     | "toggle claim reminders"     |
| Approaching threshold | {threshold} EUR    | "set threshold alert to N"   |

These control when I proactively notify you about rewards events.

---

## Template: No Card Linked

**No mavi Card linked yet**

To start tracking rewards, I need to link your mavi Card.

- If you have the **mavi Payment Agent** installed, it will handle linking automatically.
- Otherwise, tell me your card's **last 4 digits** and **email** to link now.
- Don't have a card? Get one free at [mavi-finans.com/card](https://mavi-finans.com/card)

---

## Template: Skills Hub Listing

**mavi Rewards Tracker -- Track and maximize your mavi Card rewards**

Never miss a reward again. The mavi Rewards Tracker gives you a personal dashboard for all your mavi Card perks:

- **Live cashback balance** -- see exactly what you've earned
- **Milestone progress** -- visual bars showing how close you are to bonuses
- **Monthly breakdowns** -- spending trends and cashback earned per month
- **Proactive alerts** -- get notified when milestones approach or rewards are claimable
- **One-tap claiming** -- transfer rewards to your card or apply to next payment
- **Full history** -- every transaction logged with reward breakdown

Works standalone or as a companion to the mavi Payment Agent for automatic tracking.

**Free install** | Optional premium: 3 EUR one-time for advanced analytics + export
