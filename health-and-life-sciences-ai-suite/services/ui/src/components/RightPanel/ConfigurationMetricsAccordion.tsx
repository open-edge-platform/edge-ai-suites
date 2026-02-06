import React, { useEffect, useState } from "react";
import Accordion from "../common/Accordion";
import "../../assets/css/RightPanel.css";
// import { useTranslation } from "react-i18next"; // COMMENTED - not needed for Phase 1
import { useAppSelector } from "../../redux/hooks";
// import { getConfigurationMetrics, getPlatformInfo } from "../../services/api"; // COMMENTED - Phase 2

const ConfigurationMetricsAccordion: React.FC = () => {
  // const { t } = useTranslation(); // COMMENTED
  // const sessionId = useAppSelector((state) => state.ui.sessionId); // COMMENTED - ui slice doesn't exist yet
  // const summaryDone = useAppSelector(
  //   (state) => !state.ui.aiProcessing && state.ui.summaryEnabled && !state.ui.summaryLoading
  // ); // COMMENTED

  const [platformData] = useState<any>({
    Processor: 'Intel Core Ultra 7',
    NPU: 'Intel AI Boost',
    iGPU: 'Intel Arc Graphics',
    Memory: '32GB DDR5',
    Storage: '1TB NVMe SSD',
  }); // MOCK DATA for Phase 1

  const [performanceData] = useState<any>({
    ttft: '0.5s',
    tps: '120 tokens/s',
    total_tokens: '1,234',
    end_to_end_time: '10.2s',
  }); // MOCK DATA for Phase 1

  // COMMENTED - API calls for Phase 2
  // useEffect(() => {
  //   if (!platformData) {
  //     (async () => {
  //       try {
  //         const platformResp = await getPlatformInfo();
  //         setPlatformData(platformResp);
  //       } catch (err) {
  //         console.error("Failed to fetch platform info:", err);
  //       }
  //     })();
  //   }
  // }, [platformData]);

  // useEffect(() => {
  //   setPerformanceData(null);
  //   if (summaryDone && sessionId) {
  //     (async () => {
  //       try {
  //         const configResp = await getConfigurationMetrics(sessionId);
  //         setPerformanceData(configResp.performance);
  //       } catch (err) {
  //         console.error("Failed to fetch performance metrics:", err);
  //       }
  //     })();
  //   }
  // }, [summaryDone, sessionId]);

  return (
    <Accordion title="⚙️ Configuration & Metrics">
      <div className="accordion-subtitle">
        Platform configuration and system performance metrics
      </div>

      <div className="configuration-metrics two-column">
        {/* Platform configuration */}
        <div className="platform-configuration">
          <h3>Platform Configuration</h3>
          <p><strong>Processor:</strong> {platformData?.Processor || "-"}</p>
          <p><strong>NPU:</strong> {platformData?.NPU || "-"}</p>
          <p><strong>iGPU:</strong> {platformData?.iGPU || "-"}</p>
          <p><strong>Memory:</strong> {platformData?.Memory || "-"}</p>
          <p><strong>Storage:</strong> {platformData?.Storage || "-"}</p>
        </div>

        {/* Software/Performance */}
        <div className="software-performance">
          <h3>System Metrics</h3>
          <p><strong>TTFT:</strong> {performanceData?.ttft || "-"}</p>
          <p><strong>Tokens/sec:</strong> {performanceData?.tps || "-"}</p>
          <p><strong>Total Tokens:</strong> {performanceData?.total_tokens || "-"}</p>
          <p><strong>Processing Time:</strong> {performanceData?.end_to_end_time || "-"}</p>
        </div>
      </div>
    </Accordion>
  );
};

export default ConfigurationMetricsAccordion;