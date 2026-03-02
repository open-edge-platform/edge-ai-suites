import React from "react";
import { useTranslation } from "react-i18next";
import "../../assets/css/Footer.css";

const Footer: React.FC = () => {
  const { t } = useTranslation();
  const currentYear = new Date().getFullYear();
  return (
    <footer className="footer-bar">
      <span>{t('footer.copyright', { year: currentYear })}</span>
    </footer>
  );
};

export default Footer;