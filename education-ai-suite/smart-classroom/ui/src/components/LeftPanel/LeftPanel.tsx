import { useState } from "react";
import TranscriptsTab from "../Tabs/TranscriptsTab";
import AISummaryTab from "../Tabs/AISummaryTab";
import MindMapTab from "../Tabs/MindMapTab";
import "../../assets/css/LeftPanel.css";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import { setActiveTab } from "../../redux/slices/uiSlice";
import { useTranslation } from 'react-i18next';
import VideoStream from "./VideoStream";
 
const LeftPanel = () => {
  const dispatch = useAppDispatch();
  const activeTab = useAppSelector((s) => s.ui.activeTab);
  const summaryEnabled = useAppSelector((s) => s.ui.summaryEnabled);
  const summaryLoading = useAppSelector((s) => s.ui.summaryLoading);
  const mindmapEnabled = useAppSelector((s) => s.ui.mindmapEnabled);
  const mindmapLoading = useAppSelector((s) => s.ui.mindmapLoading);
  const { t } = useTranslation();
 
  const [isFullScreen, setIsFullScreen] = useState(false);
 
  const handleToggleFullScreen = () => {
    setIsFullScreen(!isFullScreen);
  };
 
  return (
  <div className={`left-panel-container ${isFullScreen ? "fullscreen" : ""}`}>
      <VideoStream isFullScreen={isFullScreen} onToggleFullScreen={handleToggleFullScreen} />
      <div className="tabs">
        <button
          className={activeTab === "transcripts" ? "active" : ""}
          onClick={() => dispatch(setActiveTab("transcripts"))}
        >
          {t('tabs.transcripts')}
        </button>
        <button
          className={activeTab === "summary" ? "active" : ""}
          onClick={() => dispatch(setActiveTab("summary"))}
          disabled={!summaryEnabled}
          title={summaryEnabled ? t('tabs.summary') : t('tabs.summary') + " available after transcription"}
        >
          <span>{t('tabs.summary')}</span>
          {summaryEnabled && summaryLoading && <span className="tab-spinner" aria-label="loading" />}
        </button>
        <button
          className={activeTab === "mindmap" ? "active" : ""}
          onClick={() => dispatch(setActiveTab("mindmap"))}
          disabled={!mindmapEnabled}
          title={mindmapEnabled ? t('tabs.mindmap') : t('tabs.mindmap') + " available after summary"}
        >
          <span>{t('tabs.mindmap')}</span>
          {mindmapEnabled && mindmapLoading && <span className="tab-spinner" aria-label="loading" />}
        </button>
      </div>
      <div className="tab-content">
        {activeTab === "transcripts" && <TranscriptsTab />}
        {activeTab === "summary" && <AISummaryTab />}
        {activeTab === "mindmap" && <MindMapTab />}
      </div>
    </div>
  );
};
 
export default LeftPanel;