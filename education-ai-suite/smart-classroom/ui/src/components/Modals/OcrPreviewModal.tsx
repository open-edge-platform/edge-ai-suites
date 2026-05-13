import React from "react";
import closeIcon from "../../assets/images/close_frame.svg";
import "../../assets/css/OcrPreviewModal.css";

interface OcrPreviewModalProps {
  isOpen: boolean;
  filename: string;
  content: string;
  loading: boolean;
  onClose: () => void;
  onDownload: () => void;
}

const OcrPreviewModal: React.FC<OcrPreviewModalProps> = ({
  isOpen,
  filename,
  content,
  loading,
  onClose,
  onDownload,
}) => {
  if (!isOpen) return null;

  return (
    <div className="cs-modal-overlay" onClick={onClose}>
      <div className="cs-ocr-preview-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cs-ocr-preview-header">
          <span className="cs-ocr-preview-title">
            "{filename}" plain-text preview
          </span>
          <button className="cs-ocr-preview-close" onClick={onClose}>
            <img src={closeIcon} alt="Close" />
          </button>
        </div>
        <div className="cs-ocr-preview-divider" />
        <div className="cs-ocr-preview-content">
          {loading ? (
            <span className="cs-ocr-preview-loading">Loading...</span>
          ) : (
            <pre className="cs-ocr-preview-text">{content}</pre>
          )}
        </div>
        <div className="cs-ocr-preview-divider" />
        <div className="cs-ocr-preview-footer">
          <button
            className="cs-ocr-download-btn"
            onClick={onDownload}
            disabled={loading}
          >
            Download .txt
          </button>
        </div>
      </div>
    </div>
  );
};

export default OcrPreviewModal;
