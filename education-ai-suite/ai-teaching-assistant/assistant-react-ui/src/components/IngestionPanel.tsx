import { useRef, useState } from "react";
import { ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES } from "../config";
import { clearContext, ingestFiles } from "../api";

export type IngestState = "idle" | "ingesting" | "success" | "error";

export interface IngestStatus {
  state: IngestState;
  message: string;
}

interface Props {
  files: File[];
  onFilesSelected: (files: File[]) => void;
  onIngested: () => void;
  disabled?: boolean;
}

// Upload + ingest + reingest. Picking one or more valid files uploads and
// ingests them together so queries are answered across every document. The
// last selection is retained so a failed ingestion can be retried without
// re-picking the files.
export default function IngestionPanel({
  files,
  onFilesSelected,
  onIngested,
  disabled,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<IngestState>("idle");
  const [message, setMessage] = useState<string>("");

  const validate = (f: File): string | null => {
    const ext = "." + (f.name.toLowerCase().split(".").pop() ?? "");
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `${f.name}: unsupported type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
    }
    if (f.size > MAX_UPLOAD_BYTES) {
      return `${f.name}: too large. Max ${MAX_UPLOAD_BYTES / (1024 * 1024)} MB`;
    }
    return null;
  };

  // Clears any prior context, then ingests the whole batch so all documents
  // share one collection and answers span every context.
  const ingestAll = async (batch: File[]) => {
    setState("ingesting");
    setMessage("");
    try {
      await clearContext();
      const result = await ingestFiles(batch);
      if (result.files_failed > 0) {
        const failed = result.results
          .filter((r) => r.status !== "ok")
          .map((r) => `${r.source} (${r.detail ?? "failed"})`)
          .join("; ");
        setState(result.files_succeeded > 0 ? "success" : "error");
        setMessage(
          `${result.files_succeeded}/${result.files_processed} ingested. Failed: ${failed}`
        );
      } else {
        setState("success");
        setMessage(
          `${result.files_succeeded} file(s) ingested \u00b7 ${result.total_chunks_added} chunks`
        );
      }
      onIngested();
    } catch {
      setState("error");
      setMessage("Ingestion failed");
    }
  };

  const handlePick = async (picked: FileList | null) => {
    if (!picked || picked.length === 0) return;
    const batch = Array.from(picked);
    const errors = batch.map(validate).filter((e): e is string => e !== null);
    if (errors.length > 0) {
      setState("error");
      setMessage(errors.join(" \u00b7 "));
      return;
    }
    // Append newly picked files to the existing selection so earlier uploads
    // are retained. De-duplicate by name+size; newer picks win.
    const merged = [...files];
    for (const f of batch) {
      const idx = merged.findIndex((e) => e.name === f.name && e.size === f.size);
      if (idx >= 0) merged[idx] = f;
      else merged.push(f);
    }
    onFilesSelected(merged);
    await ingestAll(merged);
  };

  const runIngest = async () => {
    if (files.length === 0) return;
    await ingestAll(files);
  };

  const busy = state === "ingesting" || disabled;

  return (
    <div className="space-y-3">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ALLOWED_EXTENSIONS.join(",")}
        className="hidden"
        onChange={(e) => handlePick(e.target.files)}
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
          disabled={busy || files.length === 0}
          className="flex-1 rounded-lg border border-intel-blue px-3 py-2 text-sm font-medium text-intel-blue hover:bg-intel-light disabled:opacity-50"
          title={files.length > 0 ? `Re-ingest ${files.length} file(s)` : "Select files first"}
        >
          {state === "ingesting" ? "Ingesting…" : "♻ Re-ingest"}
        </button>
      </div>

      {message && (
        <p
          className={
            "text-xs " + (state === "error" ? "text-red-600" : "text-black/70")
          }
        >
          {message}
        </p>
      )}

      <p className="text-xs text-black/70">
        Supported: {ALLOWED_EXTENSIONS.join(", ")} · max 10&nbsp;MB each. Select one or
        more files; they are ingested together and answers span every uploaded document.
        Re-ingest retries the last selection.
      </p>
    </div>
  );
}
