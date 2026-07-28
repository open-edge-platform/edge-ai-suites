import React from 'react';
import { useTranslation } from 'react-i18next';

const Help: React.FC = () => {
  const { t } = useTranslation();
  
  return (
    <div className="help-content">
      <h2>{t('menu.help')}</h2>
      <p>{t('menu.helpDescription')}</p>
    </div>
  );
};

export default Help;