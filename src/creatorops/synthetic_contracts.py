"""Write synthetic influencer / brand agreements as markdown files.

One contract per row of `contracts_index` in the synthetic database, so the text of the
contract (dates, fee, exclusivity) matches the SQL data. All contracts are fake and marked
"SYNTHETIC" at the top.
"""

import random
import sqlite3
from pathlib import Path

GOVERNING_LAW = {
    "FR": "the laws of France",
    "UK": "the laws of England and Wales",
    "US": "the laws of the State of New York",
    "TN": "the laws of Tunisia",
    "ES": "the laws of Spain",
    "DE": "the laws of Germany",
}

TEMPLATE = """# INFLUENCER MARKETING AGREEMENT ({contract_id})

> SYNTHETIC DOCUMENT generated for the CreatorOps Copilot project. Not a real contract.

This Influencer Marketing Agreement (the "Agreement") is entered into on {sign_date} between
{brand} (the "Brand") and {creator}, represented by the Agency (the "Creator").

## 1. Term
1.1 This Agreement starts on {start_date} and ends on {end_date} (the "Term").
1.2 {renewal}

## 2. Deliverables
2.1 The Creator will publish the following content during the campaign: {deliverables}.
2.2 Drafts must be sent to the Brand for review at least {review_days} business days before publication.
2.3 The Brand may request up to {revisions} rounds of revisions per deliverable.

## 3. Compensation and Payment
3.1 The Brand will pay the Creator a total fee of USD {fee:,}.
3.2 {payment_split}
3.3 Invoices are payable within {net_days} days of receipt. Late payments bear interest of {late_interest}% per month.

## 4. Exclusivity
{exclusivity}

## 5. Usage Rights and License
5.1 The Creator grants the Brand a non-exclusive license to use the published content on the Brand's own
social media accounts for {usage_months} months after first publication.
5.2 {paid_usage}
5.3 The Creator keeps ownership of all content and intellectual property rights.

## 6. Disclosure and Platform Compliance
6.1 The Creator must clearly disclose the paid relationship in every sponsored post, using the platform's
paid partnership / branded content tool where available, and a clear label such as "#ad" at the start of the caption.
6.2 The Creator must follow the branded content policies of each platform and applicable advertising laws
(including the FTC Endorsement Guides and the UK CAP Code where relevant).
{category_rule}

## 7. Termination
7.1 Either party may terminate this Agreement with {notice_days} days written notice.
7.2 The Brand may terminate immediately if the Creator publicly engages in conduct that seriously damages
the Brand's reputation (morality clause).
7.3 {kill_fee}

## 8. Confidentiality
8.1 Both parties keep the terms of this Agreement confidential for {confidential_years} years after the Term.

## 9. Governing Law
9.1 This Agreement is governed by {law}. Disputes go to the competent courts of that jurisdiction.
"""


def exclusivity_text(exclusive: int, category: str | None, brand: str, rng: random.Random) -> str:
    if not exclusive:
        return (
            "4.1 This Agreement is non-exclusive. The Creator may work with other brands, including "
            "competitors, but will not publish competing sponsored content within 48 hours of a "
            "Brand deliverable."
        )
    months = rng.choice([1, 3, 6])
    return (
        f"4.1 During the Term and for {months} month(s) after it ends, the Creator will not promote, "
        f"endorse or create sponsored content for any competitor of {brand} in the {category} "
        f'category.\n4.2 A "competitor" means any company whose main products are in the '
        f"{category} category."
    )


def write_contracts(db_path: Path, out_dir: Path, seed: int = 42) -> list[dict]:
    """Write one markdown file per contract. Returns metadata for the manifest."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """SELECT ci.contract_id, ci.doc_id, ci.start_date, ci.end_date, ci.fee_usd,
                  ci.exclusivity, ci.exclusivity_category, b.name, b.category, c.name, c.country
           FROM contracts_index ci
           JOIN brands b ON b.brand_id = ci.brand_id
           JOIN creators c ON c.creator_id = ci.creator_id
           ORDER BY ci.contract_id"""
    ).fetchall()
    conn.close()

    docs = []
    for (
        contract_id,
        doc_id,
        start,
        end,
        fee,
        exclusive,
        ex_category,
        brand,
        brand_category,
        creator,
        country,
    ) in rows:
        n_reels = rng.randint(1, 4)
        n_stories = rng.randint(2, 6)
        if brand_category == "alcohol":
            category_rule = (
                "6.3 Because the Brand sells alcohol, content must only be shown to users of legal "
                "drinking age using the platform's age-restriction settings, and must not show "
                "excessive drinking."
            )
        elif brand_category == "supplements":
            category_rule = (
                "6.3 The Creator must not make health or medical claims about the Brand's products "
                "other than claims approved in writing by the Brand."
            )
        else:
            category_rule = ""
        text = TEMPLATE.format(
            contract_id=contract_id,
            sign_date=start,
            brand=brand,
            creator=creator,
            start_date=start,
            end_date=end,
            renewal=rng.choice(
                [
                    "This Agreement does not renew automatically.",
                    "This Agreement renews automatically for one additional period of 3 months unless "
                    "either party gives 30 days written notice before the end of the Term.",
                ]
            ),
            deliverables=f"{n_reels} Instagram Reel(s), {n_stories} Instagram Stories and "
            f"{rng.randint(1, 3)} TikTok video(s)",
            review_days=rng.choice([2, 3, 5]),
            revisions=rng.choice([1, 2]),
            fee=fee,
            payment_split=rng.choice(
                [
                    "50% of the fee is paid at signature and 50% after the last deliverable is published.",
                    "100% of the fee is paid after the last deliverable is published.",
                    "30% of the fee is paid at signature and 70% after the campaign report is delivered.",
                ]
            ),
            net_days=rng.choice([30, 45, 60]),
            late_interest=rng.choice([1, 1.5]),
            exclusivity=exclusivity_text(exclusive, ex_category, brand, rng),
            usage_months=rng.choice([3, 6, 12]),
            paid_usage=rng.choice(
                [
                    "Using the content in paid advertising (whitelisting / boosting) requires a separate "
                    "written agreement and an additional fee.",
                    f"The Brand may use the content in paid advertising for {rng.choice([30, 60, 90])} "
                    "days, included in the fee.",
                ]
            ),
            category_rule=category_rule,
            notice_days=rng.choice([14, 30]),
            kill_fee=rng.choice(
                [
                    "If the Brand terminates without cause, it pays for all deliverables already published.",
                    "If the Brand terminates without cause, it pays 50% of the remaining fee as a kill fee.",
                ]
            ),
            confidential_years=rng.choice([1, 2, 3]),
            law=GOVERNING_LAW[country],
        )
        path = out_dir / f"{doc_id}.md"
        path.write_text(text, encoding="utf-8")
        docs.append(
            {
                "doc_id": doc_id,
                "title": f"Influencer Marketing Agreement {contract_id} ({brand} x {creator})",
                "path": path,
                "doc_date": start,
            }
        )
    return docs
