// src/App.tsx
import { useEffect, useState } from 'react';
import Header from './components/Header/Header';
import TopPanel from './components/TopPanel/TopPanel';
import Body from './components/common/Body';
import Footer from './components/Footer/Footer';
import './App.css';
import { MetricsPoller } from './components/common/MetricsPoller';
import { api } from './services/api';

function App() {
  const [backendReady, setBackendReady] = useState(false);
  const [initialReady, setInitialReady] = useState(false);

  useEffect(() => {
    let active = true;

    const check = async () => {
      let ok = await api.pingBackend();
      if (ok) {
        try {
          const readiness = await api.getReadiness();
          const lifecycle = String(readiness.lifecycle || '').toLowerCase();
          ok =
            readiness.ready === true ||
            lifecycle === 'running' ||
            lifecycle === 'starting';
        } catch {
          ok = false;
        }
      }
      if (active) {
        setBackendReady(ok);
        if (ok) {
          setInitialReady(true);
        }
      }
    };

    check();
    const timer = window.setInterval(check, 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  if (!initialReady) {
    return (
      <div className="app-loading">
        <div className="loading-content">
          <div className="spinner" />
          <h2>Backend Readiness Check</h2>
          <p>Waiting for backend to become ready...</p>
          <div className="auto-retry-indicator">
            <span className="spinner small" />
            <span>Retrying automatically</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <MetricsPoller />
      <Header />
      {!backendReady && (
        <div className="backend-reconnect-banner" role="status" aria-live="polite">
          <span className="spinner small" />
          <span>Backend is reconnecting. Live status and video will resume automatically.</span>
        </div>
      )}
      <TopPanel />
      <Body />
      <Footer />
    </div>
  );
}

export default App;