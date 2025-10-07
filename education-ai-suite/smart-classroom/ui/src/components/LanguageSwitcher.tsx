import React from 'react';
import { useTranslation } from 'react-i18next';
// const GlobeIcon = () => (
//     <svg width="20" height="20" viewBox="0 0 20 20" style={{ marginRight: 6, verticalAlign: 'middle' }} fill="none">
//       <circle cx="10" cy="10" r="9" stroke="#0071c5" strokeWidth="2"/>
//       <path d="M10 1C13.866 1 17 4.13401 17 8C17 11.866 13.866 15 10 15C6.13401 15 3 11.866 3 8C3 4.13401 6.13401 1 10 1Z" stroke="#0071c5" strokeWidth="1"/>
//       <path d="M1 10H19" stroke="#0071c5" strokeWidth="1"/>
//       <path d="M10 19V1" stroke="#0071c5" strokeWidth="1"/>
//     </svg>
//   );
const LanguageSwitcher: React.FC = () => {
  const { i18n } = useTranslation();
  return (
    <select
      value={i18n.language}
      onChange={e => i18n.changeLanguage(e.target.value)}
      style={{ marginRight: '16px', padding: '4px 8px', borderRadius: '4px' }}
      aria-label="Language Switch"
    >
      <option value="en">English</option>
      <option value="zh">中文</option>
    </select>
  );
};

export default LanguageSwitcher;