import React from 'react';
import { useAppSelector } from '../../redux/hooks';
import Accordion from '../common/Accordion';
import '../../assets/css/RightPanel.css';

const DEVICE_COLORS: Record<string, string> = {
  GPU: '#1565c0',
  CPU: '#2e7d32',
  NPU: '#6a1b9a',
};

const STATUS_DOT: Record<string, { color: string; label: string }> = {
  running: { color: '#4caf50', label: 'Running' },
  stopped: { color: '#9e9e9e', label: 'Idle' },
  error:   { color: '#f44336', label: 'Error' },
};

const WORKLOAD_DEFS = [
  { name: 'Polyp Detection', models: 'yolo11n-polyp', deviceKey: 'detect' },
] as const;

export function PipelinePerformanceAccordion() {
  const systemStatus = useAppSelector((state) => state.nicu.data.systemStatus);
  const pipelinePerf = useAppSelector((state) => state.nicu.data.pipelinePerformance);

  const isRunning = systemStatus === 'running' || systemStatus === 'starting';
  const status = isRunning ? 'running' : 'stopped';

  const sseLookup: Record<string, { fps?: number; latency_ms?: number; device?: string; status?: string }> = {};
  if (pipelinePerf?.workloads) {
    for (const w of pipelinePerf.workloads) sseLookup[w.name] = w;
  }

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
              <th style={thStyle}>FPS</th>
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

              return (
                <tr key={def.name} style={{ background: rowBg }}>
                  <td style={{ ...cellStyle, fontWeight: 500, color: '#24292f' }}>{def.name}</td>
                  <td style={{ ...cellStyle, fontSize: '10px', color: '#888', fontFamily: 'monospace' }}>{def.models}</td>
                  <td style={cellStyle}>
                    <span style={{
                      display: 'inline-block',
                      padding: '2px 10px',
                      border: '1px solid',
                      borderRadius: '10px',
                      fontFamily: 'monospace',
                      fontWeight: 700,
                      fontSize: '10px',
                      backgroundColor: devColor + '14',
                      color: devColor,
                      borderColor: devColor + '40',
                    }}>
                      {actualDevice}
                    </span>
                  </td>
                  <td style={{ ...cellStyle, fontFamily: 'monospace', fontWeight: 600 }}>
                    {sseRow.fps !== undefined ? sseRow.fps.toFixed(1) : '—'}
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
        {pipelinePerf?.pipeline_fps > 0 && (
          <div style={{ marginTop: 12, padding: '8px 10px', background: '#f0f4f8', borderRadius: 4, fontSize: 12 }}>
            <strong>End-to-end pipeline FPS:</strong> {pipelinePerf.pipeline_fps.toFixed(1)}
            {pipelinePerf.decode && <span style={{ marginLeft: 12, color: '#666' }}>· decode {pipelinePerf.decode}</span>}
          </div>
        )}
      </div>
    </Accordion>
  );
}

export default PipelinePerformanceAccordion;
