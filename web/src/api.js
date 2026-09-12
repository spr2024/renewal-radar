const API_BASE = "http://localhost:8000";

export async function fetchCompanies() {
  const res = await fetch(`${API_BASE}/api/companies`);
  if (!res.ok) throw new Error(`Failed to load companies (${res.status})`);
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
