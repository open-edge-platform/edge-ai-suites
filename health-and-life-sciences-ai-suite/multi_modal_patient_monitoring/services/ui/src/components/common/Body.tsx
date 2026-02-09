// src/components/common/Body.tsx
import React, { useState, useEffect } from "react";
import LeftPanel from "../LeftPanel/LeftPanel";
import RightPanel from "../RightPanel/RightPanel";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import { setExpandedWorkload } from "../../redux/slices/appSlice";
import "../../assets/css/Body.css";

const Body: React.FC = () => {
  const dispatch = useAppDispatch();
  const [isRightPanelCollapsed, setIsRightPanelCollapsed] = useState(false);
  const expandedWorkload = useAppSelector((state) => state.app.expandedWorkload);

  // Auto-collapse right panel when a card is expanded
  useEffect(() => {
    if (expandedWorkload) {
      setIsRightPanelCollapsed(true);
    }
  }, [expandedWorkload]);

  const toggleRightPanel = () => {
    if (isRightPanelCollapsed && expandedWorkload) {
      // If right panel is collapsed AND a card is expanded
      // Return to default state: close expanded card + show right panel
      dispatch(setExpandedWorkload(null));
      setIsRightPanelCollapsed(false);
    } else {
      // Normal toggle behavior
      setIsRightPanelCollapsed(!isRightPanelCollapsed);
    }
  };

  const shouldShowRightPanel = !isRightPanelCollapsed;

  return (
    <div className="container">
      <div className="left-panel">
        <LeftPanel />
      </div>
      {shouldShowRightPanel && (
        <div className="right-panel">
          <RightPanel />
        </div>
      )}
      {/* Arrow always visible */}
      <div
        className={`arrow${isRightPanelCollapsed ? ' collapsed' : ''}`}
        style={{
          left: isRightPanelCollapsed ? 'calc(100% - 38px)' : 'calc(50% - 14px)',
          top: '50%',
          transform: 'translateY(-50%)'
        }}
        onClick={toggleRightPanel}
        title={isRightPanelCollapsed && expandedWorkload ? 'Click to return to default view' : 'Toggle right panel'}
      >
        {isRightPanelCollapsed ? "◀" : "▶"}
      </div>
    </div>
  );
};

export default Body;