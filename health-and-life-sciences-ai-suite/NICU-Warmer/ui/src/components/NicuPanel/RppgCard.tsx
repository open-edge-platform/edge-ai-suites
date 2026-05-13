import React, { useRef, useEffect } from 'react';
import type { RppgData } from '../../types/nicu';

interface RppgCardProps {
  rppg: RppgData;
}

/** Draw a waveform on a canvas with gradient fill. */
function drawWaveform(
  canvas: HTMLCanvasElement,
  data: number[],
  strokeColor: string,
  fillColorTop: string,
) {
  const ctx = canvas.getContext('2d');
  if (!ctx || data.length < 2) return;

  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = rect.height;
  const pad = 4;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  ctx.clearRect(0, 0, w, h);

  // Grid lines
  ctx.strokeStyle = '#edf0f3';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= 3; i++) {
    const y = pad + ((h - pad * 2) / 3) * i;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }

  // Gradient fill
  const gradient = ctx.createLinearGradient(0, 0, 0, h);
  gradient.addColorStop(0, fillColorTop);
  gradient.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = gradient;
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
  ctx.fill();

  // Line
  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Trailing dot
  const lv = data[data.length - 1];
  const ly = h - pad - ((lv - min) / range) * (h - pad * 2);
  ctx.beginPath();
  ctx.arc(w - 1, ly, 3, 0, Math.PI * 2);
  ctx.fillStyle = strokeColor;
  ctx.fill();
}

const RppgCard: React.FC<RppgCardProps> = ({ rppg }) => {
  const pulseCanvasRef = useRef<HTMLCanvasElement>(null);
  const respCanvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (pulseCanvasRef.current && rppg.waveform.length >= 2) {
      drawWaveform(pulseCanvasRef.current, rppg.waveform, '#c62828', 'rgba(198,40,40,0.18)');
    }
  }, [rppg.waveform]);

  useEffect(() => {
    if (respCanvasRef.current && rppg.respWaveform.length >= 2) {
      drawWaveform(respCanvasRef.current, rppg.respWaveform, '#1565c0', 'rgba(21,101,192,0.18)');
    }
  }, [rppg.respWaveform]);

  const hr = rppg.heartRate;
  const rr = rppg.respirationRate;
  const confPct = Math.round(rppg.confidence * 100);
  const hasData = hr !== null || rr !== null;

  return (
    <div className="nicu-card nicu-rppg-card">

      {/* Header */}
      <div className="nicu-card-header">
        <h4 className="nicu-card-title">rPPG Vitals</h4>
        <span className={`nicu-rppg-session ${hasData ? 'nicu-rppg-session--active' : 'nicu-rppg-session--inactive'}`}>
          {hasData ? `${confPct}% confidence` : '○ Waiting'}
        </span>
      </div>

      {/* Vitals row */}
      <div className="nicu-rppg-vitals">
        <div className="nicu-rppg-bpm-block">
          <span className="nicu-rppg-value nicu-rppg-value--normal">
            {hr !== null ? hr.toFixed(1) : '--'}
          </span>
          <span className="nicu-rppg-unit">bpm</span>
        </div>
        <div className="nicu-rppg-bpm-block">
          <span className="nicu-rppg-value" style={{ color: '#1565c0' }}>
            {rr !== null ? rr.toFixed(1) : '--'}
          </span>
          <span className="nicu-rppg-unit">br/min</span>
        </div>
      </div>

      {/* Pulse waveform */}
      <div className="nicu-rppg-canvas-wrap">
        <span className="nicu-rppg-canvas-label" style={{ color: '#c62828' }}>Heart Rate</span>
        <canvas ref={pulseCanvasRef} className="nicu-rppg-canvas" />
      </div>

      {/* Resp waveform */}
      <div className="nicu-rppg-canvas-wrap">
        <span className="nicu-rppg-canvas-label" style={{ color: '#1565c0' }}>Respiration</span>
        <canvas ref={respCanvasRef} className="nicu-rppg-canvas" />
      </div>

    </div>
  );
};

export default RppgCard;