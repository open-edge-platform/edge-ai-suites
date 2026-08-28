// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Catches render-phase crashes. Without this React 19 unmounts the whole tree
// on an uncaught error, produces blank white window.
//
// Deliberately free of i18n, Redux and app services: whatever broke may be one
// of them, so this screen must be able to render on its own.

import React from 'react';
import '../../assets/css/ErrorBoundary.css';

interface Props {
  children: React.ReactNode;
}

interface State {
  error: Error | null;
  componentStack: string;
}

function formatReport(error: Error, componentStack: string): string {
  return [
    `Time: ${new Date().toISOString()}`,
    `Error: ${error.name}: ${error.message}`,
    '',
    'Stack:',
    error.stack ?? '(none)',
    '',
    'Component stack:',
    componentStack || '(none)',
  ].join('\n');
}

class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null, componentStack: '' };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    this.setState({ componentStack: info.componentStack ?? '' });
    // Also lands in the Electron main-process log via the console-message hook.
    console.error('[ui] render crash:', error, info.componentStack);
  }

  handleCopy = () => {
    const { error, componentStack } = this.state;
    if (error) navigator.clipboard?.writeText(formatReport(error, componentStack)).catch(() => undefined);
  };

  handleReload = () => {
    window.location.reload();
  };

  // Re-mounts the tree; useful when the crash came from transient state.
  handleDismiss = () => {
    this.setState({ error: null, componentStack: '' });
  };

  render() {
    const { error, componentStack } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="crash-screen">
        <div className="crash-card">
          <h1 className="crash-title">The interface stopped responding</h1>
          <p className="crash-lead">
            A rendering error was caught. The backend services are unaffected and keep running.
          </p>

          <div className="crash-message">
            {error.name}: {error.message}
          </div>

          <details className="crash-details" open>
            <summary>Details</summary>
            <pre className="crash-stack">{formatReport(error, componentStack)}</pre>
          </details>

          <div className="crash-actions">
            <button className="crash-btn crash-btn-primary" onClick={this.handleReload}>
              Reload
            </button>
            <button className="crash-btn" onClick={this.handleDismiss}>
              Try to continue
            </button>
            <button className="crash-btn" onClick={this.handleCopy}>
              Copy report
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
