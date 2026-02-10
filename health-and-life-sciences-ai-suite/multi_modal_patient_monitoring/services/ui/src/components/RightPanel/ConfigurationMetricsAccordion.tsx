import React from 'react';
import { useAppSelector } from '../../redux/hooks';
import Accordion from '../common/Accordion';
import '../../assets/css/RightPanel.css';

export function ConfigurationMetricsAccordion() {
  const platformData = useAppSelector((state) => state.metrics.platform);

  console.log('[ConfigurationMetricsAccordion] Rendering with data:', platformData);

  return (
    <Accordion title="Configuration" defaultOpen>
      <div className="configuration-metrics">
        <div className="platform-configuration">
          <h3>Platform Configuration</h3>
          {/* Use capital letters to match API */}
          <p><strong>Processor:</strong> {platformData?.Processor || 'Loading...'}</p>
          <p><strong>NPU:</strong> {platformData?.NPU || 'N/A'}</p>
          <p><strong>iGPU:</strong> {platformData?.iGPU || 'N/A'}</p>
          <p><strong>Memory:</strong> {platformData?.Memory || 'Loading...'}</p>
          <p><strong>Storage:</strong> {platformData?.Storage || 'Loading...'}</p>
          <p><strong>OS:</strong> {platformData?.OS || 'Linux'}</p>
        </div>
      </div>
    </Accordion>
  );
}

export default ConfigurationMetricsAccordion;