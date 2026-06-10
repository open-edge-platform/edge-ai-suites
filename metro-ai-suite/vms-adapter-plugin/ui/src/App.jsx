// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { useState, useCallback, useEffect } from 'react';
import { Toaster } from '@/components/ui/sonner';
import { toast } from 'sonner';
import { Camera, Zap } from 'lucide-react';

import Header from '@/components/Navbar';
import { StatCards, CameraDiscoveryPanel, AnalyticsEnginePanel, AnalysisResultsPanel } from '@/components/MainPage';

import { discoverCameras, listCameras, setCameraEnabled, stopAnalyticsAppRun, listAnalyticsAppRuns } from '@/services/api';
import { useHealth } from '@/hooks';
import { t } from '@/utils/i18n';

export default function App() {
  const [activeSection, setActiveSection] = useState('cameras');
  const [cameras,      setCameras]      = useState([]);
  const [lvcRuns,      setLvcRuns]      = useState([]);
  const [odRuns,       setOdRuns]       = useState([]);
  const [discovering,  setDiscovering]  = useState(false);
  const [analyticsApp,      setAnalyticsApp]      = useState('');

  const engineStatus = useHealth();
  const enabledCount = cameras.filter((c) => c.enabled).length;

  // Stop all running LVC pipelines when the user refreshes or leaves the page.
  useEffect(() => {
    const stopAllOnUnload = () => {
      if (lvcRuns.length === 0) return;
      // sendBeacon is the only reliable way to fire a request on page unload.
      navigator.sendBeacon('/v1/analytics-apps/live_captioning/runs/stop-all');
    };
    window.addEventListener('beforeunload', stopAllOnUnload);
    return () => window.removeEventListener('beforeunload', stopAllOnUnload);
  }, [lvcRuns]);

  // Load persisted cameras from DB on mount (preserves enabled state across page refreshes)
  useEffect(() => {
    listCameras().then((cams) => {
      if (cams.length > 0) setCameras(cams);
    }).catch(() => {/* backend not ready yet — user can Discover manually */});

    // Load active LVC runs on mount.
    listAnalyticsAppRuns('live_captioning').then((runs) => {
      if (Array.isArray(runs) && runs.length > 0) setLvcRuns(runs);
    }).catch(() => {});
  }, []);

  // Poll LVC every 5 seconds to keep run state in sync.
  // Always-on: if a run stops unexpectedly (e.g. pipeline abort) the user
  // sees the change immediately, and once they restart the run the UI
  // picks it up without needing a page refresh.
  useEffect(() => {
    const id = setInterval(() => {
      listAnalyticsAppRuns('live_captioning').then((runs) => {
        if (!Array.isArray(runs)) return;
        setLvcRuns((prev) => {
          const prevIds = prev.map((r) => r.runId ?? r.run_id).join(',');
          const nextIds = runs.map((r) => r.runId ?? r.run_id).join(',');
          return prevIds === nextIds ? prev : runs;
        });
      }).catch(() => {/* LVC unreachable — keep previous state */});
    }, 5000);
    return () => clearInterval(id);
  }, []);  // run once on mount, always polling

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      const discovered = await discoverCameras();
      setCameras(discovered);
      toast.success(t('toastDiscoverSuccess', { count: discovered.length }));
    } catch (err) {
      toast.error(t('toastDiscoverFailed', { message: err.message ?? err }));
    } finally {
      setDiscovering(false);
    }
  };

  const handleCameraToggle = async (cameraId, enabled) => {
    const cam = cameras.find((c) => c.camera_id === cameraId);
    const action = enabled ? 'enable' : 'disable';
    try {
      await setCameraEnabled([cameraId], enabled);
      setCameras((prev) => prev.map((c) => c.camera_id === cameraId ? { ...c, enabled } : c));
      if (cam) toast.success(t(enabled ? 'toastCameraEnabled' : 'toastCameraDisabled', { name: cam.camera_name }));
    } catch (err) {
      toast.error(t('toastCameraToggleFailed', { action, message: err.message ?? err }));
    }
  };

  const handleStopLvc = useCallback(async (runId) => {
    try {
      await stopAnalyticsAppRun('live_captioning', runId);
      setLvcRuns((prev) => prev.filter((r) => (r.runId || r.run_id) !== runId));
      toast.success('Live Captioning run stopped');
    } catch (err) {
      toast.error(`Failed to stop run: ${err.message ?? err}`);
      throw err;
    }
  }, []);

  const handleStartAnalysis = useCallback(async (appId, response) => {
    const run = response?.result ?? response ?? {};
    if (appId === 'live_captioning') {
      // Optimistically add the run immediately so the Live Stream tab appears
      setLvcRuns((prev) => [...prev, run]);
      // Then fetch the enriched run list from the API (guarantees peerId is present)
      listAnalyticsAppRuns('live_captioning').then((runs) => {
        if (Array.isArray(runs) && runs.length > 0) setLvcRuns(runs);
      }).catch(() => {/* fallback to optimistic run */});
    } else {
      setOdRuns((prev) => [...prev, run]);
    }
    toast.success('Analysis started — check the Live Stream tab');
  }, []);

  // Stop the first active run for the given app (called from the engine panel Stop button)
  const handleStopAnalysis = useCallback(async (appId, runId) => {
    if (!appId || !runId) return;
    try {
      await stopAnalyticsAppRun(appId, runId);
      if (appId === 'live_captioning') {
        setLvcRuns((prev) => prev.filter((r) => (r.runId || r.run_id) !== runId));
      } else {
        setOdRuns((prev) => prev.filter((r) => (r.runId || r.run_id) !== runId));
      }
      toast.success('Analysis stopped');
    } catch (err) {
      toast.error(`Failed to stop run: ${err.message ?? err}`);
    }
  }, []);

  const NAV = [
    { id: 'cameras',   label: t('navCameraDiscovery'), icon: Camera, desc: t('navCameraDesc') },
    { id: 'analytics', label: t('navAnalyticsEngine'), icon: Zap,    desc: t('navAnalyticsDesc') },
  ];

  return (
    <div className="min-h-screen bg-[#EEF2FA] flex flex-col">
      <Header engineStatus={engineStatus} />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="vms-sidebar">
          {/* System label */}
          <div className="px-5 pt-5 pb-4 border-b border-white/[0.06]">
            <p className="vms-sidebar-section-label mb-[2px]">{t('appPlatform')}</p>
            <p className="text-[0.78rem] text-white/85 font-medium">{t('appBrand')}</p>
          </div>

          {/* Nav section label */}
          <div className="px-5 pt-5 pb-2">
            <p className="vms-sidebar-section-label">{t('navNavigation')}</p>
          </div>

          {/* Nav items */}
          <nav className="flex flex-col gap-[3px] px-3">
            {NAV.map(({ id, label, icon: Icon, desc }) => {
              const active = activeSection === id;
              return (
                <button
                  key={id}
                  onClick={() => setActiveSection(id)}
                  className={`vms-nav-btn ${active ? 'vms-nav-btn-active' : ''}`}
                >
                  {active && <span className="vms-nav-active-bar" />}
                  <span className={`vms-nav-icon ${active ? 'vms-nav-icon-active' : ''}`}>
                    <Icon size={14} />
                  </span>
                  <div className="flex flex-col leading-none min-w-0">
                    <span className="vms-nav-label">{label}</span>
                    <span className={`vms-nav-desc`}>{desc}</span>
                  </div>
                </button>
              );
            })}
          </nav>

          <div className="mt-auto" />
        </aside>

        {/* Content */}
        <main className="vms-main-content">

          {/* ── Page Header ── */}
          <div className="vms-page-hdr">
            <div className="flex items-center gap-3">
              <div className={`w-9 h-9 flex items-center justify-center shrink-0 shadow-[0_1px_3px_rgba(0,0,0,0.07)] ${
                activeSection === 'cameras'  ? 'bg-[#EBF5FF]' : 'bg-[#EDF0FD]'
              }`}>
                {activeSection === 'cameras'   && <Camera size={17} className="text-[#0071C5]" />}
                {activeSection === 'analytics' && <Zap    size={17} className="text-[#0071C5]" />}
              </div>
              <div>
                <div className="flex items-center gap-[6px] mb-[3px]">
                  <span className="vms-breadcrumb-root">{t('breadcrumbRoot')}</span>
                  <span className="text-[#D4DAF0]">/</span>
                  <span className="vms-breadcrumb-current">
                    {activeSection === 'cameras' ? t('breadcrumbCameras') : t('breadcrumbAnalytics')}
                  </span>
                </div>
                <h1 className="vms-page-title">
                  {activeSection === 'cameras' ? t('pageHeaderCameras') : t('pageHeaderAnalytics')}
                </h1>
              </div>
            </div>

            {/* Right side context info */}
            <div className="flex items-center gap-3">
              {(activeSection === 'cameras') && cameras.length > 0 && (
                <>
                  {[
                    { label: t('statusOnline'),  count: cameras.filter(c=>c.status==='online').length,  cls:'vms-badge vms-badge-green' },
                    { label: t('statusOffline'), count: cameras.filter(c=>c.status==='offline').length, cls:'vms-badge vms-badge-red'   },
                    { label: t('statusUnknown'), count: cameras.filter(c=>c.status==='unknown').length, cls:'vms-badge vms-badge-gray'  },
                  ].map(({ label, count, cls }) => (
                    <span key={label} className={cls}>{count} {label}</span>
                  ))}
                  <div className="w-px h-4 bg-[#DDE3F0]" />
                  <span className="text-[0.72rem] text-[#A3B0CC]">{cameras.filter(c=>c.enabled).length} enabled</span>
                </>
              )}
              {activeSection === 'analytics' && (
                <div className="flex items-center gap-2">
                  <span className="w-[7px] h-[7px] rounded-full bg-[#0DBF8C] animate-pulse-dot" />
                  <span className="text-[0.72rem] font-medium text-[#6B7BA4]">{t('navPipelineActive')}</span>
                  <div className="w-px h-4 bg-[#DDE3F0]" />
                  <span className="vms-badge vms-badge-purple">{analyticsApp}</span>
                </div>
              )}
            </div>
          </div>

          {/* ── Section Content ── */}
          <div className="px-7 pt-5">
            <StatCards stats={{ nvrs:2, discovered:cameras.length, enabled:enabledCount, analyticsApp }} />

            {activeSection === 'cameras' && (
              <div className="mt-5 animate-slide-in">
                <CameraDiscoveryPanel
                  cameras={cameras}
                  discovering={discovering}
                  onDiscover={handleDiscover}
                  onToggle={handleCameraToggle}
                />
              </div>
            )}

            {activeSection === 'analytics' && (
              <div className="mt-5 flex flex-col gap-0 animate-slide-in">
                <AnalyticsEnginePanel
                  analyticsApp={analyticsApp}
                  cameras={cameras}
                  onAnalyticsAppChange={setAnalyticsApp}
                  activeRuns={{ live_captioning: lvcRuns, dls_vision: odRuns }}
                  onStartAnalysis={handleStartAnalysis}
                  onStopAnalysis={handleStopAnalysis}
                />

                <div className="vms-section-divider">
                  <div className="vms-divider-line" />
                  <div className="vms-divider-badge">
                    <span className="w-[6px] h-[6px] rounded-full bg-[#0071C5] shrink-0" />
                    <span className="vms-divider-badge-label">Pipeline Monitoring</span>
                  </div>
                  <div className="vms-divider-line" />
                </div>

                <div className="pb-5">
                  <AnalysisResultsPanel
                    lvcRuns={lvcRuns}
                    onStopLvc={handleStopLvc}
                  />
                </div>
              </div>
            )}
          </div>
        </main>
      </div>

      <Toaster
        position="bottom-right"
        offset="58px"
        toastOptions={{ classNames:{ toast:'border-l-4 border-l-[#0DBF8C] shadow-md font-sans text-[0.855rem]' } }}
      />
    </div>
  );
}
