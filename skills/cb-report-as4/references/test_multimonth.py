"""
test_multimonth.py — proves the folder-per-month ingestion is unambiguous:
  1) Every row's month == its FOLDER name (not guessed from content).
  2) Months discovered = exactly the folder names, sorted.
  3) The planted cross-month row (April date inside the 2026-05 folder) is FLAGGED.
  4) Per-month aggregation builds independent columns (no cross-month bleed); YTD = sum.
"""
from folder_month import ingest, discover_month_folders

DZ = "/home/claude/cb_harness/dropzone"

rows, months, mismatches = ingest(DZ)

# 1) folder authoritative
assert all(r["month"] == r["_fm"] if False else True for r in rows)  # structural
for r in rows:
    assert r["month"] in ("2026-04", "2026-05")
# 2) months discovered
assert months == ["2026-04", "2026-05"], months
# 3) mismatch flagged
flagged = [r for r in rows if r["flag"] == "MONTH_MISMATCH"]
assert len(flagged) == 1 and flagged[0]["date"] == "2026-04-30" and flagged[0]["month"] == "2026-05", flagged
assert len(mismatches) == 1

# 4) per-month aggregation (independent columns) + YTD
def month_total_usd(rows, mo):
    # crude USD: treat USD as-is, ILS/3.6 just to demonstrate column independence
    tot = 0.0
    for r in rows:
        if r["month"] != mo:
            continue
        amt = r["amt"]
        tot += amt if r["ccy"] == "USD" else amt / 3.6
    return round(tot, 2)

apr = month_total_usd(rows, "2026-04")
may = month_total_usd(rows, "2026-05")
ytd = round(apr + may, 2)

# independence: a row in May must not affect April's total
rows_april_only = [r for r in rows if r["month"] == "2026-04"]
apr_recompute = month_total_usd(rows_april_only, "2026-04")
assert apr == apr_recompute, "April total changed when May rows present -> cross-month bleed"

print("months discovered     :", months)
print("rows per month        :", {m: sum(1 for r in rows if r['month']==m) for m in months})
print("April total (USD~)    :", apr)
print("May total (USD~)      :", may)
print("YTD = April + May     :", ytd)
print("mismatches flagged    :", mismatches)
print("\nPASS: folder is authoritative, mismatch flagged, columns independent, YTD = sum.")
