---
name: CB_REPORT_AS4
description: >
  CFO Financial System (v51) — strict monthly cash burn reports. Use whenever the user
  uploads bank files (Leumi, HSBC, Hapoalim, Discount, CC 5791/5890, deposits/PKAM, SVB,
  Comerica, Brex, PayPal, Chase) and asks for a cash burn report — "run CB report",
  "run CB report AS4", "CB_REPORT_AS4", "CB AS4", "CB AS", "הרץ דוח", "עדכן קאשברן",
  "run the monthly", or any variant implying a financial pipeline. ALWAYS use when files are
  uploaded and a report is requested. Produces a 10-tab Excel, an HTML CEO dashboard, and
  validation.json. FX: BOI rates per transaction date. v47/v48 hardening retained. v52 adds:
  Leumi extended-description (תיאור מורחב) → Desc2, Desc2 as primary classification key, and
  an external-payee guard stopping real vendor/rent/tax payments being false-netted as
  Internal. Additive, backward-compatible (columns A–R fixed).
---

# CB_REPORT_AS4 — CFO Financial System v52

> **v52 changes (additive only):** (1) Leumi parsers (`parse_leumi_ils` / `parse_leumi_usd`)
> MUST read the `תיאור מורחב` extended-description column into `Desc2` (col E) — the real
> counterparty (e.g. "העברה אל: …", "תשלום עבור: …", "העברה מאת: …"). (2) For Leumi rows,
> `Desc2` is the PRIMARY classification key; the short action type in `Description`
> ("העברה דיגיטל" etc.) is only the fallback. (3) Addition D external-payee guard: mirror-pair
> netting is skipped for any leg whose `Desc2` names an external party, so genuine
> supplier/rent/tax outflows are no longer silently netted to zero (which understated burn).
> See Step 1 (Leumi extended description → Desc2) and Addition D (External-payee guard).
> Reference harness `references/pipeline.py` is left on the locked baseline; the v52 behavior
> is specified here and applied by the runtime parser.

> **v46 changes (additive only):** (1) Per-transaction ILS→USD conversion enforced at the
> transaction date's BOI rate, with an audit that no non-USD row lacks an FX rate/source;
> (2) Formulas mandatory across ALL report parts — in BALANCES, formulas where the value is
> derived (Mesh, computed deposits), and value + **Source Note** where it comes from a
> PDF/HTML statement; (3) FX Difference in DETAILED SUMMARY stated explicitly as
> `Closing − Opening (prior-month close) − NET BURN`; (4) ALL income except Investment rolls
> into TOTAL OPERATIONAL IN; (5) Executive Summary top FX row — month-end rates with formula
> `non-USD rate ÷ USD rate` (BOI); (6) smart multi-language classification with a Confidence
> column (HIGH/MED/LOW), defaulting to LOW + Review flag when uncertain; (7) Cash Management
> Policy gains two pies — currency mix (₪/$/€) and USD balance per account (5 charts total);
> (8) Addition D — inter-account transfer detection that nets such moves out of every
> computational tab; (9) Addition E — VENDOR_CLASSIF promoted to TIER1 (authoritative source
> of truth) with vendor-name unification and full retroactive application to TRANSACTIONS;
> (10) circle-level reconciliation tightened to validate every level
> (transaction → category → summary → balance).
> All v44/v45 additions and the 10-tab structure are unchanged.
>
> **v47 changes (CB_REPORT_AS, additive only):** (1) Global formula enforcement — every
> derived numeric cell across Executive Summary, VC, Cash Management Policy helper tables and
> the FX row must be a formula (DETAILED SUMMARY/BALANCES already are); PDF/external figures
> stay static + Source Note; audited in `validation.json → formula_integrity_global`.
> (2) Deterministic chart grid for Cash Management Policy (fixed positions, label row above
> each, helper tables below — zero overlap). (3) Vendor normalization engine `normalize_vendor()`
> run before classification + VENDOR_CLASSIF `Aliases` column + `vendor_fragmentation_score`.
> (4) Persistent `vendor_memory.json` (precedence VENDOR_CLASSIF TIER1 > vendor_memory >
> heuristic). (5) Header-based `detect_parser()` + generic fallback. (6) Multi-layer confidence
> CLASS/FX/PARSER → FINAL_CONFIDENCE (internal + validation.json; NO new visible columns —
> A–R frozen). (7) FX confidence/quality scoring. (8) Hard blocking validation + overall_status.
> (9) Balance cross-check (BALANCE_MISMATCH). (10) FX-exposure KPI. (11) Dashboard insights.
> (12) Reclassify hardening (normalization + vendor_memory reapplied). (13) Internal-pair IDs,
> Audit_ID, ERROR_TYPE internal fields. (14) Expanded RTL accountant workflow guide
> (STEP 1–9, tab-usage rules, reclassify instructions). Existing 0.5% internal-transfer
> tolerance and all column indexes are preserved.

## Execution Mode — STRICT after a single pre-approval gate

STRICT MODE is active, **but it is preceded by one pre-flight confirmation** so it complies
with the organization's pre-approval policy. The gate is the only deviation; once approved,
the pipeline runs strict and unchanged.

**Step −1 — Pre-flight (read-only, before any processing):**
- Scan the uploaded files and present ONE short summary: company, month, transaction count,
  accounts detected, currencies detected, opening balances, and any ⚠ gaps (e.g. an account
  with transactions but no opening-balance seed).
- This scan performs **no classification, no FX conversion, no Excel writing** — it cannot
  change any output.
- End with "להריץ? (Proceed?)" and **wait** for explicit approval.

**After approval — STRICT MODE (unchanged):**
- Execute the full pipeline below, start to finish, without deviation.
- Do NOT explain steps as you go — only deliver the final output.
- Do NOT ask further clarifying questions — everything was auto-detected and confirmed.
- Do NOT summarize at the end — validate, then deliver both files and one status line.

```python
# Step -1, before the pipeline:
pf = build_preflight(COMPANY)              # read-only scan
present(pf["summary"]); await_approval()   # org pre-approval gate
# only on approval:
run_strict_pipeline()                      # existing behaviour, untouched
```

---

## BUILD PATH

## Addition U — FX single-source enforcement, currency-data limits & tab manifest (v51)

### U-1. EOM rate: single source only

The Executive Summary month-end (EOM) rate **must** be derived **exclusively** from
`get_fx(last_trading_day, "USD")` — the same function and same source used for transactions.
**Never** set an EOM rate by hand or from any other source.

```python
eom_date = last_boi_trading_day(reporting_month)          # e.g. "2026-05-30"
usd_eom, src = get_fx_and_source(eom_date, "USD")          # ONLY source of EOM USD rate
# config['EOM_RATES'][month]['USD'] is FILLED from this call — never typed in manually.
config['EOM_RATES'][reporting_month]['USD'] = usd_eom
```

> Root cause this fixes: a config EOM rate for May was derived separately from the normal
> transaction lookup (a manual/other-source value), so 31/05 transactions used 2.907 from the EOM
> config while `get_fx("2026-05-30","USD")` would have returned 2.811 — an internal inconsistency.

### U-2. Blocking cross-check inside the script

Before writing the Excel, the script must assert the config EOM rate equals the FX function's value
for the last trading day. If it fails, **the report is not written**:

```python
assert cfg['EOM_RATES'][month]['USD'] == get_fx(last_trading_day_of_month, 'USD')[0], \
    f"EOM rate mismatch for {month}"
```

### U-3. validation.json + FX_RATES highlight

The FX block and `validation.json` must show the EOM value **with its source explicitly**, so it can
be verified at a glance:

```json
"fx_eom": {
  "EOM_May": "2.811 (source: BOI 2026-05-30)",
  "EOM_Jun": "<rate> (source: BOI <last_trading_day>)",
  "single_source_assert": "PASS"
}
```

The Executive Summary FX row label likewise records the exact date used, e.g. `BOI EOM (2026-05-30)`.

### U-4. Required FX coverage start — 2025-12-31 (no silent constant)

The relevant reporting period for FY2026 begins **2025-12-31**, so daily FX rates must be available
**from 2025-12-31 onward** to cover every transaction during 2026. Rates are supplied at runtime via
the uploaded template `boi_rates_template.xlsx` (whoever runs the skill uploads it with the bank
files); the embedded `currency-data` may begin later, in which case the upload backfills the gap.

The effective coverage start is **dynamic** — it is whichever is earliest among the embedded
`currency-data` start and the uploaded rates file. For any transaction dated **before the effective
coverage start** (i.e. with no daily rate available), the script labels the row
`FX_Source = BOI_fallback` and raises a **WARN** in validation — it must **not** silently fill a
constant.

> What went wrong originally: dates before the embedded data start were silently filled with a
> single constant (the first available day's rate). That is now forbidden — a missing rate surfaces
> as a WARN, never a frozen constant.

### U-5. BOI_fallback validation blocker (WARN)

If any ILS transaction carries `FX_Source = BOI_fallback` in a month that is **not** the latest month
covered by the skill, add an explicit WARN line to `validation.json` and the chat status:

```
WARN: X March transactions converted at a constant 3.170 — daily BOI rates for March are missing.
```

```json
"fx_fallback_warnings": [
  {"month": "2026-03", "count": <X>, "rate_used": 3.170,
   "message": "constant-rate fallback; daily BOI rates missing — supply boi_rates_sample.xlsx"}
]
```

> **Real fix (operational, outside the script):** ensure `boi_rates_template.xlsx` /
> `CurrencyExchange.xlsx` holds daily rates from **2025-12-31 onward**. Once coverage starts at the
> period start, the gate (U-10) stays green and no `BOI_fallback` row is ever produced for 2026.

### U-6. MANDATORY read of SKILL.md before any code

At the very start of the BUILD PATH:

> **MANDATORY: Read this SKILL.md in full before writing any xlsxwriter code. The 10-tab structure
> section is not optional — implement every tab, in order.**

### U-7. Fixed tab manifest at the top of the script

```python
REQUIRED_TABS = [
    "Executive Summary", "TRANSACTIONS", "__LISTS__",
    "DETAILED SUMMARY", "VC", "BALANCES",
    "REFERENCE", "VENDOR_CLASSIF", "הנחייה לחשב", "Cash Management Policy",
]
```

### U-8. Blocking tab assertion before `wb.close()`

```python
built_tabs = [ws.get_name() for ws in wb.worksheets()]
missing = [t for t in REQUIRED_TABS if t not in built_tabs]
if missing:
    raise RuntimeError(f"BLOCKING: missing tabs {missing} — workbook not saved")
wb.close()
```

If a tab is missing the script fails loudly — it never silently emits a wrong file.

### U-9. validation.json — tab manifest check

```json
"tab_manifest": {
  "required": ["Executive Summary","TRANSACTIONS","__LISTS__","DETAILED SUMMARY","VC","BALANCES","REFERENCE","VENDOR_CLASSIF","הנחייה לחשב","Cash Management Policy"],
  "built": ["...actual tabs..."],
  "missing": [],
  "status": "PASS"
}
```

If `missing` is non-empty → `overall_status = FAIL`.

**Governing principle:** anything that can be forgotten needs an assertion that halts the run when it
is absent. A prose description is not enough.

---

---


No bundled script ships with this skill. Build the pipeline in Python and emit the
workbook with `xlsxwriter`, following every step and rule here exactly.

Outputs (auto-versioned, never overwrites):
- `CB_Report_{COMPANY}_{MONTH}_v1.xlsx`
- `CB_Report_{COMPANY}_{MONTH}_v1_Dashboard.html`
- `CB_Report_{COMPANY}_{MONTH}_v1_validation.json`

Copy all three to workspace. Present xlsx + html. Show 3-line validation status in chat.

---

## New Client Template

```python
COMPANY = "ClientName"
FOLDER  = "/path/to/client/bank-files/"

COMPANY_ABALS = {
    "Leumi-ILS": {"ILS": True,  "2026-05": 0},
    "Leumi-USD": {"ILS": False, "2026-05": 0},
}
COMPANY_DEP_ILS = {}
COMPANY_DEP_USD = {}
COMPANY_VENDOR_OVERRIDES = {}
COMPANY_TRANSFER_KEYWORDS = ["clientname"]

# row_type: sect | cat | sub | tot | ocf | burn | fx | bal | nf | sp | recon
COMPANY_STRUCT = [
    ("OPERATIONAL CASH IN", "", "sect"),
    ("Revenue", "", "cat"), ("Grants", "", "cat"),
    ("Interest Income", "", "cat"), ("Other IN", "", "cat"),
    ("TOTAL OPERATIONAL IN", "", "tot"), ("", "", "sp"),
    ("OPERATIONAL CASH OUT", "", "sect"),
    ("Payroll",  "Salaries",            "sub"), ("Payroll",  "", "cat"),
    ("R&D",      "Cloud Infrastructure","sub"), ("R&D", "SaaS Tools", "sub"),
    ("R&D",      "AI Tools",            "sub"), ("R&D", "Dev Contractors", "sub"),
    ("R&D",      "", "cat"),
    ("G&A",      "Rent",                "sub"), ("G&A", "Legal & Accounting", "sub"),
    ("G&A",      "Insurance",           "sub"), ("G&A", "Bank Fees", "sub"),
    ("G&A",      "", "cat"),
    ("S&M", "", "cat"), ("Other OUT", "", "cat"),
    ("TOTAL OPERATIONAL OUT", "", "tot"), ("", "", "sp"),
    ("OPERATING CASH FLOW", "", "ocf"), ("", "", "sp"),
    ("NON-OPERATIONAL", "", "sect"),
    ("Investment", "VC Round", "sub"), ("Investment", "", "cat"),
    ("Tax",        "Income Tax", "sub"), ("Tax", "", "cat"),
    ("", "", "sp"), ("FX Difference", "", "fx"), ("NET BURN", "", "burn"), ("", "", "sp"),
    ("BALANCE (USD)", "", "sect"),
    ("Opening Balance", "", "bal"), ("Net Cash Flow", "", "nf"),
    ("FX Difference (plug)", "", "fx"), ("Closing Balance", "", "bal"),
    ("Reconciliation", "", "recon"),
]
```

`OPERATIONAL_IN`, `OPERATIONAL_OUT`, `NONOP` are **auto-derived** from `COMPANY_STRUCT`
via `_derive_op_sets()` — never hardcode them.

### TOTAL OPERATIONAL IN scope (v46 — ENFORCED)

**ALL cash-in categories except Investment roll into `TOTAL OPERATIONAL IN`.** This
includes Revenue, Grants, Interest Income, and any Other IN. The ONLY inflow that stays in
NON-OPERATIONAL is `Investment` (VC Round / equity / convertible). Concretely:

- `Interest Income` (bank interest, MMF dividends, deposit yield) is moved **out** of the
  old NON-OPERATIONAL `Interest` line and **into** OPERATIONAL CASH IN. It is operational
  cash the business genuinely received.
- `TOTAL OPERATIONAL IN` = SUM of every `cat` row inside the OPERATIONAL CASH IN section.
  `_derive_op_sets()` must pick these up automatically from the section boundaries; do not
  hardcode the category list.
- When classifying, route any non-investment inflow to an OPERATIONAL CASH IN category. If
  an inflow cannot be matched to Revenue/Grants/Interest Income, place it in `Other IN`
  (operational), NOT in a non-operational bucket.

---

## Step 0 — FX Pre-load

Load BOI rates from the `currency-data` skill SKILL.md (extract embedded JSON).


### U-10. currency-data coverage-start gate (v51 — BLOCKING)

`currency-data` is read at Step 0 and must cover the **whole reporting period dictated by the
transactions** — its coverage must begin no later than the earliest transaction date, not at an
arbitrary fixed date. After loading the embedded rates (and merging any uploaded rates Excel),
compute the earliest transaction date and verify coverage:

```python
cov_start = min(parse_date(d) for d in _FX_LIVE.keys())     # currency-data + uploaded rates merged
min_txn   = min(t["date"] for t in transactions)            # earliest transaction processed

if min_txn < cov_start:
    # Is the gap covered by an uploaded external rates file (boi_rates_template.xlsx)?
    if rates_xlsx and load_fx_from_excel(rates_xlsx)[0]:
        # uploaded file extends coverage backward; OK if it reaches min_txn
        ext_start = min(parse_date(d) for d in load_fx_from_excel(rates_xlsx)[0].keys())
        assert ext_start <= min_txn, (
            f"FX coverage gap: transactions start {min_txn}, rates start {min(cov_start, ext_start)}")
    else:
        flag("FX_COVERAGE_START_GAP", min_txn, cov_start)   # -> validation.json (WARN)
        # rows before cov_start carry FX_Source = BOI_fallback (U-4/U-5) until the gap is filled
```

Record the result in `validation.json`:

```json
"fx_coverage_window": {
  "currency_data_start": "2026-03-30",
  "earliest_transaction": "2026-01-08",
  "covered": false,
  "gap_days_uncovered": 81,
  "status": "WARN — extend currency-data backward to <= earliest_transaction, or upload boi_rates_template.xlsx"
}
```

**Permanent fix:** extend the embedded `currency-data` history backward so `currency_data_start
<= earliest_transaction` for every period processed; then this gate is always green and no
`BOI_fallback` row is ever produced.

Populate `_FX_LIVE = {(YYYY-MM-DD, CCY): rate}`.

5-strategy pipeline: boi_rates.json → BOI SDMX CSV → BOI PublicApi JSON → Bank Leumi
page → Embedded `_FX_FALLBACK`. **No third-party sources. No mid-market rates.**

`get_fx_and_source(date, ccy)` returns `(rate, source_label)`:
`BOI_daily` / `BOI_EOM` / `BOI_walkback_Nd` / `estimated` / `estimated_wbNd` / `hardcoded`.
Write this label to the `FX_Source` column in TRANSACTIONS for every row.

### Per-transaction conversion (v46 — ENFORCED)

Every non-USD transaction is converted to USD **at the BOI rate of its own transaction
date** — never an end-of-month or blended rate. ILS, EUR, GBP all follow the same rule.

```python
def to_usd(amount, ccy, txn_date):
    if ccy == "USD":
        return round(amount, 2), 1.0, "USD_native"
    if ccy == "ILS":
        # ILS is the BOI base — there is NO "ILS" key in the rate series.
        usd_rate, src = get_fx_and_source(txn_date, "USD")  # ILS per 1 USD
        return round(amount / usd_rate, 2), usd_rate, src
    rate, src = get_fx_and_source(txn_date, ccy)   # rate = non-USD units per 1 USD (BOI)
    return round(amount / rate, 2), rate, src
```

**ILS is the BOI base currency — no 'ILS' key exists in the rate series.** ILS transactions
must be converted to USD using the daily USD rate (ILS per 1 USD) of the transaction date:

```python
# ILS → USD: divide the ILS amount by the USD BOI rate at the transaction date.
# NEVER look up get_fx_and_source(date, "ILS") — that key does not exist.
# Correct:
if ccy == "ILS":
    usd_rate, src = get_fx_and_source(txn_date, "USD")   # ILS per 1 USD
    return round(amount / usd_rate, 2), usd_rate, src
```

For each transaction write three columns: `Amt USD` (col I), `FX Rate` (col J), and
`FX_Source` (col K). The `FX Rate` cell is the literal BOI rate used for that date, so the
conversion is auditable line by line.

**FX-coverage audit (v46):** after building TRANSACTIONS, assert that **no** non-USD row
has an empty `FX Rate` or `FX_Source`. Any such row is logged to
`validation.json → v46_audit.fx_coverage_gaps` and flagged `Review (no FX rate)` in the
Flag column. A non-USD row with rate source `hardcoded` or `estimated*` is allowed but
counted, so the controller can see how many rows relied on a fallback rather than a true
daily BOI rate.

**FX confidence/quality (v47):** see v47 Addition F. A confidence/quality score is derived
from each row's FX source label and stored **internally** (no new visible column — A–R
frozen) and summarized in `validation.json → fx_quality_summary`.

