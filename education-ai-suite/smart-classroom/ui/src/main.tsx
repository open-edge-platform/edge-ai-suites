import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Provider } from 'react-redux';
import { store } from './redux/store';
import App from './App';
import ErrorBoundary from './components/common/ErrorBoundary';
import './index.css';
import './i18n'; // Add this import at the top

// Electron-only: mark the document so the custom title bar drag regions and
// window-control safe-area styles activate. No-op in the plain web app.
if (window.electronAPI?.isElectron) {
  document.body.classList.add('electron', `platform-${window.electronAPI.platform}`);
}

const container = document.getElementById('root')!;

// Failures before or during the first render happen outside React, so the error
// boundary cannot catch them. Paint a minimal panel by hand instead of leaving
// a blank window. Built with DOM APIs so the message is never parsed as HTML.
function renderBootstrapFailure(error: unknown): void {
  if (container.childElementCount > 0) return;

  const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
  const stack = error instanceof Error ? error.stack ?? '' : '';

  const screen = document.createElement('div');
  screen.className = 'crash-screen';
  const card = document.createElement('div');
  card.className = 'crash-card';

  const title = document.createElement('h1');
  title.className = 'crash-title';
  title.textContent = 'The interface failed to start';

  const detail = document.createElement('div');
  detail.className = 'crash-message';
  detail.textContent = message;

  const pre = document.createElement('pre');
  pre.className = 'crash-stack';
  pre.textContent = stack || '(no stack available)';

  const actions = document.createElement('div');
  actions.className = 'crash-actions';
  const reload = document.createElement('button');
  reload.className = 'crash-btn crash-btn-primary';
  reload.textContent = 'Reload';
  reload.onclick = () => window.location.reload();
  actions.append(reload);

  card.append(title, detail, pre, actions);
  screen.append(card);
  container.append(screen);
}

window.addEventListener('error', (event) => renderBootstrapFailure(event.error ?? event.message));
window.addEventListener('unhandledrejection', (event) => renderBootstrapFailure(event.reason));

try {
  createRoot(container).render(
    <StrictMode>
      <ErrorBoundary>
        <Provider store={store}>
          <App />
        </Provider>
      </ErrorBoundary>
    </StrictMode>,
  );
} catch (error) {
  renderBootstrapFailure(error);
}
