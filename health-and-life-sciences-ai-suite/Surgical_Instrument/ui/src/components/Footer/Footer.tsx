// src/components/Footer/Footer.tsx
import { constants } from '../../constants';
import '../../assets/css/Footer.css';

const Footer = () => {
  return (
    <div className="footer-bar">
      <span>{constants.COPYRIGHT}</span>
    </div>
  );
};

export default Footer;