---

## Step 0b — Operating Mode Detection

| Mode | When | Behaviour |
|---|---|---|
| `classify` | Fresh files, no prior workbook | Build full model (one column per month found) |
| `update` | Existing workbook + new month files | Append new month column(s) |
| `update (multi-month, per-folder)` | Existing workbook + a drop of **per-month folders** (`YYYY-MM/`) | Append **one new column per folder**, in folder order |
| `reclassify` | No bank files, prior workbook present | Re-apply VENDOR_CLASSIF |

### Per-month folder convention (drag-and-drop, multi-month update — v48)

To add several months at once without confusion, accept files organized in folders named
`YYYY-MM` (e.g. `2026-04/`, `2026-05/`). **The folder name is the authoritative month tag**
for every file inside it — the month is NEVER guessed from file content, so two months can be
dropped together with zero cross-month mixing.

Safety rule (prevents misfiling): each transaction's own date is checked against its folder.
A row whose date falls outside its folder's month is **flagged `MONTH_MISMATCH` (Review)** and
listed in `validation.json → month_mismatches`, but is still placed in the **declared folder
month** — the report never silently moves money to another column; the controller fixes the
source file instead. Processing order = folder names sorted ascending, so columns append
chronologically (opening balance of each month = closing of the previous, per the BALANCE
section). Files NOT inside a `YYYY-MM` folder fall back to single-month detection as before.

```python
# month is taken from the folder, then validated against each row's date:
folder_month = resolve_month_from_folder(path)        # 'YYYY-MM' from the folder name
row["month"] = folder_month                           # authoritative column assignment
if row["date"][:7] != folder_month:
    row["flag"] = "MONTH_MISMATCH"                    # surfaced, NOT auto-moved
```

---

## Step 1 — File Detection & Parsing

| Signal | Type | Parser |
|---|---|---|
| עוש שח / leumi il NIS | `CHECKING_NIS` | `parse_leumi_ils` |
| עוש דולר / leumi usd | `CHECKING_USD` | `parse_leumi_usd` |
| CC 5791/5890 NIS/USD | `CC_NIS/USD` | `parse_cc_ils/usd` |
| hapoalim ils/usd | `HAPOALIM` | `parse_hapoalim` |
| discount ils | `DISCOUNT_NIS` | `parse_discount_ils` |
| HSBC / PKAM | `HSBC` | `parse_hsbc` |
| Mesh CSV/XLSX | `MESH` | `parse_mesh` |
| svb/comerica/bill.com/brex/paypal/chase | generic | Addition C |

**HTML-disguised XLS:** `pandas.read_html()`. Per-file try/except — one bad file skips.

**Header-based parser detection (v47):** see v47 Addition J. `detect_parser(df)` chooses a
parser by column headers (`תאריך`→Leumi ILS, `Narrative`→HSBC, `merchant`→CC) and falls back
to `parse_generic` (Flag `Review (generic parser)`, Confidence `LOW`). A `parser_confidence`
field is logged to `validation.json`. The existing signal/filename table above remains the
primary route; header detection is the complementary fallback.

**Leumi extended description → Desc2 (v52 — MANDATORY):** Leumi checking exports
(`parse_leumi_ils` / `parse_leumi_usd`) contain TWO description fields:

| Source column | Goes to | Role |
|---|---|---|
| `תיאור פעולה` / `תיאור תנועה` (short action type, e.g. "העברה דיגיטל", "זיכוי", "חיוב") | `Description` (col D) | the bank action verb only |
| `תיאור מורחב` (extended description — the real counterparty, e.g. "העברה אל: אפי נכסים", "תשלום עבור: רשות המיסים / ביטוח לאומי", "העברה מאת: VALLEY NATIONAL BANK") | `Desc2` (col E) | the real payee / payer |

The parser MUST read the `תיאור מורחב` column and write it to `Desc2`. If the column is
absent or empty for a row, `Desc2` stays blank and the row is flagged `Review (no Desc2)`.
**Never collapse the short action type alone into the classification key** — the extended
description carries the counterparty. Per Addition B2, `Desc2` (the real payee) is the
PRIMARY classification key for Leumi rows; `Description` (the bank verb) is only the
fallback. A short action type such as "העברה דיגיטל" with no own-account / transfer-keyword
match in `Desc2` is an EXTERNAL payment (vendor / rent / tax) — classify it on its merits,
**never auto-tag it `Internal`** (see Addition D guard below).

---

## Step 2 — Classification

Priority: Internal → Investment → Grants → Tax → Payroll → Interest → R&D → G&A → S&M → Other

**`_fesc()` — CRITICAL:**
```python
def _fesc(s): return str(s).replace('"', '""')
# Hebrew vendors (בע"מ, פק"מ) contain " which breaks SUMIFS XML
```

### Smart multi-language classification + Confidence (v46)

Classification reads and interprets each transaction's description in **whatever language
it is written** — Hebrew, English, or mixed — using meaning, not just keyword matching.
Hebrew wire text, English memo lines, transliterated vendor names, and bank-specific
shorthand are all interpreted on their merits.

Every classified row gets a **Confidence** label written to the new `Confidence` column
(see column map) and mirrored into the Flag column when low:

| Confidence | When | Flag |
|---|---|---|
| `HIGH` | Exact match to a VENDOR_CLASSIF entry, an unambiguous keyword, or a deterministic rule (payroll provider, known tax authority, signed VC wire). | — |
| `MED`  | Strong inference from description semantics but no exact prior mapping (e.g. a SaaS-sounding English vendor not yet in VENDOR_CLASSIF). | `Review (med confidence)` |
| `LOW`  | **Default whenever the classifier is not sure.** Ambiguous, generic ("transfer", "העברה"), unreadable, or a brand-new payee with no signal. | `Review (low confidence)` |

Rules:
- **When in doubt, assign LOW — never guess HIGH.** It is correct and expected for a fresh
  client's first run to have many LOW rows; the controller resolves them via VENDOR_CLASSIF.
- LOW rows are still given a best-guess Category/Sub so totals are complete, but they are
  flagged for review and logged to `validation.json → v46_audit.low_confidence_log`.
- A VENDOR_CLASSIF (TIER1) match always overrides the heuristic and sets Confidence `HIGH`
  (see Addition E) — manual classification is authoritative.
- Confidence is computed per row and never blanks. The validation step reports the
  HIGH/MED/LOW distribution as a percentage in the chat status line.

### Direction-aware fallback (TIER3 — v48) — bank vs card, by cash direction

A credit (cash IN) carries a **different meaning depending on the source tab**, and only the
direction-aware rule below resolves it when no keyword/TIER1 match was found:

| Tab type | Cash IN (credit), unmatched | Cash OUT (debit), unmatched |
|---|---|---|
| **Bank** (Leumi, HSBC, Hapoalim, Discount, SVB, Comerica, Bill.com, Chase) | `Revenue` — unknown customer payment (best guess) | `Other OUT` |
| **Card** (Mesh, Brex, PayPal) | `Vendors / Refund` — a card credit is a **vendor refund, NOT** a customer payment | `Vendors / <merchant>` |

Rules:
- This rule lives at **TIER3** — it fires **only** when TIER1 (VENDOR_CLASSIF), vendor_memory,
  and the deterministic/semantic keyword rules (TIER2) all produced no match. A keyword or a
  human mapping **always wins** over it.
- All rows it produces are **Confidence = LOW** with a Review flag, so the controller confirms
  them in VENDOR_CLASSIF (where the decision becomes TIER1 and is remembered).
- `CARD_TABS = {"Mesh", "Brex", "PayPal"}` determines tab type. A card credit misread as a
  customer payment would otherwise inflate operational revenue — this rule prevents that.

```python
# inside classify(), AFTER all keyword/TIER2 rules, as the final fallback:
if amount > 0:                     # cash IN
    if is_card:
        return "Vendors", "Refund", "", "LOW"      # card credit = vendor refund
    return "Revenue", "", "", "LOW"                # bank credit = customer payment (best guess)
return "Other OUT", "", "", "LOW"                  # ambiguous cash OUT
```

### MCC-based classification (TIER2.5 — v48) — card tabs

Card exports (Mesh/Brex) usually carry a Merchant Category Code. MCC is the strongest single
signal for an unmatched card row, so map it to (Category, Sub) **after** keyword/TIER1 rules
but **before** the TIER3 direction fallback. MCC is broad, so unambiguous codes (software,
advertising) yield HIGH while intent-ambiguous codes (restaurants, network services) yield
MED. A keyword or human (VENDOR_CLASSIF) match always wins over MCC.

```python
MCC_MAP = {
    "7372": ("R&D", "SaaS Tools", "HIGH"),  "5734": ("R&D", "SaaS Tools", "HIGH"),
    "4816": ("R&D", "Cloud Infrastructure", "MED"), "7311": ("S&M", "Advertising", "HIGH"),
    "5968": ("R&D", "SaaS Tools", "MED"),   "5812": ("G&A", "Meals & Entertainment", "MED"),
    "4214": ("G&A", "Shipping & Courier", "MED"),
}
# inside classify(), after keyword rules, before the direction fallback:
if is_card and mcc and str(mcc) in MCC_MAP:
    cat, sub, conf = MCC_MAP[str(mcc)]
    return cat, sub, canonical_vendor(desc), conf
```

