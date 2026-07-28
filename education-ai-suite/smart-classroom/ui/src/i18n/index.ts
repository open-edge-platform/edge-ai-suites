import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './en.json';
import zh from './zh.json';

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      zh: { translation: zh }
    },
    lng: 'en',
    fallbackLng: 'en',
    interpolation: { escapeValue: false }
  });

// Keep the Electron native menus (application + context menu) in sync with the
// app language. No-op on the plain web app, where `electronAPI` is undefined.
const syncElectronMenuLanguage = (lang: string) => {
  window.electronAPI?.setLanguage?.(lang);
};
syncElectronMenuLanguage(i18n.language);
i18n.on('languageChanged', syncElectronMenuLanguage);

export default i18n;