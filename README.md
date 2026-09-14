# Renewal Radar

A prospecting tool for employee benefits brokers: it turns public DOL Form 5500 /
Schedule A filings into a directory of renewal opportunities, then uses Claude to
generate a call-prep briefing for each one a reason to call, the renewal timing,
coverage gaps versus peers, and a cold-call opener, grounded entirely in the filed
data.

Built in a single hackathon session. Backend is Python/FastAPI, frontend is
React/Vite, and the call-prep reports are generated live by the Anthropic API —
nothing in the report content is templated or hand-written.

## What it does

- **Prospect Ledger** — a directory of real, single-employer DOL filers (mid-size,
  250–4,999 employees; multi-employer trusts, union welfare funds, and mega-corps
  filtered out), with KPI cards, sortable columns, and a spreadsheet-style filter
  (search + checkbox list of distinct values) on every column.
- **Renewal window projection** — rolls each company's most recent Schedule A
  policy period (or plan-year-end, if no dated coverage line exists) forward to
  the next future renewal date.
- **Premium estimate** — trends the last reported premium forward at a standard
  rate, since Form 5500 filings lag 1–2+ years behind the current renewal.
- **Coverage gap detection** — compares an employer's filed benefit lines against
  peer adoption rates for companies of the same size bucket.
- **Claude-generated call-prep report** — click a row, hit "Run Caller Report,"
  and get a structured briefing (reason to call, renewal summary, coverage gaps,
  key facts, talking points, cold-call opener, urgency score) generated live from
  that company's actual filing data.
- **Status + notes tracking** — a lightweight pipeline (Not Contacted → Contacted
  → Meeting Scheduled → Won/Lost) plus a free-text notes column, persisted
  server-side.
- **Rewards/Perks** — a UI demo of a "send a gift card" outreach incentive.
  **This is a mockup.** No real gift card is issued or charged; it's a clearly
  labeled, non-functional prototype of the interaction.

## Architecture

```
data/raw/, data/processed/   Bulk DOL Form 5500 + Schedule A extracts and the
                              SQLite DB built from them (gitignored - see below)
backend/fetcher.py            Search + enrichment logic against the SQLite DB
                              (renewal window, premium estimate, coverage gaps)
backend/generator.py          Claude API call: turns one enriched filing into
                              the structured call-prep report
backend/api.py                FastAPI app: serves the curated demo set, the
                              report endpoint, and status/notes tracking
web/                          React (Vite) frontend
data/demo_companies.json      The 50-company curated demo set the app actually
                              serves (committed - the app runs without the raw
                              DOL data or the SQLite DB)
data/golden_set.json          5 hand-built eval cases with grounding/urgency
                              rubrics for backend.generator
scripts/run_evals.py          Scores live generator output against the golden set
scripts/build_db.py           One-time ETL: raw DOL CSVs -> SQLite DB
scripts/build_demo_set.py     Curates the 50-company demo set from the DB
```

## Running it locally

You only need `data/demo_companies.json` (already committed) to run the app —
the raw DOL bulk data and the SQLite database it's built from are **not**
required unless you want to search the full ~66,000-company dataset yourself
(see "Rebuilding the full dataset" below).

**1. Backend**

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your own Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Then start the API:

```
.venv\Scripts\uvicorn backend.api:app --port 8000
```

**2. Frontend**

```
cd web
npm install
npm run dev
```

Open the URL Vite prints (typically `http://localhost:5173`). The frontend talks
to the backend at `http://localhost:8000` by default — override with a
`VITE_API_BASE_URL` env var if you're running the backend elsewhere.

## Rebuilding the full dataset (optional)

The curated 50-company demo set is a filtered sample of a larger local pipeline
built from DOL's public bulk data releases. To rebuild it from scratch:

1. Download the Form 5500 and Schedule A bulk CSV extracts from
   [DOL EBSA's public researcher data page](https://www.dol.gov/agencies/ebsa/researchers/data)
   into `data/raw/`.
2. `.venv\Scripts\python scripts\build_db.py` — builds `data/processed/form5500.db`
   (companies, coverage lines, peer benchmarks) from the raw CSVs.
3. `.venv\Scripts\python scripts\build_demo_set.py` — re-curates the 50-company
   demo set (filters out trusts/unions/mega-corps, picks a diverse sample,
   enriches each with renewal/premium/gap data) into `data/demo_companies.json`.

## The Claude integration

`backend/generator.py` calls `claude-sonnet-5` with a system prompt structured
around **Context, Role, Interview, Task**: it establishes what the data is and
who it's for, gives Claude a checklist of questions to reason through before
answering (what's the strongest reason to call, which facts are actually in the
data versus inferred, is a "gap" real or a filing quirk), then specifies the
exact JSON schema to return. Every claim is required to be grounded in the
input — the model is explicitly instructed never to invent carrier names,
dollar amounts, or dates not present in the filing.

## Evals

`data/golden_set.json` has 5 hand-built scenarios (a mix of urgent/not-urgent,
gap-heavy/gap-free, with/without a premium estimate), each with a rubric:
required keyword grounding, a hallucination guard (carriers that must *not*
appear, since they're not in that filing), and urgency bounds. Run it with:

```
.venv\Scripts\python scripts\run_evals.py
```

This calls the live Anthropic API (small real cost) and scores the actual
output — it's what caught a token-truncation bug during development and
validated that a prompt rewrite didn't regress grounding or urgency
calibration.

## Known limitations

This is a hackathon prototype, not a finished product. Notably:

- No authentication, multi-user support, or manager/team views.
- Peer benchmarking is by employee-count size bucket only — not filtered by
  industry (NAICS code), so a 300-person restaurant and a 300-person law firm
  are currently benchmarked against the same peer group.
- No PDF export, CSV export, or CRM integration.
- The "reason to call" is LLM-generated reasoning over the raw filing data,
  not a deterministic rule-based signal engine — it's often specific and
  well-grounded, but not guaranteed reproducible the way a fixed-threshold
  system would be.
- The directory is a fixed, curated 50-company sample, not a live search
  across the full dataset.
