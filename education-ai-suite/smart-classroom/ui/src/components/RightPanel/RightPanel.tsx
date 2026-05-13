import React from "react";
import ConfigurationMetricsAccordion from "./ConfigurationMetricsAccordion";
import ResourceUtilizationAccordion from "./ResourceUtilizationAccordion";
import ClassStatisticsAccordion from './ClassEngagementAccordion';
import PreValidatedModelsAccordion from "./PreValidatedModelsAccordion";
import "../../assets/css/RightPanel.css";

interface RightPanelProps {
  activeScreen: 'main' | 'content-search';
}

const RightPanel: React.FC<RightPanelProps> = ({ activeScreen }) => {
  return (
    <div className="right-panel">
      <ConfigurationMetricsAccordion activeScreen={activeScreen} />
      <ResourceUtilizationAccordion activeScreen={activeScreen} />
      <div style={{ display: activeScreen === 'main' ? 'contents' : 'none' }}>
        <ClassStatisticsAccordion />
      </div>
      <PreValidatedModelsAccordion activeScreen={activeScreen} />
    </div>
  );
};

export default RightPanel;