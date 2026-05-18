import React from "react";
import { useTranslation } from "react-i18next";
import "../../assets/css/RemoveConfirmationModal.css";

interface RemoveConfirmationModalProps {
  isOpen: boolean;
  fileName: string;
  onCancel: () => void;
  onConfirm: () => void;
  isRemoving?: boolean;
}

const RemoveConfirmationModal: React.FC<RemoveConfirmationModalProps> = ({
  isOpen,
  fileName,
  onCancel,
  onConfirm,
  isRemoving = false,
}) => {
  const { t } = useTranslation();

  if (!isOpen) return null;

  return (
    <div className="rcm-modal-overlay">
      <div className="rcm-modal">
        <p>{t("fileManager.removeConfirm", { fileName })}</p>
        <p className="rcm-modal-warning">
          {t("fileManager.removeWarning")}
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
    </div>
  );
};

export default RemoveConfirmationModal;
