interface Props {
  recording: boolean;
  inputLevel?: number;
  disabled?: boolean;
  onStart: () => void;
  onStop: () => void;
}

export default function MicButton({ recording, inputLevel = 0, disabled, onStart, onStop }: Props) {
  const scale = recording ? 1 + inputLevel * 0.35 : 1;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={recording ? onStop : onStart}
      className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-white shadow-md transition disabled:opacity-40 ${
        recording
          ? "animate-pulse bg-black hover:bg-black/90"
          : "bg-intel-blue hover:bg-intel-dark"
      }`}
      style={{ transform: `scale(${scale.toFixed(3)})` }}
      title={recording ? "Stop recording" : "Start recording"}
    >
      {recording ? (
        <span className="block h-3.5 w-3.5 rounded-sm bg-white" />
      ) : (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="white"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-5 w-5"
          aria-hidden="true"
        >
          <rect x="9" y="2" width="6" height="12" rx="3" />
          <path d="M5 11a7 7 0 0 0 14 0" />
          <line x1="12" y1="18" x2="12" y2="22" />
        </svg>
      )}
    </button>
  );
}
