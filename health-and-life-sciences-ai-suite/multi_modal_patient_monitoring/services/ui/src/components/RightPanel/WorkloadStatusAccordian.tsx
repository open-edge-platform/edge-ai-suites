import React from 'react';
import { useAppSelector } from '../../redux/hooks';
import Accordion from '../common/Accordion';
import { WORKLOADS } from '../../constants';
import '../../assets/css/RightPanel.css';

const WorkloadStatusAccordion = () => {
  const isProcessing = useAppSelector((state) => state.app.isProcessing);
  const aggregatorStatus = useAppSelector((state) => state.services.aggregator.status);
  const workloads = useAppSelector((state) => state.services.workloads);
  // ADD THIS:
  const workloadDevices = useAppSelector((state) => state.metrics.workloadDevices);

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

  // ADD THIS: Map workload IDs to device keys
  const deviceKeyMap: Record<string, string> = {
    'rppg': 'rppg',
    'ai-ecg': 'ai_ecg',
    'mdpnp': 'mdpnp',
    '3d-pose': 'pose_3d',
  };

  return (
    <Accordion title="Workload Devices" defaultOpen>
      <div className="workload-status-list">
        {WORKLOADS.map((workload) => {
          const state = workloads[workload.id];
          // ADD THIS: Get device info for this workload
          const deviceKey = deviceKeyMap[workload.id];
          const deviceInfo = workloadDevices?.workloads?.[deviceKey as keyof typeof workloadDevices.workloads];
          
          return (
            <div key={workload.id} className="workload-status-item">
              <div className="workload-status-header">
                <span className="workload-name">{workload.name}</span>
                   {/* ADD THIS: Show device info */}
              {deviceInfo && (
                <div style={{ 
                  marginTop: '8px', 
                  padding: '8px', 
                  background: '#f8f9fa', 
                  borderRadius: '4px',
                  fontSize: '11px'
                }}>
                  <div style={{ marginBottom: '4px' }}>
                    <strong>Device:</strong>{' '}
                    <span style={{ 
                      padding: '2px 6px', 
                      background: '#0071c5', 
                      color: 'white', 
                      borderRadius: '3px',
                      fontWeight: 'bold',
                      fontSize: '10px'
                    }}>
                      {deviceInfo.configured_device}
                    </span>
                  </div>
                  <div style={{ color: '#666', lineHeight: '1.4' }}>
                    {deviceInfo.resolved_detail}
                  </div>
                </div>
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