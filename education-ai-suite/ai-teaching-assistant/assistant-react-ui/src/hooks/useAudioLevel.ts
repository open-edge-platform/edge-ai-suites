import { useEffect, useState } from "react";

// Reads a live normalized [0..1] RMS level from an analyser node.
export function useAudioLevel(analyser: AnalyserNode | null, active: boolean): number {
  const [level, setLevel] = useState(0);

  useEffect(() => {
    if (!analyser || !active) {
      setLevel(0);
      return;
    }

    const data = new Uint8Array(analyser.fftSize);
    let raf = 0;
    let smoothed = 0;

    const tick = () => {
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        const centered = (data[i] - 128) / 128;
        sum += centered * centered;
      }
      const rms = Math.sqrt(sum / data.length);
      // Smooth to avoid jittery button scaling.
      smoothed = smoothed * 0.78 + rms * 0.22;
      const normalized = Math.max(0, Math.min(1, smoothed * 3.2));
      setLevel(normalized);
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [analyser, active]);

  return level;
}
