"""
test_mcc_fuzzy.py — proves recommendations 1 (MCC) and 2 (fuzzy vendor) add value safely.

  1) A card row with NO keyword but an MCC is classified via MCC (was LOW/Other before).
  2) MCC is a fallback: a keyword/TIER1 match still wins over MCC.
  3) Fuzzy merges a near-duplicate vendor name to its canonical form (>=0.90).
  4) Guard: a genuinely different vendor is NOT merged (stays itself).
"""
import pipeline as pl

# 1) card row, no keyword, MCC 7311 (advertising)
c_mcc = pl.classify("CHARGE 5521 REF", 900.0, is_card=True, mcc="7311")
print("1) MCC-only card row :", c_mcc)
assert c_mcc[0] == "S&M" and c_mcc[1] == "Advertising", "MCC fallback did not classify"

# 2) precedence: a card row that ALSO has a keyword must use the keyword, not MCC
#    "AWS" keyword -> R&D/Cloud Infrastructure even if MCC says advertising
c_kw_over_mcc = pl.classify("AWS EMEA CLOUD", -500.0, is_card=True, mcc="7311")
print("2) keyword vs MCC    :", c_kw_over_mcc)
assert c_kw_over_mcc[0] == "R&D", "MCC wrongly overrode a keyword match"

# 3) fuzzy: near-duplicate of a canonical vendor merges
fuzz_hit = pl.canonical_vendor("Amazon Web Servicess")     # typo'd duplicate
print("3) fuzzy merge       :", fuzz_hit)
assert fuzz_hit == "Amazon Web Services", f"fuzzy did not merge: {fuzz_hit}"

# 4) guard: a clearly different vendor must NOT collapse into a canonical one
no_merge = pl.canonical_vendor("Microsoft Azure Cloud")
print("4) no false merge    :", no_merge)
assert no_merge != "Amazon Web Services", "false merge — threshold too loose"

# also confirm fuzzy score behaviour around the threshold
s_dup = pl._token_set_ratio(pl.normalize_vendor("Amazon Web Servicess"),
                            pl.normalize_vendor("Amazon Web Services"))
s_diff = pl._token_set_ratio(pl.normalize_vendor("Microsoft Azure Cloud"),
                             pl.normalize_vendor("Amazon Web Services"))
print(f"   sim(dup)={s_dup:.3f}  sim(diff)={s_diff:.3f}  threshold=0.90")
assert s_dup >= 0.90 and s_diff < 0.90

print("\nPASS: MCC adds value as a fallback, keywords still win, fuzzy merges duplicates, no false merge.")
