import React from "react";
import ConfigurationMetricsAccordion from "./ConfigurationMetricsAccordion";
import ResourceUtilizationAccordion from "./ResourceUtilizationAccordion";
import ClassStatisticsAccordion from './ClassEngagementAccordion';
import TimelineAccordion from './TimelineAccordion';
import PreValidatedModelsAccordion from "./PreValidatedModelsAccordion";
import "../../assets/css/RightPanel.css";
import type { FeatureGuard } from "../../utils/featureGuards";

interface RightPanelProps {
  activeScreen: 'main' | 'content-search' | 'grading';
  featureGuard: FeatureGuard;
}

const RightPanel: React.FC<RightPanelProps> = ({ activeScreen, featureGuard }) => {
  const hasASR = featureGuard.hasFeature('asr');
  const hasVideoAnalytics = featureGuard.hasFeature('video_analytics');
  
  return (
    <div className="right-panel">
      <ConfigurationMetricsAccordion activeScreen={activeScreen} />
      <ResourceUtilizationAccordion activeScreen={activeScreen} />
      <div style={{ display: activeScreen === 'main' ? 'contents' : 'none' }}>
        {/* Show ClassStatisticsAccordion when video analytics is enabled */}
        {hasVideoAnalytics && <ClassStatisticsAccordion featureGuard={featureGuard} />}
        
        {/* Show standalone TimelineAccordion only when ASR is enabled but video analytics is NOT */}
        {hasASR && !hasVideoAnalytics && <TimelineAccordion />}
      </div>
      <PreValidatedModelsAccordion activeScreen={activeScreen} />
    </div>
  );
};

export default RightPanel;