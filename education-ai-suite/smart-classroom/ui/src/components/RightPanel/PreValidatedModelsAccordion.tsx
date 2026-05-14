import React, { useEffect, useState } from "react";
import Accordion from "../common/Accordion";
import "../../assets/css/RightPanel.css";
import { useTranslation } from "react-i18next";
import { getPlatformInfo, getCsSystemConfig } from "../../services/api";

interface Props {
  activeScreen: 'main' | 'content-search';
}

const PreValidatedModelsAccordion: React.FC<Props> = ({ activeScreen }) => {
  const { t } = useTranslation();

  const [models, setModels] = useState<{ asr_model?: string; summarizer_model?: string }>({});
  const [csConfig, setCsConfig] = useState<any>(null);

  useEffect(() => {
    if (activeScreen === 'main') {
      const fetchModels = async () => {
        const data = await getPlatformInfo();
        setModels({
          asr_model: data?.asr_model,
          summarizer_model: data?.summarizer_model,
        });
      };
      fetchModels();
    }
  }, [activeScreen]);

  useEffect(() => {
    if (activeScreen === 'content-search' && !csConfig) {
      getCsSystemConfig()
        .then(setCsConfig)
        .catch((err) => console.error("Failed to fetch CS system config:", err));
    }
  }, [activeScreen, csConfig]);

  return (
    <Accordion title={t("accordion.models")}>
      <div className="accordion-subtitle">{t("accordion.subtitle_models")}</div>

      {activeScreen === 'content-search' ? (
        <div className="dropdown-container" style={{ flexWrap: "wrap" }}>
          <div className="dropdown-section" style={{ flex: "1 1 calc(50% - 10px)", minWidth: 0 }}>
            <div className="accordion-content">{t("accordion.vlmModel") || "VLM Model"}</div>
            <select className="dropdown">
              <option>{csConfig?.vlm_model || "loading..."}</option>
            </select>
          </div>
          <div className="dropdown-section" style={{ flex: "1 1 calc(50% - 10px)", minWidth: 0 }}>
            <div className="accordion-content">{t("accordion.visualEmbeddingModel") || "Visual Embedding Model"}</div>
            <select className="dropdown">
              <option>{csConfig?.visual_embedding_model || "loading..."}</option>
            </select>
          </div>
          <div className="dropdown-section" style={{ flex: "1 1 calc(50% - 10px)", minWidth: 0 }}>
            <div className="accordion-content">{t("accordion.docEmbeddingModel") || "Document Embedding Model"}</div>
            <select className="dropdown">
              <option>{csConfig?.doc_embedding_model || "loading..."}</option>
            </select>
          </div>
          <div className="dropdown-section" style={{ flex: "1 1 calc(50% - 10px)", minWidth: 0 }}>
            <div className="accordion-content">{t("accordion.rerankerModel") || "Reranker Model"}</div>
            <select className="dropdown">
              <option>{csConfig?.reranker_model || "loading..."}</option>
            </select>
          </div>
        </div>
      ) : (
        <div className="dropdown-container">
          <div className="dropdown-section">
            <div className="accordion-content">{t("accordion.transcriptsModel")}</div>
            <select className="dropdown">
              {models.asr_model ? (
                <option value={models.asr_model}>{models.asr_model}</option>
              ) : (
                <option>loading...</option>
              )}
            </select>
          </div>
          <div className="dropdown-section">
            <div className="accordion-content">{t("accordion.summaryModel")}</div>
            <select className="dropdown">
              {models.summarizer_model ? (
                <option value={models.summarizer_model}>{models.summarizer_model}</option>
              ) : (
                <option>loading...</option>
              )}
            </select>
          </div>
        </div>
      )}
    </Accordion>
  );
};

export default PreValidatedModelsAccordion;
