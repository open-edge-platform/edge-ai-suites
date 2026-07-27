import React from "react";
import ConfigurationMetricsAccordion from "./ConfigurationMetricsAccordion";
import ResourceUtilizationAccordion from "./ResourceUtilizationAccordion";
import ClassStatisticsAccordion from './ClassEngagementAccordion';
import PreValidatedModelsAccordion from "./PreValidatedModelsAccordion";
import "../../assets/css/RightPanel.css";
import type { FeatureGuard } from "../../utils/featureGuards";

interface RightPanelProps {
  activeScreen: 'main' | 'content-search' | 'grading';
  featureGuard: FeatureGuard;
}

const RightPanel: React.FC<RightPanelProps> = ({ activeScreen, featureGuard }) => {
  return (
    <div className="right-panel">
      <ConfigurationMetricsAccordion activeScreen={activeScreen} />
      <ResourceUtilizationAccordion activeScreen={activeScreen} />
      <div style={{ display: activeScreen === 'main' ? 'contents' : 'none' }}>
        {featureGuard.hasFeature('video_analytics') && <ClassStatisticsAccordion />}
      </div>
      <PreValidatedModelsAccordion activeScreen={activeScreen} />
    </div>
  );
};

export default RightPanel;