"""
harness.py — runs the pipeline, forces a real recalc via LibreOffice, reads back the
computed circle/recon cells, measures classification accuracy vs the tagged fixture,
and writes baseline.json (the locked regression baseline).
"""
import json, os, subprocess, shutil, sys
import openpyxl
from pipeline import build, classify, canonical_vendor, build_rows
from fixture import TXNS

WORK = "/home/claude/cb_harness"
SRC = f"{WORK}/baseline_build.xlsx"
RECALC_DIR = f"{WORK}/recalc"

def _force_recalc_config():
    """Write registrymodifications so LibreOffice ALWAYS recalcs xlsx on load."""
    cfg = f"{WORK}/.config/libreoffice/4/user"
    os.makedirs(cfg, exist_ok=True)
    xcu = '''<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
 <item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>0</value></prop></item>
 <item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="ODFRecalcMode" oor:op="fuse"><value>0</value></prop></item>
</oor:items>'''
    with open(f"{cfg}/registrymodifications.xcu", "w") as f:
        f.write(xcu)

def recalc_with_libreoffice(src):
    """Convert through LibreOffice headless -> forces formula recalc, returns recalced path."""
    _force_recalc_config()
    if os.path.exists(RECALC_DIR):
        shutil.rmtree(RECALC_DIR)
    os.makedirs(RECALC_DIR)
    env = dict(os.environ, HOME=WORK)
    subprocess.run(
        ["soffice", "--headless", "--calc", "--convert-to", "xlsx",
         "--outdir", RECALC_DIR, src],
        check=True, capture_output=True, env=env, timeout=120)
    out = os.path.join(RECALC_DIR, os.path.basename(src))
    return out

def read_circles(xlsx):
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    ds = wb["DETAILED SUMMARY"]
    circles, recon = {}, None
    for row in ds.iter_rows():
        for cell in row:
            v = cell.value
            if isinstance(v, str):
                if v.startswith(("OK C", "ERR C")):
                    circles[v.split()[-1]] = v.startswith("OK")
                if v in ("OK", "ERROR"):
                    recon = v
    return circles, recon

def measure_accuracy():
    rows = build_rows()
    total = correct_cat = correct_conf = 0
    misses = []
    for r, spec in zip(rows, TXNS):
        (_d, _a, desc, _d2, _c, _amt, _card, exp_cat, exp_sub, exp_vendor, exp_int, exp_conf) = spec
        total += 1
        cat_ok = (r["cat"] == exp_cat)
        conf_ok = (r["conf"] == exp_conf)
        correct_cat += cat_ok
        correct_conf += conf_ok
        if not cat_ok or not conf_ok:
            misses.append({"desc": desc[:40], "got": (r["cat"], r["conf"]),
                           "exp": (exp_cat, exp_conf)})
    return {
        "n": total,
        "classification_accuracy_pct": round(100 * correct_cat / total, 1),
        "confidence_accuracy_pct": round(100 * correct_conf / total, 1),
        "misses": misses,
    }

def main():
    meta = build(SRC)
    lits = [k for k, v in meta["written"].items() if v == "literal"]
    formula_integrity = "PASS" if not lits else "FAIL"

    recalced = recalc_with_libreoffice(SRC)
    circles, recon = read_circles(recalced)
    acc = measure_accuracy()

    all_circles_ok = len(circles) >= 5 and all(circles.values())
    overall = "PASS"
    if formula_integrity != "PASS" or recon != "OK" or not all_circles_ok:
        overall = "FAIL"
    elif acc["classification_accuracy_pct"] < 100:
        overall = "WARN"

    baseline = {
        "overall_status": overall,
        "formula_integrity_global": formula_integrity,
        "derived_literal_cells": len(lits),
        "reconciliation": recon,
        "circles": circles,
        "all_circles_ok": all_circles_ok,
        "rows": meta["nrows"],
        **acc,
    }
    with open(f"{WORK}/baseline.json", "w") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
    print(json.dumps(baseline, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
