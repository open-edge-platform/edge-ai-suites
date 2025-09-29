import React from "react";
import { useTranslation } from "react-i18next";
import "../../assets/css/Footer.css";

const Footer: React.FC = () => {
  const { t } = useTranslation();
  return (
    <footer className="footer-bar">
      <span>{t('footer.copyright')}</span>
    </footer>
  );
};

export default Footer;