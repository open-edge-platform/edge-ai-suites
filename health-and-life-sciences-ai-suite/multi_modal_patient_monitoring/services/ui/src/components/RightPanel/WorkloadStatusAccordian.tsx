// src/components/RightPanel/WorkloadStatusAccordion.tsx
import { useAppSelector } from '../../redux/hooks';
import Accordion from '../common/Accordion';
import { WORKLOADS } from '../../constants';
import '../../assets/css/RightPanel.css';

const WorkloadStatusAccordion = () => {
  const isProcessing = useAppSelector((state) => state.app.isProcessing);
  const aggregatorStatus = useAppSelector((state) => state.services.aggregator.status);
  const workloads = useAppSelector((state) => state.services.workloads);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return '#28a745';
      case 'error':
        return '#dc3545';
      case 'stopped':
        return '#ffc107';
      default:
        return '#6c757d';
    }
  };

  return (
    <Accordion title="📊 Workload Status" defaultOpen>
      <div style={{ marginBottom: '16px' }}>
        <strong>Processing:</strong> {isProcessing ? '🟢 Active' : '⚪ Idle'}
      </div>

      <div style={{ marginBottom: '16px', paddingBottom: '12px', borderBottom: '1px solid #e6e7e8' }}>
        <strong>SSE Connection:</strong>{' '}
        <span style={{ color: getStatusColor(aggregatorStatus) }}>
          {aggregatorStatus.toUpperCase()}
        </span>
      </div>

      <div className="workload-status-list">
        {WORKLOADS.map((workload) => {
          const state = workloads[workload.id];
          
          return (
            <div key={workload.id} className="workload-status-item">
              <div className="workload-status-header">
                <span className="workload-icon" style={{ fontSize: '20px' }}>
                  {workload.icon}
                </span>
                <span className="workload-name">{workload.name}</span>
                <div className="status-indicator">
                  <span 
                    className="status-dot" 
                    style={{ 
                      backgroundColor: getStatusColor(state?.status || 'idle'),
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      display: 'inline-block'
                    }} 
                  />
                  <span className="status-text" style={{ marginLeft: '8px', fontSize: '12px' }}>
                    {state?.status || 'idle'}
                  </span>
                </div>
              </div>
              
              <div className="workload-status-meta" style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>
                <span className="event-count">
                  📊 {state?.eventCount || 0} events
                </span>
                {state?.lastEventTime && (
                  <span style={{ marginLeft: '12px' }}>
                    🕐 {new Date(state.lastEventTime).toLocaleTimeString()}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Accordion>
  );
};

export default WorkloadStatusAccordion;