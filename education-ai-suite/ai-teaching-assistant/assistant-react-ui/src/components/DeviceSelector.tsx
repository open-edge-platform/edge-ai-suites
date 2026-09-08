import { useEffect, useState } from "react";

interface Props {
  value: string | undefined;
  onChange: (deviceId: string) => void;
  disabled?: boolean;
}

// Enumerates browser microphone input devices for capture selection.
export default function DeviceSelector({ value, onChange, disabled }: Props) {
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      // Prompt for permission so device labels are populated.
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      const all = await navigator.mediaDevices.enumerateDevices();
      const inputs = all.filter((d) => d.kind === "audioinput");
      setDevices(inputs);
      if (!value && inputs.length > 0) onChange(inputs[0].deviceId);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Microphone access denied");
    }
  };

  useEffect(() => {
    void refresh();
    navigator.mediaDevices.addEventListener("devicechange", refresh);
    return () => navigator.mediaDevices.removeEventListener("devicechange", refresh);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <label className="mb-1 block text-sm font-semibold text-black">
        Microphone
      </label>
      <div className="flex gap-2">
        <select
          className="w-full rounded-lg border-2 border-slate-200 bg-white px-3 py-2 text-sm text-black shadow-sm focus:border-intel-blue focus:outline-none disabled:opacity-50"
          value={value ?? ""}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        >
          {devices.length === 0 && <option value="">No microphone found</option>}
          {devices.map((d, i) => (
            <option key={d.deviceId} value={d.deviceId}>
              {d.label || `Microphone ${i + 1}`}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={refresh}
          disabled={disabled}
          className="rounded-lg border-2 border-slate-200 px-3 py-2 text-sm text-black shadow-sm hover:bg-blue-50 disabled:opacity-50"
          title="Refresh device list"
        >
          ↻
        </button>
      </div>
      {error && <p className="mt-1 text-xs text-black">{error}</p>}
    </div>
  );
}
