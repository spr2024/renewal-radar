export function formatMoney(estimate) {
  if (!estimate) return null;
  const mid =
    (estimate.estimated_current_annual_premium_low + estimate.estimated_current_annual_premium_high) / 2;
  return "$" + Math.round(mid).toLocaleString("en-US");
}

export function isHot(daysUntilRenewal) {
  return daysUntilRenewal <= 100;
}
