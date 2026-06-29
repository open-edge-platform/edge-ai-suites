import { useAppSelector } from '../store';
import './Footer.css';

export default function Footer() {
  const buildSha = useAppSelector((s) => s.status.buildSha);
  return (
    <footer className="ftr">
      <div className="ftr-left">
        © Intel Corporation · Edge AI Suites — Health &amp; Life Sciences
      </div>
      <div className="ftr-right">
        <span className="ftr-disclaimer">Reference implementation — not a medical device</span>
        {buildSha && <span className="ftr-sha">build {buildSha.slice(0, 7)}</span>}
      </div>
    </footer>
  );
}
