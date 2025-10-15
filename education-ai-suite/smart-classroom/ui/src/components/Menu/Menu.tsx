import { forwardRef } from 'react';
import SettingsModal from './SettingsButton';

interface MenuProps {
  projectName: string;
  setProjectName: (name: string) => void;
  isSettingsOpen: boolean;
  setIsSettingsOpen: (isOpen: boolean) => void;
}

const Menu = forwardRef<HTMLDivElement, MenuProps>(
  ({ projectName, setProjectName, isSettingsOpen, setIsSettingsOpen }, ref) => {
    const closeSettings = () => {
      setIsSettingsOpen(false);
    };

    return (
      <div ref={ref}>
        <SettingsModal
          isOpen={isSettingsOpen}
          onClose={closeSettings}
          projectName={projectName}
          setProjectName={setProjectName}
        />
      </div>
    );
  }
);

export default Menu;
