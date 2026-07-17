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
      className={`flex h-16 w-16 items-center justify-center rounded-full text-2xl text-white shadow-lg transition disabled:opacity-40 ${
        recording
          ? "animate-pulse bg-black hover:bg-black/90"
          : "bg-intel-blue hover:bg-intel-dark"
      }`}
      style={{ transform: `scale(${scale.toFixed(3)})` }}
      title={recording ? "Stop recording" : "Start recording"}
    >
      {recording ? "■" : "🎤"}
    </button>
  );
}
