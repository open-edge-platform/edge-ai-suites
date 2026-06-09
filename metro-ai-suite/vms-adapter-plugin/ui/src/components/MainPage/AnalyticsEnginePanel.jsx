// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

/**
 * AnalyticsEnginePanel
 * --------------------
 * Schema-driven Analytics App selector + parameter form.
 *
 *   1. On mount → GET /v1/analytics-apps/discover
 *      → list every Analytics App registered in the I/O plugin along with
 *        its live `available` flag and Pydantic JSON Schema.
 *   2. The user picks a Analytics App → render its schema as form inputs
 *      (via <SchemaForm/>).
 *   3. The user clicks **Start Analysis** → POST the validated payload
 *      to /v1/analytics-apps/{appId}/start; backend Pydantic-validates the
 *      payload and triggers the AI application's start endpoint.
 *
 * No Analytics App-specific code lives here — adding a new Analytics App in the
 * backend (with a new `param_model`) is automatically picked up by this
 * panel without any UI change.
 */

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import {
  Settings2, PlayCircle, StopCircle, Loader2, AlertCircle, Cpu, ScanLine, WifiOff,
} from 'lucide-react';
import { t } from '@/utils/i18n';

import {
  discoverAnalyticsApps,
  startAnalyticsApp,
  getAnalyticsAppOptions,
} from '@/services/api';
import SchemaForm, { initialFormState } from './SchemaForm';

