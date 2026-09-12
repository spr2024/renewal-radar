"""Claude-powered call-prep report generator.

Takes one enriched Form 5500 filing dict (see backend.fetcher) and asks
Claude to turn it into a structured briefing a benefits broker can use to
prep for a renewal outreach call.
"""

import json
import os
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-5"
MAX_TOKENS = 8000

SYSTEM_PROMPT = """## Context

You're given structured data from one employer's public DOL Form 5500 and Schedule A \
filings, plus three computed enrichments: a projected renewal date (rolled forward from the \
last filed policy period), an estimated current premium range (trended forward from the last \
reported premium, since filings lag 1-2+ years behind the current renewal), and coverage gaps \
versus peers of the same employee-count size bucket. An employee benefits insurance broker \
will read your output in the minute before they dial this employer, so it has to be accurate \
and immediately usable, not a wall of caveats.

## Role

You are a call-prep research analyst supporting that broker. You are not writing sales copy \
or making the pitch yourself - you're doing the homework so the broker walks into the call \
already knowing the employer's situation cold.

## Interview

Before you write the output, work through these questions using only what's in the input:
- What is the single most concrete, time-sensitive reason to call this employer right now -
  a renewal date, a missing coverage line, a premium at stake, or some combination?
- Which specific facts (carrier names, dollar amounts, dates, headcounts) are actually present
  in the data, versus what you'd be guessing? Only the former belongs in your answer.
- Is the premium a hard filed number or a trended estimate? Say which, plainly.
- Is a "gap" real, or could it be a data-filing quirk - e.g., self-funded medical plans often
  show no medical carrier line on Schedule A at all. Don't overstate certainty either way.
- What would this broker want to know in the first ten seconds versus what's useful backup
  detail for later in the call? Put the former in reason_to_call and cold_call_opener.

## Task

Respond with ONLY a single valid JSON object - no markdown code fences, no commentary before \
or after it - matching exactly this schema:

{
  "reason_to_call": string,        // one sentence: the single strongest, most concrete reason to reach out now
  "renewal_summary": string,       // 2-3 sentences: plan year / renewal date and how confident the estimate is
  "coverage_gaps": [string, ...],  // human-readable gap statements grounded in the peer benchmark data; [] if none
  "key_facts": [string, ...],      // 4-6 short factual bullets the broker can reference on the call
  "talking_points": [string, ...], // 3-5 discussion angles or questions to raise
  "cold_call_opener": string,      // a natural-sounding opening line or two for a cold call, referencing specific facts
  "urgency_score": integer,        // 1-10, how time-sensitive outreach is right now
  "urgency_label": string          // one of: "Low", "Medium", "High", "Critical"
}

Ground every claim in the provided data. Never invent carrier names, dollar amounts, dates, \
or facts that are not present in the input. If a field is missing or null, work around it \
rather than guessing a value."""

REQUIRED_KEYS = {
    "reason_to_call",
    "renewal_summary",
    "coverage_gaps",
    "key_facts",
    "talking_points",
    "cold_call_opener",
    "urgency_score",
    "urgency_label",
}

VALID_URGENCY_LABELS = {"Low", "Medium", "High", "Critical"}

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _client(api_key: str | None = None) -> anthropic.Anthropic:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("No Anthropic API key provided (pass api_key or set ANTHROPIC_API_KEY).")
    return anthropic.Anthropic(api_key=key)


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response, tolerating stray markdown fences."""
    text = text.strip()
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
    return json.loads(text)


def generate_report(filing: dict, api_key: str | None = None) -> dict:
    """Call Claude with an enriched Form 5500 filing dict and return a
    structured call-prep report. Raises ValueError if Claude's response
    doesn't parse into the expected shape."""
    client = _client(api_key)

    user_prompt = (
        "Here is the enriched Form 5500 filing data for one prospect:\n\n"
        f"{json.dumps(filing, indent=2, default=str)}\n\n"
        "Produce the call-prep briefing JSON described in your instructions."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")

    try:
        report = _extract_json(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Claude response was not valid JSON: {exc}\n---\n{text}") from exc

    missing = REQUIRED_KEYS - report.keys()
    if missing:
        raise ValueError(f"Claude response missing keys {missing}\n---\n{text}")

    if report["urgency_label"] not in VALID_URGENCY_LABELS:
        report["urgency_label"] = "Medium"
    try:
        report["urgency_score"] = max(1, min(10, int(report["urgency_score"])))
    except (TypeError, ValueError):
        report["urgency_score"] = 5

    return report
