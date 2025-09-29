import TranscriptsTab from "../Tabs/TranscriptsTab";
import AISummaryTab from "../Tabs/AISummaryTab";
import "../../assets/css/LeftPanel.css";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import { setActiveTab } from "../../redux/slices/uiSlice";
import { useTranslation } from 'react-i18next';

const LeftPanel = () => {
  const dispatch = useAppDispatch();
  const activeTab = useAppSelector((s) => s.ui.activeTab);
  const summaryEnabled = useAppSelector((s) => s.ui.summaryEnabled);
  const summaryLoading = useAppSelector((s) => s.ui.summaryLoading);
  const { t } = useTranslation();
  return (
    <div className="left-panel">
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
      </div>
      <div className="tab-content">
        {activeTab === "transcripts" && <TranscriptsTab />}
        {activeTab === "summary" && <AISummaryTab />}
      </div>
    </div>
  );
};

export default LeftPanel;