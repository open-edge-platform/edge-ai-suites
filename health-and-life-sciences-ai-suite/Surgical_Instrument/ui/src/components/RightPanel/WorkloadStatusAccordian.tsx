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
      <div className="configuration-metrics">
        {WORKLOADS.map((workload) => {
          const deviceKey = deviceKeyMap[workload.id];
          const deviceInfo =
            workloadDevices?.workloads?.[
              deviceKey as keyof typeof workloadDevices.workloads
            ];

          return (
            <div
              key={workload.id}
              className="platform-configuration"
            >
              <h3>{workload.name}</h3>

              {deviceInfo ? (
                <>
                  <p>
                    <strong>Device:</strong>{' '}
                    <span className="value">
                      {deviceInfo.configured_device}
                    </span>
                  </p>
                </>
              ) : (
                <p className="muted">No device information available</p>
              )}
            </div>
          );
        })}
      </div>
    </Accordion>
  );
};

export default WorkloadStatusAccordion;