/**
 * Content Search - Main Application (Search & Backend Health Check Only)
 * File upload functionality is handled by app_ui_renderer_v3.js and app_file_manager.js
 */

/**
 * Backend Status Checker
 * Checks if the backend API is reachable
 */
const API_BASE_URL = "http://127.0.0.1:9011";
window.API_BASE_URL = API_BASE_URL; // Export for other scripts
const HEALTH_CHECK_INTERVAL = 10000; // Check every 10 seconds
const HEALTH_CHECK_TIMEOUT = 3000; // 3 second timeout for health check

let healthCheckTimer = null;
let currentBackendStatus = "checking";

function updateBackendStatusUI(status, message) {
  const statusEl = el("backend-status");
  const textEl = el("backend-status-text");
  const retryBtn = el("backend-status-retry");

  // Remove all status classes
  statusEl.classList.remove("backend-status--online", "backend-status--offline", "backend-status--checking");

  // Add current status class
  statusEl.classList.add(`backend-status--${status}`);

  // Update text
  textEl.textContent = message;

  // Show/hide retry button
  retryBtn.hidden = status !== "offline";

  currentBackendStatus = status;
}

async function checkBackendHealth() {
  try {
    updateBackendStatusUI("checking", "Checking...");

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), HEALTH_CHECK_TIMEOUT);

    // Use dedicated health check endpoint
    const response = await fetch(`${API_BASE_URL}/api/v1/system/health`, {
      method: "GET",
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (response.ok) {
      const data = await response.json();

      // Check if backend and database are healthy
      if (data.status === "ok") {
        const dbStatus = data.services?.database;
        if (dbStatus === "healthy") {
          updateBackendStatusUI("online", "Online");
          return true;
        } else {
          updateBackendStatusUI("offline", "DB Error");
          console.warn("Database unhealthy:", dbStatus);
          return false;
        }
      } else {
        updateBackendStatusUI("offline", "Unhealthy");
        return false;
      }
    } else {
      updateBackendStatusUI("offline", `Error ${response.status}`);
      return false;
    }
  } catch (error) {
    if (error.name === "AbortError") {
      updateBackendStatusUI("offline", "Timeout");
    } else {
      updateBackendStatusUI("offline", "Offline");
    }
    return false;
  }
}

function startHealthCheck() {
  // Initial check
  checkBackendHealth();

  // Setup periodic check
  if (healthCheckTimer) {
    clearInterval(healthCheckTimer);
  }
  healthCheckTimer = setInterval(checkBackendHealth, HEALTH_CHECK_INTERVAL);
}

function stopHealthCheck() {
  if (healthCheckTimer) {
    clearInterval(healthCheckTimer);
    healthCheckTimer = null;
  }
}

/**
 * Business error codes mapping
 */
const ERROR_CODES = {
  20000: "SUCCESS",
  40000: "BAD_REQUEST",
  40001: "AUTH_FAILED",
  40901: "FILE_ALREADY_EXISTS",
  50001: "FILE_TYPE_ERROR",
  50002: "TASK_NOT_FOUND",
  50003: "PROCESS_FAILED",
};

/**
 * Get user-friendly error message based on business code
 */
function getErrorMessage(code, defaultMessage) {
  const errorMessages = {
    40000: "Bad request. Please check your input and try again.",
    40001: "Authentication failed. Invalid username or password.",
    40901: "File already exists. This file has been uploaded before.",
    50001: "Unsupported file format. Please check the file type.",
    50002: "Task not found. The task may have expired or been deleted.",
    50003: "Processing failed. An internal error occurred.",
  };

  return errorMessages[code] || defaultMessage || "An unknown error occurred.";
}

/**
 * Parse API response and throw error if business code indicates failure
 */
function parseApiResponse(data, defaultErrorMsg = "Operation failed") {
  if (!data) {
    throw new Error(defaultErrorMsg);
  }

  const code = data.code;

  if (code === 20000) {
    return data;
  }

  // Non-success code
  const errorType = ERROR_CODES[code] || "UNKNOWN_ERROR";
  const userMessage = getErrorMessage(code, data.message);
  const error = new Error(userMessage);
  error.code = code;
  error.errorType = errorType;
  error.originalMessage = data.message;

  throw error;
}

