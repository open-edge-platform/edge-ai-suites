import React from 'react';
import fullscreenIcon from '../../assets/images/fullScreenIcon.svg';
import minimizeIcon from '../../assets/images/minimize.svg';
import '../../assets/css/WorkloadCard.css';

interface WorkloadConfig {
  id: string;
  name: string;
  color: string;
  description: string;
  dataKeys: readonly string[];
  hasWaveform: boolean;
}

interface WorkloadCardProps {
  config: WorkloadConfig;
  status: 'idle' | 'running' | 'stopped' | 'error';
  eventCount: number;
  latestVitals: Record<string, any>;
  lastEventTime: number | null;
  isExpanded: boolean;
  onExpand: () => void;
  waveform?: number[];
  frameData?: string; // ✅ Add frame data prop
}

const WorkloadCard: React.FC<WorkloadCardProps> = ({
  config,
  status,
  eventCount,
  latestVitals,
  lastEventTime,
  isExpanded,
  onExpand,
  waveform,
  frameData, // ✅ Add frame data prop
}) => {
  const statusColors = {
    idle: '#6c757d',
    running: '#28a745',
    stopped: '#6c757d',
    error: '#dc3545',
  };

  const formatValue = (key: string, value: any) => {
    if (value === undefined || value === null) return '--';
    if (key === 'prediction') return String(value);
    if (key === 'filename') return String(value);
    if (key === 'joints') return 'Detected';
    
    // Format all numeric vitals
    if (key === 'HR' || key === 'RR' || key === 'SpO2' || key === 'CO2_ET' || key === 'BP_DIA' || key === 'BP_SYS') {
      return typeof value === 'number' ? value.toFixed(1) : '--';
    }

    if (typeof value === 'number') {
      return value.toFixed(1);
    }

    return String(value);
  };

  const getUnit = (key: string) => {
    const units: Record<string, string> = {
      HR: 'bpm',
      RR: 'rpm',
      SpO2: '%',
      CO2_ET: 'mmHg',
      BP_DIA: 'mmHg',
      BP_SYS: 'mmHg',
      prediction: '',
      joints: '',
    };
    return units[key] || '';
  };

  const handleCardClick = () => {
    if (!isExpanded) {
      onExpand();
    }
  };

  const handleIconClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onExpand();
  };

  const renderWaveform = (canvas: HTMLCanvasElement | null) => {
    if (!canvas || !waveform || waveform.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Draw baseline
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();

    // Calculate min/max for scaling
    let min = Math.min(...waveform);
    let max = Math.max(...waveform);
    let range = max - min || 1;

    // Special scaling for AI-ECG
    if (config.id === 'ai-ecg') {
      min = -200;
      max = 1400;
      range = max - min;
    }

    // Draw waveform
    ctx.strokeStyle = config.color;
    ctx.lineWidth = 2;
    ctx.beginPath();

    waveform.forEach((value, i) => {
      const x = (i / waveform.length) * width;
      const y = height - ((value - min) / range) * height;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.stroke();
  };

  return (
    <div
      className={`workload-card ${isExpanded ? 'expanded' : ''} ${status}`}
      style={{ borderLeftColor: config.color }}
      onClick={handleCardClick}
    >
      {/* Header */}
      <div className="workload-card-header">
        <div className="workload-info">
          <h3 className="workload-name">{config.name}</h3>
          <p className="workload-description">{config.description}</p>
        </div>
        <img
          src={isExpanded ? minimizeIcon : fullscreenIcon}
          alt={isExpanded ? 'Minimize' : 'Expand'}
          className="fullscreen-icon"
          onClick={handleIconClick}
        />
      </div>

      {/* Status */}
      <div className="workload-status">
        <span className="status-dot" style={{ backgroundColor: statusColors[status] }} />
        <span className="status-text">{status}</span>
      </div>

      {/* Vitals - Always Visible */}
      <div className="workload-vitals">
        {Object.keys(latestVitals).length > 0 ? (
          <div className="vitals-list">
            {config.dataKeys.map((key) => {
              const value = latestVitals[key];
              if (value === undefined || value === null) return null;

              return (
                <div key={key} className="vital-item">
                  <span className="vital-label">{key}:</span>
                  <span className="vital-value">{formatValue(key, value)}</span>
                  <span className="vital-unit">{getUnit(key)}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="no-vitals">Waiting for data...</div>
        )}
      </div>
        {/* ✅ Add Video Frame Display */}
      {config.id === '3d-pose' && frameData && (
        <div className="video-frame" style={{ marginTop: '12px' }}>
          <h4 style={{ fontSize: '12px', marginBottom: '8px', color: '#6A6D75' }}>
            Live Video Feed
          </h4>
          <img
            src={frameData}
            alt="3D Pose Detection"
            style={{
              width: '100%',
              maxHeight: isExpanded ? '300px' : '200px',
              objectFit: 'contain',
              borderRadius: '4px',
              border: '1px solid #e0e0e0',
              backgroundColor: '#f8f9fa'
            }}
            onError={(e) => {
              console.error('Failed to load frame:', e);
            }}
          />
        </div>
      )}
      {/* Waveform */}
      {isExpanded && config.hasWaveform && waveform && waveform.length > 0 && (
        <div className="waveform-preview" style={{ marginTop: '12px' }}>
          <h4 style={{ fontSize: '12px', marginBottom: '8px', color: '#6A6D75' }}>
            {config.id === 'rppg'
              ? `Respiratory Waveform (${waveform.length} samples @ 30Hz)`
              : config.id === 'ai-ecg'
              ? `ECG Waveform (${waveform.length} samples @ 360Hz)`
              : 'Waveform'}
          </h4>
          <canvas
            ref={renderWaveform}
            width={600}
            height={150}
            className="waveform-canvas"
          />
        </div>
      )}

      {/* Footer */}
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