Keep the full MCC→(Category, Sub) table in the REFERENCE tab so the controller can see and
extend it; treat REFERENCE as read-only input to the engine (do not edit it mid-run).

### Fuzzy vendor resolution (v48) — merge near-duplicate names

After the exact canonical-fragment match, add a fuzzy fallback so slightly different spellings
of the same vendor (e.g. "Amazon Web Services" vs "Amazon Web Servicess") collapse to one
canonical name instead of appearing as separate vendors. Use a token-set similarity (stdlib
`difflib`, no external dependency); **merge only at ≥0.90** so a genuinely different vendor is
never collapsed. Scores 0.80–0.90 may be suggested with Confidence MED + Review.

```python
import difflib
def _token_set_ratio(a, b):
    ta = " ".join(sorted(set(a.split()))); tb = " ".join(sorted(set(b.split())))
    return difflib.SequenceMatcher(None, ta, tb).ratio()
# in canonical_vendor(), only if no exact fragment matched:
best, score = max(((c, max(_token_set_ratio(key, normalize_vendor(c)),
                            _token_set_ratio(key, f)))
                   for f, c in CANON.items()), key=lambda x: x[1])
if score >= 0.90:
    return best
```

Abbreviation cases with no surface overlap (e.g. "AMZN Mktp" → Amazon) are NOT caught by
fuzzy; handle those with explicit aliases in `CANON` / VENDOR_CLASSIF, not by lowering the
threshold (which would cause false merges).

### Description de-noising (v48) — clean for matching, PRESERVE the original

Before matching (keyword / fuzzy / MCC), build a cleaned match string by removing dates,
reference/asmachta numbers, long bare numbers, and payment-processor prefixes
("PAYPAL \*", "SUMUP \*", "AMZN Mktp US\*…"). This lifts the hit-rate of every layer because
they match on the merchant fragment instead of noise.

**Nothing is lost — this is an audit requirement, not a cosmetic step:**
- The full original bank text stays in `Description` (col D) — never mutated.
- The raw payee string stays in `Vendor_Raw` (col Q).
- The cleaned text is used **only internally** for matching; it is not written over the source.
- Everything removed is recorded per row in `validation.json → denoise_stripped`
  (`{kind: date|ref|longnum|processor, text: "..."}`), so a controller can always see exactly
  what was stripped and recover it. Do **not** add a visible column for this (A–R stay fixed).

```python
def denoise(desc):
    text, stripped = str(desc), []
    for pat, kind in DENOISE_PATTERNS:          # dates, ref/asmachta, long numbers, processor *
        for m in re.findall(pat, text, re.I):
            stripped.append({"kind": kind, "text": (m if isinstance(m, str) else " ".join(m)).strip()})
        text = re.sub(pat, " ", text, flags=re.I)
    return re.sub(r"\s{2,}", " ", text).strip(), stripped
# classify() matches on denoise(desc)[0]; the row keeps the untouched Description + Vendor_Raw.
```

### Hierarchical taxonomy enforcement (v48) — consistent sub-categories

Keep a canonical `Category → [allowed Sub_Category]` map (`TAXONOMY`) in the REFERENCE tab.
After classification, validate each (Category, Sub) pair: an out-of-taxonomy sub is **blanked**
(category kept) and the row flagged `TAXONOMY` for Review, and the violation is logged to
`validation.json → taxonomy_violations`. This stops sub-category drift ("Cloud Infra" vs
"Cloud Infrastructure", "Salary" vs "Salaries") that otherwise accumulates across months.

```python
def enforce_taxonomy(cat, sub):
    allowed = TAXONOMY.get(cat)
    if allowed is None:      return cat, sub, False     # unknown category -> flag
    if sub in allowed:       return cat, sub, True
    return cat, "", False                                # drop invalid sub, keep cat, flag
```

The check runs after TIER1/vendor_memory too, so even a human/memory mapping with a typo'd
sub is caught and surfaced rather than silently propagating.

---

## Step 3 — Deposit (PKAM) Processing

Placement → `Internal/Deposit Placement`
Redemption → `Internal/Deposit Redemption`
HSBC MMF Div Reinvest → `Interest Income/MMF Dividend` (operational, per v46)

Note (v46): `Internal/Deposit Placement` and `Internal/Deposit Redemption` are intra-entity
moves and are netted out of all computational tabs by the inter-account logic (Addition D).
Only the **yield** (interest/dividend) is an operational inflow.

### Deposit interest as a FORMULA (v48) — ILS and USD

For a time deposit (פיקדון / PKAM), the interest/yield earned is computed **as a formula**, not
a literal: `interest = redeemed − principal deposited`. Place this on the deposit's interest
line so the workbook stays formula-driven (this is a derived cell, not in A–R):

```python
# interest_cell = redeemed_cell − principal_cell
ws.write_formula(r, c, f"={redeemed_cell}-{principal_cell}")   # e.g. "=E10-D10"
```

Apply to ILS deposits **especially** (and USD): the principal placed and the amount redeemed
are matched by account + deposit id, and only the difference (the yield) is routed to
`Interest Income` (operational). The placement/redemption legs themselves remain
`Internal` and net out.

### Interest extraction in the other accounts (v48)

Beyond MMF, extract the interest amount wherever it appears and route it to `Interest Income`:
- HSBC checking `INTEREST PAID FROM … THRU …` lines (e.g. 455.15, 139.40) → `Interest Income/Bank Interest`.
- MMF transaction history: `Div Reinvest` → `Interest Income/MMF Dividend`; `Sell` / redemption → `Internal` (money returning to checking, netted); `Buy` → `Internal`.

### Third-party inflow → Investment CANDIDATE (v48)

Read the Description of every CASH-IN. If it did **not** arrive via the same entity, a known
customer, or interest, flag it as a **candidate** for the `Investment` category with
Confidence = LOW and a Review flag — **never** an automatic Investment classification; the
controller confirms in VENDOR_CLASSIF. Same-entity / known-plumbing counterparties
(`BOLD.AI`, `SS&C GIDS` = the MMF transfer agent, `Mesh`/`MeshPay`) are treated as internal,
not investment. Signals that raise a candidate: `OPTIONSPURCHASE`, share/equity/SAFE/
convertible/capital-call wording, or a sizable inbound wire (≥ $50K) from an unrecognised
counterparty.

---

## Step 4 — Mesh Balance Computation (v45)

Compute Mesh closing balances from transactions BEFORE writing BALANCES tab:

```python
from collections import defaultdict

mesh_monthly = defaultdict(float)
for t in all_txns:
    if t.get("source_tab", "").lower().startswith("mesh"):
        usd, _rate, _src = to_usd(
            t.get("amount", 0), t.get("currency", "USD"), t["date"])
        mesh_monthly[mof(t["date"])] += usd

mesh_cum = 0.0
for mo in MONTHS:
    mesh_cum += mesh_monthly.get(mo, 0.0)
    COMPANY_ABALS.setdefault("Mesh", {"ILS": False})[mo] = round(mesh_cum, 2)
```

Include Mesh as its own row in BALANCES. Mesh deposits (Internal/Mesh Funding) cancel out
in the Mesh account; the net Mesh balance = unspent card float.

---

## Step 5 — Excel Output (xlsxwriter)

### Critical rules
- **No `write_dynamic_array_formula()`** — causes XML corruption.
- **`_fesc()` ALL strings embedded in SUMIFS formulas.**
- **Tab 1 = Executive Summary** — first `add_worksheet()` call.
- **KPI pre-computation precedes `Workbook(...)`.**
- **Auto-versioned output**: `_v1`, `_v2` etc.

### Helper: column index → Excel letter
```python
def xlcol(n):   # 0-indexed
    s = ""; n += 1
    while n:
        s = chr(65 + (n-1) % 26) + s; n = (n-1) // 26
    return s

def cellref(sheet, row0, col0):
    return f"'{sheet}'!${xlcol(col0)}${row0+1}"
```

### TRANSACTIONS column map (0-indexed, for SUMIFS)
```
col 0  = A = Date
col 1  = B = Month        ← SUMIFS month filter
col 2  = C = Account
col 3  = D = Description
col 4  = E = Desc2
col 5  = F = Ref
col 6  = G = CCY
col 7  = H = Amt Native
col 8  = I = Amt USD      ← SUMIFS values column
col 9  = J = FX Rate      ← BOI rate at transaction date (literal, auditable)
col 10 = K = FX Source
col 11 = L = Category     ← SUMIFS category filter
col 12 = M = Sub_Category ← SUMIFS sub filter
col 13 = N = Vendor       ← SUMIFS vendor filter (UNIFIED canonical name, v46)
col 14 = O = Flag
col 15 = P = Confidence   ← HIGH / MED / LOW (v46)
col 16 = Q = Vendor_Raw   ← original payee text before unification (v46, audit)
col 17 = R = Internal     ← "Y" if inter-account transfer (netted out), else "" (v46)
```

**Important:** the SUMIFS value/filter columns (I, L, M, N) keep their existing positions so
all v45 DETAILED SUMMARY formula templates remain valid. The three new columns (P, Q, R) are
appended at the end — additive, non-breaking. The `Internal` column (R) lets every
computational tab exclude inter-account transfers with one extra SUMIFS criterion
(`TRANSACTIONS!$R:$R,"<>Y"`) — see Addition D.

---

### DETAILED SUMMARY — Formula rules (v45 ENFORCED)

**ALL numeric data cells in DETAILED SUMMARY must be written with `ws.write_formula()`.
NEVER use `ws.write(row, col, python_float, fmt)` for any category/sub/vendor/total data cell.**

Why: `write_formula()` embeds the SUMIFS string in the xlsx XML. When the controller
edits VENDOR_CLASSIF and re-opens the file, Excel recalculates automatically. Static
`ws.write()` with Python floats produce dead cells that never update.

```python
# Category row — one month:
formula = (f'=SUMIFS(TRANSACTIONS!$I:$I,'
           f'TRANSACTIONS!$B:$B,"{mo}",'
           f'TRANSACTIONS!$L:$L,"{_fesc(cat)}")')
ws.write_formula(row, col, formula, fmt)

# Sub-category row — add Sub filter:
formula = (f'=SUMIFS(TRANSACTIONS!$I:$I,'
           f'TRANSACTIONS!$B:$B,"{mo}",'
           f'TRANSACTIONS!$L:$L,"{_fesc(cat)}",'
           f'TRANSACTIONS!$M:$M,"{_fesc(sub)}")')
ws.write_formula(row, col, formula, fmt)

# Vendor row — add Vendor filter:
formula = (f'=SUMIFS(TRANSACTIONS!$I:$I,'
           f'TRANSACTIONS!$B:$B,"{mo}",'
           f'TRANSACTIONS!$L:$L,"{_fesc(cat)}",'
           f'TRANSACTIONS!$M:$M,"{_fesc(sub)}",'
           f'TRANSACTIONS!$N:$N,"{_fesc(vendor)}")')
ws.write_formula(row, col, formula, fmt)

# YTD column — reference the month cells already written in this row:
ytd = "=" + "+".join(f"{xlcol(month_cols[i])}{row+1}" for i in range(len(MONTHS)))
ws.write_formula(row, ytd_col, ytd, fmt)

# Totals rows (TOTAL OPERATIONAL IN/OUT, OCF, NET BURN) — sum category cells above:
tot = "=" + "+".join(f"{xlcol(col)}{cat_row+1}" for cat_row in cat_rows_in_section)
ws.write_formula(tot_row, col, tot, fmt)
```

**Exception:** section headers ("OPERATIONAL CASH IN"), spacer rows, Δ%, and
Reconciliation text may use `ws.write()` with strings.

---

### DETAILED SUMMARY — Row grouping / drill-down (v45)

```python
# Enable outline controls (summary rows at top of group):
ws.outline_settings(True, False, True, True)

# Sub-category rows → level 1, initially collapsed:
ws.set_row(sub_row, 15, fmt_sub, {"level": 1, "hidden": True, "collapsed": False})

# Vendor rows → level 2, initially collapsed:
ws.set_row(vendor_row, 15, fmt_vendor, {"level": 2, "hidden": True, "collapsed": False})
```

Controllers click `+` next to a category row to expand sub-categories; `+` next to a
sub-category to expand vendors. Category rows (level 0) are always visible.

**Full breakout requirement (v48):** emit a drill-down row for **every** Category **and every
allowed Sub-category** in the taxonomy (not only the ones that happen to be non-zero this
month), each as its own `SUMIFS`. This gives a complete, stable Category/Sub breakdown that
keeps the same row set across months (so multi-month columns line up) and lets the controller
see a $0 sub explicitly rather than wondering if it was dropped. A zero sub still renders (its
SUMIFS returns 0). These rows are informational — totals and the reconciliation circles keep
summing the **category** cells only, so adding sub rows never changes NET BURN or any circle.

---

### DETAILED SUMMARY — BALANCE section (v45)

After "NET BURN", write a "BALANCE (USD)" section. Reference BALANCES tab for values —
do not embed Python floats.

```
Row  Label                  Formula
---  ---------------------  ---------------------------------------------------------
     BALANCE (USD)          [section header]
bal  Opening Balance        =BALANCES!${xlcol(tot_col)}${prior_month_row+1}  (or 0 for first month)
nf   Net Cash Flow          ={xlcol(ocf_col)}{ocf_row+1}+{xlcol(nonop_col)}{nonop_row+1}  (sum all OCF+nonop rows)
fx   FX Difference (plug)   ={closing_cell}-{opening_cell}-{net_burn_cell}
bal  Closing Balance        =BALANCES!${xlcol(tot_col)}${this_month_row+1}
recon Reconciliation        =IF(ABS({closing}-{opening}-{net_burn}-{fx})<1,"OK","ERROR "&TEXT({closing}-{opening}-{net_burn}-{fx},"$#,##0"))
```

### FX Difference — explicit definition (v46)

**`FX Difference = Closing Balance − Opening Balance − NET BURN`**, where:
- **Closing Balance** = this month's total in BALANCES.
- **Opening Balance** = prior-month Closing Balance (= prior-month total in BALANCES; 0 for
  the first period).
