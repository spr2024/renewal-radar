"""
Build renewal-radar's SQLite database from DOL Form 5500 + Schedule A bulk CSVs.

Grain:
  - companies: one row per employer (grouped by EIN, falling back to normalized
    sponsor name), aggregated across all of their welfare-benefit plan filings.
  - coverage_lines: one row per Schedule A carrier line (a company can have
    several: medical, dental, vision, life, stop-loss, each from a different
    carrier / policy period).
  - benchmarks: peer coverage-adoption rates by company size bucket, used to
    flag "gaps" (things similar-sized companies usually carry that this one
    doesn't appear to).

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\build_db.py
"""

import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "processed" / "form5500.db"

F5500_CSV = RAW / "f_5500_2024_latest.csv"
SCHA_CSV = RAW / "F_SCH_A_2024_latest.csv"

SIZE_BUCKETS = [
    (100, 249, "100-249"),
    (250, 499, "250-499"),
    (500, 999, "500-999"),
    (1000, 4999, "1000-4999"),
    (5000, float("inf"), "5000+"),
]

SUFFIX_RE = re.compile(
    r"\b(INC|LLC|LLP|LP|CORP|CORPORATION|CO|COMPANY|LTD|PLC|GROUP|HOLDINGS|"
    r"INCORPORATED|THE)\b\.?",
    flags=re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    n = name.upper()
    n = re.sub(r"[^A-Z0-9 &]", " ", n)
    n = SUFFIX_RE.sub(" ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def size_bucket(count) -> str:
    if pd.isna(count):
        return "unknown"
    for lo, hi, label in SIZE_BUCKETS:
        if lo <= count <= hi:
            return label
    return "unknown"


def load_f5500() -> pd.DataFrame:
    cols = [
        "ACK_ID",
        "SPONSOR_DFE_NAME",
        "SPONS_DFE_EIN",
        "SPONS_DFE_MAIL_US_CITY",
        "SPONS_DFE_MAIL_US_STATE",
        "BUSINESS_CODE",
        "TYPE_PLAN_ENTITY_CD",
        "TYPE_WELFARE_BNFT_CODE",
        "FUNDING_INSURANCE_IND",
        "TOT_ACTIVE_PARTCP_CNT",
        "TOT_PARTCP_BOY_CNT",
        "FORM_PLAN_YEAR_BEGIN_DATE",
        "FORM_TAX_PRD",
        "DATE_RECEIVED",
        "FILING_STATUS",
    ]
    df = pd.read_csv(F5500_CSV, usecols=cols, dtype=str, low_memory=False)

    # Keep welfare-benefit filings only (pension-only filings have this blank).
    df = df[df["TYPE_WELFARE_BNFT_CODE"].notna() & (df["TYPE_WELFARE_BNFT_CODE"].str.strip() != "")]

    df["TOT_ACTIVE_PARTCP_CNT"] = pd.to_numeric(df["TOT_ACTIVE_PARTCP_CNT"], errors="coerce")
    df["TOT_PARTCP_BOY_CNT"] = pd.to_numeric(df["TOT_PARTCP_BOY_CNT"], errors="coerce")
    df["headcount"] = df["TOT_ACTIVE_PARTCP_CNT"].fillna(df["TOT_PARTCP_BOY_CNT"])

    df["ein"] = df["SPONS_DFE_EIN"].str.strip()
    df["norm_name"] = df["SPONSOR_DFE_NAME"].apply(normalize_name)
    # company_key: EIN when present, else normalized name (covers sloppy EIN entry).
    df["company_key"] = df["ein"].where(df["ein"].str.len() == 9, df["norm_name"])

    return df


def load_scha() -> pd.DataFrame:
    cols = [
        "ACK_ID",
        "INS_CARRIER_NAME",
        "INS_CARRIER_NAIC_CODE",
        "INS_PRSN_COVERED_EOY_CNT",
        "INS_POLICY_FROM_DATE",
        "INS_POLICY_TO_DATE",
        "INS_BROKER_COMM_TOT_AMT",
        "INS_BROKER_FEES_TOT_AMT",
        "WLFR_BNFT_HEALTH_IND",
        "WLFR_BNFT_DENTAL_IND",
        "WLFR_BNFT_VISION_IND",
        "WLFR_BNFT_LIFE_INSUR_IND",
        "WLFR_BNFT_TEMP_DISAB_IND",
        "WLFR_BNFT_LONG_TERM_DISAB_IND",
        "WLFR_BNFT_DRUG_IND",
        "WLFR_BNFT_STOP_LOSS_IND",
        "WLFR_BNFT_HMO_IND",
        "WLFR_BNFT_PPO_IND",
        "WLFR_BNFT_INDEMNITY_IND",
        "WLFR_BNFT_OTHER_IND",
        "WLFR_PREMIUM_RCVD_AMT",
        "WLFR_TOT_EARNED_PREM_AMT",
        "WLFR_TOT_CHARGES_PAID_AMT",
    ]
    df = pd.read_csv(SCHA_CSV, usecols=cols, dtype=str, low_memory=False)

    numeric_cols = [
        "INS_PRSN_COVERED_EOY_CNT",
        "INS_BROKER_COMM_TOT_AMT",
        "INS_BROKER_FEES_TOT_AMT",
        "WLFR_PREMIUM_RCVD_AMT",
        "WLFR_TOT_EARNED_PREM_AMT",
        "WLFR_TOT_CHARGES_PAID_AMT",
    ]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    ind_cols = [c for c in cols if c.startswith("WLFR_BNFT_")]
    for c in ind_cols:
        df[c] = df[c] == "1"

    return df


def build():
    print("Loading F_5500 (welfare filings only)...")
    f5500 = load_f5500()
    print(f"  -> {len(f5500):,} welfare-benefit filings")

    print("Loading Schedule A...")
    scha = load_scha()
    print(f"  -> {len(scha):,} carrier lines")

    merged = scha.merge(
        f5500[["ACK_ID", "company_key", "norm_name", "SPONSOR_DFE_NAME"]],
        on="ACK_ID",
        how="inner",
    )
    print(f"  -> {len(merged):,} carrier lines matched to a sponsor")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)

    companies = (
        f5500.sort_values("DATE_RECEIVED", ascending=False)
        .groupby("company_key")
        .agg(
            sponsor_name=("SPONSOR_DFE_NAME", "first"),
            norm_name=("norm_name", "first"),
            city=("SPONS_DFE_MAIL_US_CITY", "first"),
            state=("SPONS_DFE_MAIL_US_STATE", "first"),
            business_code=("BUSINESS_CODE", "first"),
            headcount=("headcount", "max"),
            num_plans=("ACK_ID", "nunique"),
            latest_filing_date=("DATE_RECEIVED", "max"),
            plan_year_end_fallback=("FORM_TAX_PRD", "first"),
        )
        .reset_index()
    )
    companies["size_bucket"] = companies["headcount"].apply(size_bucket)
    companies.to_sql("companies", conn, if_exists="replace", index=False)

    coverage_cols = [
        "ACK_ID",
        "company_key",
        "INS_CARRIER_NAME",
        "INS_CARRIER_NAIC_CODE",
        "INS_PRSN_COVERED_EOY_CNT",
        "INS_POLICY_FROM_DATE",
        "INS_POLICY_TO_DATE",
        "INS_BROKER_COMM_TOT_AMT",
        "INS_BROKER_FEES_TOT_AMT",
        "WLFR_BNFT_HEALTH_IND",
        "WLFR_BNFT_DENTAL_IND",
        "WLFR_BNFT_VISION_IND",
        "WLFR_BNFT_LIFE_INSUR_IND",
        "WLFR_BNFT_TEMP_DISAB_IND",
        "WLFR_BNFT_LONG_TERM_DISAB_IND",
        "WLFR_BNFT_DRUG_IND",
        "WLFR_BNFT_STOP_LOSS_IND",
        "WLFR_BNFT_HMO_IND",
        "WLFR_BNFT_PPO_IND",
        "WLFR_BNFT_INDEMNITY_IND",
        "WLFR_BNFT_OTHER_IND",
        "WLFR_PREMIUM_RCVD_AMT",
        "WLFR_TOT_EARNED_PREM_AMT",
        "WLFR_TOT_CHARGES_PAID_AMT",
    ]
    merged[coverage_cols].to_sql("coverage_lines", conn, if_exists="replace", index=False)

    # Peer benchmark: % of companies in each size bucket carrying each benefit line.
    flag_cols = [c for c in coverage_cols if c.startswith("WLFR_BNFT_")]
    cov_with_bucket = merged.merge(
        companies[["company_key", "size_bucket"]], on="company_key", how="left"
    )
    company_flags = cov_with_bucket.groupby("company_key")[flag_cols].max()
    company_flags = company_flags.merge(
        companies[["company_key", "size_bucket"]], on="company_key", how="left"
    )
    bench = company_flags.groupby("size_bucket")[flag_cols].mean().reset_index()
    bench_long = bench.melt(id_vars="size_bucket", var_name="benefit_flag", value_name="peer_pct")
    bench_long.to_sql("benchmarks", conn, if_exists="replace", index=False)

    conn.execute("CREATE INDEX idx_companies_norm_name ON companies(norm_name)")
    conn.execute("CREATE INDEX idx_coverage_company_key ON coverage_lines(company_key)")
    conn.commit()

    n_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    print(f"Done. {n_companies:,} companies written to {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    build()
