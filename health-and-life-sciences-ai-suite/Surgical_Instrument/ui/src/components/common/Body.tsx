import React from "react";
import RightPanel from "../RightPanel/RightPanel";
import ConfigPanel from "../ConfigPanel/ConfigPanel";
import "../../assets/css/Body.css";

const Body: React.FC = () => {
  return (
    <div className="container">
      <div className="left-panel">
        <ConfigPanel />
      </div>
      <div className="right-panel-shell">
        <RightPanel />
      </div>
    </div>
  );
};

export default Body;