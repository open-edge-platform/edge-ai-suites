import { useEffect, useRef, useState } from "react";
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
  onIngested: (topic?: string) => void;
  onBusyChange?: (busy: boolean) => void;
  disabled?: boolean;
  // Status restored from a previous session (e.g. the ingested chunk count)
  // shown until the user ingests again.
  initialMessage?: string;
}

// Upload + ingest + reingest. Picking one or more valid files uploads and
// ingests them together so queries are answered across every document. The
// last selection is retained so a failed ingestion can be retried without
// re-picking the files.
export default function IngestionPanel({
  files,
  onFilesSelected,
  onIngested,
  onBusyChange,
  disabled,
  initialMessage,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<IngestState>("idle");
  const [message, setMessage] = useState<string>("");

  // Seed the status line from a restored session once, without clobbering a
  // message produced by a later ingest in this session.
  useEffect(() => {
    if (initialMessage) {
      setState((s) => (s === "idle" ? "success" : s));
      setMessage((m) => (m === "" ? initialMessage : m));
    }
  }, [initialMessage]);

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
    onBusyChange?.(true);
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
      const topic = result.results.find((r) => r.status === "ok" && r.topic)?.topic ?? undefined;
      onIngested(topic ?? undefined);
    } catch (err) {
      setState("error");
      setMessage(`Ingestion failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      onBusyChange?.(false);
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
          className="flex flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-intel-blue px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-intel-dark disabled:opacity-50"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-4 w-4 shrink-0"
            aria-hidden="true"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          Upload &amp; Ingest
        </button>
        <button
          type="button"
          onClick={runIngest}
          disabled={busy || files.length === 0}
          className="flex-1 rounded-lg border border-intel-blue px-3 py-2 text-sm font-medium text-intel-blue shadow-sm hover:bg-intel-light disabled:opacity-50"
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
    </div>
  );
}
