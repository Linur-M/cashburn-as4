"""
vendor_memory.py — company-scoped persistent vendor memory (point 1).

Structure (scoped by company at the TOP level):
{
  "Acme":    { "<normalized_vendor>": {"cat":..., "sub":..., "canonical":...}, ... },
  "OtherCo": { ... }                       # never consulted when COMPANY != "OtherCo"
}

Precedence is preserved exactly as the skill requires:
    VENDOR_CLASSIF (human, TIER1)  >  vendor_memory  >  heuristic
so a human decision always wins; memory only fills where the heuristic would otherwise guess.
"""
import json, os

def load(path, company):
    """Return ONLY this company's memory block; empty dict if file/company absent."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    block = data.get(company, {})
    return block if isinstance(block, dict) else {}

def apply(mem_block, norm_vendor):
    """Look up a normalized vendor in this company's block. None if absent."""
    return mem_block.get(norm_vendor)

def save(path, company, mem_block):
    """Merge this company's block back, leaving other companies' blocks untouched."""
    data = {}
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[company] = mem_block
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
