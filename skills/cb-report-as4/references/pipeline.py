"""
pipeline.py — minimal faithful core of cb-report-as, scoped to what the baseline needs:
classification -> per-date FX -> TRANSACTIONS -> DETAILED SUMMARY (SUMIFS formulas)
-> 5 reconciliation circles -> BALANCES. No charts / dashboard / styling.

This reflects CURRENT (pre-change) behaviour so it can serve as the regression baseline.
formula_integrity is tracked exactly like the skill's _written_as map.
"""
import re, xlsxwriter, difflib
import vendor_memory as vmem
import hsbc_deposits as hd
from fixture import TXNS, FX, MONTH, OPENING_USD, TRANSFER_KEYWORDS

# Company scope for vendor_memory (point 1). Memory file is optional; when absent the
# pipeline behaves exactly as before, so the locked baseline is unaffected.
COMPANY = "Acme"
VENDOR_MEMORY_PATH = None   # set by the harness/leak-test; None = no memory (baseline)

# LibreOffice coerces a criteria like "2026-05" to arithmetic; use an unambiguous
# text token in the Month column + criteria so SUMIFS matches as text in any engine.
MKEY = "M" + MONTH

# ---------- FX ----------
def get_fx(date, ccy):
    if ccy == "USD":
        return 1.0, "USD_native"
    if ccy == "ILS":
        # BOI base is ILS; ILS->USD uses the USD rate (ILS per 1 USD)
        ccy = "USD"
    if (date, ccy) in FX:
        return FX[(date, ccy)], "BOI_daily"
    # walk back to nearest available date for that ccy
    cands = sorted([d for (d, c) in FX if c == ccy], reverse=True)
    for d in cands:
        if d <= date:
            return FX[(d, ccy)], "BOI_walkback"
    return FX[(cands[-1], ccy)], "estimated"

def to_usd(amount, ccy, date):
    if ccy == "USD":
        return round(amount, 2), 1.0, "USD_native"
    rate, src = get_fx(date, ccy)
    return round(amount / rate, 2), rate, src

# ---------- vendor normalization (v47 Addition N) ----------
def normalize_vendor(name):
    name = str(name).lower()
    name = re.sub(r"[^\w\s]", "", name)
    for s in ["בעמ", "ltd", "inc", "llc", "gmbh", "emea"]:
        name = name.replace(s, "")
    return name.strip()

CANON = {  # normalized fragment -> canonical
    "amazon web services": "Amazon Web Services", "aws": "Amazon Web Services",
    "openai": "OpenAI", "hetzner online": "Hetzner", "hetzner": "Hetzner",
    "notion labs": "Notion", "notion": "Notion", "google ads": "Google Ads",
    "facebook ads": "Meta", "refund facebook ads": "Meta",
    "wework": "WeWork", "gusto": "Gusto", "sequoia": "Sequoia",
}
def _token_set_ratio(a, b):
    ta = " ".join(sorted(set(a.split())))
    tb = " ".join(sorted(set(b.split())))
    return difflib.SequenceMatcher(None, ta, tb).ratio()

def canonical_vendor(raw):
    key = normalize_vendor(raw)
    for frag, canon in CANON.items():
        if frag in key:
            return canon
    # fuzzy fallback (rec 2): only merge on strong surface similarity (>=0.9),
    # so a genuinely different vendor is never collapsed into a canonical one.
    best, best_score = None, 0.0
    for frag, canon in CANON.items():
        score = max(_token_set_ratio(key, normalize_vendor(canon)),
                    _token_set_ratio(key, frag))
        if score > best_score:
            best, best_score = canon, score
    if best_score >= 0.90:
        return best
    return raw.strip().title()