- **NET BURN** = the NET BURN row already computed above in this same column (it equals
  Operating Cash Flow + all NON-OPERATIONAL lines = the period's Net Cash Flow).

So the plug cell references the **NET BURN row directly**, not a separately recomputed NCF:

```python
fx_formula = f"={closing_cell}-{opening_cell}-{xlcol(col)}{net_burn_row+1}"
ws.write_formula(fx_row, col, fx_formula, fmt_fx)
```

**FX Difference** is the reconciliation plug. It absorbs unrealized FX gain/loss so that
`Opening + NET BURN + FX = Closing` exactly. A nonzero FX Difference is EXPECTED for
ILS-heavy companies on months the shekel moves — it is the revaluation of non-USD balances
at the new month-end rate, NOT an error. Colour: orange if |FX| > $50K.

For multi-month reports, Opening Balance of month M = Closing Balance of month M-1.
For the first month, Opening Balance = BALANCES total at the column before the first month
(write 0 if no prior period data exists).

---

### BALANCES tab (v46)

Row order: Leumi accounts → HSBC accounts → **Mesh** (from Step 4) → Deposits (PKAM) → TOTAL.

**Formulas where the value is derived; value + Source Note where it is a statement figure.**
Add a `Source Note` column to the right of the month columns:

| Balance origin | How to write it | Source Note |
|---|---|---|
| **Derived** — Mesh (Step 4), computed deposit running balance, or any balance built from transactions | `ws.write_formula(...)` referencing the transaction-derived cumulative (e.g. `=SUMIFS(TRANSACTIONS!$I:$I,...)` up to month, or a running-sum formula across month columns) | `derived from TRANSACTIONS` |
| **PDF/HTML statement** — closing balance read from a bank statement file | `ws.write(r, c, value, fmt)` (literal value — NOT a formula) | the filename + page/section, e.g. `Leumi_OSH_2026-05.pdf p.1 closing` |
| **Manual `COMPANY_ABALS`** seed | `ws.write(r, c, value, fmt)` | `COMPANY_ABALS seed` |

```python
# Derived balance → formula
ws.write_formula(r, c, f"=SUMIFS(TRANSACTIONS!$I:$I,"
                       f'TRANSACTIONS!$C:$C,"{_fesc(acct)}",'
                       f'TRANSACTIONS!$B:$B,"<={mo}")', fmt_num)
ws.write(r, src_col, "derived from TRANSACTIONS", fmt_note)

# PDF/HTML statement balance → literal + source note for review
ws.write(r, c, stmt_value, fmt_num)
ws.write(r, src_col, f"{pdf_filename} {page_ref}", fmt_note)
```

Rationale (per controller policy): formula-where-possible keeps the file live; but a balance
that came from a PDF/HTML statement is a captured external figure — keep it as a value and
**record where it was read from** so it can be reviewed and re-checked against the source
document. The FX-coverage and reconciliation audits both read the Source Note column.

TOTAL row: `=SUM(account_cells_in_column)` formula (always a formula).

### HSBC MMF account balance = Pending Cash Balance (v48)

The HSBC MMF account row in BALANCES is **not** built from transaction movements — its balance
is the **`Pending Cash Balance`** figure from the MMF portfolio statement (PDF or Excel), taken
as a captured external value with a source note (like any statement balance). Example
(uploaded May statement): `Pending Cash Balance = 15,640,038.07 USD`, `Accrued Interest (MTD) =
12,017.48`.

```python
mmf = parse_mmf_balance(ocr_text_or_excel)         # {pending_cash_balance, accrued_interest_mtd, currency}
ws.write(r, c, mmf["pending_cash_balance"], fmt_num)
ws.write(r, src_col, "HSBC MMF: Pending Cash Balance", fmt_note)
```

**These MMF/HSBC PDFs are scanned (no text layer)** — extraction requires OCR, or prefer an
Excel/CSV export of the same statement when available. Anchor extraction on the data-row
structure (the figure after the `USD` currency = Pending Cash Balance; the figure before the
buy/sell cutoff time = Accrued Interest), not on the header label, because in the scanned
layout headers and values are separated.

The DETAILED SUMMARY BALANCE section references the TOTAL row via `cellref("BALANCES", tot_row, col)`.

---

### 10-tab structure

| Tab | Notes |
|---|---|
| **Executive Summary** | **Top row: month-end FX rates** (v46). KPI formulas ref BALANCES + DETAILED SUMMARY. Top 12 vendors. |
| TRANSACTIONS | 18 cols (adds Confidence, Vendor_Raw, Internal — v46), zebra, autofilter, `repeat_rows(0,0)`. |
| __LISTS__ | Hidden. |
| DETAILED SUMMARY | SUMIFS formulas, row grouping, BALANCE section, explicit FX Difference. |
| VC | Vendor × Month totals (canonical unified names). |
| BALANCES | Mesh row; formulas where derived, value + Source Note where from PDF/HTML. |
| REFERENCE | Category mapping. |
| VENDOR_CLASSIF | **TIER1 — authoritative** (v46). Vendor-name unification, retroactive. |
| הנחייה לחשב | RTL, structured guide — see content spec. |
| Cash Management Policy | **5 charts** (v46): existing 3 + currency-mix pie + per-account USD pie. |

---

### Executive Summary — month-end FX row (v46)

**Layout integrity (v48) — prevent overwrite/overlap.** Build the Executive Summary on a
**deterministic row/column grid** (the same discipline used for the Cash Management Policy
charts): reserve fixed, non-overlapping row bands for each block — FX row band, KPI tiles band,
then any chart/insight band — and compute each block's start row from the cumulative height of
the blocks above it, never with hard-coded offsets that can collide when the number of months
or KPIs changes. Place charts/images anchored to cells **below** the last written data row
(track `next_free_row`), so a wider month set or extra KPI never lands on top of an existing
block. One block writes, advances `next_free_row`, and the next block starts there.

Insert a dedicated FX block at the **top** of Executive Summary, above the KPI tiles, one
column per reporting month. For each non-USD currency held (ILS, EUR, GBP):

```
Label                         Cell content
----------------------------  ----------------------------------------------------------
Month-end FX (BOI)            [section header]
USD (BOI, per USD)            =1                          ← USD anchor = 1
ILS / USD                     ={ils_eom_rate}/{usd_anchor}   (BOI EOM ILS rate ÷ USD)
EUR / USD                     ={eur_eom_rate}/{usd_anchor}
GBP / USD                     ={gbp_eom_rate}/{usd_anchor}
```

The intent: every rate is expressed **relative to USD** so the reader sees how many units of
the foreign currency equal 1 USD at month-end, derived from Bank of Israel's published rates.
Because BOI quotes each currency against ILS, the USD-relative cross rate is the **non-USD
BOI rate divided by the USD BOI rate** for the same month-end date:

```python
# month-end BOI rates (ILS per 1 unit of currency) come from get_fx_and_source(eom, ccy)
usd_rate, _ = get_fx_and_source(eom_date, "USD")   # ILS per 1 USD
ils_anchor  = 1.0                                  # ILS is the BOI base
# Write as live formulas so the cross-rate recomputes if a rate cell is edited:
# cell for "ILS / USD"  → = <ILS_per_USD cell>           (i.e. usd_rate)
# cell for "EUR / USD"  → = <EUR ILS-rate cell> / <USD ILS-rate cell>
# cell for "GBP / USD"  → = <GBP ILS-rate cell> / <USD ILS-rate cell>
```

Write the raw BOI month-end rates (ILS per unit) into helper cells, then the USD-relative
cross rates as **formulas dividing the non-USD rate by the USD rate** — never as static
numbers — so the row is auditable and recomputes on edit. Label the source `BOI EOM` and
note the exact month-end date used.

**Global formula enforcement + FX-exposure KPI (v47):** see v47 Additions G and M. Every
derived KPI tile in Executive Summary (including the new **FX Exposure** KPI =
`non-USD balances ÷ total balances`) must be written as a `write_formula()` referencing
BALANCES / DETAILED SUMMARY — never a Python literal. FX Exposure is also reported in
`validation.json → fx_exposure`.

---

## Cash Management Policy — Tab Content Spec (v46)

The tab now holds **5 charts** (the existing 3 plus 2 new pies). All values are in USD and
sourced from BALANCES (latest reporting month) and DETAILED SUMMARY.

| # | Chart | Data | Source |
|---|---|---|---|
| 1 | (existing) | — | — |
| 2 | (existing) | — | — |
| 3 | (existing) | — | — |
| 4 | **Currency mix pie (₪ / $ / €)** (v46) | USD-equivalent total held in ILS vs USD vs EUR (and GBP if held) at latest month-end | BALANCES, grouped by each account's native currency |
| 5 | **USD balance per account pie** (v46) | USD-equivalent balance in each individual account (Leumi-ILS, Leumi-USD, HSBC, Mesh, Deposits, …) | BALANCES, one slice per account row |

```python
# Chart 4 — currency mix. Build a small helper table on the tab first (so the pie has a
# live range), grouped by native currency of each BALANCES account:
#   ILS total (USD-equiv) | USD total | EUR total | GBP total
# Each helper cell is a SUM/SUMIF formula over the BALANCES accounts of that currency,
# so the pie recomputes when balances change — do NOT hardcode the slice values.
cur_mix = wb.add_chart({"type": "pie"})
cur_mix.add_series({
    "name":       "Currency Mix (USD-equiv)",
    "categories": f"='Cash Management Policy'!$A${cm_first}:$A${cm_last}",
    "values":     f"='Cash Management Policy'!$B${cm_first}:$B${cm_last}",
    "data_labels": {"percentage": True, "category": True},
})

# Chart 5 — USD balance per account. Categories = account names from BALANCES,
# values = each account's latest-month USD balance (formula references to BALANCES cells).
acct_pie = wb.add_chart({"type": "pie"})
acct_pie.add_series({
    "name":       "USD Balance by Account",
    "categories": f"='Cash Management Policy'!$D${ap_first}:$D${ap_last}",
    "values":     f"='Cash Management Policy'!$E${ap_first}:$E${ap_last}",
    "data_labels": {"percentage": True, "category": True},
})
```

**Layout:** with 5 charts, lay them out on a grid rather than a single row to avoid overlap.
Use two rows of chart anchors (e.g. row-1 x_offsets `4 / 264 / 524`, row-2 x_offsets
`4 / 264`) with a dedicated label row above each chart. Update the "Charts overlap" fix in
Known Issues accordingly. The helper tables that feed charts 4 and 5 sit below the charts,
built from BALANCES formulas so every slice is live and auditable.

**Deterministic chart grid (v47 — supersedes the pixel x_offset approach):** see v47 Addition
L. Place charts at fixed `(row, col)` anchors instead of pixel x_offsets so layout is
reproducible and never overlaps:

```python
chart_positions = [(1, 4), (1, 10), (1, 16), (20, 4), (20, 10)]
for (r, c), chart in zip(chart_positions, charts):
    ws.insert_chart(r, c, chart, {"x_offset": 10, "y_offset": 10})
```

Each chart keeps a dedicated label row above it; helper tables are placed **below** the chart
grid; no overlap is permitted under any scenario. (The v46 x_offset note above is retained for
reference; the grid is the enforced method in v47.)

The inter-account netting (Addition D) applies here too: per-account balances reflect true
end-of-period positions, and the currency-mix pie is unaffected by transfers between
accounts because transfers net to zero across the set.

---

## הנחייה לחשב — Tab Content Spec (v45)

Set `ws.right_to_left()`. Col A width=24 (label, bold), Col B width=58 (detail, wrap).

Build from this `GUIDE_CONTENT` list at script build time:

```python
GUIDE_CONTENT = [
    (f"הנחייה לחשב — {COMPANY}  |  {date.today().strftime('%d/%m/%Y')}", "", "title"),
    ("", "", "blank"),
    ("📋  לשוניות הקובץ", "", "section"),
    ("TRANSACTIONS",
     "כל תנועה גולמית מהבנק לאחר עיבוד.\n"
     "עמודת Flag = ⚠️ Review: תנועות שסווגו Other OUT ומצריכות בדיקה.\n"
     "אזהרה: גיליון גנרטיבי — אל תערוך ישירות. שינויים יאבדו בריצה הבאה.", "row"),
    ("DETAILED SUMMARY",
     "סיכום Category → Sub-Category → Vendor, עמודה לכל חודש + YTD + Δ%.\n"
     "לחץ + כדי להרחיב לרמת ספק.\n"
     "כל התאים — נוסחאות SUMIFS חיות המפנות ל-TRANSACTIONS.", "row"),
    ("VENDOR_CLASSIF",
     "מפת סיווג ספקים שנוצרת אוטומטית.\n"
     "ערוך כאן Category/Sub_Category לכל ספק.\n"
     "בריצה הבאה — הסיווגים יוחלו רטרואקטיבית על כל התנועות.", "row"),
    ("BALANCES",
     "יתרות חשבון לפי חודש (בדולר).\n"
     "כולל חשבונות Mesh המחושבים אוטומטית מהתנועות.", "row"),
    ("Executive Summary",
     "גיליון מוכן להדפסה/PDF (A4 landscape).\n"
     "Export: File → Export → Create PDF/XPS.", "row"),
    ("", "", "blank"),
    ("🔄  תהליך עבודה חודשי", "", "section"),
    ("שלב 1 — הורד קבצים",
     "ייצא מ-Bank Leumi Online:\n"
     "• עו\"ש שח (ILS checking)\n"
     "• עו\"ש מט\"ח (USD checking)\n"
     "• פיקדונות אם יש\n"
     "• פירוט כרטיסי אשראי 5791 / 5890", "row"),
    ("שלב 2 — העלה ל-Claude",
     "גרור את הקבצים לחלון השיחה ב-Cowork.\n"
     "כתוב: \"הרץ CB Report\" — הסקיל יפעל אוטומטית.", "row"),
    ("שלב 3 — תקן סיווגים",
     "אל תערוך ישירות ב-TRANSACTIONS — שינויים יאבדו.\n"
     "הדרך: עדכן VENDOR_CLASSIF → שמור → הרץ מחדש.", "row"),
    ("שלב 4 — סיווג רטרואקטיבי",
     "לאחר עדכון VENDOR_CLASSIF ושמירת הקובץ:\n"
     "רשום ב-Claude: \"הרץ מחדש סיווג\"\n"
     "הסקריפט עובר ל-RECLASSIFY-ONLY MODE אוטומטית.\n"
     "כל התנועות מתעדכנות רטרואקטיבית.", "row"),
    ("", "", "blank"),
    ("✅  Checklist חודשי", "", "section"),
    ("יתרות בנק",       "האם COMPANY_ABALS עודכן לחודש החדש?", "row"),
    ("שע\"ח",           "האם שערי ה-BOI (currency-data skill) מכסים את כל ימי החודש?", "row"),
    ("פיקדונות (פק\"מ)","האם COMPANY_DEP_ILS/USD עודכנו עם יתרת הפיקדונות?", "row"),
    ("Mesh",            "האם חשבונות Mesh מופיעים ב-BALANCES עם יתרה סבירה?", "row"),
    ("Other OUT > 10%", "אם Other OUT > 10% מה-Opex — זהה וסווג את הספקים הבולטים", "row"),
    ("ספקים חדשים",     "ב-VC, חפש ספקים שלא היו בחודשים קודמים — וודא שמסווגים נכון", "row"),
    ("FX Difference",   "אם FX Difference > $50K — בדוק תנועות המרה ורכישות פיקדון.", "row"),
    ("Recon Status",    "ב-DETAILED SUMMARY שורת Reconciliation — כל חודש צריך להסתכם ב-OK", "row"),
    ("", "", "blank"),
    ("⚠️  טעויות נפוצות", "", "section"),
    ("עריכה ישירה ב-TRANSACTIONS",
     "אל תערוך TRANSACTIONS ישירות — הגיליון נדרס בריצה הבאה.\n"
     "הדרך: עדכן VENDOR_CLASSIF → שמור → הרץ מחדש.", "row"),
    ("יתרת פיקדון שגוייה",
     "COMPANY_DEP_ILS צריך לכלול כל פיקדונות פעילים (לא רק החדש).\n"
     "תוצאה: Total Cash מופיע נמוך מהאמיתי.", "row"),
    ("Recon Status = ERROR",
     "שינוי היתרה != Net Cash + FX.\n"
     "בדוק: האם יש תנועה חסרה? האם COMPANY_ABALS נכון?", "row"),
    ("SUMIFS מחזיר 0",
     "ייתכן שגוי כתיב בשם ספק/קטגוריה בין VENDOR_CLASSIF ל-TRANSACTIONS.\n"
     "בדוק רווחים, גרשיים ורישיות.", "row"),
    ("", "", "blank"),
    ("✆️  שאלות ותמיכה", "", "section"),
    ("עדכון סקיל",
     "הסקיל CB_REPORT_AS מעודכן ב-Cowork Plugin.\n"
     "לעדכון: Settings → Capabilities → Plugins → Update.", "row"),
    ("", "", "blank"),
    ("🔧  תהליך עבודה בפועל (MANDATORY)", "", "section"),
    ("STEP 1 — הורד קבצים",
     "הורד מהבנק את כל קבצי החודש (עו\"ש שח/מט\"ח, פיקדונות, כרטיסי אשראי).", "row"),
    ("STEP 2 — העלה ל-Claude", "גרור את הקבצים לחלון השיחה ב-Cowork.", "row"),
    ("STEP 3 — הרץ CB Report",
     "כתוב \"run CB report\".\n"
     "הסקיל יציג תחילה תקציר: קבצים שזוהו, חודש, יתרות פתיחה — ויבקש אישור.\n"
     "אשר (\"הרץ\") כדי שהפייפליין ירוץ. זו נקודת בקרה, לא תקיעה.", "row"),
    ("STEP 4 — עבור ל-VENDOR_CLASSIF",
     "תקן ספקים עם Confidence = LOW (Category / Sub_Category / Canonical Vendor).", "row"),
    ("STEP 5 — שמור את הקובץ", "שמור את ה-xlsx לאחר התיקונים.", "row"),
    ("STEP 6 — חזור ל-Claude",
     "רשום: \"run CB report reclassify\".", "row"),
    ("STEP 7 — המערכת תבצע",
     "reclassification מלא + עדכון רטרואקטיבי + חישוב מחדש של כל הנוסחאות.", "row"),
    ("STEP 8 — בדוק Reconciliation",
     "ב-DETAILED SUMMARY ודא ששורת Reconciliation = OK לכל חודש.", "row"),
    ("STEP 9 — ייצא PDF",
     "ייצא את Executive Summary ל-PDF (File → Export → Create PDF/XPS).", "row"),
    ("", "", "blank"),
    ("📑  כללי שימוש בלשוניות (CRITICAL)", "", "section"),
    ("VENDOR_CLASSIF",
     "ערוך רק: Category, Sub_Category, Canonical Vendor.\n"
     "אל תיצור שמות ספק כפולים; אל תערוך שדות מנורמלים.\n"
     "השתמש תמיד בשם canonical מאוחד.", "row"),
    ("REFERENCE", "קריאה בלבד — אין לבצע שינויים ידניים.", "row"),
    ("", "", "blank"),
    ("♻️  הרצת Reclassify", "", "section"),
    ("לאחר עדכון VENDOR_CLASSIF",
     "1. שמור את הקובץ.\n"
     "2. עבור ל-Claude.\n"
     "3. רשום: \"run CB report reclassify\".\n"
     "המערכת תבצע: טעינת TRANSACTIONS → הפעלת VENDOR_CLASSIF → עדכון רטרואקטיבי מלא.", "row"),
    ("", "", "blank"),
    ("🧠  זיכרון ספקים — vendor_memory.json", "", "section"),
    ("מה זה",
     "קובץ JSON שנוצר אוטומטית ליד החוברת בכל הרצה.\n"
     "שומר את הסיווגים שנלמדו (ספק → קטגוריה / תת-קטגוריה / שם מאוחד)\n"
     "כדי שלא תצטרך לסווג מחדש בכל חודש.", "row"),
    ("חשוב — חודש הבא",
     "העלה את vendor_memory.json מהחודש הקודם יחד עם קבצי הבנק.\n"
     "בלעדיו — הזיכרון הנלמד אובד והסיווג מתחיל מאפס.", "row"),
    ("הפרדה בין חברות",
     "הקובץ מתויג לפי שם החברה. אל תעלה vendor_memory של חברה אחת\n"
     "לחברה אחרת — זה יגרום לסיווגים שגויים. קובץ נפרד לכל לקוח.", "row"),
    ("", "", "blank"),
    ("🔁  מחזור חודשי מתמשך (update — בלי לדרוס נתונים)", "", "section"),
    ("מתי", "כשכבר קיימת חוברת מחודשים קודמים ואתה מוסיף חודש חדש.", "row"),
    ("שלב 1 — העלאה",
     "העלה את קבצי הבנק של החודש החדש + vendor_memory.json מהחודש הקודם.", "row"),
    ("שלב 2 — הרצה",
     "כתוב \"run CB report update\".\n"
     "הסקיל מוסיף עמודת חודש חדשה לצד הקיימות — לא דורס נתונים קודמים.", "row"),
    ("שלב 3 — תיקון",
     "תקן שורות Confidence = LOW ב-VENDOR_CLASSIF.", "row"),
    ("שלב 4 — סיווג רטרואקטיבי",
     "שמור → \"run CB report reclassify\". הסיווגים מוחלים על כל החודשים.", "row"),
    ("שלב 5 — בדיקת סגירה",
     "ודא Reconciliation = OK לכל חודש ו-overall_status = PASS.", "row"),
    ("", "", "blank"),
    ("📁  הוספת כמה חודשים יחד (גרירת תיקיות)", "", "section"),
    ("איך מסדרים",
     "צור תיקייה לכל חודש בשם בפורמט YYYY-MM (למשל 2026-04, 2026-05),\n"
     "ושים בתוך כל תיקייה את כל קבצי אותו חודש (עו\\\"ש, פיקדונות, כרטיסים).", "row"),
    ("איך גוררים",
     "גרור את כל התיקיות יחד בהרצה אחת וכתוב \"run CB report update\".\n"
     "הסקיל מוסיף עמודה אחת לכל תיקייה, לפי סדר החודשים.", "row"),
    ("למה אין בלבול",
     "שם התיקייה הוא שקובע את החודש — לא תוכן הקובץ.\n"
     "אם תנועה מתוארכת לחודש אחר מהתיקייה — היא תסומן MONTH_MISMATCH\n"
     "לבדיקה, אבל לא תזוז לעמודה אחרת מעצמה.", "row"),
    ("בדיקה",
     "בסיום ודא: עמודה לכל חודש, Reconciliation = OK לכל חודש,\n"
     "ואפס שורות MONTH_MISMATCH (או שתיקנת אותן בקובץ המקור).", "row"),
    ("", "", "blank"),
    ("⚠️  בנק מול כרטיס", "", "section"),
    ("דגל TAXONOMY",
     "אם שורה מסומנת TAXONOMY — תת-הקטגוריה לא ברשימה המותרת ל-Category שלה\n"
     "(למשל 'Cloud Infra' במקום 'Cloud Infrastructure'). תקן ב-VENDOR_CLASSIF\n"
     "לערך תקני מתוך REFERENCE.", "row"),
    ("זיכוי בכרטיס סווג כהחזר ספק",
     "בכרטיסי אשראי (Mesh / Brex / PayPal) זיכוי = החזר ספק, לא תשלום לקוח.\n"
     "זו התנהגות מכוונת. אם זה באמת תשלום לקוח — תקן ב-VENDOR_CLASSIF.", "row"),
]
```

Write loop:
```python
wg = wb.add_worksheet("הנחייה לחשב")
wg.right_to_left()
wg.set_column(0, 0, 24)
wg.set_column(1, 1, 58)
fmt_title   = wb.add_format({"bold": True, "font_size": 13, "font_color": "#1e3a5f"})
fmt_section = wb.add_format({"bold": True, "font_size": 11, "fg_color": "#dce6f1"})
fmt_key     = wb.add_format({"bold": True, "text_wrap": True, "valign": "top"})
fmt_val     = wb.add_format({"text_wrap": True, "valign": "top"})
r = 0
for key, val, rtype in GUIDE_CONTENT:
    if rtype == "title":
        wg.merge_range(r, 0, r, 1, key, fmt_title); wg.set_row(r, 20)
    elif rtype == "section":
        wg.merge_range(r, 0, r, 1, key, fmt_section); wg.set_row(r, 18)
    elif rtype == "row":
        wg.write(r, 0, key, fmt_key)
        wg.write(r, 1, val, fmt_val)
        lines = val.count("\n") + 1
        wg.set_row(r, max(15, lines * 14))
    # blank: skip
    r += 1
```

---

## Step 6 — Reconciliation (circle-level, v46)

The file must **close at every level** ("סגירה ברמת מעגלים") — each circle reconciles to the
one above it, all the way from a single transaction up to the period balance. Every check is a
live Excel formula so it re-verifies on edit.

**Circle 1 — Transaction → Category.** For each month and category, the category cell equals
the SUMIFS over its transactions (it already is that SUMIFS). Cross-check: the sum of all
category cells in a section equals an independent SUMIFS over the section's category set.

**Circle 2 — Category → Section totals.** `TOTAL OPERATIONAL IN` = Σ operational-in
categories; `TOTAL OPERATIONAL OUT` = Σ operational-out categories; `OPERATING CASH FLOW` =
IN − OUT. Each total is a formula summing the cells above, and a guard formula asserts it
equals the matching SUMIFS.

**Circle 3 — Sections → NET BURN.** `NET BURN = OCF + Σ NON-OPERATIONAL` (Investment, Tax).
Internal transfers excluded via `$R:$R,"<>Y"`.

**Circle 4 — NET BURN → Balance.** `FX Difference = Closing − Opening − NET BURN`, and
`Reconciliation = IF(ABS(Closing − Opening − NET BURN − FX) < 1, "OK", "ERROR …")`. With FX as
the plug this is identically OK, which **proves** the balance circle ties to the cash-flow
circle.

**Circle 5 — Account → BALANCES TOTAL.** BALANCES TOTAL = `SUM(account rows)`; each derived
account balance ties to its transaction-cumulative SUMIFS, each statement balance carries a
Source Note. A guard formula compares the BALANCES TOTAL to the DETAILED SUMMARY Closing
Balance — must match to the cent.

Flag orange in Excel if |FX Diff| > $50K. Flag red in the chat status line if
|FX Diff / Closing| > 15%. The validation step (Step 8) reports each circle's status; the run
is "fully closed" only when all five circles read OK for every month.

---

## Step 7 — HTML CEO Dashboard

Self-contained. Chart.js 4.4 CDN. Dark navy #0f1923.
4 KPI tiles → bar chart (Cash In/Out by month) + line chart (balance) → top-12 vendor table.

**Insights block (v47):** see v47 Addition K. Add an auto-generated CFO insights section to
the HTML — largest expense category, largest vendor, and FX impact (% of closing balance).

---

## Step 8 — Validation

After `wb.close()`:
- Print: transactions, unclassified %, formula-literal violations count, recon status
- **v46 checks:**
  - `fx_coverage` — count of non-USD rows missing an FX rate/source (must be 0); count of
    rows relying on `hardcoded`/`estimated*` fallback.
  - `confidence_distribution` — HIGH/MED/LOW counts and percentages.
  - `circle_status` — OK/ERROR for each of the five reconciliation circles, per month.
  - `internal_transfers` — number of netted pairs and total netted USD.
  - `vendor_unification` — canonical vendors, folded aliases, rows retroactively relabeled.
- Save `_validation.json` with audit blocks (incl. `v46_audit`)
- Present 3-line status in chat (include LOW-confidence % and whether all circles closed)
- **v47 checks (see v47 Additions G/H/I/P):**
  - `formula_integrity_global` — FAIL if any derived numeric cell (Executive Summary, VC,
    Cash Management Policy helpers, FX row, DETAILED SUMMARY, derived BALANCES) was written as
    a literal instead of a formula.
  - **Hard blocking:** `overall_status = FAIL` if `formula_integrity_global != PASS` OR any
    month's `reconciliation != OK`. Status `WARN` when `low_confidence_pct > 20%` or
    `fx_fallback_pct > 5%`. Otherwise `PASS`.
  - `balance_delta` — `|Σ BALANCES − Σ Amt USD|`; if `> 1` add `BALANCE_MISMATCH`.
  - `fx_exposure` — non-USD balances ÷ total balances.
  - `fx_quality_summary`, `vendor_fragmentation_score`, and the multi-layer confidence
    distribution (CLASS / FX / PARSER / FINAL).

### validation.json — v47 structure (additive)

```json
{
  "overall_status": "PASS|WARN|FAIL",
  "formula_integrity_global": "PASS|FAIL",
  "reconciliation": "OK|ERROR",
  "low_confidence_pct": 0.0,
  "fx_fallback_pct": 0.0,
  "balance_delta": 0.0,
  "fx_exposure": 0.0,
  "fx_quality_summary": {"HIGH": 0, "MED": 0, "LOW": 0, "fallback_rows": 0},
  "vendor_fragmentation_score": 0,
  "v47_audit": {
    "internal_pairs": [],
    "final_confidence_distribution": {"HIGH": 0, "MED": 0, "LOW": 0},
    "error_types": {"FX_MISSING": 0, "LOW_CONF": 0, "PARSER_FAIL": 0, "BALANCE_MISMATCH": 0}
  }
}
```

All existing `v44_audit` / `v46_audit` blocks are preserved; v47 keys are added alongside them.

---

## Known Issues & Fixes

| Issue | Fix |
|---|---|
| DETAILED SUMMARY has static Python values | All cells use `write_formula()` with SUMIFS strings |
| Mesh missing from BALANCES | Step 4 computes running Mesh balance from transactions |
| No opening balance in DETAILED SUMMARY | BALANCE section: Opening/NCF/FX plug/Closing/Recon |
| No drill-down in DETAILED SUMMARY | `set_row(..., {"level": N})` + `outline_settings()` |
| `write_dynamic_array_formula` crashes | Use `write_formula()` with static SUMIFS strings |
| Hebrew `"` in vendor names | `_fesc()` all formula-embedded strings |
| Charts overlap in Cash Management Policy | 5 charts on a 2-row grid; dedicated label row above each; row-1 x_offset 4/264/524, row-2 x_offset 4/264 |
| Executive Summary wrong tab position | Must be first `add_worksheet()` call |
| `runway_str` NameError | KPI pre-computation before `Workbook(...)` |
| BOI API unreachable | Falls back to embedded rates silently |
| One bad bank file crashes full run | Per-file try/except |
| Prior run overwritten | Auto-version `_vN` |
| Non-USD row converted at wrong rate | v46: `to_usd` uses BOI rate of the transaction date; FX-coverage audit asserts no row lacks a rate |
| Interest income sat in NON-OPERATIONAL | v46: Interest Income moved into OPERATIONAL CASH IN; only Investment stays non-op |
| Inter-account transfer double-counted | v46 Addition D: tag `Internal=Y`, exclude with `$R:$R,"<>Y"` in every SUMIFS |
| Same vendor spelled many ways | v46 Addition E: canonical_vendor() + VENDOR_CLASSIF Aliases; Vendor_Raw kept for audit |
| Manual VENDOR_CLASSIF edit not authoritative | v46: VENDOR_CLASSIF is TIER1; applied retroactively to all rows on next run |
| BALANCES values not auditable to source | v46: formula where derived; value + Source Note (filename/page) where from PDF/HTML |
| Could not see classifier certainty | v46: Confidence column (HIGH/MED/LOW), LOW default when unsure + Review flag |
| Derived cells written as static values | v47: global formula enforcement; `formula_integrity_global` FAILs any literal derived cell (Exec Summary / VC / Cash Policy helpers / FX row) |
| Charts still overlapping on some screens | v47: deterministic chart grid `[(1,4),(1,10),(1,16),(20,4),(20,10)]`, label row above each, helper tables below grid |
| Same vendor fragmented across spellings | v47: `normalize_vendor()` before classification + VENDOR_CLASSIF `Aliases` column; `vendor_fragmentation_score` reported |
| Vendor fixes lost between clients/runs | v47: persistent `vendor_memory.json` (load→apply→save); precedence VENDOR_CLASSIF TIER1 > vendor_memory > heuristic |
| Bad/unknown bank layout silently misparsed | v47: header-based `detect_parser()` + generic fallback flagged LOW; `parser_confidence` logged |
| Confidence reflected only classification | v47: multi-layer CLASS/FX/PARSER → FINAL_CONFIDENCE (internal + validation.json; no new visible columns) |
| Run shipped despite broken formulas/recon | v47: hard blocking validation — `overall_status=FAIL` if formula_integrity≠PASS or reconciliation≠OK |
| Balances and transactions silently diverged | v47: balance cross-check `|Σ BALANCES − Σ Amt USD|>1` → `BALANCE_MISMATCH` + `balance_delta` |

---

## Step 9b — PDF Statement Balance Extraction

Auto-runs when `.pdf` files found in FOLDER/UPLOADS.
Extracts Opening/Closing balances. Fills gaps in COMPANY_ABALS. Adds PDF BALANCE CHECK tab.

---

## Step 10 — Enhanced Features

### VENDOR_CLASSIF Learning Loop
`_reclassify_from_workbook()` reads prior `CB_Report_*.xlsx` VENDOR_CLASSIF → applies
vendor overrides retroactively on re-run.

### TRANSACTIONS — Flag column
`Review` on every `Other OUT / Uncategorized`. Auto-filter for triage.

### Multi-currency
`get_fx(date, ccy)` supports USD, EUR, GBP. BOI שע"י 5-strategy pipeline.

---

# v44 ADDITIONS

## Addition A — Validation Pass (report-only, never rewrites output)

### A1 — Formula-integrity check
Track every cell written to DETAILED SUMMARY as `formula` or `literal`.
Report literal cells in validation.json. Surface count in chat status line.

```python
_written_as = {}   # {(row,col): "formula"/"literal"}
# After ws.write_formula(...): _written_as[(row,col)] = "formula"
# After ws.write(..., float): _written_as[(row,col)] = "literal"

def audit_formulas(written_as):
    literals = [k for k,v in written_as.items() if v == "literal"]
    return {"check": "formulas_only", "literal_cells": len(literals),
            "status": "pass" if not literals else "warn"}
```

### A2 — Case-variant duplicate check
Same category/sub/vendor in different casings → SUMIFS double-count risk.

### A3 — Currency cross-check
Sum op-out by source currency vs TOTAL OPERATIONAL OUT. Report gap > $10.

---

## Addition B — Classification Accuracy

**B1** Internal-transfer by sender — match SENDER in Hebrew/English wire against
`COMPANY_TRANSFER_KEYWORDS`.

**B2** Real payee key — use `desc2` wire payee as classification key.

**B3** Hebrew→English vendor names — transliterate + flag unknown names.

**B4** Customer-name breakdown — extract payer per wire, not "Customer Payment".

**B5** Best-Guess audit log — flag heuristic rows `Review/Best Guess` + log in
validation.json under `v44_audit.best_guess_log`.

**B6** Accurate `FX_Source` per row — write true label from `get_fx_and_source()`.

---

## Addition C — Extended Input Detection

SVB / Comerica / Bill.com / Brex / PayPal / Chase: detect by filename+header → generic
best-effort parser → flag ALL rows `Review (generic parser)`. Dedicated parsers locked
until sample files provided.

---

# v46 ADDITIONS

## Addition D — Inter-Account Transfer Detection & Netting

A move of the company's own money between two of its own accounts is **not** cash in or out
of the business and must be netted out of every computational tab (DETAILED SUMMARY, VC,
Cash Management Policy charts, KPIs). It still appears as a row in TRANSACTIONS for the audit
trail, but is **excluded from all aggregations**.

### Detection

Mark a transaction `Internal = "Y"` (col R) when it matches any of:

1. **Account-pair match** — the description/`desc2` names another account that belongs to
   this company (own IBAN/account number, or a `COMPANY_TRANSFER_KEYWORDS` hit on the
   company's own name as sender or receiver).
2. **Mirror pair** — an outflow in one account and an inflow in another company account, same
   (or near-same after FX conversion to USD) amount, within a small date window (±3 business
   days). Match them and tag both legs `Internal = "Y"` **only if neither leg's `Desc2` names
   an external counterparty** (see the external-payee guard below).
3. **Known internal categories** — `Internal/Deposit Placement`, `Internal/Deposit
   Redemption`, `Internal/Mesh Funding`, FX conversions between the company's own ILS and USD
   accounts.

**External-payee guard (v52 — fixes false netting):** A short bank action type such as
"העברה דיגיטל" / "העברה" / "זיכוי" must NOT be treated as internal on its own. The decision
is driven by `Desc2` (the real counterparty from `תיאור מורחב`). If `Desc2` names a party
that is NOT one of the company's own accounts/keywords — e.g. "העברה אל: <ספק>",
"תשלום עבור: רשות המיסים / ביטוח לאומי", a landlord, a vendor — the row is an EXTERNAL payment
and is excluded from mirror-pair netting even if its amount coincidentally mirrors an inflow.
Mirror-pair netting may only fire when both legs look internal (no external `Desc2`, and at
least one leg carries an own-account or `COMPANY_TRANSFER_KEYWORDS` signal). This prevents
real supplier/rent/tax outflows from being silently netted to zero, which previously
understated operational burn.

```python
def _is_external_payee(t, company_accounts, transfer_keywords):
    """True when Desc2 names a party that is NOT the company itself."""
    d2 = str(t.get("desc2", "")).strip().lower()
    if not d2:
        return False  # no counterparty info -> let other rules decide
    own = _names_own_account(d2, company_accounts) or any(k in d2 for k in transfer_keywords)
    return not own  # named counterparty, and it isn't us -> external

def detect_internal(txns, company_accounts, transfer_keywords):
    # 1) keyword / own-account hits — match on Desc2 (real counterparty) first, then desc
    for t in txns:
        blob = f"{t.get('desc2','')} {t['desc']}".lower()
        if any(k in blob for k in transfer_keywords) or _names_own_account(blob, company_accounts):
            t["internal"] = "Y"; t["category"] = "Internal"
    # 2) mirror-pair matching — skip any leg that names an EXTERNAL payee in Desc2
    outs = [t for t in txns if t["amt_usd"] < 0 and t["internal"] != "Y"
            and not _is_external_payee(t, company_accounts, transfer_keywords)]
    ins  = [t for t in txns if t["amt_usd"] > 0 and t["internal"] != "Y"
            and not _is_external_payee(t, company_accounts, transfer_keywords)]
    for o in outs:
        for i in ins:
            if abs(abs(o["amt_usd"]) - i["amt_usd"]) <= max(1.0, 0.005*i["amt_usd"]) \
               and _within_days(o["date"], i["date"], 3) \
               and o["account"] != i["account"]:
                o["internal"] = i["internal"] = "Y"
                o["category"] = i["category"] = "Internal"
                break
    return txns
```

### Netting in formulas

Every SUMIFS in DETAILED SUMMARY / VC / KPIs adds one criterion so internal rows never count:

```python
# append to EVERY aggregation SUMIFS:
'...,TRANSACTIONS!$R:$R,"<>Y"'
```

Because internal legs cancel (one negative, one positive) they would net to ~0 anyway, but a
residual FX delta between the two legs would otherwise leak into operational totals. Excluding
them explicitly keeps Operating Cash Flow clean; the genuine FX revaluation still lands in the
FX Difference plug, where it belongs.

### Audit

Log every netted pair to `validation.json → v46_audit.internal_transfers` with both row
indices, accounts, and USD amounts. Surface the count and total netted USD in the chat status
line so the controller can sanity-check it.

---

## Addition E — VENDOR_CLASSIF as TIER1 (Authoritative) + Vendor-Name Unification

VENDOR_CLASSIF is promoted from a "learning sheet" to the **TIER1 source of truth**. When it
is present, its classifications **override** every heuristic, and a manual edit there is
applied **retroactively to all rows in TRANSACTIONS** — past and future — on the next run.

### Classification precedence (v46)

```
TIER1  VENDOR_CLASSIF exact/normalized match   → authoritative, Confidence = HIGH
TIER2  deterministic rules (payroll, tax, VC)  → HIGH
TIER3  semantic multi-language inference        → MED
TIER4  fallback / generic / unknown             → LOW + Review
```

A VENDOR_CLASSIF hit always wins, even over a deterministic rule, because it represents a
human decision.

### Vendor-name unification (normalization)

Many statements spell the same vendor differently ("AWS", "Amazon Web Services", "AMAZON WEB
SERVICES EMEA", "אמזון"). Unify them to one **canonical name** before aggregating:

```python
def canonical_vendor(raw, alias_map):
    key = _normalize(raw)          # lowercase, strip punctuation, collapse spaces,
                                   # transliterate Hebrew→Latin, drop corp suffixes
                                   # (בע"מ / ltd / inc / gmbh / llc)
    return alias_map.get(key, raw_titlecased)   # alias_map persisted in VENDOR_CLASSIF
```

- Write the **canonical** name to `Vendor` (col N — the SUMIFS key) and keep the **original**
  text in `Vendor_Raw` (col Q) for audit.
- VENDOR_CLASSIF gains an `Aliases` column: a controller can list raw spellings that should
  all fold into one canonical vendor. The next run reads it and applies the merge everywhere.
- Fuzzy pre-merge: when two raw names normalize to a high-similarity key (e.g. token-set
  ratio ≥ 0.9) and neither is yet in VENDOR_CLASSIF, propose the merge — fold them under one
  canonical name and flag the proposed alias for the controller to confirm in VENDOR_CLASSIF.

### Retroactive application

On every run (including `reclassify` mode):

1. Read VENDOR_CLASSIF: `{canonical_vendor: (Category, Sub_Category)}` and the `Aliases` map.
2. Rebuild the alias→canonical map; re-derive `Vendor` for **all** transactions from
   `Vendor_Raw` so a newly-added alias retroactively re-labels old rows.
3. Apply TIER1 Category/Sub to every matching row, set Confidence = HIGH, clear its Review
   flag (unless still genuinely ambiguous).
4. Rewrite TRANSACTIONS fully — never edit in place — so the SUMIFS formulas downstream pick
   up the corrected canonical names.

The existing `_reclassify_from_workbook()` is extended to read the new `Aliases` column and to
treat VENDOR_CLASSIF as TIER1 rather than a soft override. The result: **one manual fix in
VENDOR_CLASSIF reclassifies that vendor across the entire history on the next run.**

### Audit

`validation.json → v46_audit.vendor_unification` lists each canonical vendor, the raw spellings
folded into it, and how many rows were retroactively relabeled.

---

## Policy notes

The previous conflict ("STRICT can conflict with org pre-approval; resolve at policy level")
is now resolved **in the skill** (v48): the Step −1 pre-flight gate in Execution Mode satisfies
the org pre-approval policy without weakening STRICT execution after approval. The gate adds no
computation and does not alter any formula, column, or reconciliation circle.

---


## Addition T — Month-End Balance Source Precedence (v50)

*(from `CB_REPORT_AS4_balance_source_patch.md` — folded in verbatim)*

**Why:** A run took a Leumi transaction-export header balance ("יתרה: …", printed 01/06, marked
*"פירוט הפעולות אינו סופי"*) as the May month-end closing (₪79,532.33), when the certified balance
confirmation (אישור יתרות, as of 31/05) said ₪162,658.33. The export header is a snapshot at the
print date — not necessarily the reporting month-end. This patch makes the certified confirmation
authoritative and adds a blocking cross-check.

For every account, the month-end **closing balance** written to BALANCES is chosen by this strict
precedence (highest wins):

1. **Official balance confirmation** (`אישור יתרות`) whose "הנדון: אישור יתרות ל-DD/MM/YY" date
   equals the reporting month-end — **authoritative**. It also carries deposits (פיקדונות) and
   foreign-currency (מטבע חוץ / פמ"ח) balances in one certified document; use it as the primary
   BALANCES feed whenever present for the month.
2. **Last itemized running balance** — the balance on the **final dated transaction row** of the
   account's statement for the month (layout-independent; see savings running-balance rule).
3. **Transaction-export header** figure (`יתרה: …`) — **lowest priority**. It is the balance at the
   export/print date (`תאריך שמירה/הדפסה`), frequently *after* month-end and flagged
   "פירוט הפעולות להיום אינו סופי". Never let it override (1) or (2).

```python
def month_end_balance(acct, mo, confirmation=None, last_itemized=None, export_header=None):
    for src, val in (("balance_confirmation", confirmation),
                     ("last_itemized_running", last_itemized),
                     ("export_header", export_header)):
        if val is not None:
            return val, src
    return None, "none"
```

### Cross-check (BLOCKING)

After resolving each account's closing, compare all three candidate values:

```python
cands = {k: v for k, v in {"confirmation": confirmation,
                           "last_itemized": last_itemized,
                           "header": export_header}.items() if v is not None}
spread = (max(cands.values()) - min(cands.values())) if len(cands) > 1 else 0
if spread > 1:                      # native-currency units
    flag("BALANCE_SOURCE_MISMATCH", acct, mo, cands)   # -> validation.json
    # keep the precedence winner (confirmation > last_itemized > header)
```

- Log every mismatch to `validation.json → balance_source_mismatches`
  (`{account, month, confirmation, last_itemized, header, chosen, chosen_source}`).
- A `BALANCE_SOURCE_MISMATCH` does **not** auto-fail the run, but it is surfaced in the chat status
  line and the BALANCES `Source Note` records which source was used
  (e.g. `אישור יתרות 31/05` vs `export header (superseded)`).

### Guard — distrust a stale export header

If the export's print date (`תאריך שמירה/הדפסה`) is **later than** the reporting month-end, the
header "יתרה" may include post-month-end activity → demote it below the last itemized running
balance automatically (already lowest priority; this guard also flags it `HEADER_AFTER_MONTH_END`).

### Preflight surfacing (Step −1)

In the read-only pre-flight summary, when both an `אישור יתרות` PDF and a transaction export exist
for the same account/month, print **both** candidate balances side by side, e.g.:

```
Leumi-ILS 2026-05  | confirmation 162,658.33 | export header 79,532.33  ⚠ mismatch -> using confirmation
```

---

## Addition T-U — Deposit (פיקדון / פק"מ) valuation basis = PRINCIPAL (v50)

For Israeli time deposits, the balance-confirmation (`אישור יתרות`) shows **two** money columns:

| Column | Meaning |
|---|---|
| `סכום פקדון` | **Principal** — the amount originally deposited (the cash that returns at maturity). |
| `שווי בש"ח` | **Value** — principal **plus accrued-but-unpaid interest** to the confirmation date. |

**Rule:** the BALANCES figure for every deposit = the **principal (`סכום פקדון` / קרן)**, NOT the
`שווי בש"ח` value, and NOT the snapshot/`שערוך` figure from the `פיקדונות` export (which is a
value-basis number). Accrued-but-unpaid interest is **excluded** from the cash balance.

```python
# deposit closing balance:
deposit_balance = principal_amount            # 'סכום פקדון' / קרן  — NOT 'שווי בש"ח', NOT 'שערוך'
```

Rationale: accrued interest that has not been paid into a checking account is not realized cash;
counting it would overstate the balance and leak unrealized yield into the cash position.

**Interest recognition (unchanged, complementary):** realized deposit interest is recognized only
when **paid** — i.e. at redemption, `Interest = redeemed amount − principal` routed to
`Interest Income` (operational); the placement/redemption legs stay `Internal` and net out.

**Pre-flight note:** when a deposit appears in both the confirmation and a `פיקדונות` snapshot,
print the principal and the value side by side and confirm the **principal** is the one used,
e.g. `Deposits-ILS 2026-04 | principal 6,648,255.64 | value 6,675,678.95 -> using principal`.

---

## Addition T-2 — Deposit balances: PRINCIPAL + month-end confirmation only (v53)

**Why:** a run took deposit balances from `פירוט פיקדונות ש_ח.xlsx` dated **07/06**
(7 days after the 31/05 month-end). Prime-linked (פריים) deposits accrue interest
**daily**, so the later file was 43₪ and 343₪ too high. Deposits were also taken at the
**revalued** figure and, for FX deposits, the revalued ILS was divided by the EOM rate —
double-applying FX (USD deposits read $899,649 instead of the correct $850,000 principal).

### Rule 1 — value at PRINCIPAL, never revalued
Deposits (פיקדונות / פק"מ, incl. pledged/משועבד, time and prime deposits) are valued at
**principal** (יתרת קרן / סכום קרן / כמות במקור). NEVER use the revalued column
(סכום משוערך / "יתרה כוללת מסופקת בש"ח").

### Rule 2 — source = the month-end balance confirmation, dated == month-end
Highest wins:
1. `אישור יתרות` whose "נכון ל-DD/MM/YY" == reporting month-end → AUTHORITATIVE. Read the
   **principal** column.
2. A deposit statement dated exactly on the month-end.

**NEVER** use a `פירוט פיקדונות` / deposit report whose print / "נכון ל" date is **after**
the reporting month-end (daily accrual overstates it).

### Rule 3 — currency
- **FX deposit (מט"ח / USD / EUR):** value = **native-currency principal**
  (e.g. 100K×3 + 150K×2 + 250K = $850,000). Do **not** take revalued ILS ÷ EOM rate.
- **ILS deposit:** value(USD) = ILS principal ÷ EOM BOI USD rate
  (`get_fx(last_trading_day, "USD")` — same source as transactions, per Addition U-1).

### Rule 4 — blocking guards
```python
if deposit_source_date > reporting_month_end:
    flag("DEPOSIT_SOURCE_DATE_AFTER_MONTH_END", deposit_id, deposit_source_date)
    # discard; fall back to the month-end אישור יתרות principal
if deposit_value_used == revalued_value:
    flag("DEPOSIT_USED_REVALUED_NOT_PRINCIPAL", deposit_id)   # must be principal
```
```json
"deposit_source_check": {
  "all_principal": true,
  "source": "אישור יתרות <DD/MM/YY == month-end>",
  "no_post_month_end_files": true,
  "status": "PASS"
}
```

### Companion (same principle — money-market/checking)
A money-market / checking month-end balance comes from the **statement ENDING BALANCE**
(e.g. HSBC eStatement "ENDING BALANCE 05/29/26"), **not** the transaction-export
"closing ledger balance" (observed: 976,211 export vs 1,048,243 statement, +$72K).
This extends Addition T's precedence: statement ENDING balance > export closing-ledger.

---


### User-provided rates Excel — runtime upload (ported v51)

The controller MAY upload a rates workbook **together with the bank files** — the template
`boi_rates_template.xlsx`; nothing has to be supplied ahead of time. When present it is the
highest-priority FX source (precedence 0) and fills any dates before the embedded `currency-data`
start (down to the required period start 2025-12-31), which is exactly what keeps the U-10 gate
green and prevents any `BOI_fallback` row.

Layout: a sheet named like `BOI`/`Rates`/`שער` (else the first sheet), header
`Date | USD | EUR | GBP` (Hebrew `תאריך` accepted), `Date` as `YYYY-MM-DD`/`DD/MM/YYYY` or a real
Excel date, values = ILS per 1 unit.

```python
import fx_excel as fxx                              # shipped in references/ (ported v51)
rates_xlsx = fxx.find_rates_excel(UPLOAD_PATHS)      # filename match: boi/rate/fx/שער/מטבע
if rates_xlsx:
    rates, fx_meta = fxx.load_fx_from_excel(rates_xlsx)
    fxx.merge_into_fx_live(_FX_LIVE, rates, override=True)   # uploaded file wins on conflicts
    # rows priced from these dates carry FX_Source = fx_meta["source"]  (e.g. "BOI_xlsx (…)")
```

Unit test: `references/test_fx_excel.py` (load + override merge + month-end + filename detection +
Hebrew/DD-MM-YYYY) — passes in the plugin.


---

## Changelog

### v53 — deposits at PRINCIPAL + month-end confirmation only (additive)
See Addition T-2. Deposits valued at principal (never revalued); source must be the month-end אישור יתרות; blocking DEPOSIT_SOURCE_DATE_AFTER_MONTH_END / DEPOSIT_USED_REVALUED_NOT_PRINCIPAL guards + validation.json deposit_source_check. Companion: money-market/checking uses statement ENDING balance over export closing-ledger.

### v52.1 — VENDOR_CLASSIF income-row guard (additive)
See PATCH P-1. Income descriptions (ריבית etc.) are protected from TIER1 vendor override; positive-amount rows from expense vendors are skipped; blocking assert on any ריבית row classified as expense; validation.json interest_income_audit.

### v51 (2026-06-30) — FX single-source + tab manifest (additive)
See Addition U above. EOM rate sourced only from get_fx(last_trading_day,'USD') with a blocking assert before Excel write; required FX coverage start set to 2025-12-31 (period start); coverage is dynamic (embedded currency-data + uploaded boi_rates_template.xlsx); any date before the effective coverage start -> BOI_fallback WARN, never a silent constant; MANDATORY SKILL.md read; REQUIRED_TABS manifest + blocking missing-tab RuntimeError before wb.close(); validation.json -> tab_manifest FAILs on any missing tab.

### v50 (2026-06-30) — month-end balance source precedence (additive)
See Addition T above. month-end closing = balance confirmation (אישור יתרות) > last itemized running balance > transaction-export header; blocking BALANCE_SOURCE_MISMATCH cross-check + validation.json -> balance_source_mismatches; stale-header guard (HEADER_AFTER_MONTH_END); both candidates shown in pre-flight.


### v48 (2026-06-22) — CB_REPORT_AS4: three additive, harness-validated changes
Forked from `CB_REPORT_AS` v47 as a new skill `CB_REPORT_AS4`; all v47 logic, formulas and
column indexes (A–R) preserved unchanged. Each change was validated against a regression
harness (tagged fixture + LibreOffice recalc): the 5 reconciliation circles stay OK,
`formula_integrity_global` stays PASS, and classification accuracy stays 100% — i.e. the
baseline did not move.
1. **vendor_memory is company-scoped** (Addition O) — the JSON is keyed by company at the top
   level; only the current company's block is loaded/merged, so a mapping learned for one
   client can never mislabel another. TIER1 precedence preserved.
2. **Direction-aware TIER3 classification** (Step 2) — an unmatched credit is a vendor refund
   on a card tab (Mesh/Brex/PayPal) but a customer payment on a bank tab; fires only as a
   fallback, so TIER1/keyword rules always win. All such rows are Confidence = LOW.
3. **STRICT-with-pre-approval gate** (Execution Mode) — a single read-only Step −1 pre-flight
   summary (company, month, accounts, currencies, opening balances, ⚠ gaps) + "Proceed?"
   resolves the documented STRICT-vs-org-policy conflict. No computation added.
The accountant guide (הנחייה לחשב) gains: a vendor_memory block (incl. cross-company
separation), a monthly `update` cycle, a pre-flight note on STEP 3, and a bank-vs-card note.
Also clarifies in Step 0 that ILS is the BOI base currency (no "ILS" rate key) and must be
converted via the USD rate (ILS per 1 USD) at the transaction date. Adds a multi-month
`update` mode: drop per-month folders (`YYYY-MM/`) and the skill appends one column per folder,
folder name authoritative for the month, with `MONTH_MISMATCH` flags for any row dated outside
its folder (surfaced in validation.json, never silently moved). Classification engine
strengthened (rec 1+2): MCC-based classification for card tabs at TIER2.5 (below keyword/TIER1,
above the direction fallback; broad codes → MED, software/ads → HIGH) and fuzzy vendor
resolution via stdlib difflib (merge near-duplicate names at ≥0.90 only — no false merges).
Both are additive fallbacks; the locked baseline (PASS, 5 circles OK, classification 100%) is
unchanged. Also adds (rec 3+4): description de-noising — a cleaned match string strips dates,
ref/asmachta numbers, and processor prefixes to lift hit-rate, while the original stays in
Description (D) and Vendor_Raw (Q) and everything removed is logged to
`validation.json → denoise_stripped` (nothing lost); and hierarchical taxonomy enforcement —
a `Category → [allowed Sub]` map in REFERENCE blanks+flags any out-of-taxonomy sub (logged to
`validation.json → taxonomy_violations`) to stop sub-category drift across months. Statement &
ledger handling (this round): HSBC MMF account balance is taken from the statement's
`Pending Cash Balance` (not movement sums; MMF/HSBC PDFs are scanned → OCR or prefer Excel);
deposit (PKAM) interest is computed as a formula `redeemed − principal` for ILS and USD; MMF
`Div Reinvest` → Interest Income, `Sell`/`Buy` → Internal; HSBC `INTEREST PAID` lines →
Interest Income; a CASH-IN not via the same entity/known customer/interest is flagged as an
Investment **candidate** (LOW/Review, never auto). DETAILED SUMMARY emits a full per-Category
and per-Sub breakout (every allowed sub, zero or not; informational — totals/circles still sum
category cells only). Executive Summary is built on a deterministic grid with a tracked
`next_free_row` so blocks/charts never overwrite or overlap.

### v47 (2026-06-22) — CB_REPORT_AS: consolidated production hardening (additive only)
Forked from `run-cb-report` v46 as a new skill `CB_REPORT_AS`; all v46 logic, formulas and
column indexes (A–R) preserved unchanged. Fourteen additive enhancements (detailed in the
"v47 ADDITIONS" section, Additions F–S):
1. **Global formula enforcement** — every derived numeric cell across Executive Summary, VC,
   Cash Management Policy helper tables and the FX row is a formula; PDF/external stays
   static + Source Note; `validation.json → formula_integrity_global` FAILs any literal.
2. **Deterministic chart grid** — fixed `(row,col)` anchors, label row above each chart,
   helper tables below; zero overlap.
3. **Vendor normalization engine** — `normalize_vendor()` before classification, VENDOR_CLASSIF
   `Aliases` column, `vendor_fragmentation_score`.
4. **Persistent `vendor_memory.json`** — load→apply→save; precedence VENDOR_CLASSIF TIER1 >
   vendor_memory > heuristic (TIER1 authority preserved).
5. **Header-based `detect_parser()`** + generic fallback (LOW); `parser_confidence` logged.
6. **Multi-layer confidence** — CLASS/FX/PARSER → FINAL_CONFIDENCE, internal + validation.json,
   **no new visible columns** (A–R frozen).
7. **FX confidence/quality** scoring from the FX source label (internal + fx_quality_summary).
8. **Hard blocking validation** — `overall_status` PASS|WARN|FAIL; FAIL on formula/recon break.
9. **Balance cross-check** — `BALANCE_MISMATCH` + `balance_delta`.
10. **FX-exposure KPI** — non-USD ÷ total balances; Exec Summary + validation.json.
11. **Dashboard insights** — largest expense category, largest vendor, FX impact %.
12. **Reclassify hardening** — no parsing; reapply normalization + VENDOR_CLASSIF + vendor_memory.
13. **Internal-pair IDs, Audit_ID, ERROR_TYPE** — internal audit fields.
14. **Expanded RTL accountant guide** — STEP 1–9 mandatory workflow, tab-usage rules,
    reclassify instructions.
Existing 0.5% internal-transfer tolerance kept (not changed to 1%).

### v46 (2026-06-21) — Ten additive enhancements
1. **Per-transaction ILS→USD conversion** enforced at the transaction date's BOI rate;
   `to_usd()` returns (usd, rate, source); FX Rate written literally per row; FX-coverage
   audit asserts no non-USD row lacks a rate/source.
2. **Formulas mandatory across all report parts** — BALANCES now uses formulas where the
   balance is derived (Mesh, computed deposits) and value + **Source Note** (filename/page)
   where it comes from a PDF/HTML statement, so external figures stay reviewable.
3. **Explicit FX Difference** in DETAILED SUMMARY = `Closing − Opening (prior-month close) −
   NET BURN`, referencing the NET BURN row directly.
4. **TOTAL OPERATIONAL IN scope** — all income except Investment rolls in; Interest Income
   moved from NON-OPERATIONAL into OPERATIONAL CASH IN.
5. **Executive Summary month-end FX row** — top block; USD-relative cross rates written as
   formulas dividing the non-USD BOI rate by the USD BOI rate (BOI EOM).
6. **Smart multi-language classification + Confidence column** (HIGH/MED/LOW); LOW is the
   default whenever uncertain, with a Review flag and a low-confidence audit log.
7. **Cash Management Policy — 5 charts**: existing 3 + currency-mix pie (₪/$/€) + per-account
   USD balance pie; 2-row grid layout; live formula-fed slice ranges.
8. **Addition D — inter-account transfer detection & netting**: tag `Internal=Y` (col R),
   exclude from every aggregation via `$R:$R,"<>Y"`; mirror-pair matching on USD amount.
9. **Addition E — VENDOR_CLASSIF as TIER1**: authoritative override, vendor-name unification
   (canonical_vendor + Aliases column, Vendor_Raw kept for audit), full retroactive
   application to all TRANSACTIONS on the next run.
10. **Circle-level reconciliation**: five circles (transaction → category → section → NET
    BURN → balance), each a live guard formula; run is "fully closed" only when all read OK.

### v45 (2026-06-21) — Five structural fixes
1. **DETAILED SUMMARY formulas**: `write_formula()` + SUMIFS for all data cells. TRANSACTIONS
   column index map documented. Formula templates for cat/sub/vendor/YTD/total rows.
2. **Mesh in BALANCES**: Step 4 — compute Mesh running balance from transactions before
   writing BALANCES. Mesh row in BALANCES after HSBC accounts.
3. **DETAILED SUMMARY BALANCE section**: Opening Balance (ref BALANCES prior month) + Net
   Cash Flow + FX Difference (plug = Closing - Opening - NCF) + Closing Balance (ref BALANCES)
   + Reconciliation formula. FX plug expected nonzero for ILS-heavy companies.
4. **Row grouping drill-down**: `outline_settings()` + `set_row(..., {"level": 1/2})` for
   sub-category and vendor rows. Controllers use `+` button to expand.
5. **הנחייה לחשב content**: Updated to Nextage standard with 4-step monthly workflow,
   8-item checklist (adds Mesh + FX Difference checks), 4 common errors, support contact.
   Defined as `GUIDE_CONTENT` list for reproducibility.

### v44 (2026-06-21)
- Additions A (validation), B (classification accuracy), C (generic bank detection).
- Build path: no bundled script. Step 0–10 is authoritative.
- FX pipeline: 5-strategy BOI-only.

### v43 — Step 0 FX pre-load from currency-data skill
### v42 — FX BOI-only 3-strategy pipeline
### v40 — FX Fallback EUR/GBP daily + June 2026
### v39 — REFERENCE tab full-year daily rates
### v38 — _last_m fix

---

# v47 ADDITIONS (CB_REPORT_AS)

All v47 additions are **additive and backward-compatible**. They do **not** change any
existing formula, do **not** shift column indexes (A–R remain fixed), do **not** convert any
formula into a static value, and add **no new visible Excel columns** — every new computed
field below is stored internally and/or in `validation.json` only. The full pipeline still
runs with **no dependency on external APIs** (FX falls back to embedded BOI rates as in v46).

## Addition F — FX Confidence & Quality (Step 0)

`get_fx_and_source(date, ccy)` keeps its existing **2-tuple** return `(rate, source_label)`
so every current caller (`rate, src = get_fx_and_source(...)`, `to_usd()`, Mesh balance loop,
Executive Summary FX row) is untouched. Confidence/quality is derived from the label via a
**new sibling helper** — never by changing the existing signature:

```python
_FX_QUALITY = {
    "BOI_daily":     ("HIGH", 100),
    "BOI_walkback":  ("MED",   80),   # also BOI_walkback_Nd / estimated_wbNd → walkback family
    "BOI_EOM":       ("MED",   70),
    "estimated":     ("LOW",   40),
    "hardcoded":     ("LOW",   20),
}

def fx_confidence_from_source(label):
    base = label.split("_")[0:2]
    key = "_".join(base) if "_".join(base) in _FX_QUALITY else label
    if key not in _FX_QUALITY:
        if "walkback" in label or "wb" in label: key = "BOI_walkback"
        elif label.startswith("estimated"):      key = "estimated"
        elif label.startswith("BOI_daily"):      key = "BOI_daily"
    return _FX_QUALITY.get(key, ("LOW", 20))     # (confidence, quality_score)
```

Stored as the internal `FX_CONFIDENCE` (and quality_score) per row — **not** as a visible
column. Validation counts rows on a fallback source (`estimated*` / `hardcoded`) and writes
`validation.json → fx_quality_summary = {"HIGH":n,"MED":n,"LOW":n,"fallback_rows":n}`. The
existing `J` (FX Rate) and `K` (FX Source) columns are unchanged.

## Addition G — Global Formula Enforcement (all tabs)

Extends the v45 DETAILED-SUMMARY rule to **every tab**: any numeric cell **derived from
TRANSACTIONS** must be written with `ws.write_formula()`. A value that comes from a
**PDF/external statement** is still allowed as a literal **with a Source Note** (unchanged
v46 BALANCES rule).

| Tab | v47 enforcement |
|---|---|
| DETAILED SUMMARY | already enforced (v45) — unchanged |
| BALANCES | derived rows = formula; PDF/statement rows = value + Source Note (unchanged) |
| Executive Summary | **ADD** — KPI tiles + FX row written as formulas |
| VC | **ADD** — vendor × month cells are SUMIFS formulas |
| Cash Management Policy | **ADD** — helper tables that feed the pies are SUM/SUMIF formulas |
| FX row | **ADD** — cross rates as `non-USD ÷ USD` formulas (already required in v46 Exec FX row) |

Track each derived cell as `formula`/`literal` (reuse the v44 `_written_as` map across all
tabs) and emit `validation.json → formula_integrity_global = "PASS"|"FAIL"`. **FAIL if any
derived numeric cell is a literal.** Feeds the hard-blocking rule (Addition H).

## Addition H — Hard Blocking Validation (Step 8)

```
overall_status = FAIL  if formula_integrity_global != PASS
overall_status = FAIL  if reconciliation != OK (any month)
overall_status = WARN  if low_confidence_pct > 20%  OR  fx_fallback_pct > 5%
overall_status = PASS  otherwise
```

`reconciliation` is the aggregate of the five circle-level checks (Step 6). The chat status
line states `overall_status` explicitly; a `FAIL` run is surfaced as blocking, not silently
delivered. Keys added to `validation.json`: `overall_status`, `formula_integrity_global`,
`reconciliation`, `low_confidence_pct`, `fx_fallback_pct`.

## Addition I — Balance Cross-Check

```python
balance_delta = abs(sum_balances - sum_amt_usd)   # Σ BALANCES TOTAL vs Σ TRANSACTIONS Amt USD (col I)
if balance_delta > 1:
    add_error_type("BALANCE_MISMATCH")
```

Complements Circle 5 (which ties BALANCES TOTAL to the DETAILED SUMMARY Closing Balance).
`validation.json → balance_delta`; a breach also tags `ERROR_TYPE = BALANCE_MISMATCH`
(Addition S).

## Addition J — Header-Based Parser Detection (Step 1)

```python
def detect_parser(df):
    cols = list(df.columns)
    if "תאריך"    in cols: return parse_leumi_ils
    if "Narrative" in cols: return parse_hsbc
    if "merchant"  in cols: return parse_cc
    return parse_generic            # Flag = "Review (generic parser)", Confidence = LOW
```

Used as a complementary fallback **after** the existing signal/filename routing in Step 1
(that table stays primary). Each parsed file records an internal `parser_confidence`.

---

## PATCH P-1 — VENDOR_CLASSIF Override: Income-Row Guard (v52.1)

> **Root cause this fixes:** When a vendor (e.g. `Bank Leumi`) is mapped to an expense
> category in VENDOR_CLASSIF (e.g. G&A/Bank Fees), the TIER1 override was applied
> blindly to ALL rows for that vendor — including positive-amount rows such as
> `ריבית מט"ח` (deposit interest), which are income. This caused Interest Income
> to disappear from the P&L silently.

### P-1-A. Income-row whitelist — always exempt from VENDOR_CLASSIF override

The following Description values are permanently protected. When a row matches any entry
in this set, the TIER1 override is **skipped entirely** and the row is forced to an IN
category instead.

```python
INCOME_DESCRIPTIONS = {
    'ריבית מט"ח',    # foreign-currency deposit interest
    'ריבית פיקדון',  # ILS deposit interest
    'ריבית שח',      # ILS interest (alternate spelling)
    'מענק לאומיטק',  # Leumi bank cashback / grant
    'ריבית',         # generic interest catch-all
}

def apply_vendor_classif_override(r: dict, vc_map: dict) -> None:
    """Apply TIER1 vendor override with income-row guard and direction guard."""
    desc = (r.get('Description') or '').strip()

    # -- Income guard --
    if any(d in desc for d in INCOME_DESCRIPTIONS):
        # Force to Interest Income if not already an IN category
        if r.get('Category') not in ('Interest Income', 'Revenue', 'Grants', 'Other IN'):
            r['Category']     = 'Interest Income'
            r['Sub_Category'] = 'Deposit Interest'
            r['Confidence']   = 'HIGH'
            r['Flag']         = ''
        return  # STOP: never apply VENDOR_CLASSIF override to income rows
```

### P-1-B. Direction guard — expense-category overrides skip positive-amount rows

After the income-description check, apply a second guard: if the VENDOR_CLASSIF maps
this vendor to an expense category (OP_OUT or Tax), do not override rows where
`Amt Native > 0`. This catches refunds, cashbacks, and any other credits from a
vendor that is normally an expense.

```python
    # -- Direction guard --
    OP_OUT_CATS = {'Payroll', 'R&D', 'G&A', 'S&M', 'Other OUT', 'Tax'}
    key = (r.get('Vendor') or '').strip().lower()
    if key not in vc_map:
        return
    ov = vc_map[key]
    try:
        native = float(r.get('Amt Native') or 0)
    except (TypeError, ValueError):
        native = 0.0
    if ov['Category'] in OP_OUT_CATS and native > 0:
        return  # positive amount + expense vendor -> income row, skip override

    # -- Apply override --
    r['Category']     = ov['Category']
    r['Sub_Category'] = ov['Sub_Category']
    r['Confidence']   = ov['Confidence']
```

### P-1-C. Blocking assertion before `wb.close()`

After all overrides are applied, assert that no `ריבית` row ended up classified as
an expense. If the assertion fails, the workbook is **not written**.

```python
for r in rows:
    if r.get('Internal', 'N') == 'Y':
        continue
    desc = r.get('Description') or ''
    if 'ריבית' in desc:
        assert r.get('Category') in ('Interest Income', 'Revenue', 'Other IN'), (
            f"BLOCKING: ריבית row reclassified as expense — "
            f"{r.get('Date')} | {desc} | Category={r.get('Category')}"
        )
```

### P-1-D. `validation.json` — interest income audit key

```json
"interest_income_audit": {
  "rows_found": <N>,
  "rows_correctly_categorised": <N>,
  "override_guard_status": "PASS",
  "note": "ריבית rows are income-protected; VENDOR_CLASSIF override never applies to them"
}
```

`override_guard_status = FAIL` → `overall_status = FAIL`.

### P-1-E. Practical rule for controllers

When adding a new entry to VENDOR_CLASSIF:
- **Bank or financial institution vendors** (e.g. Bank Leumi, Bank Hapoalim) map only
  their fee rows. Interest / deposit yield rows from the same vendor are automatically
  excluded by P-1-A and P-1-B — no special action needed.
- A vendor mapped to an expense category will never "eat" a positive-amount row. If a
  vendor should cover both income and expense (rare), split it into two vendor names
  (e.g. `Bank Leumi Fee` vs `Bank Leumi Interest`) and map them separately.
