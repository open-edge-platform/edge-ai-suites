import React, { useEffect, useState } from "react";
import Accordion from "../common/Accordion";
import "../../assets/css/RightPanel.css";
import { useTranslation } from "react-i18next";
import { getPlatformInfo } from "../../services/api";

const PreValidatedModelsAccordion: React.FC = () => {
  const { t } = useTranslation();

  const [models, setModels] = useState<{ asr_model?: string; summarizer_model?: string }>({});

  useEffect(() => {
    const fetchModels = async () => {
      const data = await getPlatformInfo();
      setModels({
        asr_model: data?.asr_model,
        summarizer_model: data?.summarizer_model,
      });
    };

    fetchModels();
  }, []);

  return (
    <Accordion title={t("accordion.models")}>
      <div className="accordion-subtitle">{t("accordion.subtitle_models")}</div>
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
    </Accordion>
  );
};

export default PreValidatedModelsAccordion;