# ---------- de-noising (rec 3) — clean text for matching, PRESERVE what was stripped ----------
_DENOISE_PATTERNS = [
    (r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}\b", "date"),     # dates
    (r"\b20\d{2}[-/]\d{2}[-/]\d{2}\b", "date"),             # ISO dates
    (r"\b(?:ref|asmachta|אסמכתא|conf|auth|trace|txn|inv)[:#\s]*\w*\d+\w*\b", "ref"),
    (r"\b\d{5,}\b", "longnum"),                             # long bare numbers (ref-like)
    (r"\b(?:paypal|sumup|sq|stripe|amzn mktp|tlv|us|il)\s*[*#]", "processor"),
    (r"[*#]+", "symbol"),
]
def denoise(desc):
    """Return (clean_text, stripped_list). Never mutates the source; only builds a match string."""
    text = str(desc)
    stripped = []
    for pat, kind in _DENOISE_PATTERNS:
        for m in re.findall(pat, text, flags=re.IGNORECASE):
            frag = m if isinstance(m, str) else " ".join(x for x in m if x)
            if frag.strip():
                stripped.append({"kind": kind, "text": frag.strip()})
        text = re.sub(pat, " ", text, flags=re.IGNORECASE)
    clean = re.sub(r"\s{2,}", " ", text).strip()
    return clean, stripped

# ---------- hierarchical taxonomy (rec 4) — Category -> allowed Sub list ----------
TAXONOMY = {
    "Revenue": [""], "Grants": [""], "Interest Income": [""], "Other IN": [""],
    "Payroll": ["Salaries", "Benefits", "Payroll Taxes"],
    "R&D": ["Cloud Infrastructure", "AI Tools", "SaaS Tools", ""],
    "G&A": ["Rent", "Legal & Accounting", "Bank Fees", "Meals & Entertainment",
            "Shipping & Courier", "Insurance", ""],
    "S&M": ["Advertising", ""],
    "Vendors": ["Refund", ""],
    "Travel": ["Airfare", "Transport", "Hotels", ""],
    "Tax": ["Income Tax", "VAT", ""],
    "Investment": ["VC Round", "SAFE", "Loan", ""],
    "Internal": [""], "Other OUT": [""],
}
def enforce_taxonomy(cat, sub):
    """Return (cat, sub, ok). If (cat, sub) is not allowed, blank the sub and flag not-ok."""
    allowed = TAXONOMY.get(cat)
    if allowed is None:
        return cat, sub, False              # unknown category
    if sub in allowed:
        return cat, sub, True
    return cat, "", False                   # keep category, drop invalid sub, flag for review
# MCC is a strong but broad signal: unambiguous software/ads = HIGH, fuzzy intent = MED.
MCC_MAP = {
    "7372": ("R&D", "SaaS Tools", "HIGH"),          # prepackaged / computer software
    "5734": ("R&D", "SaaS Tools", "HIGH"),          # computer software stores
    "4816": ("R&D", "Cloud Infrastructure", "MED"), # computer network / information services
    "7311": ("S&M", "Advertising", "HIGH"),         # advertising services
    "5968": ("R&D", "SaaS Tools", "MED"),           # subscription / continuity merchants
    "5812": ("G&A", "Meals & Entertainment", "MED"),# eating places
    "4214": ("G&A", "Shipping & Courier", "MED"),   # freight / courier
    "4112": ("Travel", "Transport", "MED"),         # passenger railways
    "3000": ("Travel", "Airfare", "MED"),           # airlines (3000-3299 block, sampled)
}

