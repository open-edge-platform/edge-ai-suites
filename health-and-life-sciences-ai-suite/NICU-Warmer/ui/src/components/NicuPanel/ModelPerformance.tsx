import React from 'react';
import type { ModelMetrics } from '../../types/nicu';

interface ModelPerformanceProps {
  models: ModelMetrics[];
}

const ModelPerformance: React.FC<ModelPerformanceProps> = ({ models }) => (
  <div className="nicu-card">
    <div className="nicu-card-header">
      <h4 className="nicu-card-title">
        <span className="nicu-card-title-icon">⚡</span>
        Model Performance
      </h4>
    </div>
    <table className="nicu-model-table">
      <thead>
        <tr>
          <th>Model</th>
          <th>FPS</th>
          <th>Latency</th>
          <th>Frames</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {models.map((m) => (
          <tr key={m.name}>
            <td>{m.name}</td>
            <td>{m.fps.toFixed(1)}</td>
            <td>{m.latency.toFixed(1)} ms</td>
            <td>{m.framesProcessed.toLocaleString()}</td>
            <td>
              <span className={`nicu-model-dot nicu-model-dot--${m.status}`} />
              {m.status}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export default ModelPerformance;