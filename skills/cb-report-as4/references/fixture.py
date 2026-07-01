"""
fixture.py — tagged synthetic fixture for the cb-report-as regression harness.

Each transaction carries the KNOWN-CORRECT answer (expected_cat / expected_sub /
expected_vendor). The harness classifies independently and compares, so we can
measure classification accuracy as a NUMBER and catch regressions.

Coverage targets (by design):
  - Hebrew, English, and mixed-language descriptions
  - ILS + USD + EUR currencies (per-date BOI conversion)
  - one inter-account transfer PAIR (must net out, Internal=Y)
  - one card refund (credit on a card tab = vendor refund, NOT customer payment)
  - several genuinely-ambiguous rows expected to land LOW
  - all income except Investment -> OPERATIONAL CASH IN
"""

# Deterministic month-end-ish BOI rates (ILS per 1 unit). USD anchor included.
# Keyed (YYYY-MM-DD, CCY). Daily granularity kept small but real-shaped.
FX = {
    ("2026-05-04", "USD"): 3.65, ("2026-05-04", "EUR"): 3.95,
    ("2026-05-11", "USD"): 3.67, ("2026-05-11", "EUR"): 3.97,
    ("2026-05-18", "USD"): 3.63, ("2026-05-18", "EUR"): 3.92,
    ("2026-05-25", "USD"): 3.66, ("2026-05-25", "EUR"): 3.96,
    ("2026-05-31", "USD"): 3.64, ("2026-05-31", "EUR"): 3.94, ("2026-05-31", "GBP"): 4.60,
}

MONTH = "2026-05"

# Opening balances (USD) per account at end of prior month (seed).
OPENING_USD = {
    "Leumi-ILS": 120_000.00,
    "Leumi-USD": 380_000.00,
    "Mesh":       15_000.00,
}

# Company's own-name keywords for internal-transfer detection.
TRANSFER_KEYWORDS = ["acme", "אקמי"]