function el(id) {
  return document.getElementById(id);
}

function setStatus(target, message) {
  target.textContent = message || "";
}

function formatTimestamp(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function setupQueryImage() {
  const input = el("query-image");
  const preview = el("query-image-preview");
  const empty = el("query-image-preview-empty");
  const img = el("query-image-preview-img");
  const clearBtn = el("query-image-clear");

  let objectUrl = null;

  const clear = () => {
    input.value = "";
    empty.hidden = false;
    img.hidden = true;
    clearBtn.hidden = true;
    img.removeAttribute("src");
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    }
  };

  input.addEventListener("change", () => {
    const file = input.files?.[0];
    if (!file) {
      clear();
      return;
    }

    // Enforce .jpg for query image.
    const ext = fileExtension(file.name);
    const mime = String(file.type || "").toLowerCase();
    const isJpg = ext === ".jpg" || mime === "image/jpeg";
    if (!isJpg) {
      clear();
      return;
    }

    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(file);
    img.src = objectUrl;
    empty.hidden = true;
    img.hidden = false;
    clearBtn.hidden = false;
  });

  clearBtn.addEventListener("click", clear);

  return {
    getFile: () => input.files?.[0] || null,
    clear,
  };
}

function fileExtension(name) {
  const lower = String(name || "").toLowerCase();
  if (!lower.includes(".")) return "";
  return lower.slice(lower.lastIndexOf("."));
}

/**
 * Extract file_key from file_path for download API
 * file_path format: "local://content-search/runs/xxx/raw/video/default/test.mp4"
 * file_key format: "runs/xxx/raw/video/default/test.mp4"
 */
