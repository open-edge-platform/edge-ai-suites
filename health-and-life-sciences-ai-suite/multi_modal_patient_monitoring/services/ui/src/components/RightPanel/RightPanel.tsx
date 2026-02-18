import React from 'react';
import ConfigurationMetricsAccordion from './ConfigurationMetricsAccordion';
import ResourceUtilizationAccordion from './ResourceUtilizationAccordion';
import '../../assets/css/RightPanel.css';
import WorkloadStatusAccordion from './WorkloadStatusAccordian';

const RightPanel: React.FC = () => {
  return (
    <div className="right-panel">
      <ConfigurationMetricsAccordion />
      <WorkloadStatusAccordion />
      <ResourceUtilizationAccordion />
    </div>
  );
};

export default RightPanel;