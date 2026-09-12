import { useEffect, useState } from "react";
import KpiRow from "./components/KpiRow";
import ProspectTable from "./components/ProspectTable";
import CompanyModal from "./components/CompanyModal";
import PerksModal from "./components/PerksModal";
import { fetchCompanies } from "./api";

export default function App() {
  const [companies, setCompanies] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);
  const [selectedKey, setSelectedKey] = useState(null);
  const [perksKey, setPerksKey] = useState(null);

  useEffect(() => {
    fetchCompanies()
      .then((data) => {
        setCompanies(data);
        setStatus("ready");
      })
      .catch((err) => {
        setError(err.message);
        setStatus("error");
      });
  }, []);

  const selected = companies.find((c) => c.company_key === selectedKey) || null;
  const perksTarget = companies.find((c) => c.company_key === perksKey) || null;

  return (
    <>
      <header>
        <p className="eyebrow">Renewal Radar &middot; Broker Directory</p>
        <h1>Prospect Ledger</h1>
        <p>
          Real, single-employer DOL Form&nbsp;5500 filers, mid-size (250&ndash;4,999 employees),
          with multi-employer trusts, union welfare funds, and mega-corporations filtered out.
          Click a row to pull up call-prep facts and generate a Claude briefing.
        </p>
      </header>

      {status === "loading" && <p className="status-note">Loading prospects…</p>}
      {status === "error" && (
        <p className="status-note error">
          Couldn't load the directory: {error}. Is the API running at localhost:8000?
        </p>
      )}

      {status === "ready" && (
        <>
          <KpiRow companies={companies} />

          <div className="legend">
            <span className="swatch">
              <span className="dot" /> Renewing within 100 days
            </span>
            <span>Click a column header to sort &middot; click a row for details</span>
          </div>

          <ProspectTable companies={companies} onSelect={setSelectedKey} onSendPerk={setPerksKey} />

          <footer>
            <strong>Data notes:</strong> Renewal dates are projected from each company's most
            recent Schedule&nbsp;A policy period (or plan-year-end when no dated coverage line
            exists) rolled forward to the next future anniversary from today. Premium estimates
            require reported earned-premium figures on Schedule&nbsp;A, which aren't present for
            every filer &mdash; those show "no premium on file" rather than a guessed number.
            Coverage-gap counts compare each company's filed benefit lines against peer adoption
            rates for its size bucket.
          </footer>
        </>
      )}

      {selected && <CompanyModal filing={selected} onClose={() => setSelectedKey(null)} />}
      {perksTarget && <PerksModal filing={perksTarget} onClose={() => setPerksKey(null)} />}
    </>
  );
}
