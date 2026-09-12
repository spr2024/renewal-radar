"""Form 5500 data wrapper for renewal-radar.

Wraps the local SQLite database built by scripts/build_db.py from the DOL
EFAST2 Form 5500 + Schedule A bulk CSV extracts (companies, coverage_lines,
benchmarks). DOL does not publish a live full-text search API for Form 5500
data, so this reads the pre-built local database instead of calling a remote
endpoint.

Public functions:
    search_and_enrich(query) -> list of enriched filing dicts
    search_companies(query)  -> raw company rows, no enrichment
    get_company_filing(key)  -> one enriched filing dict
"""

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "form5500.db"

sys.path.insert(0, str(ROOT))
from scripts.build_db import normalize_name  # noqa: E402  (must match build-time normalization)

# Benefit flag columns worth flagging as a "gap" when peers usually carry them.
# HMO/PPO/INDEMNITY/OTHER describe plan structure, not a distinct benefit, so
# they're excluded here even though they exist in coverage_lines.
BENEFIT_LABELS = {
    "WLFR_BNFT_HEALTH_IND": "Medical/Health",
    "WLFR_BNFT_DENTAL_IND": "Dental",
    "WLFR_BNFT_VISION_IND": "Vision",
    "WLFR_BNFT_LIFE_INSUR_IND": "Life Insurance",
    "WLFR_BNFT_TEMP_DISAB_IND": "Short-Term Disability",
    "WLFR_BNFT_LONG_TERM_DISAB_IND": "Long-Term Disability",
    "WLFR_BNFT_DRUG_IND": "Prescription Drug",
    "WLFR_BNFT_STOP_LOSS_IND": "Stop-Loss",
}

# Typical group health premium trend used to project a stale filed premium
# forward to a current-year estimate.
ANNUAL_TREND_RATE = 0.08

# Brokers typically start renewal conversations 60-120 days before the
# effective date.
OUTREACH_WINDOW_START_DAYS = 120
OUTREACH_WINDOW_END_DAYS = 60


