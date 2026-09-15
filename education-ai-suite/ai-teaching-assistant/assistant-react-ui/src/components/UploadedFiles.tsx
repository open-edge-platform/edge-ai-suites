interface Props {
  files: File[];
  onRemove: (index: number) => void;
  disabled?: boolean;
}

// Lists all uploaded files that make up the current knowledge base. Each entry
// can be removed via the "×" button, which drops it from the batch and
// re-ingests the remaining files.
export default function UploadedFiles({ files, onRemove, disabled }: Props) {
  if (files.length === 0) {
    return (
      <div className="flex aspect-square w-full items-center justify-center rounded-xl border border-dashed border-blue-300 bg-white text-sm text-black/60 shadow-xl">
        No files uploaded yet.
      </div>
    );
  }

  return (
    <div className="flex flex-col rounded-xl border border-blue-200 bg-white shadow-xl">
      <div className="flex items-center justify-between border-b border-blue-100 px-4 py-2">
        <span className="text-sm font-medium text-black">Uploaded files</span>
        <span className="ml-2 shrink-0 text-xs text-black/60">{files.length}</span>
      </div>
      <ul className="max-h-[360px] divide-y divide-blue-50 overflow-auto p-2">
        {files.map((file, index) => {
          const sizeKb = (file.size / 1024).toFixed(1);
          return (
            <li
              key={`${file.name}-${index}`}
              className="flex items-center justify-between gap-2 rounded-md px-2 py-2 hover:bg-blue-50"
            >
              <div className="min-w-0">
                <p className="truncate text-sm text-black">{file.name}</p>
                <p className="text-xs text-black/50">{sizeKb} KB</p>
              </div>
              <button
                type="button"
                onClick={() => onRemove(index)}
                disabled={disabled}
                title={`Remove ${file.name}`}
                aria-label={`Remove ${file.name}`}
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
