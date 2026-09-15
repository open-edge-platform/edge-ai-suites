import React, { useEffect, useState } from 'react';
import '../../assets/css/Grading.css';
import { useTranslation } from 'react-i18next';
import NewTaskForm from './NewTaskForm';
import TaskList from './TaskList';
import ResultsView from './ResultsView';
import GradingRightPanel from './GradingRightPanel';
import { usePanelDividerX } from '../../hooks/usePanelDividerX';
import { gradingHealth } from '../../services/api';
import type { GradingHealth } from '../../services/api';

type GradingView = 'main' | 'results';

const GradingScreen: React.FC = () => {
  const { t } = useTranslation();
  const [view, setView] = useState<GradingView>('main');
  const [refreshSignal, setRefreshSignal] = useState<number>(0);
  const [resultTaskId, setResultTaskId] = useState<string | null>(null);
  const [rightCollapsed, setRightCollapsed] = useState<boolean>(false);
  const [health, setHealth] = useState<GradingHealth | null>(null);
  const { containerRef, panelRef, arrowLeft, arrowTransition } = usePanelDividerX(
    rightCollapsed,
    view
  );

  useEffect(() => {
    const poll = async () => {
      try { setHealth(await gradingHealth()); } catch { setHealth(null); }
    };
    poll();
    const id = window.setInterval(poll, 15000);
    return () => clearInterval(id);
  }, []);

  const handleTaskCreated = () => {
    setRefreshSignal((n) => n + 1);
  };

  const handleViewResults = (taskId: string) => {
    setResultTaskId(taskId);
    setView('results');
  };

  return (
    <div className="grading-container" ref={containerRef}>
      <div className="grading-screen">
        <div className="grading-tabs">
          <button
            className={`grading-tab${view === 'main' ? ' active' : ''}`}
            onClick={() => setView('main')}
          >
            {t('grading.tabMain', 'Grading')}
          </button>
          <button
            className={`grading-tab${view === 'results' ? ' active' : ''}`}
            onClick={() => setView('results')}
          >
            {t('grading.tabResults', 'Results')}
          </button>
          <div className="grading-service-status">
            {[
              { key: 'grading', label: 'Grading', ok: health?.status === 'ok' },
              { key: 'vlm', label: 'VLM', ok: health?.dependencies?.vlm === 'healthy' },
              { key: 'layout', label: 'Layout', ok: health?.dependencies?.layout_detection === 'healthy' },
            ].map(({ key, label, ok }) => (
              <span key={key} className="grading-service-chip" title={ok ? 'Healthy' : 'Unavailable'}>
                <span className={`grading-service-dot ${ok ? 'ok' : 'fail'}`} />
                {label}
              </span>
            ))}
          </div>
        </div>

        <div className="grading-view">
          {view === 'main' && (
            <div className="grading-main">
              <NewTaskForm onTaskCreated={handleTaskCreated} />
              <TaskList refreshSignal={refreshSignal} onViewResults={handleViewResults} />
            </div>
          )}
          {view === 'results' && (
            <ResultsView taskId={resultTaskId} onBack={() => setView('main')} />
          )}
        </div>
      </div>

      <div
        className={`grading-right${rightCollapsed ? ' collapsed' : ''}`}
        ref={panelRef}
        style={{ flex: rightCollapsed ? 0 : 1 }}
      >
        <GradingRightPanel />
      </div>

      <div
        className={`arrow${rightCollapsed ? ' collapsed' : ''}`}
        style={{
          // Collapsed: let `.arrow.collapsed` park it inside the right edge.
          left: rightCollapsed ? undefined : arrowLeft,
          top: '50%',
          transform: 'translateY(-50%)',
          transition: arrowTransition,
        }}
        onClick={() => setRightCollapsed((c) => !c)}
      >
        {rightCollapsed ? '◀' : '▶'}
      </div>
    </div>
  );
};

export default GradingScreen;
