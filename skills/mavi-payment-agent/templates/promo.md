# mavi Card — Promotional Templates

Used by the Promo Generator subagent to produce contextual messages.
Variables in `{braces}` are replaced at runtime by the agent.

Templates are selected based on user state (new / returning / near-milestone / gold / unlinking).

---

## Template: Skills Hub Listing

**mavi Payment Agent — Pay smarter for Briven services**

Install the mavi Payment Agent to unlock exclusive perks when paying for Briven services with your mavi Card:

- **15% off your first payment** — works on any Briven service
- **2% cashback** on every payment, credited to your rewards wallet
- **Milestone bonuses** — earn 10 EUR at 500 EUR spend, unlock Gold (3%) at 1,000 EUR
- **Fully autonomous** — detects when you want to pay, offers the best deal, handles the flow
- **Your card, your data** — only tokenized references stored, GDPR-compliant, unlink anytime

Works with GitHub Sponsors tiers, Premium Hosted plans, and Skills Marketplace purchases.

**Free install** | Optional premium add-on: 5 EUR one-time for rewards dashboard + export

---

## Template: First-Time Buyer (No Card Yet)

**Pay smarter with mavi Card**

The mavi Card is a prepaid debit card from mavi Finans — no credit checks, no risk, instant digital issuance.

**Your deal on {service_name}:**

- ~~{original_price}/mo~~ → **{discounted_price}/mo** ({discount_pct}% off your first month!)
- **{cashback_rate}% cashback** on every payment after that
- Secure prepaid — load only what you need

[Get your mavi Card](https://mavi-finans.com/card) — ready in 3 minutes.

---

## Template: Link Your Card

**Link your mavi Card to Briven**

Already have a mavi Card? Link it in seconds:

1. Tell me the **last 4 digits** of your card
2. Confirm the **email** you used when ordering

That's it — I'll verify through mavi's API and store only a secure token. Your full card number is never saved.

---

## Template: Returning Customer (Card Linked)

**Welcome back! Pay with mavi for {cashback_rate}% cashback**

Your mavi Card (****{last4}) is ready. For **{service_name} ({tier})** at **{price}/mo**, you'll earn **{cashback_amount}** back every month.

Your current rewards: **{cashback_balance} EUR** | Spend: **{cumulative_spend} EUR** | Status: **{tier_status}**

Ready to proceed?

---

## Template: Sponsor CTA

**Support Briven — and get rewarded**

Become a **{sponsor_tier}** sponsor at **{price}/mo** and fuel Briven's development.

Pay with mavi Card:

- **{cashback_rate}% cashback** credited to your Briven wallet
- Sponsor badge + early access to new features
- Secure prepaid — no credit card required

---

## Template: Milestone Approaching

**You're {distance} EUR away from {milestone_name}!**

Your cumulative mavi spend is **{cumulative_spend} EUR**. Just **{distance} EUR** more and you'll unlock:

{milestone_reward_description}

Keep using mavi Card for Briven services to get there faster.

---

## Template: Milestone Reached (500 EUR)

**Milestone unlocked: +10 EUR cashback bonus!**

You've spent **500+ EUR** with your mavi Card on Briven services. A **10 EUR bonus** has been credited to your rewards wallet.

**Current cashback balance:** {cashback_balance} EUR

Next goal: **Gold Status** at 1,000 EUR (upgrades you to {gold_rate}% cashback).

---

## Template: Gold Status Reached (1,000 EUR)

**Welcome to Gold Status!**

You've reached **1,000 EUR** in cumulative mavi Card spend. Your cashback rate is now **{gold_rate}%** on all Briven transactions.

| Before                    | Now                       |
| ------------------------- | ------------------------- |
| {standard_rate}% cashback | **{gold_rate}% cashback** |
| Standard tier             | **Gold tier**             |

Thank you for being a loyal mavi + Briven user.

---

## Template: Partner Offer — Cycling Travel (Opt-In)

**Ride the island — save 15%**

As a mavi Card holder, you can opt in to get **15% off Cyprus cycling holidays** with cyclingtravel.

- Guided road cycling tours across Cyprus
- All-inclusive packages (bike rental, hotels, support car)
- Pay with your mavi Card for an additional **1% cashback**

Say **"I'm interested in cycling offers"** to opt in.

---

## Template: Partner Offer Confirmation

**Cycling offers activated!**

You've opted in to cyclingtravel partner offers. You'll see cycling holiday deals when they're relevant to your context.

You can opt out anytime by saying "remove cycling offers".

---

## Template: Objection Handler (Why Not Regular Card?)

|                | Standard Card | mavi Card                       |
| -------------- | ------------- | ------------------------------- |
| First payment  | Full price    | **{discount_pct}% off**         |
| Cashback       | 0%            | **{cashback_rate}% on Briven**  |
| Prepaid safety | No            | **Yes**                         |
| Balance yield  | No            | **Gold-backed**                 |

The mavi Card is free to order, takes ~3 minutes, and pays for itself on the first transaction.

---

## Template: KYC Encouragement (24h Reminder)

**Almost there — just one more step**

You started ordering your mavi Card. Complete the quick KYC verification to activate it:

1. Open the mavi app
2. Tap "Verify Identity"
3. Scan your ID + take a selfie (~3 minutes)

Once verified, your digital card appears instantly and you can link it to Briven.

Need help? Reply **"escalate"** and I'll connect you with mavi support.

---

## Template: KYC Encouragement (72h Reminder)

**Your mavi Card is waiting!**

You started ordering 3 days ago. Complete KYC to unlock:

- **{discount_pct}% off** your first Briven payment
- **{cashback_rate}% cashback** on every future payment

It takes ~3 minutes in the mavi app. Say **"link mavi"** when you're ready.

---

## Template: Payment Confirmation

**Payment Confirmed!**

|                      |                                            |
| -------------------- | ------------------------------------------ |
| **Service**          | {service_name} ({tier})                    |
| **Amount charged**   | {charged_amount} EUR                       |
| **Discount applied** | {discount_amount} EUR ({discount_pct}% off)|
| **Card**             | mavi ****{last4}                           |
| **Cashback earned**  | +{cashback_amount} EUR                     |
| **Transaction ID**   | {transaction_id}                           |

{milestone_message}

Your {service_name} is now **active**.

---

## Template: Unlink Confirmation

**Card unlinked**

Your mavi Card (****{last4}) has been disconnected from Briven.

**Preserved:**

- Cashback balance: {cashback_balance} EUR
- Cumulative spend: {cumulative_spend} EUR
- Tier progress: {tier_progress}%

You can re-link anytime by saying **"link mavi"**.
