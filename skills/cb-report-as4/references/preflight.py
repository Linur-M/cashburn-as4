"""
preflight.py — point 4. Resolves the documented conflict between STRICT MODE
("do not ask, auto-detect, deliver") and the org pre-approval policy
("state plan, ask May I proceed, wait").

It produces a short, read-only confirmation summary BEFORE the pipeline runs.
It performs NO classification, NO FX conversion, NO Excel writing — so it cannot
move the baseline. After approval, the existing STRICT pipeline runs unchanged.
"""
from fixture import TXNS, MONTH, OPENING_USD

def detect_inputs(txns):
    """Lightweight scan of what WOULD be processed — accounts, currencies, counts."""
    accounts, ccys = {}, {}
    for (date, acct, *_rest) in txns:
        accounts[acct] = accounts.get(acct, 0) + 1
    for t in txns:
        ccy = t[4]
        ccys[ccy] = ccys.get(ccy, 0) + 1
    return accounts, ccys

def build_preflight(company, txns=TXNS, month=MONTH, openings=OPENING_USD):
    accounts, ccys = detect_inputs(txns)
    lines = []
    lines.append(f"PRE-FLIGHT — {company}  |  חודש: {month}")
    lines.append(f"תנועות שזוהו: {len(txns)}")
    lines.append("חשבונות: " + ", ".join(f"{a} ({n})" for a, n in sorted(accounts.items())))
    lines.append("מטבעות: " + ", ".join(f"{c} ({n})" for c, n in sorted(ccys.items())))
    lines.append("יתרות פתיחה (USD): " + ", ".join(f"{a}={v:,.0f}" for a, v in sorted(openings.items())))
    seeded = set(openings)
    missing = sorted(set(accounts) - seeded)
    if missing:
        lines.append("⚠ חסרה יתרת פתיחה ל: " + ", ".join(missing))
    lines.append("פעולה: בנייה מלאה (STRICT) לאחר אישור.")
    summary = "\n".join(lines)
    needs_attention = bool(missing)
    return {"summary": summary, "needs_attention": needs_attention,
            "accounts": accounts, "ccys": ccys, "missing_openings": missing}

def gate(company, approved, **kw):
    """
    STRICT-with-approval: returns the pre-flight summary and whether to proceed.
    approved=False -> stop and show summary (org policy honoured).
    approved=True  -> proceed; the unchanged STRICT pipeline then runs.
    """
    pf = build_preflight(company, **kw)
    pf["proceed"] = bool(approved)
    return pf

if __name__ == "__main__":
    pf = build_preflight("Acme")
    print(pf["summary"])
    print("\nneeds_attention:", pf["needs_attention"])
