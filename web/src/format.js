export function formatMoney(estimate) {
  if (!estimate) return null;
  const mid =
    (estimate.estimated_current_annual_premium_low + estimate.estimated_current_annual_premium_high) / 2;
  return "$" + Math.round(mid).toLocaleString("en-US");
}

export function isHot(daysUntilRenewal) {
  return daysUntilRenewal <= 100;
}

export function formatTimestamp(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + " " +
    d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

export function statusClass(status) {
  const map = {
    "Not Contacted": "status-not-contacted",
    Contacted: "status-contacted",
    "Meeting Scheduled": "status-meeting",
    Won: "status-won",
    Lost: "status-lost",
  };
  return map[status] || "status-not-contacted";
}
