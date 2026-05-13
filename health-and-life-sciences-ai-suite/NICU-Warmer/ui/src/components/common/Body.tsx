import React, { useState } from "react";
import RightPanel from "../RightPanel/RightPanel";
import NicuPanel from "../NicuPanel/NicuPanel";
import "../../assets/css/Body.css";

const Body: React.FC = () => {
  const [isRightPanelCollapsed, setIsRightPanelCollapsed] = useState(false);

  return (
    <div className="container">
      {/* Left Panel — NicuPanel, expands to full width when right panel is hidden */}
      <div className={`left-panel${isRightPanelCollapsed ? ' left-panel--full' : ''}`}>
        <NicuPanel expanded={isRightPanelCollapsed} />
      </div>

      {/* Right Panel */}
      {!isRightPanelCollapsed && (
        <div className="right-panel">
          <RightPanel />
        </div>
      )}

      {/* Toggle arrow */}
      <div
        className={`arrow${isRightPanelCollapsed ? ' collapsed' : ''}`}
        onClick={() => setIsRightPanelCollapsed(prev => !prev)}
        title={isRightPanelCollapsed ? 'Show right panel' : 'Hide right panel'}
      >
        {isRightPanelCollapsed ? '◀' : '▶'}
      </div>
    </div>
  );
};

export default Body;