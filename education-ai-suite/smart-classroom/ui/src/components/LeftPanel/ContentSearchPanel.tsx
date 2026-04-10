import React from "react";
import "../../assets/css/LeftPanel.css";
import UploadSection from "./UploadSection";

const ContentSearchPanel: React.FC = () => {
  return (
    <div className="cs-panel">
      <UploadSection />
    </div>
  );
};

export default ContentSearchPanel;
