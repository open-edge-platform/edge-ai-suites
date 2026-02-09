import React from 'react';
import { useAppSelector } from '../../redux/hooks';
import Accordion from '../common/Accordion';
import '../../assets/css/RightPanel.css';

export function ConfigurationMetricsAccordion() {
  const platformData = useAppSelector((state) => state.metrics.platform);

  return (
    <Accordion title="Configuration & Metrics">
      <div className="accordion-subtitle">
        Platform & Software Configuration
      </div>

      <div className="configuration-metrics">
        <div className="platform-configuration">
          <h3>Platform Configuration</h3>
          <p><strong>Processor:</strong> {platformData?.processor || 'Loading...'}</p>
          <p><strong>NPU:</strong> {platformData?.npu || 'N/A'}</p>
          <p><strong>iGPU:</strong> {platformData?.igpu || 'N/A'}</p>
          <p><strong>Memory:</strong> {platformData?.memory || 'Loading...'}</p>
          <p><strong>Storage:</strong> {platformData?.storage || 'Loading...'}</p>
          <p><strong>OS:</strong> {platformData?.os || 'Loading...'}</p>
        </div>

        {/* <div className="software-configuration">
          <h3>Workload Configuration</h3>
          <p><strong>AI-ECG Model:</strong> MTTS-CAN</p>
          <p><strong>rPPG Model:</strong> MTTS-CAN (HDF5)</p>
          <p><strong>3D Pose Model:</strong> YOLOv8-Pose</p>
          <p><strong>MDPNP:</strong> OpenICE DDS Bridge</p>
        </div> */}
      </div>
    </Accordion>
  );
}

export default ConfigurationMetricsAccordion;