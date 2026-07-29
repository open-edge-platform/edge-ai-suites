import { useState, useCallback } from "react";
import { csCleanupTask } from "../services/api";

interface UseFileRemovalOptions {
  onSuccess?: (taskId: string) => void;
  onError?: (error: Error, taskId: string) => void;
}

interface FileToRemove {
  taskId: string;
  fileName: string;
}

export function useFileRemoval(options: UseFileRemovalOptions = {}) {
  const { onSuccess, onError } = options;
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [fileToRemove, setFileToRemove] = useState<FileToRemove | null>(null);
  const [isRemoving, setIsRemoving] = useState(false);

  const requestRemoval = useCallback((taskId: string, fileName: string) => {
    setFileToRemove({ taskId, fileName });
    setIsModalOpen(true);
  }, []);

  const cancelRemoval = useCallback(() => {
    setIsModalOpen(false);
    setFileToRemove(null);
  }, []);

  const confirmRemoval = useCallback(async () => {
    if (!fileToRemove) return;

    const { taskId } = fileToRemove;
    setIsRemoving(true);

    try {
      await csCleanupTask(taskId);
      setIsModalOpen(false);
      setFileToRemove(null);
      onSuccess?.(taskId);
    } catch (err: any) {
      console.error(`Cleanup failed for task ${taskId}:`, err);
      onError?.(err, taskId);
    } finally {
      setIsRemoving(false);
    }
  }, [fileToRemove, onSuccess, onError]);

  return {
    isModalOpen,
    fileToRemove,
    isRemoving,
    requestRemoval,
    cancelRemoval,
    confirmRemoval,
  };
}