export default function AnalyticsEnginePanel({
  cameras = [],
  onAnalyticsAppChange,
  activeRuns = {},     // { [appId]: run[] } — map of active runs per app
  onStartAnalysis,   // (appId, runResult) => void  — invoked after a successful start
  onStopAnalysis,    // (appId, runId) => void  — invoked when Stop is clicked
}) {
  const [discovered, setDiscovered] = useState([]);
  const [discovering, setDiscovering] = useState(false);
  const [hasDiscovered, setHasDiscovered] = useState(false);
  const [discoverError, setDiscoverError] = useState(null);

  const [selectedAppId, setSelectedAppId] = useState('');
  const [formValue, setFormValue] = useState({});
  const [errors, setErrors] = useState([]);
  const [starting, setStarting] = useState(false);

  const [dynamicOptions, setDynamicOptions] = useState({});

  const enabledCameras = cameras.filter((c) => c.enabled);
  const selectedApp = discovered.find((a) => a.app_id === selectedAppId);

  // ── Discovery ────────────────────────────────────────────────────────────
  const runDiscovery = useCallback(async () => {
    setDiscovering(true);
    setDiscoverError(null);
    try {
      const apps = await discoverAnalyticsApps();
      setDiscovered(apps);
      // Don't auto-select — wait for user to click a Analytics App so the
      // parameter form only appears after an explicit selection.
      setSelectedAppId('');
      setFormValue({});
      setErrors([]);
    } catch (err) {
      setDiscoverError(err.message ?? String(err));
      setDiscovered([]);
    } finally {
      setDiscovering(false);
      setHasDiscovered(true);
    }
  }, []);

  // No auto-discovery on mount — user must click "Discover Apps".

  // ── When the selected app changes, refresh form state from its schema ───
  useEffect(() => {
    if (!selectedApp) return;
    setFormValue(initialFormState(selectedApp.params_schema));
    setErrors([]);
    onAnalyticsAppChange?.(selectedApp.display_name);
  }, [selectedAppId]);  // eslint-disable-line react-hooks/exhaustive-deps

  // ── Fetch dynamic option lists (models / pipelines / …) for selected app ──
  useEffect(() => {
    if (!selectedApp) return;
    const props = selectedApp.params_schema?.properties ?? {};
    const sources = Object.values(props)
      .map((p) => (p?.anyOf?.find((b) => b['x-vms-source'])?.['x-vms-source']) || p?.['x-vms-source'])
      .filter(Boolean);

    const next = { ...dynamicOptions };
    if (sources.includes('lvc-models')) {
      getAnalyticsAppOptions(selectedApp.app_id, 'models')
        .then((d) => {
          const list = Array.isArray(d) ? d : (d?.models ?? []);
          next['lvc-models'] = list.map((m) => {
            const name = typeof m === 'string' ? m : (m.model_name ?? m.name ?? String(m));
            return { value: name, label: name };
          });
          setDynamicOptions({ ...next });
        })
        .catch(() => {});
    }
    if (sources.includes('lvc-pipelines')) {
      getAnalyticsAppOptions(selectedApp.app_id, 'pipelines')
        .then((p) => {
          const list = Array.isArray(p) ? p : [];
          next['lvc-pipelines'] = list.map((x) => {
            const name = x.pipeline_name ?? x;
            return { value: name, label: String(name).replace('GenAI_Pipeline_on_', '') + ' Pipeline' };
          });
          setDynamicOptions({ ...next });
        })
        .catch(() => {});
    }
  }, [selectedAppId]);  // eslint-disable-line react-hooks/exhaustive-deps

  // ── Start Analysis ──────────────────────────────────────────────────────
  const handleStart = async () => {
    if (!selectedApp) return;
    // Strip empty strings so the backend can apply Pydantic defaults.
    const payload = Object.fromEntries(
      Object.entries(formValue).filter(([, v]) => v !== '' && v !== null && v !== undefined),
    );
    // Coerce any string values that the schema declares as type:object.
    // This happens when a textarea is used for JSON input (e.g. "parameters").
    const schemaProps = selectedApp.params_schema?.properties ?? {};
    for (const [key, val] of Object.entries(payload)) {
      if (typeof val === 'string' && schemaProps[key]?.type === 'object') {
        try {
          payload[key] = JSON.parse(val);
        } catch {
          setErrors([{ loc: [key], msg: `"${key}" must be valid JSON`, type: 'json_parse_error' }]);
          return;
        }
      }
    }
    setStarting(true);
    setErrors([]);
    try {
      const res = await startAnalyticsApp(selectedApp.app_id, payload);
      onStartAnalysis?.(selectedApp.app_id, res);
    } catch (err) {
      if (err.status === 422 && Array.isArray(err.fieldErrors)) {
        setErrors(err.fieldErrors);
      } else {
        setErrors([{ loc: ['__root__'], msg: err.message ?? String(err), type: 'error' }]);
      }
    } finally {
      setStarting(false);
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <Card className="vms-card flex flex-col py-0">
      <CardHeader className="vms-panel-hdr">
        <div className="flex flex-col gap-[5px]">
          <h2 className="vms-panel-title">
            <span className="vms-panel-icon"><Settings2 size={15} className="text-[#0071C5]" /></span>
            {t('enginePanelTitle')}
          </h2>
          <p className="text-[0.72rem] text-[#A3B0CC] pl-[39px]">
            {hasDiscovered && discovered.length > 0
              ? `${discovered.length} analytics app${discovered.length === 1 ? '' : 's'} registered (${discovered.filter((a) => a.available).length} available)`
              : 'Click Discover Apps to query the I/O plugin for available AI applications'}
          </p>
        </div>
        <Button
          size="sm"
          className="btn-primary text-white shrink-0 text-[0.78rem] font-semibold px-4"
          onClick={runDiscovery}
          disabled={discovering}
          title="Run Analytics App discovery"
        >
          <ScanLine size={13} className="mr-[6px]" />
          {discovering
            ? 'Discovering…'
            : hasDiscovered ? 'Rediscover Apps' : 'Discover Apps'}
        </Button>
      </CardHeader>

      <CardContent className="p-0 flex-1">
        <div className="divide-y divide-[#EDF0F9] mx-[22px] mb-[22px] border border-[#EDF0F9] overflow-hidden">

          {/* Engine row */}
          <div className="vms-field-row bg-[#FAFBFF]">
            <span className="vms-field-label">{t('enginePanelTitle')}</span>
            <span className="vms-badge vms-badge-blue-dk">Open Edge Platform</span>
          </div>

          {/* Discovery error */}
          {discoverError && (
            <div className="vms-field-row bg-red-50 text-red-700 text-[0.78rem]">
              <AlertCircle size={13} className="mr-1.5" />
              Failed to discover Analytics Apps: {discoverError}
            </div>
          )}

          {/* Empty state — before first discovery */}
          {!hasDiscovered && !discovering && !discoverError && (
            <div className="vms-field-row bg-[#FAFBFF]">
              <div className="vms-empty py-6 w-full">
                <ScanLine size={32} strokeWidth={1.2} className="text-[#C8D2E8]" />
                <span>Click <strong className="text-[#6B7BA4]">Discover Apps</strong> to list available AI applications</span>
              </div>
            </div>
          )}

          {/* Analytics App selector — built from discovery */}
          {!discoverError && hasDiscovered && (
            <div className="vms-field-row items-start">
              <span className="vms-field-label pt-[3px]">{t('engineAnalyticsAppLabel')}</span>
              <RadioGroup
                value={selectedAppId}
                onValueChange={setSelectedAppId}
                className="flex flex-row gap-[8px] flex-1 flex-wrap"
              >
                {discovered.length === 0 && !discovering && (
                  <p className="text-[0.78rem] text-[#8695B8]">
                    No Analytics Apps registered in the I/O plugin.
                  </p>
                )}
                {discovered.map((app) => {
                  const isActive = selectedAppId === app.app_id;
                  return (
                    <Label key={app.app_id} htmlFor={`ca-${app.app_id}`}
                      className={`vms-radio-option ${isActive ? 'vms-radio-option-active' : ''}`}>
                      <RadioGroupItem id={`ca-${app.app_id}`} value={app.app_id} className="sr-only" />
                      <span className={`vms-radio-dot ${isActive ? 'vms-radio-dot-active' : ''}`} />
                      <Cpu size={13} className={`shrink-0 ${isActive ? 'text-[#0071C5]' : 'text-[#8695B8]'}`} />
                      <span className={`text-[0.83rem] font-semibold flex-1 ${isActive ? 'text-[#0E1C47]' : 'text-[#4A5C80]'}`}>
                        {app.display_name || app.app_id}
                      </span>
                      <span className={`vms-badge font-mono-vms ${app.available ? 'vms-badge-green' : 'vms-badge-yellow'}`}>
                        {app.available ? 'available' : 'offline'}
                      </span>
                    </Label>
                  );
                })}
              </RadioGroup>
            </div>
          )}

          {/* Offline error panel — shown instead of the form when the app is unreachable */}
          {selectedApp && !selectedApp.available && (
            <div className="px-[14px] py-[14px] bg-[#FAFBFF]">
              <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-3 text-[0.78rem] text-red-800">
                <WifiOff size={14} className="mt-[1px] shrink-0 text-red-500" />
                <div className="flex flex-col gap-[3px]">
                  <span className="font-semibold">{selectedApp.display_name} is not reachable</span>
                  <span className="text-red-700">
                    {selectedApp.error || 'The backend could not be contacted at discovery time. Re-discover once the service is running.'}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Schema-driven parameter form — only shown when app is reachable and schema is available */}
          {selectedApp && selectedApp.available && selectedApp.params_schema && (
            <div className="px-[14px] py-[14px] bg-[#FAFBFF] flex flex-col gap-[14px]">
              <span className="text-[0.72rem] font-bold uppercase tracking-[0.5px] text-[#6B7BA4]">
                {selectedApp.display_name} — Parameters
              </span>
              <SchemaForm
                schema={selectedApp.params_schema}
                value={formValue}
                onChange={setFormValue}
                cameras={enabledCameras}
                dynamicOptions={dynamicOptions}
                errors={errors}
              />
              {errors.find((e) => Array.isArray(e.loc) && e.loc.includes('__root__')) && (
                <p className="text-[0.78rem] text-red-600">
                  {errors.find((e) => e.loc.includes('__root__')).msg}
                </p>
              )}
            </div>
          )}

          {/* Start / Stop row */}
          {selectedApp && (
            <div className="vms-field-row bg-[#F0F7FF]">
              <span className="vms-field-label">Live Analysis</span>
              {(() => {
                const appRuns = activeRuns[selectedAppId] ?? [];
                const activeRun = appRuns[0];
                const isRunning = appRuns.length > 0;
                if (!isRunning) {
                  return (
                    <Button
                      size="sm"
                      className="bg-[#0071C5] hover:bg-[#005BA0] text-white text-[0.78rem] font-semibold px-4"
                      onClick={handleStart}
                      disabled={starting || !selectedApp.available}
                      title={!selectedApp.available ? 'Analytics App backend is not reachable' : 'Validate parameters and trigger the Analytics App'}
                    >
                      {starting
                        ? <><Loader2 size={13} className="mr-1.5 animate-spin" />Starting…</>
                        : <><PlayCircle size={13} className="mr-1.5" />Start Analysis</>}
                    </Button>
                  );
                }
                const runId = activeRun?.run_id ?? activeRun?.runId;
                return (
                  <Button size="sm" variant="destructive"
                    className="text-[0.78rem] font-semibold px-4"
                    onClick={() => onStopAnalysis?.(selectedAppId, runId)}>
                    <StopCircle size={13} className="mr-1.5" />Stop Analysis
                  </Button>
                );
              })()}
            </div>
          )}

        </div>
      </CardContent>
    </Card>
  );
}