# ---------- classification (current heuristic, no direction rule yet) ----------
def classify(desc, amt, is_card, mcc=None):
    d = denoise(desc)[0].lower()   # match on cleaned text; source desc is preserved by caller
    def has(*ws): return any(w in d for w in ws)
    # deterministic rules first (TIER2)
    if has("vc round", "series b", "sequoia"):           return "Investment", "VC Round", canonical_vendor(desc), "HIGH"
    if has("מס הכנסה", "tax"):                            return "Tax", "Income Tax", "Israel Tax Authority", "HIGH"
    if has("משכורת", "payroll", "gusto", "שכר"):          return "Payroll", "Salaries", canonical_vendor(desc), "HIGH"
    if has("bank interest", "ריבית", "interest credit"): return "Interest Income", "", "Bank Interest", "HIGH"
    if has("מענק", "grant", "innovation"):               return "Grants", "", "Israel Innovation Authority", "HIGH"
    if has("aws", "amazon web", "hetzner"):              return "R&D", "Cloud Infrastructure", canonical_vendor(desc), ("HIGH" if "aws" in d or "amazon" in d else "MED")
    if has("openai", "chatgpt"):                         return "R&D", "AI Tools", "OpenAI", "HIGH"
    if has("notion", "saas"):                            return "R&D", "SaaS Tools", canonical_vendor(desc), "HIGH"
    if has("wework", "שכירות", "rent"):                  return "G&A", "Rent", "WeWork", "HIGH"
    if has("רואה חשבון", "nextage", "legal", "accounting"): return "G&A", "Legal & Accounting", "Nextage", "HIGH"
    if has("bank fees", "עמלות"):                        return "G&A", "Bank Fees", "Bank Fees", "HIGH"
    if has("google ads", "facebook ads", "ads", "campaign"): return "S&M", "", canonical_vendor(desc), ("HIGH" if "google ads" in d else "MED")
    if has("customer", "invoice", "לקוח", "globex", "cyberdyne"): return "Revenue", "", canonical_vendor(desc), "HIGH"
    # ---- TIER2.5 MCC fallback (rec 1): card rows keywords didn't catch ----
    if is_card and mcc and str(mcc) in MCC_MAP:
        cat, sub, conf = MCC_MAP[str(mcc)]
        return cat, sub, canonical_vendor(desc), conf
    # ---- third-party inflow -> Investment CANDIDATE (review), reads Description ----
    if amt > 0 and hd.is_third_party_investment_candidate(desc, amt):
        return "Investment", "Candidate (review)", canonical_vendor(desc), "LOW"
    # ---- TIER3 direction-aware fallback (only when nothing above matched) ----
    # A credit (cash IN) means different things on a card vs a bank account:
    if amt > 0:
        if is_card:
            return "Vendors", "Refund", canonical_vendor(desc) if canonical_vendor(desc) != desc.strip().title() else "", "LOW"
        return "Revenue", "", "", "LOW"          # unknown bank inflow = customer payment (best guess)
    # ambiguous cash OUT -> LOW
    return "Other OUT", "", "", "LOW"

# ---------- internal-transfer detection (Addition D) ----------
def detect_internal(rows):
    for r in rows:
        blob = f"{r['desc']} {r['desc2']}".lower()
        if any(k in blob for k in TRANSFER_KEYWORDS):
            r["internal"] = "Y"; r["cat"] = "Internal"; r["sub"] = ""; r["vendor"] = "Internal"
            r["conf"] = "HIGH"; r["flag"] = ""
    outs = [r for r in rows if r["usd"] < 0 and r["internal"] != "Y"]
    ins  = [r for r in rows if r["usd"] > 0 and r["internal"] != "Y"]
    for o in outs:
        for i in ins:
            if abs(abs(o["usd"]) - i["usd"]) <= max(1.0, 0.005 * i["usd"]) and o["account"] != i["account"]:
                o["internal"] = i["internal"] = "Y"
                for x in (o, i):
                    x["cat"] = "Internal"; x["sub"] = ""; x["vendor"] = "Internal"
                    x["conf"] = "HIGH"; x["flag"] = ""
    return rows

# ---------- build rows ----------
def build_rows():
    # Load ONLY this company's memory block (point 1). Empty when no path -> baseline behaviour.
    mem_block = vmem.load(VENDOR_MEMORY_PATH, COMPANY)
    rows = []
    for (date, acct, desc, desc2, ccy, amt, is_card, *_exp) in TXNS:
        usd, rate, src = to_usd(amt, ccy, date)
        cat, sub, vendor, conf = classify(desc, amt, is_card)
        # Precedence: VENDOR_CLASSIF (TIER1, not present in harness) > vendor_memory > heuristic.
        # Memory only fills where the heuristic was unsure (conf != HIGH), never overrides a
        # confident/human result.
        if conf != "HIGH":
            hit = vmem.apply(mem_block, normalize_vendor(desc))
            if hit:
                cat, sub, vendor = hit["cat"], hit.get("sub", ""), hit.get("canonical", vendor)
                conf = "HIGH"
        # rec 3: record what de-noising stripped (preserved, never lost)
        _clean, stripped = denoise(desc)
        # rec 4: enforce hierarchical taxonomy — blank invalid sub, flag for review
        cat, sub, tax_ok = enforce_taxonomy(cat, sub)
        flag = "Review" if conf == "LOW" else ""
        if not tax_ok:
            flag = (flag + " TAXONOMY").strip()
        rows.append(dict(date=date, account=acct, desc=desc, desc2=desc2, ccy=ccy,
                         amt=amt, usd=usd, rate=rate, src=src, cat=cat, sub=sub,
                         vendor=vendor, flag=flag,
                         conf=conf, internal="", denoise_stripped=stripped, taxonomy_ok=tax_ok))
    return detect_internal(rows)

