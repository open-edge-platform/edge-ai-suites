// src/components/common/Body.tsx
import React, { useState } from "react";
import LeftPanel from "../LeftPanel/LeftPanel";
import RightPanel from "../RightPanel/RightPanel";
import "../../assets/css/Body.css";

const Body: React.FC = () => {
  const [isRightPanelCollapsed, setIsRightPanelCollapsed] = useState(false);

  const toggleRightPanel = () => {
    setIsRightPanelCollapsed(!isRightPanelCollapsed);
  };

  return (
    <div className="container">
      {/* Left Panel - always visible */}
      <div className="left-panel">
        <LeftPanel />
      </div>

      {/* Right Panel - toggles independently */}
      {!isRightPanelCollapsed && (
        <div className="right-panel">
          <RightPanel />
        </div>
      )}

      {/* Arrow - independent toggle */}
      <div
        className={`arrow${isRightPanelCollapsed ? ' collapsed' : ''}`}
        onClick={toggleRightPanel}
        title={isRightPanelCollapsed ? 'Show right panel' : 'Hide right panel'}
      >
        {isRightPanelCollapsed ? "◀" : "▶"}
      </div>
    </div>
  );
};

export default Body;