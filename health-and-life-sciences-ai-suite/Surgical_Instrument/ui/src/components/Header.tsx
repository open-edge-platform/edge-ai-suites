import './Header.css';

export default function Header() {
  return (
    <header className="hdr">
      <div className="hdr-brand">
        <span className="hdr-logo" aria-hidden>intel.</span>
        <span className="hdr-title">Surgical Instrument · Polyp Detection</span>
      </div>
      <div className="hdr-disclaimer" role="status">
        ⚠ Not for clinical use — developer reference implementation
      </div>
    </header>
  );
}
