import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import "../../assets/css/LeftPanel.css";
import UploadSection from "./UploadSection";
import SearchSection from "./SearchSection";
import { getCsHealth, type CsHealthStatus } from "../../services/api";

const ContentSearchPanel: React.FC = () => {
  const { t } = useTranslation();
  const [healthError, setHealthError] = useState<{
    unreachable: boolean;
    unhealthyServices: string[];
  } | null>(null);

  useEffect(() => {
    getCsHealth()
      .then((data: CsHealthStatus) => {
        const unhealthy = Object.entries(data.services)
          .filter(([, status]) => status !== "healthy")
          .map(([name]) => name);
        if (unhealthy.length > 0) {
          setHealthError({ unreachable: false, unhealthyServices: unhealthy });
        } else {
          setHealthError(null);
        }
      })
      .catch(() => {
        setHealthError({ unreachable: true, unhealthyServices: [] });
      });
  }, []);

  return (
    <div className="cs-panel">
      {healthError && (
        <div className="cs-health-banner">
          <span className="cs-health-banner__text">
            {healthError.unreachable
              ? t("contentSearch.backendUnreachable")
              : t("contentSearch.servicesUnhealthy", {
                  services: healthError.unhealthyServices.join(", "),
                })}
          </span>
        </div>
      )}
      <UploadSection disabled={!!healthError} />
      <SearchSection disabled={!!healthError} />
    </div>
  );
};

export default ContentSearchPanel;
