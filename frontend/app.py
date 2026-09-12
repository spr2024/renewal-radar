"""Renewal Radar - Streamlit frontend.

Search DOL Form 5500 filings by company name, then generate a Claude-written
call-prep briefing for the broker.
"""

import os
import sys
from pathlib import Path

import anthropic
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import fetcher, generator  # noqa: E402

load_dotenv()

st.set_page_config(page_title="Renewal Radar", page_icon="📡", layout="wide")

URGENCY_EMOJI = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}


def format_currency(amount) -> str:
    if amount is None:
        return "N/A"
    return f"${amount:,.0f}"


def escape_markdown(text: str) -> str:
    """Escape characters Streamlit's markdown renderer treats specially.
    Claude's output routinely contains dollar amounts like "$1.2M and $900K" -
    unescaped, st.markdown renders everything between them as LaTeX math."""
    return text.replace("$", "\\$")


with st.sidebar:
    st.header("Settings")
    sidebar_key = st.text_input(
        "Anthropic API Key",
        type="password",
        help="Falls back to ANTHROPIC_API_KEY in .env if left blank.",
    )
    api_key = sidebar_key or os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        st.caption("API key loaded ✓" if not sidebar_key else "Using key entered above ✓")
    else:
        st.warning("No API key set. Enter one above or add ANTHROPIC_API_KEY to .env.")

    st.divider()
    st.caption(
        "Data source: local DOL Form 5500 + Schedule A bulk extracts, "
        "processed by scripts/build_db.py."
    )

st.title("📡 Renewal Radar")
st.caption("Find employee-benefit renewal opportunities hiding in public DOL Form 5500 filings.")

if "results" not in st.session_state:
    st.session_state.results = []
if "selected_key" not in st.session_state:
    st.session_state.selected_key = None
if "report" not in st.session_state:
    st.session_state.report = None
if "report_key" not in st.session_state:
    st.session_state.report_key = None

with st.form("search_form"):
    query = st.text_input("Company name", placeholder="e.g. LL Bean, Northeast Bank...")
    submitted = st.form_submit_button("Search")

if submitted and query.strip():
    try:
        st.session_state.results = fetcher.search_and_enrich(query.strip())
    except FileNotFoundError as exc:
        st.error(f"{exc}")
        st.session_state.results = []
    st.session_state.selected_key = None
    st.session_state.report = None
    st.session_state.report_key = None

results = st.session_state.results

if submitted and not results:
    st.info("No companies matched that name. Try a shorter or differently-spelled query.")

if results:
    options = {f["company_key"]: f for f in results}
    labels = {
        key: f"{f['sponsor_name']} — {f['city']}, {f['state']} ({int(f['headcount'] or 0):,} employees)"
        for key, f in options.items()
    }

    selected_key = st.selectbox(
        f"{len(results)} match(es)",
        options=list(options.keys()),
        format_func=lambda k: labels[k],
    )
    st.session_state.selected_key = selected_key
    filing = options[selected_key]

    st.subheader(filing["sponsor_name"])
    st.caption(
        f"{filing['city']}, {filing['state']}  •  "
        f"{filing['num_plans']} plan(s) on file  •  "
        f"Latest filing: {filing['latest_filing_date']}  •  "
        f"Carriers: {', '.join(filing['carriers']) or 'none on file'}"
    )

    renewal = filing.get("renewal") or {}
    premium = filing.get("premium_estimate") or {}
    premium_mid = None
    if premium.get("estimated_current_annual_premium_low") is not None:
        premium_mid = (
            premium["estimated_current_annual_premium_low"]
            + premium["estimated_current_annual_premium_high"]
        ) / 2

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Headcount", f"{int(filing['headcount'] or 0):,}")
    c2.metric("Est. Renewal Date", renewal.get("renewal_date", "Unknown"))
    c3.metric(
        "Days Until Renewal",
        renewal.get("days_until_renewal", "—"),
        help="In broker outreach window (60-120 days out)" if renewal.get("in_outreach_window") else None,
    )
    c4.metric("Est. Annual Premium", format_currency(premium_mid))

    gaps = filing.get("coverage_gaps") or []
    if gaps:
        st.markdown(
            "**Coverage gaps vs. peers:** "
            + ", ".join(f"{g['benefit']} ({g['peer_adoption_pct']}% of peers carry it)" for g in gaps)
        )

    st.divider()

    generate = st.button("🤖 Generate Call-Prep Report with Claude", type="primary", disabled=not api_key)
    if not api_key:
        st.caption("Add an API key in the sidebar to generate a report.")

    if generate:
        with st.spinner("Asking Claude to prep the call..."):
            try:
                report = generator.generate_report(filing, api_key=api_key)
                st.session_state.report = report
                st.session_state.report_key = selected_key
            except anthropic.AuthenticationError:
                st.error("That API key was rejected. Double-check it in the sidebar.")
            except anthropic.RateLimitError:
                st.error("Rate limited by the Anthropic API. Wait a moment and try again.")
            except anthropic.APIStatusError as exc:
                st.error(f"Anthropic API error ({exc.status_code}): {exc.message}")
            except anthropic.APIConnectionError:
                st.error("Couldn't reach the Anthropic API. Check your network connection.")
            except ValueError as exc:
                st.error(f"Claude's response couldn't be parsed: {exc}")

    if st.session_state.report and st.session_state.report_key == selected_key:
        report = st.session_state.report

        label = report["urgency_label"]
        st.markdown(f"### {URGENCY_EMOJI.get(label, '⚪')} Urgency: {label} ({report['urgency_score']}/10)")

        st.success(f"**Reason to call:** {escape_markdown(report['reason_to_call'])}")
        st.markdown(f"**Renewal summary:** {escape_markdown(report['renewal_summary'])}")

        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("**Key facts**")
            for fact in report["key_facts"]:
                st.markdown(f"- {escape_markdown(fact)}")

            if report["coverage_gaps"]:
                st.markdown("**Coverage gaps**")
                for gap in report["coverage_gaps"]:
                    st.markdown(f"- {escape_markdown(gap)}")

        with col_right:
            st.markdown("**Talking points**")
            for point in report["talking_points"]:
                st.markdown(f"- {escape_markdown(point)}")

        st.markdown("**Cold call opener**")
        st.info(escape_markdown(report["cold_call_opener"]))
