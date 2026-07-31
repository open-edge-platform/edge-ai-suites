import React from 'react';
import ConfigurationMetricsAccordion from './ConfigurationMetricsAccordion';
import PipelinePerformanceAccordion from './PipelinePerformanceAccordion';
import ResourceUtilizationAccordion from './ResourceUtilizationAccordion';
import '../../assets/css/RightPanel.css';

const RightPanel: React.FC = () => {
  return (
    <div className="right-panel">
      <ConfigurationMetricsAccordion />
      <PipelinePerformanceAccordion />
      <ResourceUtilizationAccordion />
    </div>
  );
};

export default RightPanel;