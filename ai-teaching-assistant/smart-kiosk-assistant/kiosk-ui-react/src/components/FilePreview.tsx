import { useEffect, useState } from "react";

interface Props {
  file: File | null;
}

// Previews the currently selected upload. Text/markdown are rendered inline,
// PDFs are embedded, and other formats (e.g. .docx) show file metadata.
export default function FilePreview({ file }: Props) {
  const [textContent, setTextContent] = useState<string>("");
  const [objectUrl, setObjectUrl] = useState<string>("");

  useEffect(() => {
    setTextContent("");
    setObjectUrl("");
    if (!file) return;

    const ext = file.name.toLowerCase().split(".").pop();
    if (ext === "txt" || ext === "md") {
      file.text().then((t) => setTextContent(t.slice(0, 20000)));
    } else if (ext === "pdf") {
      const url = URL.createObjectURL(file);
      setObjectUrl(url);
      return () => URL.revokeObjectURL(url);
    }
  }, [file]);

  if (!file) {
    return (
      <div className="flex h-full min-h-[240px] items-center justify-center rounded-xl border border-dashed border-blue-300 bg-white text-sm text-black/60">
        No file selected — the preview will appear here.
      </div>
    );
  }

  const ext = file.name.toLowerCase().split(".").pop();
  const sizeKb = (file.size / 1024).toFixed(1);

  return (
    <div className="flex h-full flex-col rounded-xl border border-blue-200 bg-white">
      <div className="flex items-center justify-between border-b border-blue-100 px-4 py-2">
        <span className="truncate text-sm font-medium text-black">{file.name}</span>
        <span className="ml-2 shrink-0 text-xs text-black/60">{sizeKb} KB</span>
      </div>
      <div className="min-h-[240px] flex-1 overflow-auto p-3">
        {(ext === "txt" || ext === "md") && (
          <pre className="whitespace-pre-wrap break-words font-mono text-xs text-black">
            {textContent || "Loading…"}
          </pre>
        )}
        {ext === "pdf" && objectUrl && (
          <iframe title="PDF preview" src={objectUrl} className="h-[60vh] w-full rounded-md" />
        )}
        {ext === "docx" && (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-black/80">
            <span className="text-3xl">📄</span>
            <p>Word document ready to ingest.</p>
            <p className="text-xs text-black/60">
              Inline preview isn't available for .docx, but the text will be extracted during ingestion.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
