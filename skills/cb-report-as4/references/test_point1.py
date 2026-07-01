"""
test_point1.py — proves point 1 (company scoping) is safe:
  A) No memory file -> classification identical to baseline.
  B) A POISONED entry stored under company "OtherCo" is IGNORED when COMPANY="Acme".
  C) The same poisoned entry IS read when COMPANY="OtherCo" -> proves the ONLY thing
     stopping the leak is the company key (mechanism works, scoping is what protects).
"""
import json, importlib
import vendor_memory as vmem

POISON_PATH = "/home/claude/cb_harness/vendor_memory.json"

# A vendor that appears in Acme's data ("misc payment" is a LOW row in the fixture).
# Poison it under a DIFFERENT company with a clearly-wrong category.
import pipeline as _pl
LEAK_KEY = _pl.normalize_vendor("MISC PAYMENT REF 99812")
poison = {
    "OtherCo": {
        LEAK_KEY: {"cat": "Investment", "sub": "VC Round", "canonical": "WRONG-LEAK"}
    }
}
with open(POISON_PATH, "w", encoding="utf-8") as f:
    json.dump(poison, f, ensure_ascii=False, indent=2)

def run(company, mem_path):
    import pipeline
    importlib.reload(pipeline)
    pipeline.COMPANY = company
    pipeline.VENDOR_MEMORY_PATH = mem_path
    rows = pipeline.build_rows()
    # find the poisoned row
    target = [r for r in rows if "misc payment" in r["desc"].lower()][0]
    return target["cat"], target["vendor"], target["conf"]

# A) baseline (no memory)
a = run("Acme", None)
# B) poisoned file present, but we are Acme -> must stay LOW/Other OUT (no leak)
b = run("Acme", POISON_PATH)
# C) same file, but loaded as OtherCo -> the entry applies (mechanism proven)
c = run("OtherCo", POISON_PATH)

print("A) Acme, no memory       :", a)
print("B) Acme, poison(OtherCo) :", b, "  <- must equal A (no leak)")
print("C) OtherCo, same file    :", c, "  <- entry applies here")

assert a == b, "LEAK! OtherCo memory affected Acme"
assert a[0] == "Other OUT" and a[2] == "LOW", "baseline row changed unexpectedly"
assert c[1] == "WRONG-LEAK", "mechanism did not read the matching-company block"
print("\nPASS: memory is company-scoped; no cross-company leak; mechanism works.")
