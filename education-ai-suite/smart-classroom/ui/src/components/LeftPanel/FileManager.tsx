import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import "../../assets/css/FileManager.css";
import handwrittenIcon from "../../assets/images/handwritten_preview.svg";
import { csGetFilesList, csDownloadText, getOcrDownloadUrl } from "../../services/api";
import OcrPreviewModal from "../Modals/OcrPreviewModal";
import RemoveConfirmationModal from "../common/RemoveConfirmationModal";
import { useFileRemoval } from "../../hooks/useFileRemoval";
import { useAppDispatch } from "../../redux/hooks";
import { setCsServerFilesExist, setCsHasUploads, setCsUploadsComplete } from "../../redux/slices/uiSlice";

interface FileMeta {
  tags?: string[];
  vs_enabled?: boolean;
}

interface FileEntry {
  file_hash: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  meta: FileMeta;
  created_at: string;
  task_id?: string;
  ocr_text_key?: string;
}

interface FileListResponse {
  code: number;
  data: {
    total: number;
    files: FileEntry[];
  };
  message: string;
}

interface FileManagerProps {
  onBack: () => void;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const FileManager: React.FC<FileManagerProps> = ({ onBack }) => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removingHash, setRemovingHash] = useState<string | null>(null);

  const [ocrPreview, setOcrPreview] = useState<{
    isOpen: boolean;
    filename: string;
    content: string;
    loading: boolean;
    ocrTextKey: string;
  }>({ isOpen: false, filename: "", content: "", loading: false, ocrTextKey: "" });

  // Use common file removal hook
  const fileRemoval = useFileRemoval({
    onSuccess: (taskId) => {
      // Remove file from list after successful deletion
      setFiles((prev) => {
        const next = prev.filter((f) => f.task_id !== taskId);
        // Update Redux state based on remaining files
        const hasFiles = next.length > 0;
        dispatch(setCsServerFilesExist(hasFiles));
        if (!hasFiles) {
          dispatch(setCsHasUploads(false));
          dispatch(setCsUploadsComplete(false));
        }
        return next;
      });
      setRemovingHash(null);
    },
    onError: (err) => {
      setError(err?.message ?? "Failed to delete file");
      setRemovingHash(null);
    },
  });

  // Filter and sort state
  const [typeFilters, setTypeFilters] = useState<Set<string>>(new Set());
  const [showTypeFilter, setShowTypeFilter] = useState(false);
  const [sortColumn, setSortColumn] = useState<"size" | "created" | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const filterRef = useRef<HTMLDivElement>(null);

  // Close filter dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(event.target as Node)) {
        setShowTypeFilter(false);
      }
    };
    if (showTypeFilter) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showTypeFilter]);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response: FileListResponse = await csGetFilesList();
      const fileList = response.data?.files ?? [];
      setFiles(fileList);
      // Update Redux state based on files
      const hasFiles = fileList.length > 0;
      dispatch(setCsServerFilesExist(hasFiles));
      if (hasFiles) {
        dispatch(setCsHasUploads(true));
        dispatch(setCsUploadsComplete(true));
      } else {
        dispatch(setCsHasUploads(false));
        dispatch(setCsUploadsComplete(false));
      }
    } catch (err: any) {
      setError(err?.message ?? "Failed to load files");
    } finally {
      setLoading(false);
    }
  }, [dispatch]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const handleOcrPreview = useCallback(async (filename: string, ocrTextKey: string) => {
    setOcrPreview({ isOpen: true, filename, content: "", loading: true, ocrTextKey });
    try {
      const content = await csDownloadText(ocrTextKey);
      setOcrPreview({ isOpen: true, filename, content, loading: false, ocrTextKey });
    } catch (err) {
      setOcrPreview({ isOpen: true, filename, content: "Failed to load OCR text.", loading: false, ocrTextKey });
    }
  }, []);

  const closeOcrPreview = useCallback(() => {
    setOcrPreview({ isOpen: false, filename: "", content: "", loading: false, ocrTextKey: "" });
  }, []);

  const downloadOcrText = useCallback(() => {
    if (!ocrPreview.ocrTextKey) return;
    const link = document.createElement("a");
    link.href = getOcrDownloadUrl(ocrPreview.ocrTextKey);
    link.download = ocrPreview.filename.replace(/\.[^.]+$/, ".txt");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [ocrPreview.ocrTextKey, ocrPreview.filename]);

  const handleRemoveClick = useCallback((file: FileEntry) => {
    if (!file.task_id) {
      setError("Cannot delete: file has no task_id");
      return;
    }
    setRemovingHash(file.file_hash);
    fileRemoval.requestRemoval(file.task_id, file.file_name);
  }, [fileRemoval]);

  // Get unique file types for filter dropdown
  const uniqueTypes = useMemo(() => {
    const types = new Set<string>();
    files.forEach((f) => {
      const type = f.content_type.split("/")[1]?.toUpperCase() || f.content_type;
      types.add(type);
    });
    return Array.from(types).sort();
  }, [files]);

  // Toggle a type filter checkbox
  const toggleTypeFilter = (type: string) => {
    setTypeFilters((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  // Clear all type filters
  const clearTypeFilters = () => {
    setTypeFilters(new Set());
    setShowTypeFilter(false);
  };

  // Filter and sort files
  const filteredAndSortedFiles = useMemo(() => {
    let result = [...files];

    // Apply type filter (if any types selected, show only those)
    if (typeFilters.size > 0) {
      result = result.filter((f) => {
        const type = f.content_type.split("/")[1]?.toUpperCase() || f.content_type;
        return typeFilters.has(type);
      });
    }

    // Apply sorting
    if (sortColumn) {
      result.sort((a, b) => {
        let comparison = 0;
        if (sortColumn === "size") {
          comparison = a.size_bytes - b.size_bytes;
        } else if (sortColumn === "created") {
          comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        }
        return sortDirection === "asc" ? comparison : -comparison;
      });
    }

    return result;
  }, [files, typeFilters, sortColumn, sortDirection]);

  // Toggle sort on a column
  const handleSort = (column: "size" | "created") => {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(column);
      setSortDirection("desc");
    }
  };

  // Build tags array including summarization_enabled if vs_enabled
  const getFileTags = (file: FileEntry): string[] => {
    const tags: string[] = [...(file.meta?.tags || [])];
    if (file.meta?.vs_enabled) {
      tags.push("summarization_enabled");
    }
    return tags;
  };

  return (
    <>
      <div className="fm-container">
        <div className="fm-header">
          <button className="fm-back-btn" onClick={onBack}>
            {t("fileManager.back")}
          </button>
          <span className="fm-title">
            {t("fileManager.totalFiles")} {filteredAndSortedFiles.length}
            {typeFilters.size > 0 && ` (of ${files.length})`}
          </span>
          <button className="fm-refresh-btn" onClick={fetchFiles} disabled={loading}>
            {t("fileManager.refresh")}
          </button>
        </div>

        {loading && (
          <div className="fm-loading">
            <span className="fm-spinner"></span>
            {t("fileManager.loading")}
          </div>
        )}

        {error && (
          <div className="fm-error">
            <span>{error}</span>
            <button onClick={fetchFiles}>{t("fileManager.retry")}</button>
          </div>
        )}

        {!loading && !error && files.length === 0 && (
          <div className="fm-empty">
            {t("fileManager.noFiles")}
          </div>
        )}

        {!loading && !error && files.length > 0 && (
          <div className="fm-file-list">
            <table className="fm-file-table">
              <thead>
                <tr>
                  <th>{t("fileManager.fileName")}</th>
                  <th>
                    <div className="fm-th-filter" ref={filterRef}>
                      <span>{t("fileManager.type")}</span>
                      <button
                        className={`fm-filter-icon-btn${typeFilters.size > 0 ? " active" : ""}`}
                        onClick={() => setShowTypeFilter(!showTypeFilter)}
                        title={t("fileManager.filterByType")}
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z"/>
                        </svg>
                        {typeFilters.size > 0 && (
                          <span className="fm-filter-badge">{typeFilters.size}</span>
                        )}
                      </button>
                      {showTypeFilter && (
                        <div className="fm-filter-dropdown">
                          <div className="fm-filter-dropdown-header">
                            <span>{t("fileManager.filterByType")}</span>
                            {typeFilters.size > 0 && (
                              <button className="fm-filter-clear" onClick={clearTypeFilters}>
                                {t("fileManager.clear")}
                              </button>
                            )}
                          </div>
                          {uniqueTypes.map((type) => (
                            <label key={type} className="fm-filter-checkbox-label">
                              <input
                                type="checkbox"
                                checked={typeFilters.has(type)}
                                onChange={() => toggleTypeFilter(type)}
                              />
                              <span>{type}</span>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  </th>
                  <th className="fm-th-sortable" onClick={() => handleSort("size")}>
                    {t("fileManager.size")} {sortColumn === "size" && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                  <th className="fm-th-sortable" onClick={() => handleSort("created")}>
                    {t("fileManager.createdAt")} {sortColumn === "created" && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredAndSortedFiles.map((file) => {
                  const tags = getFileTags(file);
                  return (
                    <tr key={file.file_hash}>
                      <td>
                        <div className="fm-file-info">
                          <span className="fm-file-name" title={file.file_name}>
                            {file.file_name}
                            {file.ocr_text_key && (
                              <img
                                src={handwrittenIcon}
                                alt="OCR"
                                className="fm-ocr-icon fm-ocr-icon--clickable"
                                title={t("fileManager.ocrPreview")}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleOcrPreview(file.file_name, file.ocr_text_key!);
                                }}
                              />
                            )}
                          </span>
                          {tags.length > 0 && (
                            <div className="fm-tags">
                              {tags.map((tag) => (
                                <span
                                  key={tag}
                                  className={`fm-tag ${tag === "summarization_enabled" ? "fm-tag--vs" : ""}`}
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </td>
                      <td>{file.content_type.split("/")[1]?.toUpperCase() || file.content_type}</td>
                      <td>{formatSize(file.size_bytes)}</td>
                      <td className="fm-created-at">{formatDate(file.created_at)}</td>
                      <td className="fm-col-remove">
                        <button
                          className="fm-remove-btn"
                          disabled={removingHash === file.file_hash || fileRemoval.isRemoving}
                          onClick={() => handleRemoveClick(file)}
                          title={t("fileManager.removeFile")}
                        >
                          {removingHash === file.file_hash ? "..." : "🗑"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <OcrPreviewModal
        isOpen={ocrPreview.isOpen}
        filename={ocrPreview.filename}
        content={ocrPreview.content}
        loading={ocrPreview.loading}
        onClose={closeOcrPreview}
        onDownload={downloadOcrText}
      />

      <RemoveConfirmationModal
        isOpen={fileRemoval.isModalOpen}
        fileName={fileRemoval.fileToRemove?.fileName ?? ""}
        onCancel={() => {
          fileRemoval.cancelRemoval();
          setRemovingHash(null);
        }}
        onConfirm={fileRemoval.confirmRemoval}
        isRemoving={fileRemoval.isRemoving}
      />
    </>
  );
};

export default FileManager;
