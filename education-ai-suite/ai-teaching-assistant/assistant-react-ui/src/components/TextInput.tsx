import { useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";

interface TextInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  recording?: boolean;
  onStop?: () => void;
  trailing?: ReactNode;
}

export default function TextInput({ onSend, disabled = false, recording = false, onStop, trailing }: TextInputProps) {
  const [value, setValue] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      submit(event);
    }
  };

  return (
    <form onSubmit={submit} className="flex items-center gap-2">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled || recording}
        rows={1}
        placeholder={recording ? "Listening…" : "Or type your question and press Enter…"}
        className="min-h-[42px] flex-1 resize-none rounded-lg border-2 border-slate-200 px-3 py-2 text-sm text-black shadow-sm outline-none transition focus:border-intel-blue disabled:cursor-not-allowed disabled:opacity-50"
      />
      {recording && onStop ? (
        <button
          type="button"
          onClick={onStop}
          title="Stop recording"
          aria-label="Stop recording"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-black text-white transition hover:bg-black/90"
        >
          <span className="block h-4 w-4 rounded-sm bg-white" />
        </button>
      ) : (
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          title="Send"
          aria-label="Send"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-intel-blue text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-5 w-5"
            aria-hidden="true"
          >
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </button>
      )}
      {trailing}
    </form>
  );
}
