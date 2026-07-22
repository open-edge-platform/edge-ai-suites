import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Provider } from 'react-redux';
import { store } from './redux/store';
import App from './App';
import './index.css';
import './i18n'; // Add this import at the top

// Electron-only: mark the document so the custom title bar drag regions and
// window-control safe-area styles activate. No-op in the plain web app.
if (window.electronAPI?.isElectron) {
  document.body.classList.add('electron', `platform-${window.electronAPI.platform}`);
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider store={store}>
      <App />
    </Provider>
  </StrictMode>,
);
