"""test_fx_excel.py — validates loading BOI rates from a user-provided Excel."""
import os, tempfile
import fx_excel as fx

def _make(path):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = "BOI"
    ws.append(["Date", "USD", "EUR", "GBP"])
    for row in [
        ("2026-03-02", 3.70, 4.00, 4.65),
        ("2026-03-31", 3.63, 3.92, 4.57),   # March last trading day in this sheet
        ("2026-05-29", 3.60, 3.90, 4.55),   # May only has the 29th
        ("2026-07-31", 3.55, 3.85, 4.50),
    ]:
        ws.append(row)
    wb.save(path)

tmp = tempfile.mkdtemp(); path = os.path.join(tmp, "boi_rates.xlsx"); _make(path)

rates, meta = fx.load_fx_from_excel(path)
print("meta:", meta)
assert meta["sheet"] == "BOI" and meta["currencies"] == ["EUR", "GBP", "USD"], meta
assert meta["n_rows"] == 4 and meta["date_min"] == "2026-03-02" and meta["date_max"] == "2026-07-31", meta
assert rates[("2026-03-31", "USD")] == 3.63
assert rates[("2026-05-29", "EUR")] == 3.90

# merge into an existing _FX_LIVE; uploaded file overrides on conflict
fx_live = {("2026-03-31", "USD"): 9.99, ("2026-04-15", "USD"): 3.10}
fx.merge_into_fx_live(fx_live, rates, override=True)
assert fx_live[("2026-03-31", "USD")] == 3.63, "uploaded Excel must win on conflict"
assert fx_live[("2026-04-15", "USD")] == 3.10, "untouched dates remain"
assert fx_live[("2026-07-31", "GBP")] == 4.50

# month-end anchor resolves to the last supplied USD date inside the month
def last_day(live, mo): 
    return fx.month_coverage(live, mo, "USD")[-1]
assert last_day(fx_live, "2026-03") == "2026-03-31"
assert last_day(fx_live, "2026-05") == "2026-05-29"   # sheet's only May quote → correct EOM

# filename detector
assert fx.find_rates_excel(["/up/statement.pdf", "/up/BOI_rates_2026.xlsx"]).endswith("BOI_rates_2026.xlsx")
assert fx.find_rates_excel(["/up/random.xlsx"]) is None

# tolerant date formats
from openpyxl import Workbook
p2 = os.path.join(tmp, "alt.xlsx"); wb = Workbook(); ws = wb.active; ws.title = "Rates"
ws.append(["תאריך", "USD"]); ws.append(["31/05/2026", "3.61"]); wb.save(p2)
r2, m2 = fx.load_fx_from_excel(p2)
assert r2[("2026-05-31", "USD")] == 3.61, (r2, m2)

print("\nPASS: Excel FX load, override merge, month-end resolution, filename detection, and "
      "Hebrew header / DD/MM/YYYY dates all handled.")
