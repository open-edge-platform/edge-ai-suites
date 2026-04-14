/**
 * File Manager for Content Search UI v2.0
 * Single-row file list with individual file status management
 */

// File status constants
const FILE_STATUS = {
  PENDING: 'pending',
  UPLOADING: 'uploading',
  QUEUED: 'queued',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
};

// Status display configuration
const STATUS_CONFIG = {
  [FILE_STATUS.PENDING]: {
    icon: '⚪',
    text: 'Pending',
    class: 'status-text--pending',
  },
  [FILE_STATUS.UPLOADING]: {
    icon: '🔄',
    text: 'Uploading',
    class: 'status-text--uploading',
  },
  [FILE_STATUS.QUEUED]: {
    icon: '⏳',
    text: 'Queued',
    class: 'status-text--queued',
  },
  [FILE_STATUS.PROCESSING]: {
    icon: '⚙️',
    text: 'Processing...',
    class: 'status-text--processing',
  },
  [FILE_STATUS.COMPLETED]: {
    icon: '✅',
    text: 'Completed',
    class: 'status-text--completed',
  },
  [FILE_STATUS.FAILED]: {
    icon: '❌',
    text: 'Failed',
    class: 'status-text--failed',
  },
  [FILE_STATUS.CANCELLED]: {
    icon: '⏸️',
    text: 'Cancelled',
    class: 'status-text--pending',
  },
};

/**
 * File Manager Class
 */
class FileManager {
  constructor() {
    this.files = new Map(); // id -> fileEntry
    this.taskPollers = new Map(); // id -> intervalId
    this.availableLabels = new Set();
  }

