import { useMemo, useState } from "react";
import { formatMoney, isHot } from "../format";

const COLUMNS = [
  { key: "sponsor_name", label: "Company" },
  { key: "state", label: "Location" },
  { key: "phone", label: "Phone" },
  { key: "headcount", label: "Headcount" },
  { key: "size_bucket", label: "Size Bucket" },
  { key: "renewal_date", label: "Renewal Date" },
  { key: "days_until_renewal", label: "Days Until" },
  { key: "gaps", label: "Coverage Gaps" },
  { key: "premium", label: "Est. Annual Premium" },
];

function toRow(company) {
  return {
    company_key: company.company_key,
    sponsor_name: company.sponsor_name,
    state: company.state,
    city: company.city,
    phone: company.phone || "—",
    headcount: company.headcount || 0,
    size_bucket: company.size_bucket,
    renewal_date: company.renewal.renewal_date,
    days_until_renewal: company.renewal.days_until_renewal,
    gaps: company.coverage_gaps.length,
    gap_labels: company.coverage_gaps.map((g) => g.benefit).join(", "),
    premium: formatMoney(company.premium_estimate),
  };
}

export default function ProspectTable({ companies, onSelect, onSendPerk }) {
  const [sortKey, setSortKey] = useState("days_until_renewal");
  const [sortDir, setSortDir] = useState(1);

  const rows = useMemo(() => companies.map(toRow), [companies]);

  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string") return av.localeCompare(bv) * sortDir;
      return (av - bv) * sortDir;
    });
  }, [rows, sortKey, sortDir]);

  function handleSort(key) {
    if (key === sortKey) {
      setSortDir((d) => d * -1);
    } else {
      setSortKey(key);
      setSortDir(1);
    }
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={col.key === sortKey ? "sorted" : ""}
                data-arrow={sortDir === 1 ? "↑" : "↓"}
                onClick={() => handleSort(col.key)}
              >
                {col.label}
              </th>
            ))}
            <th className="no-sort">Rewards / Perks</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr
              key={r.company_key}
              className={isHot(r.days_until_renewal) ? "hot" : ""}
              onClick={() => onSelect(r.company_key)}
            >
              <td className="company wrap">{r.sponsor_name}</td>
              <td className="loc">
                {r.city}, {r.state}
              </td>
              <td className="mono">{r.phone}</td>
              <td className="mono">{r.headcount.toLocaleString("en-US")}</td>
              <td>{r.size_bucket}</td>
              <td className="mono">{r.renewal_date}</td>
              <td className="mono">
                <span className={`badge ${isHot(r.days_until_renewal) ? "hot" : ""}`}>
                  {r.days_until_renewal}d
                </span>
              </td>
              <td className="wrap" title={r.gap_labels}>
                {r.gaps ? `${r.gaps} – ${r.gap_labels}` : "—"}
              </td>
              <td className="mono">
                {r.premium ? r.premium : <span className="na">no premium on file</span>}
              </td>
              <td onClick={(e) => e.stopPropagation()}>
                <button className="perk-btn" onClick={() => onSendPerk(r.company_key)}>
                  🎁 Send Perk
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
