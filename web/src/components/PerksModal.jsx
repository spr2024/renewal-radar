import { useEffect, useState } from "react";

const AMOUNTS = [10, 25, 50];

export default function PerksModal({ filing, onClose }) {
  const [amount, setAmount] = useState(25);
  const [recipient, setRecipient] = useState("");
  const [sent, setSent] = useState(false);

  useEffect(() => {
    function handleKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal perks-modal" role="dialog" aria-modal="true" aria-labelledby="perksTitle">
        <button className="modal-close" aria-label="Close" onClick={onClose}>
          &times;
        </button>
        <h2 id="perksTitle">🎁 Send a Perk</h2>
        <p className="modal-sub">
          {filing.sponsor_name} &middot; {filing.city}, {filing.state}
        </p>

        {!sent ? (
          <>
            <div className="perk-field">
              <label>Gift card amount</label>
              <div className="amount-options">
                {AMOUNTS.map((a) => (
                  <button
                    key={a}
                    type="button"
                    className={`amount-btn ${amount === a ? "selected" : ""}`}
                    onClick={() => setAmount(a)}
                  >
                    ${a}
                  </button>
                ))}
              </div>
            </div>
            <div className="perk-field">
              <label htmlFor="perkRecipient">Send to (email)</label>
              <input
                id="perkRecipient"
                type="email"
                placeholder="contact@company.com"
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
              />
            </div>
            <button className="run-btn" onClick={() => setSent(true)}>
              Send ${amount} Amazon Gift Card
            </button>
            <p className="demo-disclaimer">Demo only &mdash; no real gift card is issued or charged.</p>
          </>
        ) : (
          <div className="perk-success">
            <div className="perk-success-icon">✓</div>
            <p>
              ${amount} Amazon Gift Card sent{recipient ? ` to ${recipient}` : ""} for{" "}
              {filing.sponsor_name}
            </p>
            <p className="demo-disclaimer">Demo only &mdash; no real gift card is issued or charged.</p>
          </div>
        )}
      </div>
    </div>
  );
}
