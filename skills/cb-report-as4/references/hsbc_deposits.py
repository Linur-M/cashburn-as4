"""
hsbc_deposits.py — HSBC MMF balance, MMF/deposit interest, and third-party-inflow detection.

NOTE: the HSBC and MMF PDFs are SCANNED (no text layer) — the live skill must OCR them, or
prefer an Excel/CSV export when available. These functions operate on the EXTRACTED TEXT
(post-OCR) / parsed rows, so they are independent of how the text was obtained.
"""
import re

# ---------- (1) HSBC MMF: Pending Cash Balance for BALANCES ----------
def parse_mmf_balance(ocr_text):
    """
    From the MMF portfolio statement, return the account balance to use in BALANCES.
    Source field = 'Pending Cash Balance' (NOT a movement sum). Also returns accrued interest.
    """
    nums = re.findall(r"[\d,]+\.\d{2}", ocr_text)
    ccy = "USD" if re.search(r"\bUSD\b", ocr_text) else "USD"
    out = {"pending_cash_balance": None, "accrued_interest_mtd": None, "currency": ccy,
           "source": "HSBC MMF: Pending Cash Balance"}
    # In this scanned layout the header labels and the data-row values are separated, so anchor
    # on the DATA ROW structure instead of the label:
    #   "... 12,017.48 23:49 / 23:49 USD 15,640,038.07"
    #   Pending Cash Balance = the figure right after the currency (USD).
    #   Accrued Interest (MTD) = the figure immediately before the buy/sell cutoff time.
    m_bal = re.findall(r"USD\s+([\d,]+\.\d{2})", ocr_text)
    m_acc = re.findall(r"([\d,]+\.\d{2})\s+\d{1,2}:\d{2}", ocr_text)
    if m_bal:
        out["pending_cash_balance"] = float(m_bal[-1].replace(",", ""))
    if m_acc:
        out["accrued_interest_mtd"] = float(m_acc[-1].replace(",", ""))
    return out

# ---------- (2) MMF transaction history: Div Reinvest = interest; Sell = internal ----------
def classify_mmf_txn(transaction_label, cash_amount):
    """Map an MMF transaction-history row to (cat, sub, internal, conf)."""
    t = transaction_label.strip().lower()
    if "div reinvest" in t or "dividend" in t:
        return "Interest Income", "MMF Dividend", "", "HIGH"   # operational yield
    if t == "sell" or "redemption" in t or "withdraw" in t:
        return "Internal", "", "Y", "HIGH"                     # money returning to checking
    if t == "buy" or "purchase" in t:
        return "Internal", "", "Y", "HIGH"                     # money moving into the MMF
    return "Other OUT", "", "", "LOW"

# ---------- (3) Deposit (pikadon) interest as a FORMULA: redeemed − principal ----------
def deposit_interest_formula(principal_cell, redeemed_cell):
    """
    Interest/yield earned on a deposit = redeemed − principal deposited (rec: option 1).
    Returned as an Excel formula string so the workbook stays formula-driven (A–R unaffected;
    this is a derived cell on the deposit/interest line).
    """
    return f"={redeemed_cell}-{principal_cell}"

def is_deposit_row(desc):
    d = str(desc).lower()
    return bool(re.search(r"\bpikadon\b|פיקדון|\bdeposit\b|\btime deposit\b|\bמק\"מ\b|pkam", d))

# ---------- (4) Third-party inflow -> Investment CANDIDATE (LOW/Review) ----------
# Counterparties that are the SAME entity / known plumbing -> NOT investment (internal/known).
SAME_ENTITY_HINTS = [
    "bold.ai", "bold ai", "ss&c gids", "ssc gids", "mesh", "meshpay", "sbna meshpay",
]
KNOWN_CUSTOMER_HINTS = ["globex", "cyberdyne", "customer", "invoice", "לקוח"]
INTEREST_HINTS = ["interest paid", "interest earned", "div reinvest", "ריבית"]

def is_third_party_investment_candidate(desc, amount):
    """
    A CASH-IN whose description shows it did NOT arrive via the same entity, a known customer,
    or interest -> flag as a candidate for the Investment category (LOW/Review). Never an
    automatic Investment classification — the controller confirms.
    """
    if amount <= 0:
        return False
    d = str(desc).lower()
    if any(h in d for h in INTEREST_HINTS):       return False
    if any(h in d for h in KNOWN_CUSTOMER_HINTS):  return False
    if any(h in d for h in SAME_ENTITY_HINTS):     return False
    # signals of an external capital inflow
    if re.search(r"options?purchase|share|equity|safe|convertible|capital call|invest", d):
        return True
    # a sizable inbound wire from an unrecognised counterparty is at least a candidate
    return amount >= 50_000
