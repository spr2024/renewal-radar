"""FastAPI backend for the Renewal Radar directory.

Serves the curated 50-company demo set (data/demo_companies.json) and wraps
backend.generator for on-demand call-prep report generation. Reports are
cached in memory per company_key so re-opening a row doesn't re-spend API
tokens on an unchanged filing.

Run from the project root:
    .venv\\Scripts\\uvicorn.exe backend.api:app --reload --port 8000
"""

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import generator

ROOT = Path(__file__).resolve().parent.parent
DEMO_COMPANIES_PATH = ROOT / "data" / "demo_companies.json"
STATUS_PATH = ROOT / "data" / "company_status.json"

DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
_extra_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
ALLOWED_ORIGINS = DEFAULT_ORIGINS + _extra_origins

STATUS_OPTIONS = ["Not Contacted", "Contacted", "Meeting Scheduled", "Won", "Lost"]
DEFAULT_STATUS = STATUS_OPTIONS[0]

_companies: list[dict] = []
_companies_by_key: dict[str, dict] = {}
_report_cache: dict[str, dict] = {}
_statuses: dict[str, dict] = {}


def _load_statuses() -> dict[str, dict]:
    if STATUS_PATH.exists():
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    return {}


def _save_statuses() -> None:
    STATUS_PATH.write_text(json.dumps(_statuses, indent=2), encoding="utf-8")


def _apply_status(company: dict) -> dict:
    entry = _statuses.get(company["company_key"], {})
    return {
        **company,
        "status": entry.get("status", DEFAULT_STATUS),
        "status_updated_at": entry.get("updated_at"),
        "notes": entry.get("notes", ""),
    }


def _update_tracking(company_key: str, **fields) -> dict:
    """Merge the given fields into a company's tracking entry (status and/or
    notes), stamp the update time, persist, and return the merged company."""
    entry = dict(_statuses.get(company_key, {}))
    entry.update(fields)
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _statuses[company_key] = entry
    _save_statuses()
    return _apply_status(_companies_by_key[company_key])


@asynccontextmanager
async def lifespan(app: FastAPI):
    data = json.loads(DEMO_COMPANIES_PATH.read_text(encoding="utf-8"))
    _companies[:] = data
    _companies_by_key.clear()
    _companies_by_key.update({c["company_key"]: c for c in data})
    _statuses.clear()
    _statuses.update(_load_statuses())
    yield


app = FastAPI(title="Renewal Radar API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReportRequest(BaseModel):
    api_key: str | None = None
    force: bool = False


class StatusUpdateRequest(BaseModel):
    status: str


class NotesUpdateRequest(BaseModel):
    notes: str


@app.get("/api/status-options")
def get_status_options():
    return STATUS_OPTIONS


@app.get("/api/companies")
def list_companies():
    return [_apply_status(c) for c in _companies]


@app.get("/api/companies/{company_key}")
def get_company(company_key: str):
    company = _companies_by_key.get(company_key)
    if company is None:
        raise HTTPException(status_code=404, detail=f"No company with key {company_key!r}")
    return _apply_status(company)


@app.patch("/api/companies/{company_key}/status")
def update_status(company_key: str, req: StatusUpdateRequest):
    if company_key not in _companies_by_key:
        raise HTTPException(status_code=404, detail=f"No company with key {company_key!r}")
    if req.status not in STATUS_OPTIONS:
        raise HTTPException(
            status_code=422, detail=f"status must be one of {STATUS_OPTIONS}, got {req.status!r}"
        )
    return _update_tracking(company_key, status=req.status)


@app.patch("/api/companies/{company_key}/notes")
def update_notes(company_key: str, req: NotesUpdateRequest):
    if company_key not in _companies_by_key:
        raise HTTPException(status_code=404, detail=f"No company with key {company_key!r}")
    return _update_tracking(company_key, notes=req.notes)


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
