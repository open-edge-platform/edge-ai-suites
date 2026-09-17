import { useEffect, useRef } from "react";

interface Props {
  userAnalyser: AnalyserNode | null;
  userActive: boolean;
  assistantAnalyser: AnalyserNode | null;
  assistantActive: boolean;
  userColor?: string; // reacts on the right, fading toward center
  assistantColor?: string; // reacts on the left, fading toward center
  compact?: boolean;
}

// One waveform that reads as a single line: the user's voice peaks at the
// right edge and the assistant's voice peaks at the left edge, each fading to
// the flat center baseline so the two never show a visible seam.
export default function DualVisualizer({
  userAnalyser,
  userActive,
  assistantAnalyser,
  assistantActive,
  userColor = "#0068B5",
  assistantColor = "#16A34A",
  compact = false,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const userData = userAnalyser ? new Uint8Array(userAnalyser.fftSize) : null;
    const assistantData = assistantAnalyser ? new Uint8Array(assistantAnalyser.fftSize) : null;

    // Draw one source across the full width with a horizontal amplitude
    // envelope that peaks at `edge` and fades to zero at (and past) the center.
    const drawWave = (
      data: Uint8Array<ArrayBuffer>,
      analyser: AnalyserNode,
      color: string,
      edge: "left" | "right",
      w: number,
      h: number
    ) => {
      analyser.getByteTimeDomainData(data);
      const mid = h / 2;
      const n = data.length;
      ctx.lineWidth = 2;
      ctx.strokeStyle = color;
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const t = i / (n - 1); // 0 (left) → 1 (right)
        const x = t * w;
        const linear = edge === "right" ? Math.max(0, 2 * t - 1) : Math.max(0, 1 - 2 * t);
        const env = linear * linear * (3 - 2 * linear); // smoothstep fade
        const sample = (data[i] - 128) / 128; // -1 → 1
        const amp = Math.max(-1, Math.min(1, sample * 4.2)); // amplify, then clamp to canvas
        const y = mid + amp * env * mid * 0.95;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    };

    const draw = () => {
      rafRef.current = requestAnimationFrame(draw);
      const w = (canvas.width = canvas.clientWidth * devicePixelRatio);
      const h = (canvas.height = canvas.clientHeight * devicePixelRatio);
      ctx.clearRect(0, 0, w, h);

      // Continuous idle baseline — the single line everything grows out of.
      ctx.fillStyle = "rgba(59,130,246,0.25)";
      ctx.fillRect(0, h / 2 - 1, w, 2);

      if (assistantActive && assistantAnalyser && assistantData) {
        drawWave(assistantData, assistantAnalyser, assistantColor, "left", w, h);
      }
      if (userActive && userAnalyser && userData) {
        drawWave(userData, userAnalyser, userColor, "right", w, h);
      }
    };

    draw();
    return () => cancelAnimationFrame(rafRef.current);
  }, [userAnalyser, userActive, assistantAnalyser, assistantActive, userColor, assistantColor]);

  return (
    <div className="w-full">
      <canvas
        ref={canvasRef}
        className={`w-full rounded-lg border border-slate-200 bg-white shadow-sm ${compact ? "h-6" : "h-16"}`}
      />
    </div>
  );
}
