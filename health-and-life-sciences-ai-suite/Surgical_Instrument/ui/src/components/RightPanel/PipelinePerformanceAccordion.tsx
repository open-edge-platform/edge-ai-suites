                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           import React, { useState } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import Accordion from '../common/Accordion';
import { api, type Device } from '../../services/api';
import { setActiveDevice } from '../../redux/slices/detectionSlice';
import '../../assets/css/RightPanel.css';

const DEVICE_COLORS: Record<string, string> = {
  GPU: '#1565c0',
  CPU: '#2e7d32',
  NPU: '#6a1b9a',
};

const DEVICE_OPTIONS: Device[] = ['GPU', 'CPU', 'NPU'];

const STATUS_DOT: Record<string, { color: string; label: string }> = {
  running: { color: '#4caf50', label: 'Running' },
  stopped: { color: '#9e9e9e', label: 'Idle' },
  error:   { color: '#f44336', label: 'Error' },
};

const WORKLOAD_DEFS = [
  { name: 'Polyp Detection', models: 'yolo11n-polyp', deviceKey: 'detect' },
] as const;

export function PipelinePerformanceAccordion() {
  const systemStatus = useAppSelector((state) => state.detection.data.systemStatus);
  const pipelinePerf = useAppSelector((state) => state.detection.data.pipelinePerformance);

  const isRunning = systemStatus === 'running' || systemStatus === 'starting';
  const status = isRunning ? 'running' : 'stopped';

  const [deviceError, setDeviceError] = useState<string>('');
  const [deviceBusy, setDeviceBusy] = useState(false);
  const dispatch = useAppDispatch();

  const handleDeviceChange = async (newDevice: Device) => {
    if (deviceBusy || isRunning) return;
    setDeviceBusy(true);
    setDeviceError('');
    try {
      await api.setDevice(newDevice);
      // Optimistically reflect the change immediately — SSE is closed while stopped,
      // so the pill/Model Info would otherwise stay stale until the next Start.
      dispatch(setActiveDevice(newDevice));
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setDeviceError(msg);
      setTimeout(() => setDeviceError(''), 4000);
    } finally {
      setDeviceBusy(false);
    }
  };

  const sseLookup: Record<string, {
    fps?: number;
    infer_ms?: number;
    infer_p50_ms?: number;
    infer_p90_ms?: number;
    infer_p95_ms?: number;
    infer_p99_ms?: number;
    processing_mean_ms?: number;
    processing_p50_ms?: number;
    processing_p90_ms?: number;
    processing_p95_ms?: number;
    processing_p99_ms?: number;
    e2e_mean_ms?: number;
    e2e_p50_ms?: number;
    e2e_p90_ms?: number;
    e2e_p95_ms?: number;
    e2e_p99_ms?: number;
    // legacy aliases
    latency_ms?: number;
    latency_p99_ms?: number;
    device?: string;
    status?: string;
  }> = {};
  if (pipelinePerf?.workloads) {
    for (const w of pipelinePerf.workloads) sseLookup[w.name] = w;
  }

  const modelInfo = useAppSelector((state) => state.detection.data.modelInfo);

  const thStyle: React.CSSProperties = {
    padding: '8px 10px', color: '#fff', fontWeight: 600, fontSize: '11px',
    textTransform: 'uppercase', letterSpacing: '0.4px', textAlign: 'left', border: '1px solid #888',
  };

  return (
    <Accordion title="Pipeline Performance" defaultOpen>
      <div className="pipeline-perf">
        <table style={{
          width: '100%', borderCollapse: 'collapse', fontSize: '12px', border: '2px solid #888',
        }}>
          <thead>
            <tr style={{ background: '#3a3f47' }}>
              <th style={thStyle}>Workload</th>
              <th style={thStyle}>Model</th>
              <th style={thStyle}>Device</th>
              <th style={thStyle} title="Frame arrival rate at the sink (throughput). Counted from MQTT metadata messages the backend receives.">FPS</th>
              <th style={thStyle} title="End-to-end frame residence mean over the rolling recent-frame window.">E2E mean</th>
              <th style={thStyle} title="Nearest-rank p90 for end-to-end frame latencies over the rolling window.">E2E P90</th>
              <th style={thStyle} title="Nearest-rank p95 for end-to-end frame latencies over the rolling window.">E2E P95</th>
              <th style={thStyle}>Status</th>
            </tr>
          </thead>
          <tbody>
            {WORKLOAD_DEFS.map((def, i) => {
              const sseRow = sseLookup[def.name] || {};
              const actualDevice = sseRow.device || 'GPU';
              const devColor = DEVICE_COLORS[actualDevice] || '#555';
              const actualStatus = sseRow.status || status;
              const statusInfo = STATUS_DOT[actualStatus] || STATUS_DOT.stopped;
              const rowBg = i % 2 === 0 ? '#fff' : '#f4f5f7';
              const cellStyle: React.CSSProperties = { padding: '8px 10px', border: '1px solid #bbb', verticalAlign: 'middle' };
              const numStyle: React.CSSProperties = { ...cellStyle, fontFamily: 'monospace', fontWeight: 600 };

              return (
                <tr key={def.name} style={{ background: rowBg }}>
                  <td style={{ ...cellStyle, fontWeight: 500, color: '#24292f' }}>{def.name}</td>
                  <td style={{ ...cellStyle, fontSize: '10px', color: '#888', fontFamily: 'monospace' }}>{def.models}</td>
                  <td style={cellStyle}>
                    <select
                      value={actualDevice}
                      onChange={(e) => handleDeviceChange(e.target.value as Device)}
                      disabled={isRunning || deviceBusy}
                      title={isRunning
                        ? 'Stop inference to change device'
                        : 'Change inference device (CPU / GPU / NPU)'}
                      style={{
                        padding: '2px 22px 2px 10px',
                        border: '1px solid',
                        borderRadius: '10px',
                        fontFamily: 'monospace',
                        fontWeight: 700,
                        fontSize: '10px',
                        backgroundColor: devColor + '14',
                        color: devColor,
                        borderColor: devColor + '40',
                        cursor: isRunning || deviceBusy ? 'not-allowed' : 'pointer',
                        opacity: isRunning ? 0.65 : 1,
                        appearance: 'none',
                        WebkitAppearance: 'none',
                        backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'><path fill='${encodeURIComponent(devColor)}' d='M2 4l3 3 3-3z'/></svg>")`,
                        backgroundRepeat: 'no-repeat',
                        backgroundPosition: 'right 6px center',
                      }}
                    >
                      {DEVICE_OPTIONS.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </td>
                  <td style={numStyle}>
                    {sseRow.fps !== undefined ? sseRow.fps.toFixed(1) : '—'}
                  </td>
                  <td style={numStyle} title="End-to-end frame residence mean from DL Streamer over the rolling window.">
                    {(sseRow.e2e_mean_ms ?? 0) > 0
                      ? `${(sseRow.e2e_mean_ms ?? 0).toFixed(1)} ms`
                      : '—'}
                  </td>
                  <td style={numStyle} title="Nearest-rank p90 for end-to-end frame latencies over the rolling window.">
                    {(sseRow.e2e_p90_ms ?? 0) > 0
                      ? `${(sseRow.e2e_p90_ms ?? 0).toFixed(1)} ms`
                      : '—'}
                  </td>
                  <td style={numStyle} title="Nearest-rank p95 for end-to-end frame latencies over the rolling window.">
                    {(sseRow.e2e_p95_ms ?? 0) > 0
                      ? `${(sseRow.e2e_p95_ms ?? 0).toFixed(1)} ms`
                      : '—'}
                  </td>
                  <td style={cellStyle}>
                    <span style={{
                      display: 'inline-block',
                      width: '8px', height: '8px', borderRadius: '50%',
                      marginRight: '6px', verticalAlign: 'middle',
                      backgroundColor: statusInfo.color,
                    }} />
                    <span style={{ fontSize: '11px', color: '#555', fontWeight: 500 }}>{statusInfo.label}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {!isRunning && (
          <div style={{ marginTop: 6, fontSize: 10, color: '#6b7280', fontStyle: 'italic' }}>
            Tip: click the Device pill above to switch between CPU / GPU / NPU (only while stopped).
          </div>
        )}
        <div style={{ marginTop: 6, fontSize: 10, color: '#6b7280' }}>
          Percentiles use nearest-rank over the rolling recent-frame window.
        </div>
        {deviceError && (
          <div style={{ marginTop: 6, padding: '6px 10px', background: '#fee', border: '1px solid #fcc', borderRadius: 4, fontSize: 11, color: '#c62828' }}>
            {deviceError}
          </div>
        )}

        {modelInfo && (
          <div style={{ marginTop: 10, padding: '10px 12px', background: '#fff', border: '1px solid #d9dee5', borderRadius: 4, fontSize: 12, lineHeight: 1.7 }}>
            <div style={{ fontWeight: 700, fontSize: 11, color: '#3a3f47', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>
              Model & Input
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', rowGap: 3, columnGap: 8 }}>
              <span style={{ color: '#6b7280' }}>Model:</span>
              <span style={{ fontFamily: 'monospace', color: '#24292f' }}>{modelInfo.name}</span>
              <span style={{ color: '#6b7280' }}>Precision:</span>
              <span style={{ color: '#24292f' }}>{modelInfo.precision}</span>
              <span style={{ color: '#6b7280' }}>Task:</span>
              <span style={{ color: '#24292f' }}>{modelInfo.task} <span style={{ color: '#6b7280' }}>({modelInfo.dataset})</span></span>
              <span style={{ color: '#6b7280' }}>Video source:</span>
              <span style={{ color: '#24292f' }}>{modelInfo.input_source}</span>
              <span style={{ color: '#6b7280' }}>Model input:</span>
              <span style={{ fontFamily: 'monospace', color: '#24292f' }}>{modelInfo.model_input}</span>
              <span style={{ color: '#6b7280' }}>Device:</span>
              <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#1565c0' }}>{modelInfo.device}</span>
            </div>
          </div>
        )}
      </div>
    </Accordion>
  );
}

export default PipelinePerformanceAccordion;
