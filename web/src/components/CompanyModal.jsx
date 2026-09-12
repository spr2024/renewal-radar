import { useEffect, useState } from "react";
import { formatMoney } from "../format";
import { runCallerReport } from "../api";

const URGENCY_CLASS = { Low: "u-low", Medium: "u-medium", High: "u-high", Critical: "u-critical" };

function FactsGrid({ filing }) {
  const premium = formatMoney(filing.premium_estimate);
  return (
    <div className="fact-grid">
      <div>
        <div className="fact-label">Location</div>
        <div className="fact-value">
          {filing.city}, {filing.state}
        </div>
      </div>
      <div>
        <div className="fact-label">Phone</div>
        <div className="fact-value">{filing.phone || "—"}</div>
      </div>
      <div>
        <div className="fact-label">Headcount</div>
        <div className="fact-value">
          {(filing.headcount || 0).toLocaleString("en-US")} ({filing.size_bucket})
        </div>
      </div>
      <div>
        <div className="fact-label">Renewal date</div>
        <div className="fact-value">
          {filing.renewal.renewal_date} ({filing.renewal.days_until_renewal}d)
        </div>
      </div>
      <div>
        <div className="fact-label">Carriers</div>
        <div className="fact-value">
          {filing.carriers.length ? filing.carriers.join(", ") : "none on file"}
        </div>
      </div>
      <div>
        <div className="fact-label">Est. premium</div>
        <div className="fact-value">{premium || "no premium on file"}</div>
      </div>
    </div>
  );
}

function ReportView({ report }) {
  const uClass = URGENCY_CLASS[report.urgency_label] || "u-medium";
  return (
    <>
      <div className="urgency-line">
        <span className={`u-label ${uClass}`}>{report.urgency_label} urgency</span>
        <span className="u-score">{report.urgency_score}/10</span>
      </div>
      <div className="reason-box">
        <strong>Reason to call:</strong> {report.reason_to_call}
      </div>
      <div className="report-section">
        <h3>Renewal summary</h3>
        <p>{report.renewal_summary}</p>
      </div>
      {report.coverage_gaps.length > 0 && (
        <div className="report-section">
          <h3>Coverage gaps</h3>
          <ul>
            {report.coverage_gaps.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="report-section">
        <h3>Key facts</h3>
        <ul>
          {report.key_facts.map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      </div>
      <div className="report-section">
        <h3>Talking points</h3>
        <ul>
          {report.talking_points.map((t, i) => (
            <li key={i}>{t}</li>
          ))}
        </ul>
      </div>
      <div className="report-section">
        <h3>Cold call opener</h3>
        <div className="opener-box">{report.cold_call_opener}</div>
      </div>
    </>
  );
}

export default function CompanyModal({ filing, onClose }) {
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    function handleKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  async function handleRunReport() {
    setStatus("loading");
    setError(null);
    try {
      const result = await runCallerReport(filing.company_key);
      setReport(result);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
        <button className="modal-close" aria-label="Close" onClick={onClose}>
          &times;
        </button>
        <h2 id="modalTitle">{filing.sponsor_name}</h2>
        <p className="modal-sub">
          {filing.num_plans} plan(s) on file &middot; latest filing {filing.latest_filing_date}
        </p>
        <FactsGrid filing={filing} />

        {status === "idle" && (
          <button className="run-btn" onClick={handleRunReport}>
            📞 Run Caller Report
          </button>
        )}
        {status === "loading" && (
          <button className="run-btn" disabled>
            Generating…
          </button>
        )}
        {status === "error" && (
          <>
            <div className="no-report-note error">Couldn't generate a report: {error}</div>
            <button className="run-btn" onClick={handleRunReport}>
              Try again
            </button>
          </>
        )}
        {status === "done" && report && <ReportView report={report} />}
      </div>
    </div>
  );
}
