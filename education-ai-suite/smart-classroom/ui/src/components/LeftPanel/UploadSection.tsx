import React, { useRef, useState, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import "../../assets/css/UploadSection.css";
import { csUploadIngest, csQueryTask, csIngest, createSession, startMonitoring } from "../../services/api";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import { setCsProcessing, setSessionId, setMonitoringActive, setCsUploadsComplete, setCsHasUploads } from "../../redux/slices/uiSlice";

type TaskStatus =
  | "PENDING"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED"
  | "ALREADY_EXISTS";

interface UploadEntry {
  id: string;
  file: File;
  filename: string;
  fileType: string;
  fileSize: number;
  taskId: string | null;
  fileKey: string | null;
  status: TaskStatus;
  progress: number;
  error: string | null;
  selected: boolean;
  tags: string[];
}

const POLL_INTERVAL_MS = 1000;

function genId() {
  return Math.random().toString(36).slice(2);
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const ALLOWED_EXTENSIONS = new Set([".mp4", ".ppt", ".pptx", ".docx", ".pdf", ".jpg", ".jpeg", ".csv", ".txt"]);
function isAllowed(filename: string): boolean {
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  return ALLOWED_EXTENSIONS.has(ext);
}

const TERMINAL: TaskStatus[] = ["COMPLETED", "FAILED", "ALREADY_EXISTS"];

const UploadSection: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const monitoringActive = useAppSelector((s) => s.ui.monitoringActive);
  const sessionIdRef = useRef<string | null>(sessionId);
  const monitoringActiveRef = useRef<boolean>(monitoringActive);
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => { monitoringActiveRef.current = monitoringActive; }, [monitoringActive]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [entries, setEntries] = useState<UploadEntry[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [confirmRemoveId, setConfirmRemoveId] = useState<string | null>(null);

  const selectAllRef = useRef<HTMLInputElement>(null);
  const allSelected = entries.length > 0 && entries.every((e) => e.selected);
  const someSelected = entries.some((e) => e.selected);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected && !allSelected;
    }
  }, [someSelected, allSelected]);

  // Track uploads status for search section — only set true reactively;
  // false is set explicitly on user-initiated clear to avoid resetting
  // SearchSection due to transient remounts (StrictMode or navigation).
  useEffect(() => {
    if (entries.length > 0) {
      dispatch(setCsHasUploads(true));
      const anyUploaded = entries.some(
        (e) => e.status === "COMPLETED" || e.status === "ALREADY_EXISTS"
      );
      dispatch(setCsUploadsComplete(anyUploaded));
    }
  }, [entries, dispatch]);

  const toggleSelectAll = () => {
    const next = !allSelected;
    setEntries((prev) => prev.map((e) => ({ ...e, selected: next })));
  };

  const toggleSelect = (id: string) => {
    setEntries((prev) =>
      prev.map((e) => (e.id === id ? { ...e, selected: !e.selected } : e))
    );
  };

  // ── Tag editor ──────────────────────────────────────────────
  const [tagInput, setTagInput] = useState("");

  const selectedEntries = entries.filter((e) => e.selected);

  // Add a chip tag on Enter or comma — only if all selected are in terminal state
  const handleTagKeyDown = (ev: React.KeyboardEvent<HTMLInputElement>) => {
    if (ev.key !== "Enter" && ev.key !== ",") return;
    ev.preventDefault();
    const tag = tagInput.trim().replace(/,$/, "");
    if (!tag) return;

    // Update tags locally and capture updated entries for re-ingest
    let updatedEntries: UploadEntry[] = [];
    setEntries((prev) => {
      const next = prev.map((e) =>
        e.selected && !e.tags.includes(tag) ? { ...e, tags: [...e.tags, tag] } : e
      );
      updatedEntries = next.filter((e) => e.selected && e.fileKey);
      return next;
    });
    setTagInput("");

    // Re-ingest each selected file with the latest tags
    updatedEntries.forEach((e) => {
      if (!e.fileKey) return;
      const updatedTags = e.tags.includes(tag) ? e.tags : [...e.tags, tag];
      csIngest(e.fileKey, { tags: updatedTags }).catch((err) =>
        console.warn(`Re-ingest failed for ${e.filename}:`, err)
      );
    });
  };

  const removeTag = (entryId: string, tag: string) => {
    setEntries((prev) =>
      prev.map((e) =>
        e.id === entryId ? { ...e, tags: e.tags.filter((t) => t !== tag) } : e
      )
    );
  };

  const pollTimers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  // Drive csProcessing flag: true while any entry is actively uploading/processing
  useEffect(() => {
    const anyActive = entries.some((e) => !TERMINAL.includes(e.status));
    dispatch(setCsProcessing(anyActive));
  }, [entries, dispatch]);

  const updateEntry = useCallback(
    (id: string, patch: Partial<UploadEntry>) => {
      setEntries((prev) =>
        prev.map((e) => (e.id === id ? { ...e, ...patch } : e))
      );
    },
    []
  );

  const startPolling = useCallback(
    (entryId: string, taskId: string) => {
      const timer = setInterval(async () => {
        try {
          const result = await csQueryTask(taskId);
          let status = (result.status?.toUpperCase() ?? "PROCESSING") as TaskStatus;
          const progress =
            status === "COMPLETED"
              ? 100
              : typeof result.progress === "number"
              ? result.progress
              : 0;

          if (progress === 100 && !["FAILED"].includes(status)) {
            status = "COMPLETED";
          }

          const fileKey =
            (result.result?.file_info as any)?.file_key ??
            (result.result as any)?.file_key ??
            null;
          updateEntry(entryId, { status, progress, ...(fileKey ? { fileKey } : {}) });

          if (status === "COMPLETED" || status === "FAILED") {
            clearInterval(pollTimers.current[entryId]);
            delete pollTimers.current[entryId];
          }
        } catch {
          // ignore transient poll errors
        }
      }, POLL_INTERVAL_MS);

      pollTimers.current[entryId] = timer;
    },
    [updateEntry]
  );

  // Upload files immediately on drop/browse
  const processFiles = useCallback(
    async (files: File[]) => {
      const newEntries: UploadEntry[] = files.map((f) => ({
        id: genId(),
        file: f,
        filename: f.name,
        fileType: f.name.split(".").pop()?.toUpperCase() ?? "—",
        fileSize: f.size,
        taskId: null,
        fileKey: null,
        status: "PROCESSING" as TaskStatus,
        progress: 0,
        error: null,
        selected: false,
        tags: [],
      }));
      setEntries((prev) => [...prev, ...newEntries]);

      // Ensure session + monitoring — run without blocking uploads
      const ensureSessionAndMonitoring = async () => {
        if (!sessionIdRef.current) {
          try {
            const res = await createSession();
            sessionIdRef.current = res.sessionId;
            dispatch(setSessionId(res.sessionId));
          } catch (e) {
            console.warn("Could not create session for metrics:", e);
          }
        }
        if (sessionIdRef.current && !monitoringActiveRef.current) {
          try {
            await startMonitoring(sessionIdRef.current);
            dispatch(setMonitoringActive(true));
          } catch (e) {
            console.warn("Could not start monitoring:", e);
          }
        }
      };
      ensureSessionAndMonitoring();

      await Promise.all(
        newEntries.map(async (entry) => {
          try {
            const res = await csUploadIngest(entry.file);
            if (res.status === "ALREADY_EXISTS") {
              updateEntry(entry.id, { status: "ALREADY_EXISTS", progress: 100, fileKey: res.file_key ?? null });
            } else {
              updateEntry(entry.id, { taskId: res.task_id, status: "PROCESSING", fileKey: res.file_key ?? null });
              startPolling(entry.id, res.task_id);
            }
          } catch (err: any) {
            updateEntry(entry.id, {
              status: "FAILED",
              error: err?.message ?? "Upload failed",
            });
          }
        })
      );
    },
    [updateEntry, startPolling, dispatch]
  );

  const handleRetry = useCallback(
    async (entry: UploadEntry) => {
      updateEntry(entry.id, { status: "PROCESSING", progress: 0, error: null, taskId: null });
      try {
        const meta = entry.tags.length ? { tags: entry.tags } : undefined;
        const res = await csUploadIngest(entry.file, meta);
        if (res.status === "ALREADY_EXISTS") {
          updateEntry(entry.id, { status: "ALREADY_EXISTS", progress: 100, fileKey: res.file_key ?? null });
        } else {
          updateEntry(entry.id, { taskId: res.task_id, status: "PROCESSING", fileKey: res.file_key ?? null });
          startPolling(entry.id, res.task_id);
        }
      } catch (err: any) {
        updateEntry(entry.id, { status: "FAILED", error: err?.message ?? "Upload failed" });
      }
    },
    [updateEntry, startPolling]
  );

  const handleBrowse = () => fileInputRef.current?.click();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).filter((f) => isAllowed(f.name));
    if (files.length) processFiles(files);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => setIsDragOver(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files).filter((f) => isAllowed(f.name));
    if (files.length) processFiles(files);
  };

  const confirmRemove = () => {
    const id = confirmRemoveId;
    if (!id) return;
    if (pollTimers.current[id]) {
      clearInterval(pollTimers.current[id]);
      delete pollTimers.current[id];
    }
    setEntries((prev) => {
      const next = prev.filter((e) => e.id !== id);
      if (next.length === 0) {
        dispatch(setCsHasUploads(false));
        dispatch(setCsUploadsComplete(false));
      }
      return next;
    });
    setConfirmRemoveId(null);
  };

  const getStatusLabel = (s: TaskStatus) => {
    switch (s) {
      case "PENDING":        return t("uploadSection.pending");
      case "PROCESSING":     return t("uploadSection.processing");
      case "COMPLETED":      return t("uploadSection.uploaded");
      case "FAILED":         return t("uploadSection.failed");
      case "ALREADY_EXISTS": return t("uploadSection.uploaded");
    }
  };

  const canAddTags =
    selectedEntries.length > 0 &&
    selectedEntries.every((e) => TERMINAL.includes(e.status));

