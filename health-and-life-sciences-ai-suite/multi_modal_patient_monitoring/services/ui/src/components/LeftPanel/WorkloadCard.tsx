import React from 'react';
import fullscreenIcon from '../../assets/images/fullScreenIcon.svg';
import minimizeIcon from '../../assets/images/minimize.svg';
import Pose3DVisualizer from './Pose3DVisualizer';
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
  frameData?: string;
  // ✅ Replace joints with people
  people?: Array<{
    person_id: number;
    joints_3d: Array<{
      x: number;
      y: number;
      z: number;
      visibility?: number;
    }>;
    confidence?: number[];
  }>;
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
  frameData,
  people, // ✅ Use people instead of joints
}) => {
  // ✅ Add the poseStreamUrl definition here, right after the component props
  const hostIp = (import.meta as any).env?.VITE_HOST_IP || (typeof window !== 'undefined' ? window.location.hostname : 'localhost');
  const poseStreamUrl = `${window.location.protocol}//${hostIp}:8085/video_feed`;

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
    if (key === 'activity') return String(value);
    if (key === 'joints') return 'Detected';
    
    // Format all numeric vitals
    if (key === 'HR' || key === 'RR' || key === 'SpO2' || key === 'CO2_ET' || key === 'BP_DIA' || key === 'BP_SYS') {
      return typeof value === 'number' ? value.toFixed(1) : '--';
    }

    if (key === 'confidence' && typeof value === 'number') {
      return (value * 100).toFixed(1);
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
      confidence: '%',
      activity: '',
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

    // Baseline
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();

    let min = Math.min(...waveform);
    let max = Math.max(...waveform);
    let range = max - min || 1;

    if (config.id === 'ai-ecg') {
      min = -200;
      max = 1400;
      range = max - min;
    }

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

  React.useEffect(() => {
    if (config.id === '3d-pose') {
      console.log('[WorkloadCard] 3D Pose Update:', {
        hasPeople: !!people,
        peopleCount: people?.length || 0,
        peopleData: people,
        isExpanded,
        status,
        latestVitals
      });
    }
  }, [people, isExpanded, status, config.id, latestVitals]);

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

      {/* ✅ For 3D Pose: Video + 3D Graph side-by-side when expanded */}
      {config.id === '3d-pose' ? (
        <div style={{
          marginTop: '12px',
          flex: '1 1 auto',
          display: 'flex',
          flexDirection: isExpanded ? 'row' : 'column', // ✅ Row when expanded
          gap: isExpanded ? '16px' : '8px',
          minHeight: 0,
          overflow: 'hidden'
        }}>
          {/* Video Stream Section */}
          <div style={{
            flex: isExpanded ? '1 1 50%' : '1 1 auto',
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
            minWidth: 0
          }}>
            <h4 style={{ 
              fontSize: '12px', 
              marginBottom: '8px', 
              color: '#6A6D75',
              fontWeight: '500'
            }}>
              {status === 'running' ? '🎥 Live Video Feed' : '📹 Video Feed'}
            </h4>
            {status === 'running' ? (
              <img
                src={poseStreamUrl}
                alt="3D Pose Stream"
                style={{
                  width: '100%',
                  height: isExpanded ? '400px' : '200px',
                  objectFit: 'contain',
                  borderRadius: '8px',
                  border: '1px solid #e0e0e0',
                  backgroundColor: '#000',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
                }}
                onError={(e) => {
                  console.error('[WorkloadCard] Failed to load video stream');
                }}
              />
            ) : (
              <div style={{
                width: '100%',
                height: isExpanded ? '400px' : '200px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '8px',
                border: '1px solid #e0e0e0',
                backgroundColor: '#f8f9fa',
                boxShadow: '0 2px 8px rgba(0,0,0,0.05)'
              }}>
                <div style={{
                  textAlign: 'center',
                  color: '#999',
                  fontSize: '14px',
                  padding: '20px'
                }}>
                  <div style={{ fontSize: '48px', marginBottom: '10px' }}>📹</div>
                  <div style={{ fontWeight: '500' }}>Video feed paused</div>
                  <div style={{ fontSize: '12px', marginTop: '5px', color: '#bbb' }}>
                    Start the workload to see live stream
                  </div>
                </div>
              </div>
            )}
            
            {/* ❌ REMOVE THIS ENTIRE SECTION - Activity Badge */}
            {/* 
            {latestVitals?.activity && (
              <div style={{
                marginTop: '12px',
                padding: '10px 16px',
                background: 'linear-gradient(135deg, #e7f3ff 0%, #cce5ff 100%)',
                borderRadius: '8px',
                fontSize: '13px',
                color: '#0071c5',
                fontWeight: '600',
                textAlign: 'center',
                border: '1px solid #b3d9ff',
                boxShadow: '0 2px 4px rgba(0, 113, 197, 0.1)'
              }}>
                🏃 Activity: {latestVitals.activity}
              </div>
            )}
            */}
          </div>

          {/* 3D Skeleton Visualization - Only when expanded */}
          {isExpanded && (
            <div style={{
              flex: '1 1 50%',
              display: 'flex',
              flexDirection: 'column',
              minHeight: 0,
              minWidth: 0
            }}>
              <h4 style={{ 
                fontSize: '12px', 
                marginBottom: '8px', 
                color: '#6A6D75',
                fontWeight: '500'
              }}>
                👤 3D Skeleton Visualization {people && people.length > 0 && `(${people.length} ${people.length === 1 ? 'person' : 'people'})`}
              </h4>
              
              {status === 'running' ? (
                <Pose3DVisualizer 
                  people={people && people.length > 0 ? people : []}  // ✅ Pass all people
                  isExpanded={isExpanded} 
                />
              ) : (
                <div style={{
                  width: '100%',
                  height: '400px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: '8px',
                  border: '1px solid #e0e0e0',
                  backgroundColor: '#f8f9fa',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.05)'
                }}>
                  <div style={{
                    textAlign: 'center',
                    color: '#999',
                    fontSize: '14px'
                  }}>
                    <div style={{ fontSize: '48px', marginBottom: '10px' }}>👤</div>
                    <div style={{ fontWeight: '500' }}>Waiting for pose data</div>
                    <div style={{ fontSize: '12px', marginTop: '5px', color: '#bbb' }}>
                      Start the workload to see 3D skeleton
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <>
          {/* ✅ For other workloads: Show vitals */}
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

          {/* Waveform - for other workloads */}
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
        </>
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
