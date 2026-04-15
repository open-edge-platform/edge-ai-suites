import React, { useState } from "react";
import LeftPanel from "../LeftPanel/LeftPanel";
import RightPanel from "../RightPanel/RightPanel";
import ContentSearchPanel from "../LeftPanel/ContentSearchPanel";
import "../../assets/css/Body.css";

interface BodyProps {
  isModalOpen: boolean;
  activeScreen: 'main' | 'content-search';
}

const Body: React.FC<BodyProps> = ({ isModalOpen, activeScreen }) => {
  const [isRightPanelCollapsed, setIsRightPanelCollapsed] = useState(false);
  const toggleRightPanel = () => setIsRightPanelCollapsed(!isRightPanelCollapsed);

  return (
    <div className="container">
      <div className="left-panel">
        <div style={{ display: activeScreen === 'main' ? 'contents' : 'none' }}>
          <LeftPanel />
        </div>
        <div style={{ display: activeScreen === 'content-search' ? 'contents' : 'none' }}>
          <ContentSearchPanel />
        </div>
      </div>
      <div className="right-panel" style={{ flex: isRightPanelCollapsed ? 0 : 1 }}>
        <RightPanel activeScreen={activeScreen} />
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