def _get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run `python scripts/build_db.py` first."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def search_companies(query: str, limit: int = 15) -> list[dict]:
    """Search companies by (partial) name. Returns raw company rows."""
    norm_q = normalize_name(query)
    if not norm_q:
        return []

    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM companies WHERE norm_name LIKE ? ORDER BY headcount DESC LIMIT ?",
            (f"%{norm_q}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_coverage_lines(company_key: str) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM coverage_lines WHERE company_key = ? ORDER BY INS_POLICY_TO_DATE DESC",
            (company_key,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_peer_benchmarks(size_bucket: str) -> dict[str, float]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT benefit_flag, peer_pct FROM benchmarks WHERE size_bucket = ?",
            (size_bucket,),
        ).fetchall()
        return {r["benefit_flag"]: r["peer_pct"] for r in rows}
    finally:
        conn.close()


def calculate_renewal_window(
    policy_to_date: str | None,
    policy_from_date: str | None = None,
    today: date | None = None,
) -> dict | None:
    """Project the next renewal date forward from the most recently filed
    policy period, and flag whether today falls in the typical broker
    outreach window (60-120 days before renewal)."""
    today = today or date.today()
    to_date = _parse_date(policy_to_date)
    if to_date is None:
        return None

    from_date = _parse_date(policy_from_date)
    period_days = (to_date - from_date).days if from_date else 365
    if period_days <= 0:
        period_days = 365

    renewal_date = to_date + timedelta(days=1)
    while renewal_date <= today:
        renewal_date += timedelta(days=period_days)

    outreach_start = renewal_date - timedelta(days=OUTREACH_WINDOW_START_DAYS)
    outreach_end = renewal_date - timedelta(days=OUTREACH_WINDOW_END_DAYS)

    return {
        "renewal_date": renewal_date.isoformat(),
        "days_until_renewal": (renewal_date - today).days,
        "outreach_window_start": outreach_start.isoformat(),
        "outreach_window_end": outreach_end.isoformat(),
        "in_outreach_window": outreach_start <= today <= outreach_end,
    }


def estimate_premium_range(coverage_lines: list[dict], as_of: date | None = None) -> dict | None:
    """Sum reported premium across a company's carrier lines and project it
    forward to a current-year estimate using a standard trend rate, since
    filings lag 1-2+ years behind the current renewal."""
    as_of = as_of or date.today()
    total_reported = 0.0
    latest_period_end = None

    for line in coverage_lines:
        amt = line.get("WLFR_TOT_EARNED_PREM_AMT") or line.get("WLFR_PREMIUM_RCVD_AMT") or 0
        total_reported += amt
        to_date = _parse_date(line.get("INS_POLICY_TO_DATE"))
        if to_date and (latest_period_end is None or to_date > latest_period_end):
            latest_period_end = to_date

    if total_reported <= 0 or latest_period_end is None:
        return None

    years_elapsed = max((as_of - latest_period_end).days / 365.25, 0)
    projected = total_reported * ((1 + ANNUAL_TREND_RATE) ** years_elapsed)

    return {
        "reported_annual_premium": round(total_reported),
        "reported_as_of": latest_period_end.isoformat(),
        "estimated_current_annual_premium_low": round(projected * 0.9),
        "estimated_current_annual_premium_high": round(projected * 1.15),
        "trend_rate_used": ANNUAL_TREND_RATE,
    }


def find_coverage_gaps(
    coverage_lines: list[dict], size_bucket: str, threshold: float = 0.5
) -> list[dict]:
    """Flag benefit lines that most peers of this company's size carry but
    none of this company's filed coverage lines show evidence of."""
    have = {flag for flag in BENEFIT_LABELS if any(line.get(flag) for line in coverage_lines)}
    peer = get_peer_benchmarks(size_bucket)

    gaps = [
        {"benefit": label, "peer_adoption_pct": round(peer.get(flag, 0) * 100, 1)}
        for flag, label in BENEFIT_LABELS.items()
        if flag not in have and peer.get(flag, 0) >= threshold
    ]
    gaps.sort(key=lambda g: g["peer_adoption_pct"], reverse=True)
    return gaps


def get_company_filing(company_key: str) -> dict | None:
    """Fetch one company plus its coverage lines and computed enrichments
    (renewal window, premium estimate, coverage gaps) as a single dict."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM companies WHERE company_key = ?", (company_key,)
        ).fetchone()
        if row is None:
            return None
        company = dict(row)
    finally:
        conn.close()

    lines = get_coverage_lines(company_key)

    dated_lines = [l for l in lines if l.get("INS_POLICY_TO_DATE")]
    if dated_lines:
        anchor = max(dated_lines, key=lambda l: l["INS_POLICY_TO_DATE"])
        renewal = calculate_renewal_window(
            anchor["INS_POLICY_TO_DATE"], anchor["INS_POLICY_FROM_DATE"]
        )
    else:
        renewal = calculate_renewal_window(company.get("plan_year_end_fallback"))

    return {
        "company_key": company_key,
        "sponsor_name": company["sponsor_name"],
        "city": company["city"],
        "state": company["state"],
        "headcount": company["headcount"],
        "size_bucket": company["size_bucket"],
        "num_plans": company["num_plans"],
        "latest_filing_date": company["latest_filing_date"],
        "carriers": sorted({l["INS_CARRIER_NAME"] for l in lines if l.get("INS_CARRIER_NAME")}),
        "coverage_lines": lines,
        "renewal": renewal,
        "premium_estimate": estimate_premium_range(lines),
        "coverage_gaps": find_coverage_gaps(lines, company["size_bucket"]),
    }


def search_and_enrich(query: str, limit: int = 15) -> list[dict]:
    """Search by company name and return fully enriched filings, ready to
    hand to backend.generator.generate_report()."""
    companies = search_companies(query, limit=limit)
    filings = (get_company_filing(c["company_key"]) for c in companies)
    return [f for f in filings if f is not None]
