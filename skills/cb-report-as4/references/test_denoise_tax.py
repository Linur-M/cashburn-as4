"""
test_denoise_tax.py — proves recs 3 (de-noising) and 4 (taxonomy enforcement) are safe & useful.

  1) De-noising strips refs/dates/processor prefixes for matching BUT returns them in a
     `stripped` list (nothing is lost); the cleaned text still classifies correctly.
  2) The original description is never mutated (caller keeps row["desc"]).
  3) Taxonomy: a valid (cat, sub) passes unchanged; an invalid sub is blanked and flagged,
     while the category is kept.
"""
import pipeline as pl

# 1) de-noising preserves what it strips
raw = "PAYPAL *NOTION LABS 04/15/2026 REF 99812"
clean, stripped = pl.denoise(raw)
kinds = {s["kind"] for s in stripped}
print("raw     :", raw)
print("clean   :", clean)
print("stripped:", stripped)
assert "NOTION" in clean.upper(), "merchant fragment lost during de-noising"
assert {"date", "ref"} <= kinds, f"expected date+ref recorded, got {kinds}"
assert any("99812" in s["text"] for s in stripped), "ref number not preserved in stripped list"
# cleaned text still classifies to the right place (Notion -> R&D)
cat, sub, vendor, conf = pl.classify(raw, -300.0, is_card=True)
print("classify:", (cat, sub, vendor, conf))
assert cat == "R&D", "cleaned text failed to classify Notion correctly"

# 2) source description is preserved by the build path
rows = pl.build_rows()
assert all(r["desc"] == src[2] for r, src in zip(rows, __import__("fixture").TXNS)), \
    "source description was mutated"
# and every row carries its (possibly empty) stripped record
assert all("denoise_stripped" in r for r in rows)
print("source descriptions preserved; denoise_stripped attached to every row: OK")

# 3) taxonomy enforcement
ok_cat, ok_sub, ok = pl.enforce_taxonomy("R&D", "SaaS Tools")
bad_cat, bad_sub, bad_ok = pl.enforce_taxonomy("R&D", "Cloud Infra")     # should be 'Cloud Infrastructure'
print("valid  pair :", (ok_cat, ok_sub, ok))
print("invalid pair:", (bad_cat, bad_sub, bad_ok), "<- sub blanked, category kept, flagged")
assert ok is True and ok_sub == "SaaS Tools"
assert bad_ok is False and bad_cat == "R&D" and bad_sub == ""

# the flag propagates through build_rows when taxonomy fails (simulate via a memory hit)
import vendor_memory as vmem, json, importlib
path = "/home/claude/cb_harness/vm_tax.json"
key = pl.normalize_vendor("MISC PAYMENT REF 99812")
with open(path, "w", encoding="utf-8") as f:
    json.dump({"Acme": {key: {"cat": "R&D", "sub": "Cloud Infra", "canonical": "X"}}}, f)
importlib.reload(pl); pl.COMPANY = "Acme"; pl.VENDOR_MEMORY_PATH = path
trow = [r for r in pl.build_rows() if "misc payment" in r["desc"].lower()][0]
print("memory hit w/ invalid sub:", (trow["cat"], trow["sub"], trow["flag"]))
assert trow["sub"] == "" and "TAXONOMY" in trow["flag"], "invalid sub not caught by taxonomy in build path"

print("\nPASS: de-noising preserves all stripped text, source intact, taxonomy enforces valid sub-categories.")
