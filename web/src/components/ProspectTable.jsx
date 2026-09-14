import { useEffect, useMemo, useState } from "react";
import { formatMoney, formatTimestamp, isHot, statusClass } from "../format";
import ColumnFilter from "./ColumnFilter";

const COLUMNS = [
  { key: "sponsor_name", label: "Company" },
  { key: "status", label: "Status" },
  { key: "status_updated_at", label: "Last Updated" },
  { key: "state", label: "Location" },
  { key: "phone", label: "Phone" },
  { key: "headcount", label: "Headcount" },
  { key: "size_bucket", label: "Size Bucket" },
  { key: "renewal_date", label: "Renewal Date" },
  { key: "days_until_renewal", label: "Days Until" },
  { key: "gaps", label: "Coverage Gaps" },
  { key: "premium", label: "Est. Annual Premium" },
];

// Notes is rendered separately (kept at the very end of the row), but still
// needs a filter, so its key joins this list for filter bookkeeping.
const FILTER_KEYS = [...COLUMNS.map((c) => c.key), "notes"];

function toRow(company) {
  return {
    company_key: company.company_key,
    sponsor_name: company.sponsor_name,
    status: company.status,
    status_updated_at: company.status_updated_at || "",
    notes: company.notes || "",
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

function getFilterValue(row, key) {
  switch (key) {
    case "status_updated_at":
      return formatTimestamp(row.status_updated_at) === "—" ? "" : formatTimestamp(row.status_updated_at);
    case "headcount":
      return row.headcount.toLocaleString("en-US");
    case "days_until_renewal":
      return `${row.days_until_renewal}d`;
    case "gaps":
      return String(row.gaps);
    case "premium":
      return row.premium || "no premium on file";
    default:
      return String(row[key] ?? "");
  }
}

export default function ProspectTable({
  companies,
  statusOptions,
  onSelect,
  onSendPerk,
  onStatusChange,
  onNotesChange,
}) {
  const [sortKey, setSortKey] = useState("days_until_renewal");
  const [sortDir, setSortDir] = useState(1);
  const [filters, setFilters] = useState({});
  const [openFilterKey, setOpenFilterKey] = useState(null);

  const rows = useMemo(() => companies.map(toRow), [companies]);

  const distinctValues = useMemo(() => {
    const map = {};
    for (const key of FILTER_KEYS) {
      map[key] = [...new Set(rows.map((r) => getFilterValue(r, key)))].sort();
    }
    return map;
  }, [rows]);

  useEffect(() => {
    function closeOnOutsideClick() {
      setOpenFilterKey(null);
    }
    document.addEventListener("click", closeOnOutsideClick);
    return () => document.removeEventListener("click", closeOnOutsideClick);
  }, []);

  const filtered = useMemo(() => {
    return rows.filter((r) =>
      FILTER_KEYS.every((key) => {
        const selected = filters[key];
        if (!selected) return true;
        return selected.has(getFilterValue(r, key));
      })
    );
  }, [rows, filters]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string") return av.localeCompare(bv) * sortDir;
      return (av - bv) * sortDir;
    });
  }, [filtered, sortKey, sortDir]);

  function handleSort(key) {
    if (key === sortKey) {
      setSortDir((d) => d * -1);
    } else {
      setSortKey(key);
      setSortDir(1);
    }
  }

  function selectedFor(key) {
    return filters[key] || new Set(distinctValues[key] || []);
  }

  function handleFilterChange(key, nextSet) {
    setFilters((f) => {
      const all = distinctValues[key] || [];
      const next = { ...f };
      if (nextSet.size >= all.length) delete next[key];
      else next[key] = nextSet;
      return next;
    });
  }

  const activeFilterCount = Object.keys(filters).length;

  function renderFilter(key) {
    return (
      <ColumnFilter
        values={distinctValues[key] || []}
        selected={selectedFor(key)}
        isOpen={openFilterKey === key}
        onToggleOpen={() => setOpenFilterKey((k) => (k === key ? null : key))}
        onChange={(next) => handleFilterChange(key, next)}
      />
    );
  }

  return (
    <div>
      {activeFilterCount > 0 && (
        <div className="filter-summary">
          {activeFilterCount} filter{activeFilterCount > 1 ? "s" : ""} active &middot;{" "}
          <button type="button" className="filter-clear-all" onClick={() => setFilters({})}>
            Clear all
          </button>
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <th key={col.key}>
                  <span className="th-content">
                    <span
                      className={`th-label ${col.key === sortKey ? "sorted" : ""}`}
                      data-arrow={sortDir === 1 ? "↑" : "↓"}
                      onClick={() => handleSort(col.key)}
                    >
                      {col.label}
                    </span>
                    {renderFilter(col.key)}
                  </span>
                </th>
              ))}
              <th className="no-sort">Rewards / Perks</th>
              <th className="no-sort">
                <span className="th-content">
                  <span className="th-label">Notes</span>
                  {renderFilter("notes")}
                </span>
              </th>
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
                <td onClick={(e) => e.stopPropagation()}>
                  <select
                    className={`status-select ${statusClass(r.status)}`}
                    value={r.status}
                    onChange={(e) => onStatusChange(r.company_key, e.target.value)}
                  >
                    {statusOptions.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="mono loc">{formatTimestamp(r.status_updated_at)}</td>
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
                <td onClick={(e) => e.stopPropagation()}>
                  <input
                    type="text"
                    className="notes-input"
                    defaultValue={r.notes}
                    placeholder="Add note…"
                    onBlur={(e) => {
                      if (e.target.value !== r.notes) onNotesChange(r.company_key, e.target.value);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") e.target.blur();
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {sorted.length === 0 && (
          <div className="filter-no-results">No prospects match the current filters.</div>
        )}
      </div>
    </div>
  );
}
