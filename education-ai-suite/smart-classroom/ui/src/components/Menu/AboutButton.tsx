import React from 'react';
import { useTranslation } from 'react-i18next';

const About: React.FC = () => {
  const { t } = useTranslation();
  
  return (
    <div className="about-content">
      <h2>{t('menu.about')}</h2>
      <p>{t('menu.aboutDescription')}</p>
    </div>
  );
};

export default About;