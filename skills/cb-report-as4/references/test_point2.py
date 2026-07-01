"""
test_point2.py — proves the direction-aware rule (point 2) works and stays at TIER3.

  1) Ambiguous credit on a CARD  -> Vendors/Refund (not customer payment).
  2) Same ambiguous credit on a BANK -> Revenue (customer payment).  [direction matters]
  3) A keyword row still beats the TIER3 rule (REFUND FACEBOOK ADS -> S&M, not Vendors).
  4) TIER1 (vendor_memory for this company) still overrides the TIER3 fallback.
"""
import json
import pipeline as pl
import vendor_memory as vmem

# 1) ambiguous credit, card
c_card = pl.classify("CREDIT ADJUSTMENT 4471", 220.0, is_card=True)
# 2) ambiguous credit, bank
c_bank = pl.classify("CREDIT ADJUSTMENT 4471", 220.0, is_card=False)
# 3) keyword row on a card (should NOT fall to the direction rule)
c_kw   = pl.classify("REFUND FACEBOOK ADS", 600.0, is_card=True)

print("1) card credit :", c_card, " <- vendor refund")
print("2) bank credit :", c_bank, " <- customer payment")
print("3) keyword card:", c_kw,   " <- S&M (keyword beats TIER3)")

assert c_card[0] == "Vendors" and c_card[1] == "Refund", "card credit not treated as refund"
assert c_bank[0] == "Revenue", "bank credit not treated as customer payment"
assert c_kw[0] == "S&M", "keyword row was wrongly captured by the direction rule"

# 4) TIER1 (vendor_memory) overrides the TIER3 fallback
path = "/home/claude/cb_harness/vm2.json"
key = pl.normalize_vendor("CREDIT ADJUSTMENT 4471")
with open(path, "w", encoding="utf-8") as f:
    json.dump({"Acme": {key: {"cat": "G&A", "sub": "Bank Fees", "canonical": "Adj"}}}, f)
pl.COMPANY = "Acme"; pl.VENDOR_MEMORY_PATH = path
rows = pl.build_rows()
adj = [r for r in rows if "credit adjustment" in r["desc"].lower()][0]
print("4) with memory :", (adj["cat"], adj["sub"], adj["conf"]), " <- memory overrides TIER3")
assert adj["cat"] == "G&A" and adj["conf"] == "HIGH", "vendor_memory did not override TIER3"

print("\nPASS: direction rule works, sits at TIER3, and is correctly overridden by higher tiers.")
