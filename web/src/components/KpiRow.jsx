import { formatMoney, isHot } from "../format";

export default function KpiRow({ companies }) {
  const total = companies.length;
  const hotCount = companies.filter((c) => isHot(c.renewal.days_until_renewal)).length;
  const gapCount = companies.filter((c) => c.coverage_gaps.length > 0).length;
  const premiumCount = companies.filter((c) => formatMoney(c.premium_estimate)).length;

  return (
    <section className="kpi-row">
      <div className="kpi">
        <div className="value">{total}</div>
        <div className="label">Prospects in this set</div>
      </div>
      <div className="kpi warn-tile">
        <div className="value">{hotCount}</div>
        <div className="label">Renewing within 100 days</div>
      </div>
      <div className="kpi">
        <div className="value">{gapCount}</div>
        <div className="label">Have at least one coverage gap</div>
      </div>
      <div className="kpi">
        <div className="value">
          {premiumCount}/{total}
        </div>
        <div className="label">Have a premium estimate on file</div>
      </div>
    </section>
  );
}
