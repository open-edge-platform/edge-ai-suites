import React from 'react';
import { useTranslation } from 'react-i18next';
import Accordion from '../common/Accordion';
import Timeline from './Timeline';

const TimelineAccordion: React.FC = () => {
  const { t } = useTranslation();

  return (
    <Accordion title={t('accordion.speakingTimeline')}>
      <div className="accordion-content">
        <div className="analytics-section audio-analytics" style={{ margin: '10px 2px 3px 4px' }}>
          <Timeline />
        </div>
      </div>
    </Accordion>
  );
};

export default TimelineAccordion;