function extractFileKey(filePath) {
  if (!filePath) return null;
  // Remove protocol and bucket name
  return filePath.replace(/^[a-z]+:\/\/[^/]+\//, '');
}

/**
 * Open preview modal
 */
function openPreviewModal(result) {
  const modal = el("preview-modal");
  const title = el("preview-modal-title");
  const body = el("preview-modal-body");

  if (!modal || !title || !body) return;

  title.textContent = result.filename || "Preview";
  body.innerHTML = '<div class="preview-loading">Loading preview...</div>';

  // Show modal
  modal.hidden = false;
  document.body.style.overflow = "hidden";

  // Get file key for download
  const fileKey = extractFileKey(result.file_path);
  if (!fileKey) {
    body.innerHTML = '<div class="preview-error">Cannot preview this file (invalid path)</div>';
    return;
  }

  const downloadUrl = `${API_BASE_URL}/api/v1/object/download?file_key=${encodeURIComponent(fileKey)}`;

  // Render preview based on type
  setTimeout(() => {
    try {
      let content = '';

      // Info section
      content += '<div class="preview-info">';
      content += `<div class="preview-info__row"><span class="preview-info__label">Filename:</span><span class="preview-info__value">${result.filename}</span></div>`;
      content += `<div class="preview-info__row"><span class="preview-info__label">Type:</span><span class="preview-info__value">${result.type}</span></div>`;
      content += `<div class="preview-info__row"><span class="preview-info__label">Score:</span><span class="preview-info__value">${result.score}%</span></div>`;

      if (result.type === 'video' && result.timestamp) {
        content += `<div class="preview-info__row"><span class="preview-info__label">Match Time:</span><span class="preview-info__value">${result.timestamp}</span></div>`;
      } else if (result.type === 'document' && result.page) {
        content += `<div class="preview-info__row"><span class="preview-info__label">Page:</span><span class="preview-info__value">${result.page}</span></div>`;
      }

      content += '</div>';

      // Preview content based on type
      if (result.type === 'video') {
        const videoSrc = downloadUrl;
        const startTime = result.video_pin_second || 0;

        // Add hint if there's a specific timestamp
        if (startTime > 0) {
          content += `<div class="preview-hint">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style="margin-right: 4px;">
              <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" stroke-width="1.5"/>
              <path d="M8 4v4l3 2" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>
            </svg>
            Video will start at ${result.timestamp || formatTimestamp(Math.floor(startTime))} (matched scene)
          </div>`;
        }

        content += `<video class="preview-video" controls autoplay>
          <source src="${videoSrc}#t=${startTime}" type="video/mp4">
          Your browser does not support the video tag.
        </video>`;
      } else if (result.type === 'image') {
        content += `<img class="preview-image" src="${downloadUrl}" alt="${result.filename}">`;
      } else if (result.type === 'document') {
        if (result.subtype === 'pdf') {
          content += `<iframe class="preview-pdf" src="${downloadUrl}" type="application/pdf"></iframe>`;
        } else if (result.summary) {
          content += `<div class="preview-text">${result.summary}</div>`;
        } else {
          content += `<div class="preview-info">
            <p>Document preview not available. <a href="${downloadUrl}" download>Click here to download</a></p>
          </div>`;
        }
      }

      body.innerHTML = content;

      // If video, ensure we seek to the exact timestamp (multiple fallbacks)
      if (result.type === 'video' && result.video_pin_second) {
        const video = body.querySelector('video');
        if (video) {
          const targetTime = result.video_pin_second;

          // Method 1: Set on loadedmetadata (most reliable)
          video.addEventListener('loadedmetadata', () => {
            video.currentTime = targetTime;
          });

          // Method 2: Set on canplay (backup)
          video.addEventListener('canplay', () => {
            if (Math.abs(video.currentTime - targetTime) > 0.5) {
              video.currentTime = targetTime;
            }
          });

          // Method 3: Force set after a short delay (final fallback)
          setTimeout(() => {
            if (video.readyState >= 2 && Math.abs(video.currentTime - targetTime) > 0.5) {
              video.currentTime = targetTime;
            }
          }, 500);
        }
      }
    } catch (error) {
      body.innerHTML = `<div class="preview-error">Error loading preview: ${error.message}</div>`;
    }
  }, 100);
}

/**
 * Close preview modal
 */
function closePreviewModal() {
  const modal = el("preview-modal");
  const body = el("preview-modal-body");

  if (modal) {
    modal.hidden = true;
    document.body.style.overflow = "";
  }

  // Stop any playing media
  if (body) {
    const video = body.querySelector('video');
    if (video) {
      video.pause();
      video.src = "";
    }
    body.innerHTML = "";
  }
}

function renderResults(listEl, metaEl, results, metaText) {
  metaEl.textContent = metaText;
  listEl.innerHTML = "";
  results.forEach((r) => {
    const li = document.createElement("li");
    li.className = "result-card";

    // ── Header: filename · preview icon · score ──────────────────
    const header = document.createElement("div");
    header.className = "result-card__header";

    // Filename container with preview icon
    const filenameContainer = document.createElement("div");
    filenameContainer.className = "result-card__filename-container";

    const filename = document.createElement("h4");
    filename.className = "result-card__filename";
    filename.textContent = r.filename || r.title || "Unknown";
    filename.title = r.filename; // Show full name on hover

    // Preview icon button
    const previewIcon = document.createElement("button");
    previewIcon.className = "result-card__preview-icon";
    previewIcon.type = "button";
    previewIcon.title = "Preview";
    previewIcon.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="8" cy="8" r="3"/>
      <path d="M2 8s2-4 6-4 6 4 6 4-2 4-6 4-6-4-6-4z"/>
    </svg>`;
    previewIcon.addEventListener("click", (e) => {
      e.stopPropagation();
      openPreviewModal(r);
    });

    filenameContainer.appendChild(filename);
    filenameContainer.appendChild(previewIcon);

    const scoreEl = document.createElement("span");
    const sv = typeof r.score === "number" ? r.score : null;
    if (sv !== null) {
      scoreEl.className = "result-card__score" +
        (sv >= 85 ? " result-card__score--high" : sv >= 60 ? " result-card__score--mid" : " result-card__score--low");
      scoreEl.textContent = `Score: ${sv}%`;
    }

    header.append(filenameContainer, scoreEl);
    li.appendChild(header);

    // ── Metadata list ─────────────────────────────
    const detailsList = document.createElement("ul");
    detailsList.className = "result-card__details";

    // Page or timestamp information
    if (r.type === "document" && r.page) {
      const pageItem = document.createElement("li");
      pageItem.textContent = r.page;
      detailsList.appendChild(pageItem);
    } else if (r.type === "video") {
      if (r.timestamp) {
        const timeItem = document.createElement("li");
        timeItem.textContent = `Time: ${r.timestamp}`;
        detailsList.appendChild(timeItem);
      } else if (r.time_range) {
        const timeItem = document.createElement("li");
        timeItem.textContent = `Time: ${r.time_range}`;
        detailsList.appendChild(timeItem);
      }
    }

    // Labels
    if (r.labels && r.labels.length) {
      const labelsItem = document.createElement("li");
      labelsItem.className = "result-card__labels-item";

      const labelText = document.createElement("span");
      labelText.textContent = "Labels: ";
      labelText.style.marginRight = "8px";
      labelsItem.appendChild(labelText);

      r.labels.forEach((lbl) => {
        const chip = document.createElement("span");
        chip.className = "tag tag--sm";
        chip.textContent = lbl;
        labelsItem.appendChild(chip);
      });

      detailsList.appendChild(labelsItem);
    }

    if (detailsList.children.length > 0) {
      li.appendChild(detailsList);
    }

    listEl.appendChild(li);
  });
}

function clampIntegerInInput(inputEl, { min, max, fallback }) {
  const raw = String(inputEl.value ?? "").trim();
  // Allow user to temporarily clear the field while typing.
  if (raw === "") return;

  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed)) {
    inputEl.value = String(fallback);
    return;
  }

  const clamped = Math.max(min, Math.min(max, parsed));
  if (clamped !== parsed) inputEl.value = String(clamped);
}

function filterResultsByType(results, filterValue) {
  const value = String(filterValue || "all").toLowerCase();
  if (value === "all") return results;
  const allowed = new Set(["document", "image", "video"]);
  if (!allowed.has(value)) return results;
  return results.filter((r) => String(r?.type || "").toLowerCase() === value);
}

(function main() {
  // Note: File upload functionality is handled by app_ui_renderer_v3.js and app_file_manager.js
  // This file only handles search functionality and backend health check

  const searchStatus = el("search-status");
  const resultsMeta = el("results-meta");
  const resultsList = el("results-list");
  const resultsFilterEl = el("results-filter");

  /** @type {{ type?: string, title: string, meta: string }[]} */
  let lastResults = [];
  /** @type {string} */
  let lastResultsMetaText = "";

  // Global pool of all labels (populated from fileManager in app_ui_renderer_v3.js)
  const availableLabels = window.fileManagerUI?.fileManager?.availableLabels || new Set();
  const NO_LABEL_KEY = "__no_label__";
  const searchSelectedLabels = new Set();
  const labelDropdownBtn = el("label-dropdown-btn");
  const labelDropdownPanel = el("label-dropdown-panel");
  const labelDropdownList = el("label-dropdown-list");
  const labelDropdownSelectAllCb = el("label-dropdown-selectall");
  const labelSelectedChipsEl = el("label-selected-chips");

  const updateDropdownSummary = () => {
    // +1 accounts for the permanent "No Label" option
    const total = availableLabels.size + 1;
    const selected = searchSelectedLabels.size;
    const summaryEl = el("label-dropdown-summary");
    if (total === 1 && availableLabels.size === 0) {
      // Only the No Label option exists (no real labels uploaded yet)
      if (selected === 0) {
        summaryEl.textContent = "All Labels";
      } else {
        summaryEl.textContent = "No Label";
      }
    } else if (selected === 0 || selected === total) {
      summaryEl.textContent = "All Labels";
    } else {
      summaryEl.textContent = `${selected} of ${total} selected`;
    }
    labelDropdownBtn.disabled = false;
  };

  const makeDropdownItem = (key, displayText, isSpecial = false) => {
    const li = document.createElement("li");
    li.className = "label-dropdown__item" + (isSpecial ? " label-dropdown__item--special" : "");
    const cbId = `ldf-${key.replace(/[^a-zA-Z0-9]/g, "-")}`;
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = cbId;
    cb.className = "label-dropdown__cb";
    cb.checked = searchSelectedLabels.has(key);
    cb.addEventListener("change", () => {
      if (cb.checked) {
        searchSelectedLabels.add(key);
      } else {
        searchSelectedLabels.delete(key);
      }
      renderSearchLabelFilter();
    });
    const lbl = document.createElement("label");
    lbl.htmlFor = cbId;
    lbl.className = "label-dropdown__label";
    lbl.textContent = displayText;
    li.append(cb, lbl);
    return li;
  };

  const renderSearchLabelFilter = () => {
    labelDropdownList.innerHTML = "";
    const total = availableLabels.size + 1; // +1 for No Label
    const selected = searchSelectedLabels.size;
    labelDropdownSelectAllCb.checked = selected === total;
    labelDropdownSelectAllCb.indeterminate = selected > 0 && selected < total;

    // Always-present "No Label" item at the top
    labelDropdownList.appendChild(makeDropdownItem(NO_LABEL_KEY, "(No Label)", true));

    // Separator between special item and real labels
    if (availableLabels.size > 0) {
      const sep = document.createElement("li");
      sep.className = "label-dropdown__item-sep";
      sep.setAttribute("role", "separator");
      labelDropdownList.appendChild(sep);
    }

    availableLabels.forEach((label) => {
      labelDropdownList.appendChild(makeDropdownItem(label, label));
    });

    updateDropdownSummary();

    // Render selected chips below the dropdown
    labelSelectedChipsEl.innerHTML = "";
    if (searchSelectedLabels.size === 0) {
      labelSelectedChipsEl.hidden = true;
    } else {
      labelSelectedChipsEl.hidden = false;
      searchSelectedLabels.forEach((key) => {
        const chip = document.createElement("span");
        chip.className = "label-sel-chip";
        const text = document.createElement("span");
        text.textContent = key === NO_LABEL_KEY ? "(No Label)" : key;
        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "label-sel-chip__remove";
        removeBtn.setAttribute("aria-label", `Remove ${text.textContent}`);
        removeBtn.innerHTML = `<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;
        removeBtn.addEventListener("click", () => {
          searchSelectedLabels.delete(key);
          renderSearchLabelFilter();
        });
        chip.append(text, removeBtn);
        labelSelectedChipsEl.appendChild(chip);
      });
    }
  };

  // Toggle dropdown open/close
  labelDropdownBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = !labelDropdownPanel.hidden;
    labelDropdownPanel.hidden = isOpen;
    labelDropdownBtn.setAttribute("aria-expanded", String(!isOpen));
  });

  // Select All / Clear All
  labelDropdownSelectAllCb.addEventListener("change", () => {
    if (labelDropdownSelectAllCb.checked) {
      searchSelectedLabels.add(NO_LABEL_KEY);
      availableLabels.forEach((l) => searchSelectedLabels.add(l));
    } else {
      searchSelectedLabels.clear();
    }
    renderSearchLabelFilter();
  });

  // Close dropdown when clicking outside
  document.addEventListener("click", (e) => {
    if (!el("label-dropdown").contains(e.target)) {
      labelDropdownPanel.hidden = true;
      labelDropdownBtn.setAttribute("aria-expanded", "false");
    }
  });

  const queryImage = setupQueryImage();
  const queryTextEl = el("query-text");
  const queryImageEl = el("query-image");
  const modeTextBtn = el("mode-text");
  const modeImageBtn = el("mode-image");
  const queryTextWrap = el("query-text-wrap");
  const queryImageWrap = el("query-image-wrap");
  const topKEl = el("topk");

  /** @type {"text" | "image"} */
  let queryMode = "text";

  // Search type multi-select
  const typeDocEl = el("type-document");
  const typeImgEl = el("type-image");
  const typeVidEl = el("type-video");
  const typeDocLabel = typeDocEl?.closest("label");

  let docCheckedBeforeImageMode = true;

  const getSelectedTypes = () => {
    const selected = [];
    if (typeDocEl.checked) selected.push("document");
    if (typeImgEl.checked) selected.push("image");
    if (typeVidEl.checked) selected.push("video");
    return selected;
  };

  const enforceTypeRulesForMode = (mode) => {
    if (mode === "image") {
      // Image query: allow only image/video (document not supported).
      docCheckedBeforeImageMode = typeDocEl.checked;
      typeDocEl.checked = false;
      typeDocEl.disabled = true;
      typeDocLabel?.classList.add("is-disabled");
      typeDocLabel?.setAttribute("aria-disabled", "true");
    } else {
      typeDocEl.disabled = false;
      typeDocLabel?.classList.remove("is-disabled");
      typeDocLabel?.removeAttribute("aria-disabled");
      typeDocEl.checked = Boolean(docCheckedBeforeImageMode);
    }
  };

  const setQueryMode = (mode) => {
    queryMode = mode;

    const isText = mode === "text";
    modeTextBtn.classList.toggle("is-active", isText);
    modeImageBtn.classList.toggle("is-active", !isText);
    modeTextBtn.setAttribute("aria-selected", String(isText));
    modeImageBtn.setAttribute("aria-selected", String(!isText));

    queryTextWrap.classList.toggle("is-disabled", !isText);
    queryImageWrap.classList.toggle("is-disabled", isText);
    queryImageWrap.setAttribute("aria-disabled", String(isText));

    queryTextEl.disabled = !isText;
    queryImageEl.disabled = isText;

    if (isText) {
      queryImage.clear();
      queryTextEl.focus();
    } else {
      queryTextEl.value = "";
      queryTextEl.blur();
      queryImageEl.focus();
    }

    enforceTypeRulesForMode(mode);
  };

  // Query mode toggle makes the mutual exclusivity explicit.
  modeTextBtn.addEventListener("click", () => setQueryMode("text"));
  modeImageBtn.addEventListener("click", () => setQueryMode("image"));

  // Also allow clicking the panels to switch mode.
  queryTextWrap.addEventListener("click", () => setQueryMode("text"));
  queryImageWrap.addEventListener("click", () => setQueryMode("image"));

  // If user starts typing, switch to text mode.
  queryTextEl.addEventListener("input", () => {
    if ((queryTextEl.value || "").trim().length > 0 && queryMode !== "text") {
      setQueryMode("text");
    }
  });

  // If user picks an image, switch to image mode.
  queryImageEl.addEventListener("change", () => {
    const hasImage = Boolean(queryImage.getFile());
    if (hasImage && queryMode !== "image") {
      setQueryMode("image");
    }
  });

  // Keep TopK within 1..10 even when users type via keyboard.
  topKEl.addEventListener("input", () => {
    clampIntegerInInput(topKEl, { min: 1, max: 10, fallback: 10 });
  });
  topKEl.addEventListener("blur", () => {
    // On blur, force an empty value back to a safe default.
    if (String(topKEl.value ?? "").trim() === "") topKEl.value = "10";
    clampIntegerInInput(topKEl, { min: 1, max: 10, fallback: 10 });
  });

  const renderFilteredResults = () => {
    const filtered = filterResultsByType(lastResults, resultsFilterEl?.value);

    const filterLabel = String(resultsFilterEl?.value || "all").toLowerCase();
    const filterMeta = filterLabel === "all" ? "All" : filterLabel;
    const meta = lastResultsMetaText
      ? `${lastResultsMetaText} · Filter: ${filterMeta} · Showing: ${filtered.length}/${lastResults.length}`
      : "";

    renderResults(resultsList, resultsMeta, filtered, meta);
  };

  resultsFilterEl?.addEventListener("change", () => {
    renderFilteredResults();
  });

  /**
   * Perform text search via API
   */
  async function performTextSearch(query, maxResults, filter) {
    const requestBody = {
      query: query.trim(),
      max_num_results: maxResults,
    };

    if (Object.keys(filter).length > 0) {
      requestBody.filter = filter;
    }

    const response = await fetch(`${API_BASE_URL}/api/v1/object/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(errText || `HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    parseApiResponse(data, "Search failed");

    return (data.data?.results || []).map(mapApiResultToUi);
  }

  /**
   * Perform image search via API (Base64 encoded)
   */
  async function performImageSearch(imageFile, maxResults, filter) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = async () => {
        try {
          const base64 = reader.result.split(',')[1];

          const requestBody = {
            image_base64: base64,
            max_num_results: maxResults,
          };

          if (Object.keys(filter).length > 0) {
            requestBody.filter = filter;
          }

          const response = await fetch(`${API_BASE_URL}/api/v1/object/search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(requestBody),
          });

          if (!response.ok) {
            const errText = await response.text();
            throw new Error(errText || `HTTP ${response.status}: ${response.statusText}`);
          }

          const data = await response.json();
          parseApiResponse(data, "Image search failed");

          resolve((data.data?.results || []).map(mapApiResultToUi));
        } catch (error) {
          reject(error);
        }
      };

      reader.onerror = () => reject(new Error("Failed to read image file"));
      reader.readAsDataURL(imageFile);
    });
  }

  /**
   * Map API response to UI display format
   */
  function mapApiResultToUi(apiResult) {
    const meta = apiResult.meta || {};
    const type = meta.type || "document";

    // Use score directly from API response (already calculated as percentage)
    const scorePercent = Math.round(apiResult.score || 0);

    const result = {
      type: type,
      score: scorePercent,
      labels: meta.tags || [],
      // Use file_name if available, otherwise extract from file_path
      filename: meta.file_name || extractFilename(meta.file_path) || "Unknown",
      summary: meta.summary_text || meta.chunk_text || "",
      // Keep original data for preview
      file_path: meta.file_path,
      video_pin_second: meta.video_pin_second,
    };

    // Type-specific fields
    if (type === "video") {
      // Use video_pin_second for single timestamp
      if (meta.video_pin_second !== undefined) {
        result.timestamp = formatTimestamp(Math.floor(meta.video_pin_second));
      }
      // Support range if start_time and end_time exist
      if (meta.start_time !== undefined && meta.end_time !== undefined) {
        result.time_range = `${formatTimestamp(Math.floor(meta.start_time))} - ${formatTimestamp(Math.floor(meta.end_time))}`;
      }
    }

    if (type === "document") {
      // Check if it's a video summary
      if (meta.chunk_id || meta.chunk_text) {
        result.subtype = "video_summary";
        result.chunk_id = meta.chunk_id;
      } else if (meta.doc_filetype === "application/pdf" || meta.doc_page_number !== undefined) {
        result.subtype = "pdf";
        // Handle page information
        if (meta.doc_page_number !== undefined) {
          result.page = `Page: ${meta.doc_page_number}`;
        } else if (meta.page_range) {
          result.page = meta.page_range;
        }
      } else {
        result.subtype = "txt";
      }
    }

    if (type === "image") {
      // Add any image-specific metadata here
    }

    return result;
  }

  /**
   * Extract filename from file path
   */
  function extractFilename(filePath) {
    if (!filePath) return null;
    // Remove protocol prefix (local://, etc.)
    const path = filePath.replace(/^[a-z]+:\/\/[^/]+\//, '');
    // Get last part of path
    const parts = path.split('/');
    return parts[parts.length - 1];
  }

  el("btn-search").addEventListener("click", async () => {
    const selectedTypes = getSelectedTypes();
    const topK = Number.parseInt(topKEl.value, 10);
    const textQuery = el("query-text").value || "";
    const imageFile = queryImage.getFile();

    const hasText = queryMode === "text" && textQuery.trim().length > 0;
    const hasImage = queryMode === "image" && Boolean(imageFile);

    if (!hasText && !hasImage) {
      setStatus(searchStatus, queryMode === "text" ? "Enter text before searching." : "Choose an image before searching.");
      return;
    }

    if (selectedTypes.length === 0) {
      setStatus(searchStatus, "Select at least one search type (Documents/Image/Video).");
      return;
    }

    if (queryMode === "image" && selectedTypes.includes("document")) {
      setStatus(searchStatus, "Image query supports Image and Video types only.");
      return;
    }

    const safeTopK = Number.isFinite(topK) ? Math.max(1, Math.min(10, topK)) : 10;
    topKEl.value = String(safeTopK);

    // Build filter object
    const filter = {};
    if (selectedTypes.length > 0 && selectedTypes.length < 3) {
      filter.type = selectedTypes;
    }

    // Add label filter if labels are selected
    const chosenLabels = Array.from(searchSelectedLabels).filter((l) => l !== NO_LABEL_KEY);
    if (chosenLabels.length > 0 && chosenLabels.length < availableLabels.size) {
      filter.tags = chosenLabels;
    }

    setStatus(searchStatus, "Searching...");

    try {
      let results;

      if (hasImage) {
        // Image search - convert to Base64
        results = await performImageSearch(imageFile, safeTopK, filter);
      } else {
        // Text search
        results = await performTextSearch(textQuery, safeTopK, filter);
      }

      const typeLabel = selectedTypes.length === 3 ? "document, image, video" : selectedTypes.join(", ");
      const includesNoLabel = searchSelectedLabels.has(NO_LABEL_KEY);
      const labelParts = [...chosenLabels, ...(includesNoLabel ? ["(No Label)"] : [])];
      const labelNote = labelParts.length ? ` · Labels: [${labelParts.join(", ")}]` : "";
      setStatus(searchStatus, `Search completed: ${results.length} results found.`);

      lastResults = results;
      lastResultsMetaText = `Types: ${typeLabel} · TopK: ${safeTopK} · Mode: ${hasImage ? "image" : "text"}${labelNote}`;
      renderFilteredResults();
    } catch (error) {
      setStatus(searchStatus, `Search failed: ${error?.message || "Unknown error"}`);
      lastResults = [];
      lastResultsMetaText = "";
      renderFilteredResults();
    }
  });

  el("btn-reset").addEventListener("click", () => {
    searchSelectedLabels.clear();
    if (labelDropdownPanel) labelDropdownPanel.hidden = true;
    if (labelDropdownBtn) labelDropdownBtn.setAttribute("aria-expanded", "false");
    renderSearchLabelFilter();

    el("query-text").value = "";
    queryImage.clear();

    setQueryMode("text");

    typeDocEl.checked = true;
    typeImgEl.checked = true;
    typeVidEl.checked = true;
    el("topk").value = "4";

    setStatus(searchStatus, "");
    resultsMeta.textContent = "";
    resultsList.innerHTML = "";
    if (resultsFilterEl) resultsFilterEl.value = "all";
    lastResults = [];
    lastResultsMetaText = "";
  });

  // Initialize UI state
  setQueryMode("text");
  renderSearchLabelFilter();

  // Setup preview modal close handlers
  const previewModalClose = el("preview-modal-close");
  const previewModalOverlay = el("preview-modal-overlay");

  if (previewModalClose) {
    previewModalClose.addEventListener("click", closePreviewModal);
  }

  if (previewModalOverlay) {
    previewModalOverlay.addEventListener("click", closePreviewModal);
  }

  // Close modal on Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      const modal = el("preview-modal");
      if (modal && !modal.hidden) {
        closePreviewModal();
      }
    }
  });
})();

// Backend status retry button - moved outside IIFE to ensure it runs after DOM loads
(function initBackendStatus() {
  const retryBtn = el("backend-status-retry");
  if (retryBtn) {
    retryBtn.addEventListener("click", () => {
      checkBackendHealth();
    });
  }

  // Start backend health check
  startHealthCheck();
})();
