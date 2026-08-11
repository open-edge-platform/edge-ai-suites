import React, { useState } from "react";
import LeftPanel from "../LeftPanel/LeftPanel";
import RightPanel from "../RightPanel/RightPanel";
import ContentSearchPanel from "../LeftPanel/ContentSearchPanel";
import "../../assets/css/Body.css";
import type { FeatureGuard } from "../../utils/featureGuards";

interface BodyProps {
  isModalOpen: boolean;
  activeScreen: 'main' | 'content-search' | 'grading';
  featureGuard: FeatureGuard;
  hasMainFeatures: boolean;
}

const Body: React.FC<BodyProps> = ({ isModalOpen, activeScreen, featureGuard, hasMainFeatures }) => {
  const [isRightPanelCollapsed, setIsRightPanelCollapsed] = useState(false);
  const toggleRightPanel = () => setIsRightPanelCollapsed(!isRightPanelCollapsed);
  
  // Show ContentSearchPanel if either content_search OR qa feature is enabled
  const hasContentSearchFeatures = featureGuard.hasFeature('content_search') || featureGuard.hasFeature('qa');

  return (
    <div className="container">
      <div className="left-panel">
        <div style={{ display: activeScreen === 'main' ? 'contents' : 'none' }}>
          <LeftPanel featureGuard={featureGuard} />
        </div>
        <div style={{ display: activeScreen === 'content-search' ? 'contents' : 'none' }}>
          {hasContentSearchFeatures && (
            <ContentSearchPanel active={activeScreen === 'content-search'} />
          )}
        </div>
      </div>
      <div className="right-panel" style={{ flex: isRightPanelCollapsed ? 0 : 1 }}>
        <RightPanel activeScreen={activeScreen} featureGuard={featureGuard} />
      </div>
      {!isModalOpen && (
        <div
          className={`arrow${isRightPanelCollapsed ? ' collapsed' : ''}`}
          style={{
            left: isRightPanelCollapsed ? 'calc(100% - 38px)' : 'calc(50% - 14px)',
            top: '50%',
            transform: 'translateY(-50%)'
          }}
          onClick={toggleRightPanel}
        >
          {isRightPanelCollapsed ? "◀" : "▶"}
        </div>
      )}
    </div>
  );
};

export default Body;