import React, { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import "../../assets/css/FileManager.css";
import handwrittenIcon from "../../assets/images/handwritten_preview.svg";
import { csGetFilesList, csDownloadText, getOcrDownloadUrl } from "../../services/api";
import OcrPreviewModal from "../Modals/OcrPreviewModal";

interface FileMeta {
  tags?: string[];
  vs_enabled?: boolean;
  ocr_text_key?: string;
}

interface FileEntry {
  file_hash: string;
  file_name: string;
  meta: FileMeta;
  created_at: string;
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

const FileManager: React.FC<FileManagerProps> = ({ onBack }) => {
  const { t } = useTranslation();
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [ocrPreview, setOcrPreview] = useState<{
    isOpen: boolean;
    filename: string;
    content: string;
    loading: boolean;
    ocrTextKey: string;
  }>({ isOpen: false, filename: "", content: "", loading: false, ocrTextKey: "" });

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response: FileListResponse = await csGetFilesList();
      setFiles(response.data?.files ?? []);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load files");
    } finally {
      setLoading(false);
    }
  }, []);

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

  // Build tags array including _summarization_enabled if vs_enabled
  const getFileTags = (file: FileEntry): string[] => {
    const tags: string[] = [...(file.meta?.tags || [])];
    if (file.meta?.vs_enabled) {
      tags.push("_summarization_enabled");
    }
    return tags;
  };

  return (
    <>
      <div className="fm-container">
        <div className="fm-header">
          <button className="fm-back-btn" onClick={onBack}>
            ← Back
          </button>
          <span className="fm-title">
            Total Files: {files.length}
          </span>
          <button className="fm-refresh-btn" onClick={fetchFiles} disabled={loading}>
            ↻
          </button>
        </div>

        {loading && (
          <div className="fm-loading">
            <span className="fm-spinner"></span>
            {t("fileManager.loading") || "Loading files..."}
          </div>
        )}

        {error && (
          <div className="fm-error">
            <span>{error}</span>
            <button onClick={fetchFiles}>{t("fileManager.retry") || "Retry"}</button>
          </div>
        )}

        {!loading && !error && files.length === 0 && (
          <div className="fm-empty">
            {t("fileManager.noFiles") || "No files uploaded yet."}
          </div>
        )}

        {!loading && !error && files.length > 0 && (
          <div className="fm-file-list">
            <table className="fm-file-table">
              <thead>
                <tr>
                  <th>File Name</th>
                  <th>Created At</th>
                </tr>
              </thead>
              <tbody>
                {files.map((file) => {
                  const tags = getFileTags(file);
                  return (
                    <tr key={file.file_hash}>
                      <td>
                        <div className="fm-file-info">
                          <span className="fm-file-name" title={file.file_name}>
                            {file.file_name}
                            {file.meta?.ocr_text_key && (
                              <img
                                src={handwrittenIcon}
                                alt="OCR"
                                className="fm-ocr-icon fm-ocr-icon--clickable"
                                title="Click to preview OCR text"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleOcrPreview(file.file_name, file.meta.ocr_text_key!);
                                }}
                              />
                            )}
                          </span>
                          {tags.length > 0 && (
                            <div className="fm-tags">
                              {tags.map((tag) => (
                                <span
                                  key={tag}
                                  className={`fm-tag ${tag === "_summarization_enabled" ? "fm-tag--vs" : ""}`}
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="fm-created-at">{formatDate(file.created_at)}</td>
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
    </>
  );
};

export default FileManager;