return (
  <>
    <div className="cs-upload-card">
      <div className="cs-upload-header">
        <span className="cs-upload-title">{t("uploadSection.upload")}</span>
      </div>

      <div
        className={`cs-dropzone-modern ${isDragOver ? "cs-dropzone-modern--active" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleBrowse}
      >
        <div className="cs-upload-icon">⇪</div>
        <p className="cs-upload-main-text">{t("uploadSection.dragDrop")}</p>
        <p className="cs-upload-link-text">{t("uploadSection.orClick")}</p>
      </div>

      <p className="cs-supported-types">{t("uploadSection.supportedTypes")}</p>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".mp4,.ppt,.pptx,.docx,.pdf,.jpg,.jpeg,.csv,.txt"
        style={{ display: "none" }}
        onChange={handleFileChange}
      />

      {/* ── Tag Editor ── */}
      {entries.length > 0 && (
        <div className="cs-meta-panel">
          {selectedEntries.length === 0 ? (
            <p className="cs-meta-hint">{t("uploadSection.selectFileToAddTags")}</p>
          ) : (
            <>
              <p className="cs-meta-title">
                {selectedEntries.length === 1
                  ? `Tags for: ${selectedEntries[0].filename}`
                  : `Tags for ${selectedEntries.length} selected files`}
              </p>

              {/* Chips per selected entry */}
              {selectedEntries.map((se) =>
                se.tags.length > 0 ? (
                  <div key={se.id} className="cs-chip-row">
                    {selectedEntries.length > 1 && (
                      <span className="cs-chip-file-label">{se.filename}:</span>
                    )}
                    {se.tags.map((tag) => (
                      <span key={tag} className="cs-chip">
                        {tag}
                        <button
                          className="cs-chip-remove"
                          onClick={() => removeTag(se.id, tag)}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                ) : null
              )}

              <div className="cs-meta-row">
                <input
                  type="text"
                  className="cs-meta-input cs-meta-input--tags"
                  placeholder={
                    canAddTags
                      ? "Add tag — press Enter or comma"
                      : "Tags available after upload completes"
                  }
                  value={tagInput}
                  disabled={!canAddTags}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleTagKeyDown}
                />
              </div>
            </>
          )}
        </div>
      )}

      {/* ── File Table ── */}
      {entries.length > 0 && (
        <>
          <table className="cs-file-table">
            <thead>
              <tr>
                <th className="cs-col-check">
                  <input
                    ref={selectAllRef}
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleSelectAll}
                    className="cs-checkbox"
                  />
                </th>
                <th>{t("uploadSection.fileName")}</th>
                <th>{t("uploadSection.type")}</th>
                <th>{t("uploadSection.size")}</th>
                <th>{t("uploadSection.status")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr
                  key={entry.id}
                  className={`cs-row-${entry.status.toLowerCase()}${entry.selected ? " cs-row-selected" : ""}`}
                >
                  <td>
                    <input
                      type="checkbox"
                      checked={entry.selected}
                      onChange={() => toggleSelect(entry.id)}
                      className="cs-checkbox"
                    />
                  </td>
                  <td>
                    <span className="cs-file-name" title={entry.filename}>
                      {entry.filename}
                    </span>
                    {entry.tags.length > 0 && (
                      <div className="cs-row-tags">
                        {entry.tags.map((t) => (
                          <span key={t} className="cs-row-chip">{t}</span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>{entry.fileType}</td>
                  <td>{formatSize(entry.fileSize)}</td>
                  <td className="cs-col-status">
                    {entry.status === "FAILED" ? (
                      <div className="cs-failed-cell">
                        <span className="cs-failed-msg" title={entry.error ?? ""}>
                          Upload of &apos;{entry.filename}&apos; failed. Please try again
                        </span>
                        <button
                          className="cs-retry-btn"
                          onClick={() => handleRetry(entry)}
                        >
                        {t("uploadSection.retry")}
                        </button>
                      </div>
                    ) : (
                      <>
                        <span
                          className={`cs-status-badge cs-status-badge--${entry.status.toLowerCase()}`}
                        >
                          {getStatusLabel(entry.status)}
                        </span>
                        {(entry.status === "PROCESSING" || entry.status === "PENDING") && (
                          <div className="cs-progress-track">
                            <div
                              className="cs-progress-bar cs-progress-bar--animated"
                              style={{ width: `${entry.progress || 100}%` }}
                            />
                          </div>
                        )}
                        {(entry.status === "COMPLETED" || entry.status === "ALREADY_EXISTS") && (
                          <div className="cs-progress-track">
                            <div
                              className="cs-progress-bar cs-progress-bar--complete"
                              style={{ width: "100%" }}
                            />
                          </div>
                        )}
                      </>
                    )}
                  </td>
                  <td className="cs-col-remove">
                    <button
                      className="cs-remove-btn"
                      onClick={() => setConfirmRemoveId(entry.id)}
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="cs-table-footer">
            <button
              className="cs-clear-all-btn"
              onClick={() => {
                Object.values(pollTimers.current).forEach(clearInterval);
                pollTimers.current = {};
                setEntries([]);
                dispatch(setCsHasUploads(false));
                dispatch(setCsUploadsComplete(false));
              }}
            >
                {t("uploadSection.clearAll")}
            </button>
          </div>
        </>
      )}
    </div>

    {confirmRemoveId && (
      <div className="cs-modal-overlay">
        <div className="cs-modal">
          <p>{t("uploadSection.removeFileConfirmation")}</p>
          <div className="cs-modal-actions">
            <button onClick={() => setConfirmRemoveId(null)}>{t("uploadSection.cancel")}</button>
            <button className="cs-danger-btn" onClick={confirmRemove}>
              {t("uploadSection.remove")}
            </button>
          </div>
        </div>
      </div>
    )}
  </>
);}

export default UploadSection;