# ---------- Excel column letters ----------
def xlcol(n):
    s = ""; n += 1
    while n:
        s = chr(65 + (n - 1) % 26) + s; n = (n - 1) // 26
    return s

def _fesc(s):
    return str(s).replace('"', '""')

# track formula vs literal for every DERIVED numeric cell
_written = {}

def write_formula(ws, r, c, formula, fmt=None):
    ws.write_formula(r, c, formula, fmt)
    _written[(ws.name, r, c)] = "formula"

def write_value(ws, r, c, val, fmt=None, derived=True):
    ws.write(r, c, val, fmt)
    if derived:
        _written[(ws.name, r, c)] = "literal"

# ---------- main build ----------
def build(path):
    rows = build_rows()
    wb = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True})
    wb.set_calc_mode("auto")
    num = wb.add_format({"num_format": "#,##0.00"})
    bold = wb.add_format({"bold": True})

    # ---- TRANSACTIONS (A..R) ----
    tx = wb.add_worksheet("TRANSACTIONS")
    hdr = ["Date","Month","Account","Description","Desc2","Ref","CCY","Amt Native",
           "Amt USD","FX Rate","FX Source","Category","Sub_Category","Vendor","Flag",
           "Confidence","Vendor_Raw","Internal"]
    for c, h in enumerate(hdr):
        tx.write(0, c, h, bold)
    for i, r in enumerate(rows, start=1):
        tx.write(i, 0, r["date"]); tx.write(i, 1, MKEY); tx.write(i, 2, r["account"])
        tx.write(i, 3, r["desc"]); tx.write(i, 4, r["desc2"]); tx.write(i, 5, "")
        tx.write(i, 6, r["ccy"]); tx.write(i, 7, r["amt"], num)
        tx.write(i, 8, r["usd"], num)            # I = Amt USD (source figure, not derived-from-formula)
        tx.write(i, 9, r["rate"]); tx.write(i, 10, r["src"])
        tx.write(i, 11, r["cat"]); tx.write(i, 12, r["sub"]); tx.write(i, 13, r["vendor"])
        tx.write(i, 14, r["flag"]); tx.write(i, 15, r["conf"]); tx.write(i, 16, r["desc"])
        tx.write(i, 17, r["internal"])
    nrow = len(rows)

    # ---- DETAILED SUMMARY (SUMIFS, internal excluded via $R:$R,"<>Y") ----
    ds = wb.add_worksheet("DETAILED SUMMARY")
    NETT = ',TRANSACTIONS!$R:$R,"<>Y"'
    col = 1  # month column B
    ds.write(0, 0, "DETAILED SUMMARY", bold); ds.write(0, col, MONTH, bold)  # display label only

    op_in_cats  = ["Revenue", "Grants", "Interest Income", "Other IN"]
    op_out_cats = ["Payroll", "R&D", "G&A", "S&M", "Vendors", "Other OUT"]
    nonop_cats  = ["Investment", "Tax"]

    layout = []  # (label, kind, cat) kind: catin/catout/catnonop/tot/ocf/burn/sect
    layout.append(("OPERATIONAL CASH IN", "sect", None))
    for c_ in op_in_cats: layout.append((c_, "catin", c_))
    layout.append(("TOTAL OPERATIONAL IN", "totin", None))
    layout.append(("OPERATIONAL CASH OUT", "sect", None))
    for c_ in op_out_cats: layout.append((c_, "catout", c_))
    layout.append(("TOTAL OPERATIONAL OUT", "totout", None))
    layout.append(("OPERATING CASH FLOW", "ocf", None))
    layout.append(("NON-OPERATIONAL", "sect", None))
    for c_ in nonop_cats: layout.append((c_, "catnonop", c_))
    layout.append(("NET BURN", "burn", None))

    rowmap = {}
    r = 2
    in_rows, out_rows, nonop_rows = [], [], []
    for label, kind, cat in layout:
        ds.write(r, 0, label, bold if kind in ("sect","totin","totout","ocf","burn") else None)
        if kind in ("catin","catout","catnonop"):
            f = (f'=SUMIFS(TRANSACTIONS!$I:$I,TRANSACTIONS!$B:$B,"{MKEY}",'
                 f'TRANSACTIONS!$L:$L,"{_fesc(cat)}"{NETT})')
            write_formula(ds, r, col, f, num)
            if kind == "catin": in_rows.append(r)
            elif kind == "catout": out_rows.append(r)
            else: nonop_rows.append(r)
        rowmap[label] = r
        r += 1

    def cells(rs): return "+".join(f"{xlcol(col)}{x+1}" for x in rs)
    # totals as formulas summing the category cells
    write_formula(ds, rowmap["TOTAL OPERATIONAL IN"], col, "=" + cells(in_rows), num)
    write_formula(ds, rowmap["TOTAL OPERATIONAL OUT"], col, "=" + cells(out_rows), num)
    write_formula(ds, rowmap["OPERATING CASH FLOW"], col,
                  f"={xlcol(col)}{rowmap['TOTAL OPERATIONAL IN']+1}+{xlcol(col)}{rowmap['TOTAL OPERATIONAL OUT']+1}", num)
    write_formula(ds, rowmap["NET BURN"], col,
                  f"={xlcol(col)}{rowmap['OPERATING CASH FLOW']+1}+" + cells(nonop_rows), num)

    # ---- BALANCES ----
    bal = wb.add_worksheet("BALANCES")
    bal.write(0, 0, "Account", bold); bal.write(0, 1, MONTH, bold)
    accts = sorted(set(r2["account"] for r2 in rows))
    brow = {}
    r = 1
    for a in accts:
        bal.write(r, 0, a)
        opening = OPENING_USD.get(a, 0.0)
        # derived closing = opening + SUMIFS of this account's USD (formula)
        f = (f'={opening}+SUMIFS(TRANSACTIONS!$I:$I,TRANSACTIONS!$C:$C,"{_fesc(a)}",'
             f'TRANSACTIONS!$B:$B,"{MKEY}")')
        write_formula(bal, r, 1, f, num)
        brow[a] = r
        r += 1
    bal_total_row = r
    bal.write(r, 0, "TOTAL", bold)
    write_formula(bal, r, 1, "=" + "+".join(f"B{brow[a]+1}" for a in accts), num)

    # ---- DETAILED SUMMARY: BALANCE section + 5th circle + FX plug + recon ----
    r = rowmap["NET BURN"] + 2
    ds.write(r, 0, "BALANCE (USD)", bold); base = r
    ds.write(r+1, 0, "Opening Balance")
    total_open = sum(OPENING_USD.values())
    write_value(ds, r+1, col, total_open, num, derived=False)  # seed = source figure
    ds.write(r+2, 0, "Net Cash Flow")
    write_formula(ds, r+2, col, f"={xlcol(col)}{rowmap['NET BURN']+1}", num)
    ds.write(r+3, 0, "Closing Balance")
    write_formula(ds, r+3, col, f"=BALANCES!$B${bal_total_row+1}", num)
    ds.write(r+4, 0, "FX Difference (plug)")
    closing = f"{xlcol(col)}{r+4}"; opening = f"{xlcol(col)}{r+2}"; nb = f"{xlcol(col)}{rowmap['NET BURN']+1}"
    write_formula(ds, r+5-1, col,  # FX row at r+4
                  f"={closing}-{opening}-{nb}", num)
    ds.write(r+5, 0, "Reconciliation (Circle 4)")
    write_formula(ds, r+5, col,
                  f'=IF(ABS({closing}-{opening}-{nb}-{xlcol(col)}{r+5})<1,"OK","ERROR")', num)

    # Circle 1: sum of op-in categories == independent SUMIFS over the in-set
    cir = rowmap["NET BURN"] + 0
    gstart = r + 7
    ds.write(gstart, 0, "GUARD CIRCLES", bold)
    in_set = '","'.join(op_in_cats)
    # Circle 1 (in): total-in cell vs SUMIFS over the category set (approx via SUM of per-cat)
    write_formula(ds, gstart+1, 0,
                  f'=IF(ABS({xlcol(col)}{rowmap["TOTAL OPERATIONAL IN"]+1}-({cells(in_rows)}))<1,"OK C1in","ERR C1in")')
    write_formula(ds, gstart+2, 0,
                  f'=IF(ABS({xlcol(col)}{rowmap["TOTAL OPERATIONAL OUT"]+1}-({cells(out_rows)}))<1,"OK C2out","ERR C2out")')
    write_formula(ds, gstart+3, 0,
                  f'=IF(ABS({xlcol(col)}{rowmap["OPERATING CASH FLOW"]+1}-'
                  f'({xlcol(col)}{rowmap["TOTAL OPERATIONAL IN"]+1}+{xlcol(col)}{rowmap["TOTAL OPERATIONAL OUT"]+1}))<1,"OK C3","ERR C3")')
    write_formula(ds, gstart+4, 0,
                  f'=IF(ABS({xlcol(col)}{rowmap["NET BURN"]+1}-'
                  f'({xlcol(col)}{rowmap["OPERATING CASH FLOW"]+1}+{cells(nonop_rows)}))<1,"OK C4nb","ERR C4nb")')
    write_formula(ds, gstart+5, 0,
                  f'=IF(ABS(BALANCES!$B${bal_total_row+1}-{closing})<1,"OK C5bal","ERR C5bal")')

    guard_cells = [(("DETAILED SUMMARY"), gstart+1+k, 0) for k in range(5)]
    recon_cell = ("DETAILED SUMMARY", r+5, col)

    # ---- BREAKDOWN BY SUB-CATEGORY (additive; does not feed totals/circles) ----
    br = gstart + 7
    ds.write(br, 0, "BREAKDOWN BY CATEGORY / SUB-CATEGORY", bold)
    br += 1
    sub_pairs = [(c, s) for c, subs in [
        ("Payroll", ["Salaries", "Benefits", "Payroll Taxes"]),
        ("R&D", ["Cloud Infrastructure", "AI Tools", "SaaS Tools"]),
        ("G&A", ["Rent", "Legal & Accounting", "Bank Fees", "Meals & Entertainment", "Shipping & Courier"]),
        ("S&M", ["Advertising"]),
        ("Vendors", ["Refund"]),
        ("Interest Income", ["MMF Dividend", "Bank Interest"]),
        ("Investment", ["VC Round", "Candidate (review)"]),
    ] for s in subs]
    for cat_, sub_ in sub_pairs:
        ds.write(br, 0, f"  {cat_} / {sub_}")
        f = (f'=SUMIFS(TRANSACTIONS!$I:$I,TRANSACTIONS!$B:$B,"{MKEY}",'
             f'TRANSACTIONS!$L:$L,"{_fesc(cat_)}",TRANSACTIONS!$M:$M,"{_fesc(sub_)}"{NETT})')
        write_formula(ds, br, col, f, num)
        br += 1

    wb.close()
    return {"nrows": nrow, "guard_cells": guard_cells, "recon_cell": recon_cell,
            "written": dict(_written), "rows": rows}

if __name__ == "__main__":
    meta = build("/home/claude/cb_harness/baseline_build.xlsx")
    print("built rows:", meta["nrows"])
    lits = [k for k, v in meta["written"].items() if v == "literal"]
    print("derived literals (should be 0):", len(lits), lits[:5])
