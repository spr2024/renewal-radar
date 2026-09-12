"""Score backend.generator.generate_report() against data/golden_set.json.

Each golden case pairs a fixed, pre-enriched filing with a rubric: keyword
grounding checks (must_mention_all/any), a hallucination guardrail
(forbidden_terms - carriers not present in that filing), urgency bounds, and
list-length sanity checks (min_items/max_items). This is deterministic
string/number scoring, not an LLM judge - cheap to run and good at catching
schema drift or fabricated facts.

Usage:
    .venv\\Scripts\\python.exe scripts\\run_evals.py
    .venv\\Scripts\\python.exe scripts\\run_evals.py --case case-01-imminent-renewal-dental-gap
    .venv\\Scripts\\python.exe scripts\\run_evals.py --verbose
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import generator  # noqa: E402

GOLDEN_SET_PATH = ROOT / "data" / "golden_set.json"


def _report_text(report: dict) -> str:
    """Flatten a generated report's free-text fields into one lowercase
    string for substring checks."""
    parts = [
        report.get("reason_to_call", ""),
        report.get("renewal_summary", ""),
        report.get("cold_call_opener", ""),
        " ".join(report.get("coverage_gaps", [])),
        " ".join(report.get("key_facts", [])),
        " ".join(report.get("talking_points", [])),
    ]
    return " ".join(parts).lower()


def score_case(case: dict, report: dict) -> list[tuple[str, bool]]:
    expected = case["expected"]
    text = _report_text(report)
    checks = []

    for term in expected.get("must_mention_all", []):
        checks.append((f"must mention {term!r}", term.lower() in text))

    any_terms = expected.get("must_mention_any", [])
    if any_terms:
        checks.append((f"must mention one of {any_terms}", any(t.lower() in text for t in any_terms)))

    for term in expected.get("forbidden_terms", []):
        checks.append((f"must not mention {term!r} (hallucination guard)", term.lower() not in text))

    if "urgency_score_min" in expected:
        min_score = expected["urgency_score_min"]
        checks.append((f"urgency_score >= {min_score}", report.get("urgency_score", 0) >= min_score))
    if "urgency_score_max" in expected:
        max_score = expected["urgency_score_max"]
        checks.append((f"urgency_score <= {max_score}", report.get("urgency_score", 99) <= max_score))

    if "urgency_label_in" in expected:
        allowed = expected["urgency_label_in"]
        checks.append((f"urgency_label in {allowed}", report.get("urgency_label") in allowed))

    for field, max_len in expected.get("max_items", {}).items():
        actual_len = len(report.get(field, []) or [])
        checks.append((f"len({field}) <= {max_len}", actual_len <= max_len))

    for field, min_len in expected.get("min_items", {}).items():
        actual_len = len(report.get(field, []) or [])
        checks.append((f"len({field}) >= {min_len}", actual_len >= min_len))

    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", help="Run only the case with this id")
    parser.add_argument("--verbose", action="store_true", help="Print the full generated report JSON per case")
    args = parser.parse_args()

    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    cases = golden["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"No case with id {args.case!r}")
            sys.exit(1)

    total_passed = 0
    total_checks = 0
    error_count = 0

    for case in cases:
        print(f"\n=== {case['id']} ===")
        if case.get("description"):
            print(case["description"])

        try:
            report = generator.generate_report(case["filing"])
        except Exception as exc:
            print(f"  ERROR generating report: {exc}")
            error_count += 1
            continue

        checks = score_case(case, report)
        passed = sum(1 for _, ok in checks if ok)
        total_passed += passed
        total_checks += len(checks)

        print(f"  urgency: {report.get('urgency_score')} ({report.get('urgency_label')})")
        for label, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

        if args.verbose:
            print(json.dumps(report, indent=2))

    print("\n=== Summary ===")
    print(f"Cases run: {len(cases)}  |  Errors: {error_count}")
    if total_checks:
        pct = 100 * total_passed / total_checks
        print(f"Checks passed: {total_passed}/{total_checks} ({pct:.0f}%)")

    if error_count or (total_checks and total_passed < total_checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
