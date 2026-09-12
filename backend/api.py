"""FastAPI backend for the Renewal Radar directory.

Serves the curated 50-company demo set (data/demo_companies.json) and wraps
backend.generator for on-demand call-prep report generation. Reports are
cached in memory per company_key so re-opening a row doesn't re-spend API
tokens on an unchanged filing.

Run from the project root:
    .venv\\Scripts\\uvicorn.exe backend.api:app --reload --port 8000
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import generator

ROOT = Path(__file__).resolve().parent.parent
DEMO_COMPANIES_PATH = ROOT / "data" / "demo_companies.json"

_companies: list[dict] = []
_companies_by_key: dict[str, dict] = {}
_report_cache: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    data = json.loads(DEMO_COMPANIES_PATH.read_text(encoding="utf-8"))
    _companies[:] = data
    _companies_by_key.clear()
    _companies_by_key.update({c["company_key"]: c for c in data})
    yield


app = FastAPI(title="Renewal Radar API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReportRequest(BaseModel):
    api_key: str | None = None
    force: bool = False


@app.get("/api/companies")
def list_companies():
    return _companies


@app.get("/api/companies/{company_key}")
def get_company(company_key: str):
    company = _companies_by_key.get(company_key)
    if company is None:
        raise HTTPException(status_code=404, detail=f"No company with key {company_key!r}")
    return company


@app.post("/api/companies/{company_key}/report")
def run_caller_report(company_key: str, req: ReportRequest = ReportRequest()):
    company = _companies_by_key.get(company_key)
    if company is None:
        raise HTTPException(status_code=404, detail=f"No company with key {company_key!r}")

    if not req.force and company_key in _report_cache:
        return {"cached": True, **_report_cache[company_key]}

    try:
        report = generator.generate_report(company, api_key=req.api_key)
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid Anthropic API key.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Rate limited by the Anthropic API. Try again shortly.")
    except anthropic.APIConnectionError:
        raise HTTPException(status_code=502, detail="Could not reach the Anthropic API.")
    except anthropic.APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {exc.message}")
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Claude response could not be parsed: {exc}")

    _report_cache[company_key] = report
    return {"cached": False, **report}
