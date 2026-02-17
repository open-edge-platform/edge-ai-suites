import React from "react";
import ConfigurationMetricsAccordion from "./ConfigurationMetricsAccordion";
import ResourceUtilizationAccordion from "./ResourceUtilizationAccordion";
import ClassStatisticsAccordion from './ClassEngagementAccordion';
import PreValidatedModelsAccordion from "./PreValidatedModelsAccordion";
import "../../assets/css/RightPanel.css";

const RightPanel: React.FC = () => {
  return (
    <div className="right-panel">
      <ConfigurationMetricsAccordion />
      <ResourceUtilizationAccordion />
      <ClassStatisticsAccordion />
      <PreValidatedModelsAccordion />
    </div>
  );
};

export default RightPanel;