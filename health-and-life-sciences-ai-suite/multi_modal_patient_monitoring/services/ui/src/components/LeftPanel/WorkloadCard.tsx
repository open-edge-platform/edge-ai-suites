// src/components/LeftPanel/WorkloadCard.tsx
import React from 'react';
import fullscreenIcon from '../../assets/images/fullScreenIcon.svg';
import minimizeIcon from '../../assets/images/minimize.svg';
import '../../assets/css/WorkloadCard.css';

interface WorkloadConfig {
  id: string;
  name: string;
  icon: string;
  color: string;
  description: string;
}

interface WorkloadCardProps {
  config: WorkloadConfig;
  status: 'idle' | 'running' | 'stopped' | 'error';
  eventCount: number;
  latestVitals: any;
  lastEventTime: number | null;
  isExpanded: boolean;
  onExpand: () => void;
}

const WorkloadCard: React.FC<WorkloadCardProps> = ({
  config,
  status,
  eventCount,
  latestVitals,
  lastEventTime,
  isExpanded,
  onExpand,
}) => {
  const getStatusColor = () => {
    if (status === 'running') return '#2ecc71';
    if (status === 'error') return '#e74c3c';
    return '#95a5a6';
  };

  const getStatusText = () => {
    if (status === 'running') return 'Running';
    if (status === 'stopped') return 'Stopped';
    if (status === 'error') return 'Error';
    return 'Idle';
  };

  const renderVitals = () => {
    if (!latestVitals) {
      return <div className="no-vitals">No data available</div>;
    }

    if (config.id === 'rppg') {
      return (
        <div className="vitals-list">
          <div className="vital-item">
            <span className="vital-label">HR:</span>
            <span className="vital-value">{latestVitals.HR || '--'}</span>
            <span className="vital-unit">bpm</span>
          </div>
          <div className="vital-item">
            <span className="vital-label">RR:</span>
            <span className="vital-value">{latestVitals.RR || '--'}</span>
            <span className="vital-unit">breaths/min</span>
          </div>
        </div>
      );
    }

    if (config.id === 'ai-ecg') {
      return (
        <div className="vitals-list">
          <div className="vital-item">
            <span className="vital-label">QRS:</span>
            <span className="vital-value">{latestVitals.QRS || '--'}</span>
            <span className="vital-unit">ms</span>
          </div>
          <div className="vital-item">
            <span className="vital-label">PR:</span>
            <span className="vital-value">{latestVitals.PR || '--'}</span>
            <span className="vital-unit">ms</span>
          </div>
        </div>
      );
    }

    if (config.id === 'mdpnp') {
      return (
        <div className="vitals-list">
          <div className="vital-item">
            <span className="vital-label">BP:</span>
            <span className="vital-value">{latestVitals.BP_SYS || '--'}/{latestVitals.BP_DIA || '--'}</span>
            <span className="vital-unit">mmHg</span>
          </div>
        </div>
      );
    }

    if (config.id === '3d-pose') {
      return (
        <div className="vitals-list">
          <div className="vital-item">
            <span className="vital-label">Joints:</span>
            <span className="vital-value">{latestVitals.joints || '--'}</span>
          </div>
        </div>
      );
    }

    return null;
  };

  // Handle click on card body - switch to this card if not already expanded
  const handleCardClick = () => {
    if (!isExpanded) {
      onExpand(); // Expand this card (or switch to it)
    }
    // If already expanded, clicking body does nothing
  };

  // Handle minimize icon click - always closes/opens
  const handleMinimizeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onExpand(); // Toggle expand/collapse
  };

  return (
    <div 
      className={`workload-card ${isExpanded ? 'expanded' : ''}`}
      style={{ borderLeftColor: config.color }}
      onClick={handleCardClick}
      title={isExpanded ? '' : 'Click to expand'}
    >
      <div className="workload-card-header">
        <div className="workload-icon" style={{ backgroundColor: config.color }}>
          {config.icon}
        </div>
        <div className="workload-info">
          <h3 className="workload-name">{config.name}</h3>
          <p className="workload-description">{config.description}</p>
        </div>
        <img 
          src={isExpanded ? minimizeIcon : fullscreenIcon}
          alt={isExpanded ? 'Minimize' : 'Fullscreen'}
          className="fullscreen-icon"
          title={isExpanded ? 'Click to minimize' : 'Click to expand'}
          onClick={handleMinimizeClick}
        />
      </div>

      <div className="workload-status">
        <div className="status-dot" style={{ backgroundColor: getStatusColor() }} />
        <span className="status-text">{getStatusText()}</span>
      </div>

      <div className="workload-vitals">
        {renderVitals()}
      </div>

      <div className="workload-footer">
        <div className="event-count">
          <span className="label">Events:</span>
          <span className="value">{eventCount}</span>
        </div>
        {lastEventTime && (
          <div className="last-update">
            <span className="label">Last:</span>
            <span className="value">{new Date(lastEventTime).toLocaleTimeString()}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default WorkloadCard;