import React from 'react';
import '../../assets/css/MonitoringPausedBanner.css';
import { RESOURCE_METRIC_DURATION_MIN } from '../../utils/resourceMetricConfig';
import { useTranslation } from 'react-i18next';

interface MonitoringPausedBannerProps {
  onResume: () => void;
}

const MonitoringPausedBanner: React.FC<MonitoringPausedBannerProps> = ({ onResume }) => {
  const { t } = useTranslation();

  return (
    <div className="mpb" role="status" aria-live="polite">
      <div className="mpb__indicator" aria-hidden="true" />
      <div className="mpb__body">
        <div className="mpb__header">
          <svg className="mpb__icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <circle cx="10" cy="10" r="9" stroke="currentColor" strokeWidth="1.5" />
            <rect x="7" y="6" width="2.2" height="8" rx="1" fill="currentColor" />
            <rect x="10.8" y="6" width="2.2" height="8" rx="1" fill="currentColor" />
          </svg>
          <span className="mpb__title">
            {t('monitoring.pausedTitle', 'Resource Monitoring Paused')}
          </span>
        </div>
        <p className="mpb__message">
          {t(
            'monitoring.pausedMessage',
            `Metric polling has automatically stopped after ${RESOURCE_METRIC_DURATION_MIN} minutes to conserve system resources. Resume to continue tracking performance data.`,
            { duration: RESOURCE_METRIC_DURATION_MIN }
          )}
        </p>
      </div>
      <button
        className="mpb__resume-btn"
        onClick={onResume}
        aria-label={t('monitoring.resumeAriaLabel', 'Resume resource metric polling')}
      >
        <svg className="mpb__btn-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <polygon points="4,2 14,8 4,14" fill="currentColor" />
        </svg>
        {t('monitoring.resumeButton', 'Resume')}
      </button>
    </div>
  );
};

export default MonitoringPausedBanner;

