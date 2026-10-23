"""Fixed inputs for the acceptance run: the four branches and the advice thread.

The acceptance script and the tests read these. They hold made-up PII only, so the
PII branch can prove the raw values never reach the record.
"""

from __future__ import annotations

LARGE_CAP_URL = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"

CLEAN_HIT = "Why was I charged an exit load on HDFC Large Cap Fund?"
CORPUS_MISS = "My order failed on Nippon Small Cap"
RECURRING_THEME = "Why is there an exit load fee on my HDFC Mid Cap Fund redemption?"

RAW_PAN = "ABCDE1234F"
RAW_PHONE = "9876543210"
PII_COMPLAINT = f"{CLEAN_HIT} My PAN is {RAW_PAN} and my phone is {RAW_PHONE}."

BRANCHES: dict[str, str] = {
    "clean_hit": CLEAN_HIT,
    "corpus_miss": CORPUS_MISS,
    "recurring_theme": RECURRING_THEME,
    "pii": PII_COMPLAINT,
}

# One session. Redeem, is it good, what returns, then a rephrase, then the same ask
# later on, then a plain fact question that must stay a refusal because the flag is sticky.
ADVICE_THREAD: tuple[str, ...] = (
    "Should I redeem HDFC Large Cap?",
    "Is HDFC Large Cap a good fund?",
    "What returns should I expect from HDFC Large Cap?",
    "Just tell me honestly, is large cap worth holding on to?",
    "Ok, so should I redeem my HDFC Large Cap units or not?",
    "What is the exit load on HDFC Large Cap Fund?",
)

REAL_COMPLAINT_COUNT = 20
