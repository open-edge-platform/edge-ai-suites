/**
 * UI Renderer v3.0 - Simplified File List
 * 4 states: Pending (Upload button) | Processing | Uploaded | Failed
 */

(function() {
  'use strict';

  // Get elements
  const dropzone = document.getElementById('dropzone-compact');
  const fileInput = document.getElementById('upload-files');
  const fileListWrapper = document.getElementById('file-list-wrapper');
  const fileListItems = document.getElementById('file-list-items');
  const labelsInput = document.getElementById('labels-input');
  const btnAddToSelected = document.getElementById('btn-add-to-selected');
  const selectAllCheckbox = document.getElementById('select-all-files');
  const btnDeleteAll = document.getElementById('btn-delete-all');
  const linkClearAll = document.getElementById('link-clear-all');
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

    fileListWrapper.hidden = false;
    renderFileList();
    setStatus(`${addedFiles.length} file(s) added`);
  }

  /**
   * Render entire file list
   */
  function renderFileList() {
    fileListItems.innerHTML = '';

    const files = fileManager.getAllFiles();

    if (files.length === 0) {
      fileListWrapper.hidden = true;
      return;
    }

    files.forEach(file => {
      const item = createFileItem(file);
      fileListItems.appendChild(item);
    });

    updateSelectAllCheckbox();
  }

  /**
   * Create file item element
   */
  function createFileItem(file) {
    const container = document.createElement('div');
    container.className = 'file-item';
    if (file.checked) {
      container.classList.add('is-selected');
    }
    container.dataset.fileId = file.id;

    // Main row
    const row = document.createElement('div');
    row.className = 'file-item__row';

    // Checkbox
    const checkCell = document.createElement('div');
    checkCell.className = 'file-item__check';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = file.checked;
    checkbox.addEventListener('change', () => {
      handleFileCheckToggle(file.id);
    });
    checkCell.appendChild(checkbox);

    // File name
    const nameCell = document.createElement('div');
    nameCell.className = 'file-item__name';
    nameCell.textContent = file.filename;
    nameCell.title = file.filename;

    // Type
    const typeCell = document.createElement('div');
    typeCell.className = 'file-item__type';
    typeCell.textContent = capitalize(file.type);

    // Size
    const sizeCell = document.createElement('div');
    sizeCell.className = 'file-item__size';
    sizeCell.textContent = fileManager.formatSize(file.size);

    // Status
    const statusCell = document.createElement('div');
    statusCell.className = 'file-item__status';
    statusCell.appendChild(createStatusDisplay(file));

    // Elapsed Time
    const elapsedCell = document.createElement('div');
    elapsedCell.className = 'file-item__elapsed';
    elapsedCell.textContent = formatElapsedTime(file);

    // Actions
    const actionsCell = document.createElement('div');
    actionsCell.className = 'file-item__actions';
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'icon-btn';
    deleteBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
    </svg>`;
    deleteBtn.title = 'Delete';
    deleteBtn.type = 'button';
    deleteBtn.addEventListener('click', () => handleDeleteFile(file.id));
    actionsCell.appendChild(deleteBtn);

    // Append all cells
    row.appendChild(checkCell);
    row.appendChild(nameCell);
    row.appendChild(typeCell);
    row.appendChild(sizeCell);
    row.appendChild(statusCell);
    row.appendChild(elapsedCell);
    row.appendChild(actionsCell);

    container.appendChild(row);

    // Labels row (if has labels)
    if (file.labels.length > 0) {
      const labelsRow = document.createElement('div');
      labelsRow.className = 'file-item__labels';
      file.labels.forEach(label => {
        labelsRow.appendChild(createLabelTag(file.id, label));
      });
      container.appendChild(labelsRow);
    }

    return container;
  }

  /**
   * Create status display (4 states only)
   */
  function createStatusDisplay(file) {
    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.alignItems = 'center';
    container.style.gap = '8px';

    if (file.status === FILE_STATUS.PENDING) {
      // State 1: Pending -> [Upload] button
      const uploadBtn = document.createElement('button');
      uploadBtn.className = 'status-badge status-badge--pending';
      uploadBtn.textContent = 'Upload';
      uploadBtn.type = 'button';
      uploadBtn.addEventListener('click', () => handleUploadFile(file.id));
      container.appendChild(uploadBtn);

    } else if (
      file.status === FILE_STATUS.UPLOADING ||
      file.status === FILE_STATUS.QUEUED ||
      file.status === FILE_STATUS.PROCESSING
    ) {
      // State 2: Processing (uploading/queued/processing)
      const badge = document.createElement('span');
      badge.className = 'status-badge status-badge--processing';
      badge.innerHTML = 'Processing<span class="loading-dots"><span>.</span><span>.</span><span>.</span></span>';
      container.appendChild(badge);

    } else if (file.status === FILE_STATUS.COMPLETED) {
      // State 3: Completed -> [Uploaded ✓]
      const badge = document.createElement('span');
      badge.className = 'status-badge status-badge--completed';
      badge.textContent = 'Uploaded ✓';
      container.appendChild(badge);

    } else if (file.status === FILE_STATUS.FAILED || file.status === FILE_STATUS.CANCELLED) {
      // State 4: Failed -> [Failed ✗] [Retry]
      const failedBadge = document.createElement('span');
      failedBadge.className = 'status-badge status-badge--failed';
      failedBadge.textContent = 'Failed ✗';
      container.appendChild(failedBadge);

      const retryBtn = document.createElement('button');
      retryBtn.className = 'btn-retry';
      retryBtn.textContent = 'Retry';
      retryBtn.type = 'button';
      retryBtn.addEventListener('click', () => handleRetryFile(file.id));
      container.appendChild(retryBtn);
    }

    return container;
  }

  /**
   * Create label tag with remove button
   */
  function createLabelTag(fileId, label) {
    const tag = document.createElement('span');
    tag.className = 'file-label-tag';

    const text = document.createElement('span');
    text.textContent = label;
    tag.appendChild(text);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'file-label-tag__remove';
    removeBtn.textContent = '×';
    removeBtn.type = 'button';
    removeBtn.title = `Remove ${label}`;
    removeBtn.addEventListener('click', () => {
      fileManager.removeLabel(fileId, label);
      updateFileItem(fileId);
    });
    tag.appendChild(removeBtn);

    return tag;
  }

  /**
   * Capitalize first letter
   */
  function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  /**
   * Format elapsed time from file timestamps
   */
  function formatElapsedTime(file) {
    // Not started yet
    if (file.status === FILE_STATUS.PENDING) {
      return '-';
    }

    // No upload start time recorded (shouldn't happen but defensive)
    if (!file.uploadStartedAt) {
      return '-';
    }

    let startTime = file.uploadStartedAt; // Use upload start time, not creation time
    let endTime;

    if (file.status === FILE_STATUS.COMPLETED) {
      endTime = file.completedAt || new Date();
    } else if (file.status === FILE_STATUS.FAILED || file.status === FILE_STATUS.CANCELLED) {
      endTime = new Date();
    } else {
      // Uploading/Queued/Processing - show current elapsed time
      endTime = new Date();
    }

    const diffMs = endTime - startTime;
    const diffSec = Math.floor(diffMs / 1000);

    if (diffSec < 0) {
      return '0s'; // Safety check
    } else if (diffSec < 60) {
      return `${diffSec}s`;
    } else if (diffSec < 3600) {
      const minutes = Math.floor(diffSec / 60);
      const seconds = diffSec % 60;
      return `${minutes}m ${seconds}s`;
    } else {
      const hours = Math.floor(diffSec / 3600);
      const minutes = Math.floor((diffSec % 3600) / 60);
      return `${hours}h ${minutes}m`;
    }
  }

  /**
   * Update single file item
   */
  function updateFileItem(fileId) {
    const container = document.querySelector(`.file-item[data-file-id="${fileId}"]`);
    if (!container) return;

    const file = fileManager.getFile(fileId);
    if (!file) return;

    // Update selection class
    if (file.checked) {
      container.classList.add('is-selected');
    } else {
      container.classList.remove('is-selected');
    }

    // Update checkbox
    const checkbox = container.querySelector('input[type="checkbox"]');
    if (checkbox) {
      checkbox.checked = file.checked;
    }

    // Update status
    const statusCell = container.querySelector('.file-item__status');
    if (statusCell) {
      statusCell.innerHTML = '';
      statusCell.appendChild(createStatusDisplay(file));
    }

    // Update elapsed time
    const elapsedCell = container.querySelector('.file-item__elapsed');
    if (elapsedCell) {
      elapsedCell.textContent = formatElapsedTime(file);
    }

    // Update labels
    const existingLabels = container.querySelector('.file-item__labels');
    if (existingLabels) {
      existingLabels.remove();
    }

    if (file.labels.length > 0) {
      const labelsRow = document.createElement('div');
      labelsRow.className = 'file-item__labels';
      file.labels.forEach(label => {
        labelsRow.appendChild(createLabelTag(file.id, label));
      });
      container.appendChild(labelsRow);
    }
  }

  /**
   * Handle file checkbox toggle
   */
  function handleFileCheckToggle(fileId) {
    fileManager.toggleChecked(fileId);
    updateFileItem(fileId);
    updateSelectAllCheckbox();
  }

  /**
   * Update select-all checkbox state
   */
  function updateSelectAllCheckbox() {
    const files = fileManager.getAllFiles();
    const checked = fileManager.getCheckedFiles();

    if (files.length === 0) {
      selectAllCheckbox.checked = false;
      selectAllCheckbox.indeterminate = false;
    } else if (checked.length === 0) {
      selectAllCheckbox.checked = false;
      selectAllCheckbox.indeterminate = false;
    } else if (checked.length === files.length) {
      selectAllCheckbox.checked = true;
      selectAllCheckbox.indeterminate = false;
    } else {
      selectAllCheckbox.checked = false;
      selectAllCheckbox.indeterminate = true;
    }
  }

  /**
   * Handle upload file
   */
  async function handleUploadFile(fileId) {
    const file = fileManager.getFile(fileId);
    if (!file) return;

    // Update status to uploading (shows as Processing)
    fileManager.updateFile(fileId, {
      status: FILE_STATUS.UPLOADING,
      uploadStartedAt: new Date() // Record when upload actually starts
    });
    updateFileItem(fileId);

    try {
      const formData = new FormData();
      formData.append('file', file.file);

      if (file.labels.length > 0) {
        const meta = JSON.stringify({ tags: file.labels });
        formData.append('meta', meta);
      }

      const xhr = new XMLHttpRequest();
      file.xhr = xhr;

      // No need to track progress - just show "Processing..."

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

            updateFileItem(fileId);
            setStatus(`${file.filename} uploaded successfully`);

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

      xhr.addEventListener('error', () => {
        handleUploadError(fileId, new Error('Network error'));
      });

      xhr.open('POST', `${window.API_BASE_URL || 'http://127.0.0.1:9011'}/api/v1/object/upload-ingest`);
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
    updateFileItem(fileId);
    setStatus(`Upload failed: ${error.message}`);
  }

  /**
   * Start task polling
   */
  function startTaskPolling(fileId, taskId) {
    fileManager.updateFile(fileId, { status: FILE_STATUS.PROCESSING });
    updateFileItem(fileId);

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

      updateFileItem(fileId);
    });
  }

  /**
   * Handle retry file
   */
  function handleRetryFile(fileId) {
    fileManager.updateFile(fileId, {
      status: FILE_STATUS.PENDING,
      error: null,
      uploadStartedAt: null, // Reset timer for retry
    });
    updateFileItem(fileId);
  }

  /**
   * Handle delete file
   */
  function handleDeleteFile(fileId) {
    const file = fileManager.getFile(fileId);
    if (!file) return;

    fileManager.removeFile(fileId);
    renderFileList();
    setStatus(`${file.filename} removed`);
  }

  /**
   * Handle add labels to selected
   */
  function handleAddLabelsToSelected() {
    const input = labelsInput.value.trim();
    if (!input) {
      setStatus('Please enter labels');
      return;
    }

    const labels = input.split(/[\n,]/).map(l => l.trim()).filter(l => l);

    if (labels.length === 0) {
      setStatus('Please enter valid labels');
      return;
    }

    const checkedFiles = fileManager.getCheckedFiles();
    if (checkedFiles.length === 0) {
      setStatus('Please select files first');
      return;
    }

    const updated = fileManager.addLabelsToChecked(labels);

    if (updated > 0) {
      checkedFiles.forEach(file => updateFileItem(file.id));
      labelsInput.value = '';
      setStatus(`Added labels to ${checkedFiles.length} file(s)`);
    }
  }

  /**
   * Handle select all toggle
   */
  function handleSelectAllToggle() {
    const checked = selectAllCheckbox.checked;
    fileManager.setAllChecked(checked);
    renderFileList();
  }

  /**
   * Handle clear all files
   */
  function handleClearAll(e) {
    e.preventDefault();
    if (confirm('Clear all files?')) {
      fileManager.files.clear();
      renderFileList();
      setStatus('All files cleared');
    }
  }

  /**
   * Set status message
   */
  function setStatus(message) {
    uploadStatus.textContent = message || '';
  }

  // ===== Event Listeners =====

  fileInput.addEventListener('change', () => {
    const files = Array.from(fileInput.files || []);
    if (files.length > 0) {
      handleFilesSelected(files);
      fileInput.value = '';
    }
  });

  // Drag and drop
  dropzone.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dropzone.classList.add('is-dragover');
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
  });

  dropzone.addEventListener('dragleave', (e) => {
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

  // Labels input - Enter key to add
  labelsInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddLabelsToSelected();
    }
  });

  btnAddToSelected.addEventListener('click', handleAddLabelsToSelected);
  selectAllCheckbox.addEventListener('change', handleSelectAllToggle);
  btnDeleteAll.addEventListener('click', handleClearAll);
  linkClearAll.addEventListener('click', handleClearAll);

  // Update elapsed time for processing files every second
  setInterval(() => {
    const files = fileManager.getAllFiles();
    files.forEach(file => {
      if (
        file.status === FILE_STATUS.UPLOADING ||
        file.status === FILE_STATUS.QUEUED ||
        file.status === FILE_STATUS.PROCESSING
      ) {
        const elapsedCell = document.querySelector(`.file-item[data-file-id="${file.id}"] .file-item__elapsed`);
        if (elapsedCell) {
          elapsedCell.textContent = formatElapsedTime(file);
        }
      }
    });
  }, 1000);

  // Export for debugging
  window.fileManagerUI = {
    fileManager,
    renderFileList,
  };

})();
