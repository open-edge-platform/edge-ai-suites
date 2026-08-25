import React from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import "../../assets/css/RemoveConfirmationModal.css";
import { useTitleBarTheme } from "../../hooks/useTitleBarTheme";

interface RemoveConfirmationModalProps {
  isOpen: boolean;
  fileName: string;
  onCancel: () => void;
  onConfirm: () => void;
  isRemoving?: boolean;
  isStaged?: boolean;
}

const RemoveConfirmationModal: React.FC<RemoveConfirmationModalProps> = ({
  isOpen,
  fileName,
  onCancel,
  onConfirm,
  isRemoving = false,
  isStaged = false,
}) => {
  const { t } = useTranslation();
  useTitleBarTheme(isOpen, 'dimmed');

  if (!isOpen) return null;

  return createPortal(
    <div className="rcm-modal-overlay">
      <div className="rcm-modal">
        <p>{t("fileManager.removeConfirm", { fileName })}</p>
        <p className="rcm-modal-warning">
          {isStaged
            ? t("fileManager.removeWarningStagedFile")
            : t("fileManager.removeWarning")}
        </p>
        <div className="rcm-modal-actions">
          <button onClick={onCancel} disabled={isRemoving}>
            {t("uploadSection.cancel")}
          </button>
          <button
            className="rcm-danger-btn"
            onClick={onConfirm}
            disabled={isRemoving}
          >
            {isRemoving ? t("fileManager.removing") : t("uploadSection.remove")}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default RemoveConfirmationModal;
