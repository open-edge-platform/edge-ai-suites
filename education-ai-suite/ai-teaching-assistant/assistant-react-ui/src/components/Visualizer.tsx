import { useEffect, useRef } from "react";

interface Props {
  analyser: AnalyserNode | null;
  active: boolean;
  color: string;
  label: string;
  compact?: boolean;
}

// Canvas frequency-bar visualizer driven by a Web Audio AnalyserNode.
export default function Visualizer({
  analyser,
  active,
  color,
  label,
  compact = false,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const timeData = analyser ? new Uint8Array(analyser.fftSize) : null;

    const draw = () => {
      rafRef.current = requestAnimationFrame(draw);
      const w = (canvas.width = canvas.clientWidth * devicePixelRatio);
      const h = (canvas.height = canvas.clientHeight * devicePixelRatio);
      ctx.clearRect(0, 0, w, h);

      if (!analyser || !timeData || !active) {
        // Idle baseline
        ctx.fillStyle = "rgba(59,130,246,0.25)";
        ctx.fillRect(0, h / 2 - 1, w, 2);
        return;
      }

      analyser.getByteTimeDomainData(timeData);
      ctx.lineWidth = 2;
      ctx.strokeStyle = color;
      ctx.beginPath();
      for (let i = 0; i < timeData.length; i++) {
        const x = (i / (timeData.length - 1)) * w;
        const y = (timeData[i] / 255) * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    };

    draw();
    return () => cancelAnimationFrame(rafRef.current);
  }, [analyser, active, color]);

  return (
    <div className="w-full">
      <div className="mb-1 text-xs font-medium text-black">{label}</div>
      <canvas
        ref={canvasRef}
        className={`w-full rounded-lg border border-blue-200 bg-white ${compact ? "h-10" : "h-16"}`}
      />
    </div>
  );
}
