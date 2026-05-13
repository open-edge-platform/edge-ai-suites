import React, { useEffect, useState } from "react";
import Accordion from "../common/Accordion";
import "../../assets/css/RightPanel.css";
import { useTranslation } from "react-i18next";
import { useAppSelector } from "../../redux/hooks";
import { getConfigurationMetrics, getPlatformInfo, getCsSystemConfig } from "../../services/api";

interface Props {
  activeScreen: 'main' | 'content-search';
}

const ConfigurationMetricsAccordion: React.FC<Props> = ({ activeScreen }) => {
  const { t } = useTranslation();
  const sessionId = useAppSelector((state) => state.ui.sessionId);
  const summaryDone = useAppSelector(
    (state) => !state.ui.aiProcessing && state.ui.summaryEnabled && !state.ui.summaryLoading
  );

  const [platformData, setPlatformData] = useState<any>(null);
  const [performanceData, setPerformanceData] = useState<any>(null);
  const [csConfig, setCsConfig] = useState<any>(null);

  useEffect(() => {
    if (!platformData) {
      (async () => {
        try {
          const platformResp = await getPlatformInfo();
          setPlatformData(platformResp);
        } catch (err) {
          console.error("Failed to fetch platform info:", err);
        }
      })();
    }
  }, [platformData]);

  useEffect(() => {
    if (activeScreen === 'content-search' && !csConfig) {
      (async () => {
        try {
          const config = await getCsSystemConfig();
          setCsConfig(config);
        } catch (err) {
          console.error("Failed to fetch CS system config:", err);
        }
      })();
    }
  }, [activeScreen, csConfig]);

  useEffect(() => {
    setPerformanceData(null);
    if (summaryDone && sessionId) {
      (async () => {
        try {
          const configResp = await getConfigurationMetrics(sessionId);
          setPerformanceData(configResp.performance);
        } catch (err) {
          console.error("Failed to fetch performance metrics:", err);
        }
      })();
    }
  }, [summaryDone, sessionId]);

  return (
    <Accordion title={t("accordion.configuration")}>
      <div className="accordion-subtitle">
        {t("accordion.subtitle_configuration")}
      </div>

      <div className="configuration-metrics two-column">
        {/* Platform configuration */}
        <div className="platform-configuration">
          <h3>{t("accordion.platformConfiguration") || "Platform Configuration"}</h3>
          <p><strong>{t("accordion.processor") || "Processor"}:</strong> {platformData?.Processor || "-"}</p>
          <p><strong>{t("accordion.npu") || "NPU"}:</strong> {platformData?.NPU || "-"}</p>
          <p><strong>{t("accordion.igpu") || "iGPU"}:</strong> {platformData?.iGPU || "-"}</p>
          <p><strong>{t("accordion.memory") || "Memory"}:</strong> {platformData?.Memory || "-"}</p>
          <p><strong>{t("accordion.storage") || "Storage"}:</strong> {platformData?.Storage || "-"}</p>
        </div>

        {/* Software configuration */}
        <div className="software-performance">
          <h3>{t("accordion.softwareConfiguration") || "Software Configuration"}</h3>

          {activeScreen === 'content-search' ? (
            <>
              <p><strong>{t("accordion.vlmModel") || "VLM Model"}:</strong> {csConfig?.vlm_model || "-"}</p>
              <p><strong>{t("accordion.visualEmbeddingModel") || "Visual Embedding Model"}:</strong> {csConfig?.visual_embedding_model || "-"}</p>
              <p><strong>{t("accordion.docEmbeddingModel") || "Document Embedding Model"}:</strong> {csConfig?.doc_embedding_model || "-"}</p>
              <p><strong>{t("accordion.rerankerModel") || "Reranker Model"}:</strong> {csConfig?.reranker_model || "-"}</p>
              <p><strong>{t("accordion.vectorDb") || "Vector DB"}:</strong> {csConfig?.vector_db || "-"}</p>
              <p><strong>{t("accordion.videoSummarizationEnabled") || "Video Summarization"}:</strong> {csConfig ? (csConfig.video_summarization_enabled ? t("accordion.enabled") || "Enabled" : t("accordion.disabled") || "Disabled") : "-"}</p>
            </>
          ) : (
            <>
              <p><strong>{t("accordion.llm") || "LLM"}:</strong> {platformData?.summarizer_model || "-"}</p>
              <p><strong>{t("accordion.asr") || "ASR"}:</strong> {platformData?.asr_model || "-"}</p>

              {/* Performance metrics — main screen only */}
              <h3>{t("accordion.performanceMetrics") || "Performance Metrics"}</h3>
              <p><strong>{t("accordion.ttft") || "TTFT"}:</strong> {performanceData?.ttft || "-"}</p>
              <p><strong>{t("accordion.tps") || "Tokens Per Second"}:</strong> {performanceData?.tps || "-"}</p>
              <p><strong>{t("accordion.totalTokensProcessed") || "Total tokens processed"}:</strong> {performanceData?.total_tokens || "-"}</p>
              <p><strong>{t("accordion.totalTimeTaken") || "Total Time Taken"}:</strong> {performanceData?.end_to_end_time || "-"}</p>
            </>
          )}
        </div>
      </div>
    </Accordion>
  );
};

export default ConfigurationMetricsAccordion;
