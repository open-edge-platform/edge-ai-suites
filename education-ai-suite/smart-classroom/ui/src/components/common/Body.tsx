import React, { useState } from "react";
import LeftPanel from "../LeftPanel/LeftPanel";
import RightPanel from "../RightPanel/RightPanel";
import ContentSearchPanel from "../LeftPanel/ContentSearchPanel";
import "../../assets/css/Body.css";
import { usePanelDividerX } from "../../hooks/usePanelDividerX";
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
  const { containerRef, panelRef, arrowLeft, arrowTransition } =
    usePanelDividerX(isRightPanelCollapsed);

  // Show ContentSearchPanel if either content_search OR qa feature is enabled
  const hasContentSearchFeatures = featureGuard.hasFeature('content_search') || featureGuard.hasFeature('qa');

  return (
    <div className="container" ref={containerRef}>
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
      <div
        className="right-panel-slot"
        ref={panelRef}
        style={{ flex: isRightPanelCollapsed ? 0 : 1 }}
      >
        <RightPanel activeScreen={activeScreen} featureGuard={featureGuard} />
      </div>
      {!isModalOpen && (
        <div
          className={`arrow${isRightPanelCollapsed ? ' collapsed' : ''}`}
          style={{
            // When collapsed the divider is the container's own right edge, so
            // let `.arrow.collapsed` park the toggle just inside it instead.
            left: isRightPanelCollapsed ? undefined : arrowLeft,
            top: '50%',
            transform: 'translateY(-50%)',
            transition: arrowTransition
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