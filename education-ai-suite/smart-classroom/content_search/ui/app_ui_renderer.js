/**
 * UI Renderer for File Manager
 * Handles rendering file table and interactions
 */

(function() {
  'use strict';

  // Get elements
  const dropzone = document.getElementById('dropzone-compact');
  const fileInput = document.getElementById('upload-files');
  const fileTableWrapper = document.getElementById('file-table-wrapper');
  const fileTableBody = document.getElementById('file-table-body');
  const batchActions = document.getElementById('batch-actions');
  const batchSummary = document.getElementById('batch-summary');
  const btnUploadAll = document.getElementById('btn-upload-all');
  const btnUploadAllText = document.getElementById('btn-upload-all-text');
  const btnClearCompleted = document.getElementById('btn-clear-completed');
  const btnClearFailed = document.getElementById('btn-clear-failed');
  const uploadStatus = document.getElementById('upload-status');

  // Initialize file manager
  const fileManager = new FileManager();

  /**
   * Handle file selection
   */
  function handleFilesSelected(files) {
    const addedFiles = fileManager.addFiles(files);

    if (addedFiles.length === 0) {
      setStatus('No supported files selected');
      return;
    }

    // Show table
    fileTableWrapper.hidden = false;
    batchActions.hidden = false;

    // Render all files
    renderFileTable();
    updateBatchActions();

    setStatus(`${addedFiles.length} file(s) added`);
  }

  /**
   * Render entire file table
   */
  function renderFileTable() {
    fileTableBody.innerHTML = '';

    const files = fileManager.getAllFiles();

    if (files.length === 0) {
      fileTableWrapper.hidden = true;
      batchActions.hidden = true;
      return;
    }

    files.forEach(file => {
      const row = createFileRow(file);
      fileTableBody.appendChild(row);
    });
  }

  /**
   * Create a file table row
   */
  function createFileRow(file) {
    const tr = document.createElement('tr');
    tr.dataset.fileId = file.id;

    // Icon cell
    const iconCell = document.createElement('td');
    iconCell.className = 'file-cell-icon';
    iconCell.textContent = getFileIcon(file.type);
    tr.appendChild(iconCell);

    // Name cell
    const nameCell = document.createElement('td');
    nameCell.className = 'file-cell-name';
    nameCell.textContent = file.filename;
    nameCell.title = file.filename;
    tr.appendChild(nameCell);

    // Size cell
    const sizeCell = document.createElement('td');
    sizeCell.className = 'file-cell-size';
    sizeCell.textContent = fileManager.formatSize(file.size);
    tr.appendChild(sizeCell);

    // Labels cell
    const labelsCell = document.createElement('td');
    labelsCell.className = 'file-cell-labels';
    labelsCell.appendChild(createLabelsDisplay(file));
    tr.appendChild(labelsCell);

    // Status cell
    const statusCell = document.createElement('td');
    statusCell.className = 'file-cell-status';
    statusCell.appendChild(createStatusDisplay(file));
    tr.appendChild(statusCell);

    // Actions cell
    const actionsCell = document.createElement('td');
    actionsCell.className = 'file-cell-actions';
    actionsCell.appendChild(createActionsButtons(file));
    tr.appendChild(actionsCell);

    return tr;
  }

  /**
   * Get file icon by type
   */
  function getFileIcon(type) {
    const icons = {
      video: '📄',
      image: '📄',
      document: '📄',
    };
    return icons[type] || '📄';
  }

  /**
   * Create labels display
   */
  function createLabelsDisplay(file) {
    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.gap = '4px';
    container.style.flexWrap = 'wrap';

    if (file.labels.length === 0) {
      const empty = document.createElement('span');
      empty.className = 'file-label file-label--empty';
      empty.textContent = '-';
      container.appendChild(empty);
      return container;
    }

    // Show first 2 labels
    file.labels.slice(0, 2).forEach(label => {
      const span = document.createElement('span');
      span.className = 'file-label';
      span.textContent = label;
      container.appendChild(span);
    });

    // Show +N if more labels
    if (file.labels.length > 2) {
      const more = document.createElement('span');
      more.className = 'file-label file-label--count';
      more.textContent = `+${file.labels.length - 2}`;
      more.title = file.labels.slice(2).join(', ');
      container.appendChild(more);
    }

    return container;
  }

  /**
   * Create status display
   */
  function createStatusDisplay(file) {
    const container = document.createElement('div');
    container.className = 'file-cell-status';

    const config = STATUS_CONFIG[file.status];

    // For uploading status, show progress bar
    if (file.status === FILE_STATUS.UPLOADING) {
      const progress = document.createElement('div');
      progress.className = 'file-progress';

      const progressBar = document.createElement('div');
      progressBar.className = 'file-progress__bar';

      const progressFill = document.createElement('div');
      progressFill.className = 'file-progress__fill';
      progressFill.style.width = `${file.uploadProgress}%`;

      progressBar.appendChild(progressFill);
      progress.appendChild(progressBar);

      const progressText = document.createElement('span');
      progressText.className = 'file-progress__text';
      progressText.textContent = `${file.uploadProgress}%`;
      progress.appendChild(progressText);

      container.appendChild(progress);
      return container;
    }

    // For other statuses
    const icon = document.createElement('span');
    icon.className = 'status-icon';
    if (file.status === FILE_STATUS.PROCESSING) {
      icon.className += ' status-icon--processing';
    }
    icon.textContent = config.icon;

    const text = document.createElement('span');
    text.className = `status-text ${config.class}`;

    // Customize text based on status
    if (file.status === FILE_STATUS.COMPLETED) {
      const elapsed = file.result?.elapsed_seconds;
      if (elapsed) {
        text.textContent = `${config.text} (${Math.round(elapsed)}s)`;
      } else {
        text.textContent = config.text;
      }
    } else if (file.status === FILE_STATUS.FAILED) {
      const errorMsg = file.error?.message || 'Unknown error';
      text.textContent = errorMsg.length > 30 ? errorMsg.substring(0, 30) + '...' : errorMsg;
      text.title = errorMsg;
    } else {
      text.textContent = config.text;
    }

    container.appendChild(icon);
    container.appendChild(text);

    return container;
  }

  /**
   * Create action buttons
   */
  function createActionsButtons(file) {
    const container = document.createElement('div');
    container.className = 'file-cell-actions';

    if (file.status === FILE_STATUS.PENDING) {
      // Upload button
      const uploadBtn = createActionButton('↑', 'Upload', 'file-action-btn--upload');
      uploadBtn.onclick = () => handleUploadFile(file.id);
      container.appendChild(uploadBtn);

      // Remove button
      const removeBtn = createActionButton('×', 'Remove', 'file-action-btn--remove');
      removeBtn.onclick = () => handleRemoveFile(file.id);
      container.appendChild(removeBtn);

    } else if (file.status === FILE_STATUS.UPLOADING) {
      // Cancel button
      const cancelBtn = createActionButton('×', 'Cancel', 'file-action-btn--remove');
      cancelBtn.onclick = () => handleCancelUpload(file.id);
      container.appendChild(cancelBtn);

    } else if (file.status === FILE_STATUS.COMPLETED) {
      // View button (optional)
      // const viewBtn = createActionButton('👁', 'View');
      // viewBtn.onclick = () => handleViewFile(file.id);
      // container.appendChild(viewBtn);

      // Remove button
      const removeBtn = createActionButton('×', 'Remove', 'file-action-btn--remove');
      removeBtn.onclick = () => handleRemoveFile(file.id);
      container.appendChild(removeBtn);

    } else if (file.status === FILE_STATUS.FAILED) {
      // Retry button
      const retryBtn = createActionButton('↻', 'Retry', 'file-action-btn--retry');
      retryBtn.onclick = () => handleRetryFile(file.id);
      container.appendChild(retryBtn);

      // Remove button
      const removeBtn = createActionButton('×', 'Remove', 'file-action-btn--remove');
      removeBtn.onclick = () => handleRemoveFile(file.id);
      container.appendChild(removeBtn);

    } else {
      // No actions for queued/processing
      const noAction = document.createElement('span');
      noAction.textContent = '-';
      noAction.style.color = 'var(--muted)';
      container.appendChild(noAction);
    }

    return container;
  }

  /**
   * Create action button
   */
  function createActionButton(symbol, title, extraClass = '') {
    const btn = document.createElement('button');
    btn.className = `file-action-btn ${extraClass}`;
    btn.title = title;
    btn.textContent = symbol;
    btn.type = 'button';
    return btn;
  }

  /**
   * Update batch actions panel
   */
  function updateBatchActions() {
    const counts = fileManager.getStatusCounts();
    const total = fileManager.getAllFiles().length;

    if (total === 0) {
      batchActions.hidden = true;
      return;
    }

    batchActions.hidden = false;

    // Update summary
    const parts = [];
    if (counts.pending > 0) parts.push(`${counts.pending} pending`);
    if (counts.uploading > 0) parts.push(`${counts.uploading} uploading`);
    if (counts.queued > 0) parts.push(`${counts.queued} queued`);
    if (counts.processing > 0) parts.push(`${counts.processing} processing`);
    if (counts.completed > 0) parts.push(`${counts.completed} completed`);
    if (counts.failed > 0) parts.push(`${counts.failed} failed`);

    batchSummary.textContent = parts.join(', ') || 'No files';

    // Update buttons
    if (counts.pending > 0) {
      btnUploadAll.hidden = false;
      btnUploadAllText.textContent = `Upload All (${counts.pending})`;
    } else {
      btnUploadAll.hidden = true;
    }

    btnClearCompleted.hidden = counts.completed === 0;
    if (counts.completed > 0) {
      btnClearCompleted.textContent = `Clear Completed (${counts.completed})`;
    }

    btnClearFailed.hidden = counts.failed === 0;
    if (counts.failed > 0) {
      btnClearFailed.textContent = `Clear Failed (${counts.failed})`;
    }
  }

  /**
   * Handle upload single file
   */
  async function handleUploadFile(fileId) {
    const file = fileManager.getFile(fileId);
    if (!file) return;

    // Update status to uploading
    fileManager.updateFile(fileId, {
      status: FILE_STATUS.UPLOADING,
      uploadProgress: 0
    });
    renderFileTable();

    try {
      // Create FormData
      const formData = new FormData();
      formData.append('file', file.file);

      // Add labels as meta if present
      if (file.labels.length > 0) {
        const meta = JSON.stringify({ tags: file.labels });
        formData.append('meta', meta);
      }

      // Create XMLHttpRequest for progress tracking
      const xhr = new XMLHttpRequest();
      file.xhr = xhr;

      // Progress handler
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const progress = Math.round((e.loaded / e.total) * 100);
          fileManager.updateFile(fileId, { uploadProgress: progress });
          updateFileRow(fileId);
        }
      });

      // Complete handler
      xhr.addEventListener('load', async () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const data = JSON.parse(xhr.responseText);

          if (data.code === 20000) {
            const taskId = data.data?.task_id;

            fileManager.updateFile(fileId, {
              status: FILE_STATUS.QUEUED,
              uploadedAt: new Date(),
              taskId: taskId,
              xhr: null,
            });

            updateFileRow(fileId);
            setStatus(`${file.filename} uploaded successfully`);

            // Start polling if we have task ID
            if (taskId) {
              startTaskPolling(fileId, taskId);
            }
          } else {
            throw new Error(data.message || 'Upload failed');
          }
        } else {
          throw new Error(`HTTP ${xhr.status}`);
        }
      });

      // Error handler
      xhr.addEventListener('error', () => {
        handleUploadError(fileId, new Error('Network error'));
      });

      // Send request
      xhr.open('POST', 'http://127.0.0.1:9011/api/v1/object/upload-ingest');
      xhr.send(formData);

    } catch (error) {
      handleUploadError(fileId, error);
    }
  }

  /**
   * Handle upload error
   */
  function handleUploadError(fileId, error) {
    fileManager.updateFile(fileId, {
      status: FILE_STATUS.FAILED,
      error: {
        message: error.message || 'Upload failed',
      },
      xhr: null,
    });
    updateFileRow(fileId);
    setStatus(`Upload failed: ${error.message}`);
  }

  /**
   * Start polling task status
   */
  function startTaskPolling(fileId, taskId) {
    fileManager.updateFile(fileId, { status: FILE_STATUS.PROCESSING });
    updateFileRow(fileId);

    fileManager.startPolling(fileId, taskId, (taskData) => {
      if (!taskData) return;

      const file = fileManager.getFile(fileId);
      if (!file) return;

      const status = taskData.status;

      if (status === 'PENDING' || status === 'QUEUED') {
        fileManager.updateFile(fileId, {
          status: FILE_STATUS.QUEUED,
          taskStatus: status
        });
      } else if (status === 'PROCESSING') {
        fileManager.updateFile(fileId, {
          status: FILE_STATUS.PROCESSING,
          taskStatus: status
        });
      } else if (status === 'COMPLETED') {
        fileManager.stopPolling(fileId);
        fileManager.updateFile(fileId, {
          status: FILE_STATUS.COMPLETED,
          completedAt: new Date(),
          result: {
            elapsed_seconds: taskData.result?.video_summary?.elapsed_seconds,
            chunks: taskData.result?.video_summary?.total_chunks,
          },
        });
        setStatus(`${file.filename} completed successfully`);
      } else if (status === 'FAILED') {
        fileManager.stopPolling(fileId);
        fileManager.updateFile(fileId, {
          status: FILE_STATUS.FAILED,
          error: {
            message: taskData.result?.message || 'Processing failed',
          },
        });
        setStatus(`${file.filename} processing failed`);
      }

      updateFileRow(fileId);
      updateBatchActions();
    });
  }

  /**
   * Handle cancel upload
   */
  function handleCancelUpload(fileId) {
    const file = fileManager.getFile(fileId);
    if (!file || !file.xhr) return;

    file.xhr.abort();

    fileManager.updateFile(fileId, {
      status: FILE_STATUS.CANCELLED,
      xhr: null,
    });

    updateFileRow(fileId);
    setStatus(`${file.filename} upload cancelled`);
  }

  /**
   * Handle remove file
   */
  function handleRemoveFile(fileId) {
    const file = fileManager.getFile(fileId);
    if (!file) return;

    fileManager.removeFile(fileId);
    renderFileTable();
    updateBatchActions();
    setStatus(`${file.filename} removed`);
  }

  /**
   * Handle retry file
   */
  function handleRetryFile(fileId) {
    fileManager.updateFile(fileId, {
      status: FILE_STATUS.PENDING,
      error: null,
      uploadProgress: 0,
    });
    updateFileRow(fileId);
    updateBatchActions();
  }

  /**
   * Update single file row
   */
  function updateFileRow(fileId) {
    const row = document.querySelector(`tr[data-file-id="${fileId}"]`);
    if (!row) return;

    const file = fileManager.getFile(fileId);
    if (!file) return;

    // Update status cell
    const statusCell = row.querySelector('.file-cell-status');
    if (statusCell) {
      statusCell.innerHTML = '';
      statusCell.appendChild(createStatusDisplay(file));
    }

    // Update actions cell
    const actionsCell = row.querySelector('.file-cell-actions');
    if (actionsCell) {
      actionsCell.innerHTML = '';
      actionsCell.appendChild(createActionsButtons(file));
    }
  }

  /**
   * Set status message
   */
  function setStatus(message) {
    uploadStatus.textContent = message || '';
  }

  /**
   * Handle upload all pending files
   */
  function handleUploadAll() {
    const pending = fileManager.getFilesByStatus(FILE_STATUS.PENDING);
    pending.forEach(file => {
      handleUploadFile(file.id);
    });
  }

  /**
   * Handle clear completed files
   */
  function handleClearCompleted() {
    const count = fileManager.clearByStatus(FILE_STATUS.COMPLETED);
    renderFileTable();
    updateBatchActions();
    setStatus(`${count} completed file(s) cleared`);
  }

  /**
   * Handle clear failed files
   */
  function handleClearFailed() {
    const count = fileManager.clearByStatus(FILE_STATUS.FAILED);
    renderFileTable();
    updateBatchActions();
    setStatus(`${count} failed file(s) cleared`);
  }

  // ===== Event Listeners =====

  // File input change
  fileInput.addEventListener('change', () => {
    const files = Array.from(fileInput.files || []);
    if (files.length > 0) {
      handleFilesSelected(files);
      fileInput.value = ''; // Reset input
    }
  });

  // Drag and drop
  dropzone.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dropzone.classList.add('is-dragover');
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('is-dragover');
  });

  dropzone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    if (e.target === dropzone) {
      dropzone.classList.remove('is-dragover');
    }
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('is-dragover');

    const files = Array.from(e.dataTransfer?.files || []);
    if (files.length > 0) {
      handleFilesSelected(files);
    }
  });

  // Batch action buttons
  btnUploadAll.addEventListener('click', handleUploadAll);
  btnClearCompleted.addEventListener('click', handleClearCompleted);
  btnClearFailed.addEventListener('click', handleClearFailed);

  // Export for debugging
  window.fileManagerUI = {
    fileManager,
    renderFileTable,
    updateBatchActions,
  };

})();
