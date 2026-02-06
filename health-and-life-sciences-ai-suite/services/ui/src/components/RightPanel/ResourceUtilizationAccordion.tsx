import React from 'react';
import { useAppSelector } from '../../redux/hooks';
import Accordion from '../common/Accordion';
import '../../assets/css/RightPanel.css';

const ResourceUtilizationAccordion: React.FC = () => {
  const metrics = useAppSelector((state) => state.services.metrics);
  const isProcessing = useAppSelector((state) => state.app.isProcessing);

  return (
    <Accordion title="💻 Resource Utilization" defaultOpen={false}>
      <div className="accordion-subtitle">
        Real-time CPU, GPU, and memory usage monitoring
      </div>

      <div className="accordion-content">
        {isProcessing ? (
          metrics ? (
            <div className="resource-metrics">
              {/* CPU Usage */}
              <div className="metric-row">
                <span className="metric-label">CPU Usage:</span>
                <div className="metric-bar-container">
                  <div
                    className="metric-bar"
                    style={{
                      width: `${metrics.cpu_usage || 0}%`,
                      backgroundColor: (metrics.cpu_usage || 0) > 80 ? '#e74c3c' : '#3498db',
                    }}
                  />
                  <span className="metric-value">{metrics.cpu_usage || 0}%</span>
                </div>
              </div>

              {/* Memory Usage */}
              <div className="metric-row">
                <span className="metric-label">Memory Usage:</span>
                <div className="metric-bar-container">
                  <div
                    className="metric-bar"
                    style={{
                      width: `${((metrics.memory_usage || 0) / 32768) * 100}%`,
                      backgroundColor: '#2ecc71',
                    }}
                  />
                  <span className="metric-value">
                    {((metrics.memory_usage || 0) / 1024).toFixed(1)} GB
                  </span>
                </div>
              </div>

              {/* GPU Usage */}
              <div className="metric-row">
                <span className="metric-label">GPU Usage:</span>
                <div className="metric-bar-container">
                  <div
                    className="metric-bar"
                    style={{
                      width: `${metrics.gpu_usage || 0}%`,
                      backgroundColor: '#9b59b6',
                    }}
                  />
                  <span className="metric-value">{metrics.gpu_usage || 0}%</span>
                </div>
              </div>

              {/* Power Consumption */}
              <div className="metric-row">
                <span className="metric-label">Power:</span>
                <div className="metric-bar-container">
                  <span className="metric-value">{metrics.power_usage || 0} W</span>
                </div>
              </div>
            </div>
          ) : (
            <p style={{ textAlign: 'center', padding: '20px', fontStyle: 'italic', color: '#666' }}>
              Loading resource metrics...
            </p>
          )
        ) : (
          <div className="no-data-message">
            <p>No active session. Start processing to monitor resources.</p>
          </div>
        )}
      </div>
    </Accordion>
  );
};

export default ResourceUtilizationAccordion;