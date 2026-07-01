"""
test_hsbc_deposits.py — validates the new logic against the REAL uploaded statement values.
"""
import hsbc_deposits as h

# (1) MMF Pending Cash Balance — from the uploaded MMF 05/26 statement
mmf_text = """Account Name Fund Name Fund Type 1-Day Yield (Net) AUM (m) Daily Factor
Accrued Interest (MTD) Buy/Sell Cutoff Currency Pending Cash Balance
BOLD.AI INC HSBC U.S. Government Money Market Fund Class P CNAV 3.48 46,667.40
0.000095477 12,017.48 23:49 / 23:49 USD 15,640,038.07"""
bal = h.parse_mmf_balance(mmf_text)
print("(1) MMF balance:", bal)
assert bal["pending_cash_balance"] == 15640038.07, bal
assert bal["accrued_interest_mtd"] == 12017.48, bal

# (2) MMF transaction history
print("(2) Div Reinvest:", h.classify_mmf_txn("Div Reinvest", 41315.39))
print("    Sell        :", h.classify_mmf_txn("Sell", -5000000.00))
assert h.classify_mmf_txn("Div Reinvest", 41315.39) == ("Interest Income", "MMF Dividend", "", "HIGH")
assert h.classify_mmf_txn("Sell", -5000000.00)[2] == "Y"      # internal

# (3) deposit interest as a formula = redeemed − principal
f = h.deposit_interest_formula("D10", "E10")
print("(3) deposit interest formula:", f)
assert f == "=E10-D10"
assert h.is_deposit_row("פיקדון שקלי 90 יום") is True
assert h.is_deposit_row("AWS cloud") is False

# (4) third-party inflow -> Investment candidate (LOW/Review), from the real HSBC checking rows
checking_inflows = [
    ("INTEREST PAID FROM 03/02/26 THRU 03/29/26", 139.40, False),                 # interest
    ("2026032400039162 ... BOLD.AI INC 53RECD FED ... SS&C GIDS INC", 300000.00, False),  # MMF agent = internal
    ("2025171067JS LEVI KEREN OPTIONSPURCHASE 33RECD CHIP ISRAEL DISCOUNT BANK", 465.12, True),  # equity-ish
    ("WIRE FROM UNKNOWN HOLDINGS LP", 250000.00, True),                            # big external wire
    ("WIRE FROM CUSTOMER GLOBEX INC INVOICE 2231", 48000.00, False),               # known customer
]
print("(4) third-party inflow candidates:")
for desc, amt, expected in checking_inflows:
    got = h.is_third_party_investment_candidate(desc, amt)
    print(f"    {expected!s:5} <- got {got!s:5} | {desc[:48]}")
    assert got == expected, (desc, got, expected)

print("\nPASS: MMF balance + accrued interest, Div Reinvest=interest, Sell=internal, deposit-interest formula, and third-party Investment candidates all correct.")
