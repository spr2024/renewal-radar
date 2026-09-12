"""Curate a 50-company demo set for the directory UI.

Filters the full form5500.db down to realistic, single-employer, mid-size
prospects (excludes multi-employer trusts/union funds and mega-corps), then
enriches each with the same renewal/premium/coverage-gap logic the app uses,
plus a sponsor phone number pulled from the raw CSV (not in the processed DB).

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\build_demo_set.py
"""

import json
import random
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "form5500.db"
F5500_CSV = ROOT / "data" / "raw" / "f_5500_2024_latest.csv"
OUT_PATH = ROOT / "data" / "demo_companies.json"

SAMPLE_SIZE = 50
SEED = 42

SIZE_BUCKETS = ("250-499", "500-999", "1000-4999")

# Near-unambiguous markers of a multi-employer trust/union fund rather than a
# single employer. Deliberately NOT excluding on bare "TRUST" - "Trustees of
# X University" is a real single employer.
EXCLUDE_NAME_PATTERNS = [
    "BOARD OF TRUSTEES", "HEALTH AND WELFARE FUND", "WELFARE FUND", "BENEFIT FUND",
    "PENSION FUND", "VEBA", "JOINT BOARD", "TEAMSTERS", "SEIU", "AFL-CIO",
    "LOCAL UNION", "IBEW", "CARPENTERS HEALTH", "LABORERS HEALTH",
    "ANNUITY FUND", "APPRENTICESHIP FUND", "HEALTH ASSOCIATION",
]

import sys

sys.path.insert(0, str(ROOT))
from backend import fetcher  # noqa: E402


def format_phone(raw) -> str | None:
    if not isinstance(raw, str):
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 10:
        return None
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"


def load_phone_and_zip_by_company_key() -> pd.DataFrame:
    """Mirror scripts/build_db.py's company_key derivation so this joins
    cleanly onto the companies table, and pick each company's most recent
    filing's phone/zip (same tie-break as sponsor_name/city/state there)."""
    from scripts.build_db import normalize_name

    cols = [
        "SPONS_DFE_EIN", "SPONSOR_DFE_NAME", "SPONS_DFE_PHONE_NUM",
        "SPONS_DFE_MAIL_US_ZIP", "DATE_RECEIVED", "TYPE_WELFARE_BNFT_CODE",
    ]
    df = pd.read_csv(F5500_CSV, usecols=cols, dtype=str, low_memory=False)
    df = df[df["TYPE_WELFARE_BNFT_CODE"].notna() & (df["TYPE_WELFARE_BNFT_CODE"].str.strip() != "")]

    df["ein"] = df["SPONS_DFE_EIN"].str.strip()
    df["norm_name"] = df["SPONSOR_DFE_NAME"].apply(normalize_name)
    df["company_key"] = df["ein"].where(df["ein"].str.len() == 9, df["norm_name"])

    df = df.sort_values("DATE_RECEIVED", ascending=False).drop_duplicates("company_key", keep="first")
    return df.set_index("company_key")[["SPONS_DFE_PHONE_NUM", "SPONS_DFE_MAIL_US_ZIP"]]


def pick_candidate_keys() -> list[str]:
    where_name = " AND ".join(f'norm_name NOT LIKE "%{p}%"' for p in EXCLUDE_NAME_PATTERNS)
    placeholders = ",".join("?" for _ in SIZE_BUCKETS)
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            f"""
            SELECT company_key FROM companies
            WHERE business_code NOT LIKE '813%'
              AND size_bucket IN ({placeholders})
              AND {where_name}
            """,
            SIZE_BUCKETS,
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def main():
    print("Loading phone/zip lookup from raw CSV...")
    contact = load_phone_and_zip_by_company_key()

    print("Selecting candidate pool...")
    candidates = pick_candidate_keys()
    print(f"  -> {len(candidates):,} candidates after filtering")

    random.Random(SEED).shuffle(candidates)

    demo = []
    for key in candidates:
        if len(demo) >= SAMPLE_SIZE:
            break
        filing = fetcher.get_company_filing(key)
        if filing is None or filing["renewal"] is None:
            continue

        phone = zip_code = None
        if key in contact.index:
            row = contact.loc[key]
            phone = format_phone(row["SPONS_DFE_PHONE_NUM"])
            zip_code = row["SPONS_DFE_MAIL_US_ZIP"]

        filing["phone"] = phone
        filing["zip"] = zip_code
        demo.append(filing)

    demo.sort(key=lambda f: f["renewal"]["days_until_renewal"])

    OUT_PATH.write_text(json.dumps(demo, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Wrote {len(demo)} companies to {OUT_PATH}")

    with_phone = sum(1 for f in demo if f["phone"])
    with_premium = sum(1 for f in demo if f["premium_estimate"])
    with_gaps = sum(1 for f in demo if f["coverage_gaps"])
    print(f"  phone present: {with_phone}/{len(demo)}")
    print(f"  premium estimate present: {with_premium}/{len(demo)}")
    print(f"  at least one coverage gap: {with_gaps}/{len(demo)}")


if __name__ == "__main__":
    main()