# row: date, account, desc, desc2, ccy, amt_native, is_card,
#      expected_cat, expected_sub, expected_vendor, expected_internal, expected_conf
TXNS = [
    # --- OPERATIONAL CASH IN (all non-investment income) ---
    ("2026-05-04", "Leumi-USD", "WIRE FROM CUSTOMER GLOBEX INC INVOICE 2231", "", "USD", 48_000.00, False,
        "Revenue", "", "Globex", "", "HIGH"),
    ("2026-05-11", "Leumi-ILS", "\u05d4\u05e2\u05d1\u05e8\u05ea \u05dc\u05e7\u05d5\u05d7 \u05e1\u05d9\u05d1\u05e8\u05d3\u05d9\u05df \u05d1\u05e2\"\u05de \u05d7\u05e9\u05d1\u05d5\u05e0\u05d9\u05ea 5512", "", "ILS", 72_000.00, False,
        "Revenue", "", "Cyberdyne", "", "HIGH"),
    ("2026-05-18", "Leumi-ILS", "\u05de\u05e2\"\u05de \u05de\u05e2\u05e0\u05e7 \u05de\u05d3\u05e2\u05df \u05d4\u05d7\u05d3\u05e9\u05e0\u05d5\u05ea", "", "ILS", 90_000.00, False,
        "Grants", "", "Israel Innovation Authority", "", "HIGH"),
    ("2026-05-31", "Leumi-USD", "BANK INTEREST CREDIT", "", "USD", 1_250.00, False,
        "Interest Income", "", "Bank Interest", "", "HIGH"),

    # --- NON-OPERATIONAL inflow: Investment (the ONLY non-op inflow) ---
    ("2026-05-25", "Leumi-USD", "VC ROUND SERIES B WIRE SEQUOIA CAPITAL", "", "USD", 2_000_000.00, False,
        "Investment", "VC Round", "Sequoia", "", "HIGH"),

    # --- PAYROLL ---
    ("2026-05-04", "Leumi-ILS", "\u05de\u05e9\u05db\u05d5\u05e8\u05ea \u05de\u05d0\u05d9\u05e8\u05d5\u05e2 \u05e9\u05db\u05e8", "", "ILS", -210_000.00, False,
        "Payroll", "Salaries", "Meirav Payroll", "", "HIGH"),
    ("2026-05-04", "Leumi-USD", "GUSTO PAYROLL RUN US TEAM", "", "USD", -64_000.00, False,
        "Payroll", "Salaries", "Gusto", "", "HIGH"),

    # --- R&D ---
    ("2026-05-11", "Leumi-USD", "AWS EMEA CLOUD SERVICES", "", "USD", -22_400.00, False,
        "R&D", "Cloud Infrastructure", "Amazon Web Services", "", "HIGH"),
    ("2026-05-18", "Leumi-USD", "AMAZON WEB SERVICES INC", "", "USD", -3_100.00, False,
        "R&D", "Cloud Infrastructure", "Amazon Web Services", "", "HIGH"),  # alias -> same canonical
    ("2026-05-18", "Leumi-USD", "OPENAI CHATGPT ENTERPRISE", "", "USD", -4_800.00, False,
        "R&D", "AI Tools", "OpenAI", "", "HIGH"),
    ("2026-05-25", "Leumi-EUR", "HETZNER ONLINE GMBH SERVER", "", "EUR", -1_900.00, False,
        "R&D", "Cloud Infrastructure", "Hetzner", "", "MED"),

    # --- G&A ---
    ("2026-05-04", "Leumi-ILS", "\u05e9\u05db\u05d9\u05e8\u05d5\u05ea \u05de\u05e9\u05e8\u05d3 WeWork", "", "ILS", -33_000.00, False,
        "G&A", "Rent", "WeWork", "", "HIGH"),
    ("2026-05-11", "Leumi-ILS", "\u05e8\u05d5\u05d0\u05d4 \u05d7\u05e9\u05d1\u05d5\u05df Nextage \u05d7\u05e9\"\u05d7", "", "ILS", -18_000.00, False,
        "G&A", "Legal & Accounting", "Nextage", "", "HIGH"),
    ("2026-05-18", "Leumi-USD", "MONTHLY BANK FEES", "", "USD", -240.00, False,
        "G&A", "Bank Fees", "Bank Fees", "", "HIGH"),

    # --- S&M ---
    ("2026-05-25", "Leumi-USD", "GOOGLE ADS CAMPAIGN", "", "USD", -9_500.00, False,
        "S&M", "", "Google Ads", "", "HIGH"),

    # --- TAX (non-operational) ---
    ("2026-05-31", "Leumi-ILS", "\u05de\u05e1 \u05d4\u05db\u05e0\u05e1\u05d4 \u05ea\u05e9\u05dc\u05d5\u05dd", "", "ILS", -40_000.00, False,
        "Tax", "Income Tax", "Israel Tax Authority", "", "HIGH"),

    # --- CARD tab: a refund (credit) = vendor refund, NOT customer payment ---
    ("2026-05-18", "Mesh", "REFUND FACEBOOK ADS", "", "USD", 600.00, True,
        "S&M", "", "Meta", "", "MED"),
    ("2026-05-11", "Mesh", "NOTION LABS SUBSCRIPTION", "", "USD", -300.00, True,
        "R&D", "SaaS Tools", "Notion", "", "HIGH"),
    # ambiguous CARD credit (no give-away keyword): must be a vendor REFUND, not customer payment
    ("2026-05-25", "Mesh", "CREDIT ADJUSTMENT 4471", "", "USD", 220.00, True,
        "Vendors", "Refund", "", "", "LOW"),

    # --- INTER-ACCOUNT TRANSFER PAIR (must net out; Internal=Y) ---
    ("2026-05-25", "Leumi-USD", "TRANSFER TO ACME ILS ACCOUNT", "", "USD", -50_000.00, False,
        "Internal", "", "Internal", "Y", "HIGH"),
    ("2026-05-25", "Leumi-ILS", "\u05d4\u05e2\u05d1\u05e8\u05d4 \u05de\u05d7\u05e9\u05d1\u05d5\u05df ACME \u05d3\u05d5\u05dc\u05e8\u05d9", "", "ILS", 182_000.00, False,
        "Internal", "", "Internal", "Y", "HIGH"),

    # --- GENUINELY AMBIGUOUS rows expected to land LOW ---
    ("2026-05-11", "Leumi-ILS", "\u05d4\u05e2\u05d1\u05e8\u05d4", "", "ILS", -5_400.00, False,
        "Other OUT", "", "", "", "LOW"),
    ("2026-05-18", "Leumi-USD", "MISC PAYMENT REF 99812", "", "USD", -2_750.00, False,
        "Other OUT", "", "", "", "LOW"),
    ("2026-05-25", "Leumi-ILS", "\u05ea\u05e9\u05dc\u05d5\u05dd \u05db\u05dc\u05dc\u05d9", "", "ILS", -1_200.00, False,
        "Other OUT", "", "", "", "LOW"),
]
