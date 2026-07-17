import { useRef, useState } from "react";
import { ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES } from "../config";
import { clearContext, ingestFile } from "../api";

export type IngestState = "idle" | "ingesting" | "success" | "error";

export interface IngestStatus {
  state: IngestState;
  message: string;
}

interface Props {
  file: File | null;
  onFileSelected: (file: File) => void;
  onIngested: () => void;
  disabled?: boolean;
}

// Upload + ingest + reingest. Picking a valid file uploads and ingests it
// immediately. The last selected file is retained so a failed ingestion can be
// retried without re-picking the file.
export default function IngestionPanel({
  file,
  onFileSelected,
  onIngested,
  disabled,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<IngestState>("idle");

  const validate = (f: File): string | null => {
    const ext = "." + (f.name.toLowerCase().split(".").pop() ?? "");
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
    }
    if (f.size > MAX_UPLOAD_BYTES) {
      return `File too large. Max ${MAX_UPLOAD_BYTES / (1024 * 1024)} MB`;
    }
    return null;
  };

  const handlePick = async (f: File | undefined) => {
    if (!f) return;
    const err = validate(f);
    if (err) {
      setState("error");
      return;
    }
    onFileSelected(f);
    setState("ingesting");
    try {
      await clearContext();
      await ingestFile(f);
      setState("success");
      onIngested();
    } catch (err) {
      setState("error");
    }
  };

  const runIngest = async () => {
    if (!file) return;
    setState("ingesting");
    try {
      await clearContext();
      await ingestFile(file);
      setState("success");
      onIngested();
    } catch (err) {
      setState("error");
    }
  };

  const busy = state === "ingesting" || disabled;

  return (
    <div className="space-y-3">
      <input
        ref={inputRef}
        type="file"
        accept={ALLOWED_EXTENSIONS.join(",")}
        className="hidden"
        onChange={(e) => handlePick(e.target.files?.[0])}
      />

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          className="flex-1 rounded-lg bg-intel-blue px-3 py-2 text-sm font-medium text-white hover:bg-intel-dark disabled:opacity-50"
        >
          📄 Upload & ingest
        </button>
        <button
          type="button"
          onClick={runIngest}
          disabled={busy || !file}
          className="flex-1 rounded-lg border border-intel-blue px-3 py-2 text-sm font-medium text-intel-blue hover:bg-intel-light disabled:opacity-50"
          title={file ? `Re-ingest ${file.name}` : "Select a file first"}
        >
          {state === "ingesting" ? "Ingesting…" : "♻ Re-ingest"}
        </button>
      </div>

      <p className="text-xs text-black/70">
        Supported: {ALLOWED_EXTENSIONS.join(", ")} · max 10&nbsp;MB. Uploading a valid file
        ingests it immediately. Re-ingest retries the last uploaded file without re-selecting
        it.
      </p>
    </div>
  );
}
