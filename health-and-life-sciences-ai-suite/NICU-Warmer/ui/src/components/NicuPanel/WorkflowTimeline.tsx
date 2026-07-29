import React from 'react';
import type { WorkflowState, WorkflowStepKey } from '../../types/nicu';

interface WorkflowTimelineProps {
  workflow: WorkflowState;
}

const STEPS: { key: WorkflowStepKey; label: string }[] = [
  { key: 'shared_window_open', label: 'Shared Window Open' },
  { key: 'pull_up_latched', label: 'Pull-Up Latched' },
  { key: 'build_cab_latched', label: 'Build-Cab Latched' },
  { key: 'both_latched', label: 'Both Latched' }
];

function formatTime(iso?: string): string {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

const WorkflowTimeline: React.FC<WorkflowTimelineProps> = ({ workflow }) => {
  const doneCount = workflow.completedSteps.length;

  return (
    <div className="nicu-card">
      <div className="nicu-card-header">
        <h4 className="nicu-card-title">
          <span className="nicu-card-title-icon">📋</span>
          Workflow Progress
        </h4>
        <span className="nicu-wf-summary">
          {doneCount}/{STEPS.length} steps
        </span>
      </div>

      <div className="nicu-workflow">
        {STEPS.map((step, idx) => {
          const done = workflow.completedSteps.includes(step.key);
          const active = workflow.currentStep === step.key;
          const isLast = idx === STEPS.length - 1;
          const ts = workflow.timestamps[step.key];

          let dotClass = 'nicu-wf-dot--pending';
          if (done) dotClass = 'nicu-wf-dot--done';
          else if (active) dotClass = 'nicu-wf-dot--active';

          return (
            <div className="nicu-wf-step" key={step.key}>
              <div className="nicu-wf-track">
                <div className={`nicu-wf-dot ${dotClass}`}>
                  {done && (
                    <svg width="8" height="8" viewBox="0 0 10 10" fill="none">
                      <path
                        d="M2 5l2.5 2.5L8 3"
                        stroke="#fff"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </div>
                {!isLast && (
                  <div className={`nicu-wf-line ${done ? 'nicu-wf-line--done' : ''}`} />
                )}
              </div>
              <div className="nicu-wf-body">
                <div className={`nicu-wf-label ${!done && !active ? 'nicu-wf-label--pending' : ''}`}>
                  {step.label}
                </div>
                {ts && <div className="nicu-wf-time">{formatTime(ts)}</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default WorkflowTimeline;