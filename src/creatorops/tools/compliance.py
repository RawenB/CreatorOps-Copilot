"""check_post_compliance: a checklist for a caption before it is scheduled.

The checks are simple rules written from the documents in the corpus (FTC, UK CAP, platform policies,
agency SOP). They are deterministic on purpose: the same caption always gets the same verdict, and every
problem points to the exact passage of the stored document it comes from (so the UI can highlight it).

What it does NOT check: the image / video itself, health or performance claims, local laws of every
country. The verdict is a help for the account manager, not a legal opinion.
"""

import re

from creatorops.evaluation.metrics import normalize
from creatorops.tools.common import get_registry, to_source

# clear disclosure words (FTC: "ad", "advertisement", "sponsored", "paid partnership with ...")
CLEAR = [r"#ad\b", r"\bad:", r"^ad\b", r"\badvertisement\b", r"#advert\b", r"\bsponsored\b",
         r"#sponsored\b", r"\bpaid partnership\b", r"#paidpartnership\b", r"\bgifted by\b",
         r"\bthanks to \w+ for the free\b"]  # fmt: skip
# vague words the FTC says are not enough on their own
VAGUE = [r"#sp\b", r"#spon\b", r"#collab\b", r"#ambassador\b", r"#partner\b", r"#thanks\b",
         r"#comped\b", r"#hosted\b"]  # fmt: skip
START_CHARS = 50  # SOP 3.2: the caption must START with the disclosure
PROHIBITED_TIKTOK = {
    "tobacco": "vaporisers and vape devices",
    "weight_loss": "weight loss and detox teas",
}
AGE_RESTRICTED = {"alcohol", "gambling"}

# rule -> (doc_id, exact quote of the stored document)
RULES = {
    "missing_disclosure": ("ftc_disclosures_101", "make it obvious when you have a relationship"),
    "vague_disclosure": (
        "ftc_disclosures_101",
        "Don’t use vague or confusing terms like “sp,” “spon,” or “collab,”",
    ),
    "disclosure_not_at_start": (
        "sop_approval_process",
        "The caption starts with a clear disclosure such as",
    ),
    "disclosure_in_hashtags": (
        "ftc_disclosures_101",
        "Don’t mix your disclosure into a group of hashtags or links",
    ),
    "label_off_instagram": (
        "sop_approval_process",
        "The platform's paid partnership / branded content label is switched on",
    ),
    "label_off_tiktok": (
        "tiktok_bc_policy",
        "you must enable the commercial content disclosure toggle",
    ),
    "label_off_youtube": (
        "youtube_paid_promotion",
        "selecting the paid promotion button in your video details",
    ),
    "prohibited_tobacco": ("tiktok_bc_policy", "vaporisers and vape devices"),
    "prohibited_weight_loss": ("tiktok_bc_policy", "weight loss and detox teas"),
    "no_age_restriction": (
        "sop_approval_process",
        "For alcohol brands the age restriction is set on the post",
    ),
}

MESSAGES = {
    "missing_disclosure": "Paid / gifted post without a clear disclosure (#ad, 'Ad:', 'Paid partnership with ...').",
    "vague_disclosure": "Only a vague disclosure (#sp, #spon, #collab, #ambassador...): use #ad or 'Paid partnership'.",
    "disclosure_not_at_start": "The disclosure is not at the start of the caption (agency rule: caption starts with it).",
    "disclosure_in_hashtags": "The disclosure is mixed into a group of hashtags, it is easy to miss.",
    "label_off_instagram": "Switch on Instagram's paid partnership label.",
    "label_off_tiktok": "Switch on TikTok's commercial content disclosure toggle.",
    "label_off_youtube": "Select YouTube's paid promotion option.",
    "prohibited_tobacco": "Tobacco / vape products cannot be promoted in TikTok branded content.",
    "prohibited_weight_loss": "Weight loss products cannot be promoted in TikTok branded content.",
    "no_age_restriction": "Alcohol / gambling content needs an age restriction (18+, 21+ in the US).",
}


def find_passage(doc_id: str, quote: str) -> dict | None:
    """The stored chunk (latest version) that contains the quote, with exact offsets for highlighting."""
    for chunk in get_registry().all_chunks(latest_only=True):
        if chunk["doc_id"] == doc_id and normalize(quote) in normalize(chunk["text"]):
            return to_source(chunk)
    return None


def first_match(patterns, text) -> re.Match | None:
    matches = [m for p in patterns if (m := re.search(p, text, re.IGNORECASE | re.MULTILINE))]
    return min(matches, key=lambda m: m.start()) if matches else None


def in_hashtag_group(text: str, start: int) -> bool:
    """True if the disclosure hashtag sits among 3 or more other hashtags."""
    tokens = list(re.finditer(r"\S+", text))
    i = next((k for k, t in enumerate(tokens) if t.start() <= start < t.end()), None)
    if i is None or not tokens[i].group().startswith("#"):
        return False
    left = i
    while left > 0 and tokens[left - 1].group().startswith("#"):
        left -= 1
    right = i
    while right < len(tokens) - 1 and tokens[right + 1].group().startswith("#"):
        right += 1
    return right - left >= 3


def check_post_compliance(
    caption: str,
    platform: str,
    is_paid: bool,
    paid_label_on: bool | None = None,
    brand_category: str | None = None,
    age_restricted: bool | None = None,
    with_sources: bool = True,
) -> dict:
    """Check a caption before posting.

    is_paid: the creator was paid OR got something for free (FTC: any material connection).
    paid_label_on: is the platform's paid partnership / branded content option switched on?
    brand_category: e.g. "alcohol", "tobacco", "weight_loss", "beauty"...
    age_restricted: is an age restriction set on the post?
    """
    platform = platform.lower().strip()
    problems = []

    if is_paid:
        clear = first_match(CLEAR, caption)
        if clear is None:
            problems.append(
                "vague_disclosure" if first_match(VAGUE, caption) else "missing_disclosure"
            )
        else:
            if clear.start() > START_CHARS:
                problems.append("disclosure_not_at_start")
            if in_hashtag_group(caption, clear.start()):
                problems.append("disclosure_in_hashtags")
        if paid_label_on is False and platform in ("instagram", "tiktok", "youtube"):
            problems.append(f"label_off_{platform}")

    category = (brand_category or "").lower()
    if platform == "tiktok" and is_paid and category in PROHIBITED_TIKTOK:
        problems.append(f"prohibited_{category}")
    if category in AGE_RESTRICTED and is_paid and age_restricted is False:
        problems.append("no_age_restriction")

    result = {
        "verdict": "non_compliant" if problems else "compliant",
        "problems": [{"rule": p, "message": MESSAGES[p]} for p in problems],
        "checked": [
            "disclosure present and clear",
            "disclosure at the start",
            "not hidden in hashtags",
            "platform paid label",
            "prohibited categories (TikTok)",
            "age restriction",
        ],  # fmt: skip
    }
    if with_sources:
        result["sources"] = [s for p in problems if (s := find_passage(*RULES[p]))]
    return result
