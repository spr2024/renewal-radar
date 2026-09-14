import { useState } from "react";

function FunnelIcon({ active }) {
  return (
    <svg viewBox="0 0 10 10" width="10" height="10" className={`filter-icon ${active ? "active" : ""}`}>
      <path d="M0 0 H10 L6.2 4.6 V9 L3.8 10 V4.6 Z" />
    </svg>
  );
}

export default function ColumnFilter({ values, selected, isOpen, onToggleOpen, onChange }) {
  const [search, setSearch] = useState("");

  const isActive = selected.size < values.length;
  const visible = values.filter((v) => v.toLowerCase().includes(search.toLowerCase()));

  function toggleValue(v) {
    const next = new Set(selected);
    if (next.has(v)) next.delete(v);
    else next.add(v);
    onChange(next);
  }

  return (
    <span className="filter-wrap" onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        className="filter-btn"
        aria-label="Filter"
        onClick={(e) => {
          e.stopPropagation();
          onToggleOpen();
        }}
      >
        <FunnelIcon active={isActive} />
      </button>
      {isOpen && (
        <div className="filter-dropdown" onClick={(e) => e.stopPropagation()}>
          <input
            type="text"
            className="filter-search"
            placeholder="Search…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
          />
          <div className="filter-actions">
            <button type="button" onClick={() => onChange(new Set(values))}>
              Select all
            </button>
            <button type="button" onClick={() => onChange(new Set())}>
              Clear
            </button>
          </div>
          <div className="filter-options">
            {visible.map((v) => (
              <label key={v} className="filter-option">
                <input type="checkbox" checked={selected.has(v)} onChange={() => toggleValue(v)} />
                <span>{v === "" ? "(blank)" : v}</span>
              </label>
            ))}
            {visible.length === 0 && <div className="filter-empty">No matches</div>}
          </div>
        </div>
      )}
    </span>
  );
}
