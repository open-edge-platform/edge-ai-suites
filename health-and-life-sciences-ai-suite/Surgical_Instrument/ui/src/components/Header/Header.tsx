// src/components/Header/Header.tsx
import BrandSlot from '../../assets/images/BrandSlot.svg';
import { constants } from '../../constants';
import '../../assets/css/HeaderBar.css';

const Header = () => {
  return (
    <div className="header-bar">
      <div className="brand-slot">
        <img src={BrandSlot} alt="Intel" className="logo" />
        <span className="app-title">{constants.TITLE}</span>
      </div>
    </div>
  );
};

export default Header;