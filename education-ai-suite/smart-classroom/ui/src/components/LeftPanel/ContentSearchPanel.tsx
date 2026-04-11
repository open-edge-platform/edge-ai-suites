import React from "react";
import "../../assets/css/LeftPanel.css";
import UploadSection from "./UploadSection";
import SearchSection from "./SearchSection";

const ContentSearchPanel: React.FC = () => {
  return (
    <div className="cs-panel">
      <UploadSection />
      <SearchSection />
    </div>
  );
};

export default ContentSearchPanel;
