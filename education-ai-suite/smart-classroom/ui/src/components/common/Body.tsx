import React, { useState } from "react";
import LeftPanel from "../LeftPanel/LeftPanel";
import RightPanel from "../RightPanel/RightPanel";
import "../../assets/css/Body.css";

interface BodyProps {
  isModalOpen: boolean;
}

const Body: React.FC<BodyProps> = ({ isModalOpen }) => {
  const [isRightPanelCollapsed, setIsRightPanelCollapsed] = useState(false);

  const toggleRightPanel = () => {
    setIsRightPanelCollapsed(!isRightPanelCollapsed);
  };

  return (
    <div className="container">
      <div className="left-panel">
        <LeftPanel />
      </div>
      <div className="right-panel" style={{ flex: isRightPanelCollapsed ? 0 : 1 }}>
        <RightPanel />
      </div>
      {/* <div
        className="divider"
        style={{ left: isRightPanelCollapsed ? '100%' : '50%' }}
      /> */}
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
      //   <div
      //   className={`arrow${isRightPanelCollapsed ? ' collapsed' : ''}`}
      //   style={{ left: isRightPanelCollapsed ? 'calc(100% - 38px)' : 'calc(50% - 14px)' }}
      //   onClick={toggleRightPanel}
      // >
      //   {isRightPanelCollapsed ? "◀" : "▶"}
      // </div>
      )}
    </div>
  );
};

export default Body;