  /**
   * Generate unique ID for file
   */
  generateId() {
    return `file_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Add files to manager
   */
  addFiles(fileList) {
    const newFiles = [];

    for (const file of fileList) {
      if (!this.isSupportedFile(file)) {
        continue;
      }

      const id = this.generateId();
      const fileEntry = {
        id,
        file,
        filename: file.name,
        size: file.size,
        type: this.inferFileType(file),
        labels: [],
        checked: false, // For checkbox selection
        status: FILE_STATUS.PENDING,
        uploadProgress: 0,
        taskId: null,
        taskStatus: null,
        result: null,
        error: null,
        createdAt: new Date(),
        uploadedAt: null,
        completedAt: null,
        xhr: null, // For cancelling upload
      };

      this.files.set(id, fileEntry);
      newFiles.push(fileEntry);
    }

    return newFiles;
  }

  /**
   * Check if file is supported
   */
  isSupportedFile(file) {
    const ext = this.getFileExtension(file.name);
    const allowed = new Set([
      '.mp4', '.jpg', '.jpeg', '.png', '.pdf', '.ppt', '.pptx',
      '.docx', '.doc', '.xlsx', '.xls', '.csv', '.txt',
      '.html', '.htm', '.xml', '.md'
    ]);
    return allowed.has(ext);
  }

  /**
   * Get file extension
   */
  getFileExtension(filename) {
    const lower = String(filename || '').toLowerCase();
    if (!lower.includes('.')) return '';
    return lower.slice(lower.lastIndexOf('.'));
  }

  /**
   * Infer file type from file object
   */
  inferFileType(file) {
    const type = (file?.type || '').toLowerCase();
    if (type.startsWith('video/')) return 'video';
    if (type.startsWith('image/')) return 'image';

    const ext = this.getFileExtension(file.name);
    if (ext === '.mp4') return 'video';
    if (['.jpg', '.jpeg', '.png'].includes(ext)) return 'image';
    return 'document';
  }

  /**
   * Format file size
   */
  formatSize(bytes) {
    if (!Number.isFinite(bytes) || bytes < 0) return '';
    const units = ['B', 'KB', 'MB', 'GB'];
    let value = bytes;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
      value /= 1024;
      unitIndex += 1;
    }
    const precision = value >= 10 || unitIndex === 0 ? 0 : 1;
    return `${value.toFixed(precision)} ${units[unitIndex]}`;
  }

  /**
   * Get file entry by ID
   */
  getFile(id) {
    return this.files.get(id);
  }

  /**
   * Update file entry
   */
  updateFile(id, updates) {
    const file = this.files.get(id);
    if (file) {
      Object.assign(file, updates);
      return file;
    }
    return null;
  }

  /**
   * Remove file from manager
   */
  removeFile(id) {
    // Stop polling if active
    this.stopPolling(id);

    // Cancel upload if in progress
    const file = this.files.get(id);
    if (file && file.xhr) {
      try {
        file.xhr.abort();
      } catch (e) {
        // Ignore
      }
    }

    this.files.delete(id);
  }

  /**
   * Get all files
   */
  getAllFiles() {
    return Array.from(this.files.values());
  }

  /**
   * Get files by status
   */
  getFilesByStatus(status) {
    return this.getAllFiles().filter(f => f.status === status);
  }

  /**
   * Get file counts by status
   */
  getStatusCounts() {
    const counts = {
      pending: 0,
      uploading: 0,
      queued: 0,
      processing: 0,
      completed: 0,
      failed: 0,
      cancelled: 0,
    };

    for (const file of this.files.values()) {
      counts[file.status] = (counts[file.status] || 0) + 1;
    }

    return counts;
  }

  /**
   * Toggle file checked state
   */
  toggleChecked(id) {
    const file = this.files.get(id);
    if (file) {
      file.checked = !file.checked;
      return file.checked;
    }
    return false;
  }

  /**
   * Set checked state for file
   */
  setChecked(id, checked) {
    const file = this.files.get(id);
    if (file) {
      file.checked = checked;
      return true;
    }
    return false;
  }

  /**
   * Get all checked files
   */
  getCheckedFiles() {
    return this.getAllFiles().filter(f => f.checked);
  }

  /**
   * Check/uncheck all files
   */
  setAllChecked(checked) {
    for (const file of this.files.values()) {
      file.checked = checked;
    }
  }

  /**
   * Add label to file
   */
  addLabel(id, label) {
    const file = this.files.get(id);
    if (file && label && !file.labels.includes(label)) {
      file.labels.push(label);
      this.availableLabels.add(label);
      return true;
    }
    return false;
  }

  /**
   * Add labels to checked files
   */
  addLabelsToChecked(labels) {
    const checkedFiles = this.getCheckedFiles();
    let updated = 0;

    for (const file of checkedFiles) {
      for (const label of labels) {
        if (label && !file.labels.includes(label)) {
          file.labels.push(label);
          this.availableLabels.add(label);
          updated++;
        }
      }
    }

    return updated;
  }

  /**
   * Remove label from file
   */
  removeLabel(id, label) {
    const file = this.files.get(id);
    if (file) {
      file.labels = file.labels.filter(l => l !== label);
      return true;
    }
    return false;
  }

  /**
   * Start polling task status
   */
  startPolling(id, taskId, onUpdate) {
    this.stopPolling(id);

    const intervalId = setInterval(async () => {
      try {
        const taskData = await this.queryTaskStatus(taskId);
        if (taskData && onUpdate) {
          onUpdate(taskData);
        }
      } catch (error) {
        console.error('Poll task failed:', error);
      }
    }, 2000);

    this.taskPollers.set(id, intervalId);
  }

  /**
   * Stop polling task status
   */
  stopPolling(id) {
    const intervalId = this.taskPollers.get(id);
    if (intervalId) {
      clearInterval(intervalId);
      this.taskPollers.delete(id);
    }
  }

  /**
   * Query task status from API
   */
  async queryTaskStatus(taskId) {
    try {
      const response = await fetch(`http://127.0.0.1:9011/api/v1/task/query/${taskId}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      if (data.code === 20000) {
        return data.data;
      }
      throw new Error(data.message || 'Query failed');
    } catch (error) {
      return null;
    }
  }

  /**
   * Clear all files by status
   */
  clearByStatus(status) {
    const toRemove = [];
    for (const [id, file] of this.files.entries()) {
      if (file.status === status) {
        toRemove.push(id);
      }
    }
    toRemove.forEach(id => this.removeFile(id));
    return toRemove.length;
  }
}

// Export for use in main app.js
window.FileManager = FileManager;
window.FILE_STATUS = FILE_STATUS;
window.STATUS_CONFIG = STATUS_CONFIG;
