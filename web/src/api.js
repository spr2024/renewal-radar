const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function fetchCompanies() {
  const res = await fetch(`${API_BASE}/api/companies`);
  if (!res.ok) throw new Error(`Failed to load companies (${res.status})`);
  return res.json();
}

export async function fetchStatusOptions() {
  const res = await fetch(`${API_BASE}/api/status-options`);
  if (!res.ok) throw new Error(`Failed to load status options (${res.status})`);
  return res.json();
}

export async function updateCompanyStatus(companyKey, status) {
  const res = await fetch(`${API_BASE}/api/companies/${companyKey}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Status update failed (${res.status})`);
  }
  return res.json();
}

export async function updateCompanyNotes(companyKey, notes) {
  const res = await fetch(`${API_BASE}/api/companies/${companyKey}/notes`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Notes update failed (${res.status})`);
  }
  return res.json();
}

export async function runCallerReport(companyKey) {
  const res = await fetch(`${API_BASE}/api/companies/${companyKey}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Report generation failed (${res.status})`);
  }
  return res.json();
}
