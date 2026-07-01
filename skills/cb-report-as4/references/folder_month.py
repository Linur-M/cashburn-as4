"""
folder_month.py — multi-month ingestion by per-month folders (drag-and-drop).

Convention: each month's files live in a folder named YYYY-MM. The FOLDER NAME is the
authoritative month tag for every transaction in it — the month is NEVER guessed from file
content. To prevent silent misfiling ("no confusion"), each transaction's own date is checked
against its folder: a row whose date falls outside the folder's month is FLAGGED
(MONTH_MISMATCH / Review) but still placed in the declared folder month, so the controller
sees and fixes the source file rather than the report quietly moving money to another column.
"""
import os, re, json, glob

MONTH_DIR = re.compile(r"(20\d{2})-(0[1-9]|1[0-2])$")

def resolve_month_from_folder(folder_path):
    """Return 'YYYY-MM' from the immediate folder name, or None if it isn't a month folder."""
    base = os.path.basename(os.path.normpath(folder_path))
    m = MONTH_DIR.match(base)
    return f"{m.group(1)}-{m.group(2)}" if m else None

def discover_month_folders(dropzone):
    """Return {month: [file paths]} for every YYYY-MM subfolder under dropzone."""
    out = {}
    for entry in sorted(os.listdir(dropzone)):
        full = os.path.join(dropzone, entry)
        if os.path.isdir(full):
            mo = resolve_month_from_folder(full)
            if mo:
                out[mo] = sorted(glob.glob(os.path.join(full, "*.json")))
    return out

def ingest(dropzone):
    """
    Load all per-month folders into month-tagged rows.
    Returns (rows, months, mismatches) where each row carries:
      folder_month (authoritative column), date, and flag if its date != folder month.
    """
    folders = discover_month_folders(dropzone)
    rows, mismatches = [], []
    for mo, files in folders.items():
        for fp in files:
            with open(fp, encoding="utf-8") as f:
                for t in json.load(f):
                    date_month = t["date"][:7]
                    flag = ""
                    if date_month != mo:
                        flag = "MONTH_MISMATCH"
                        mismatches.append({"file": os.path.basename(fp),
                                           "folder_month": mo, "row_date": t["date"]})
                    row = dict(t)
                    row["month"] = mo               # FOLDER is authoritative
                    row["flag"] = flag
                    rows.append(row)
    months = sorted(folders.keys())
    return rows, months, mismatches
