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

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const precision = value >= 10 || unitIndex === 0 ? 0 : 1;
  return `${value.toFixed(precision)} ${units[unitIndex]}`;
}

function el(id) {
  return document.getElementById(id);
}

function setStatus(target, message) {
  target.textContent = message || "";
}

function withDropzone(fileInput, dropzone, onFilesPicked) {
  const stop = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };

  const handleDrop = (event) => {
    stop(event);
    dropzone.classList.remove("is-dragover");
    const files = Array.from(event.dataTransfer?.files || []);
    if (files.length) onFilesPicked(files);
  };

  const handlePick = () => {
    const files = Array.from(fileInput.files || []);
    onFilesPicked(files);
  };

  ["dragenter", "dragover"].forEach((type) => {
    dropzone.addEventListener(type, (event) => {
      stop(event);
      dropzone.classList.add("is-dragover");
    });
  });

  ["dragleave", "drop"].forEach((type) => {
    dropzone.addEventListener(type, (event) => {
      stop(event);
      dropzone.classList.remove("is-dragover");
    });
  });

  dropzone.addEventListener("drop", handleDrop);
  fileInput.addEventListener("change", handlePick);
}

function fileExtension(name) {
  const lower = String(name || "").toLowerCase();
  if (!lower.includes(".")) return "";
  return lower.slice(lower.lastIndexOf("."));
}

function isSupportedUploadFile(file) {
  const ext = fileExtension(file?.name);
  const allowed = new Set([".mp4", ".jpg", ".pdf", ".ppt", ".docx", ".csv", ".txt"]);
  return allowed.has(ext);
}

/**
 * @param {{ inputId: string, listId: string, onSelectionChange?: () => void }} opts
 */
function createFileListController({ inputId, listId, onSelectionChange }) {
  const input = el(inputId);
  const list = el(listId);
  const container = input.closest(".dropzone");
  const toolbarEl = el("filelist-toolbar");
  const selectAllCb = el("selectall-check");
  const toolbarCount = el("filelist-toolbar-count");

  /**
   * @type {{ file: File, labels: string[], checked: boolean }[]}
   */
  let entries = [];
  let showValidation = false;

  const notify = () => {
    if (typeof onSelectionChange === "function") onSelectionChange();
  };

  const syncToolbar = () => {
    const total = entries.length;
    const checked = entries.filter((e) => e.checked).length;
    toolbarEl.hidden = total === 0;
    if (total === 0) return;
    toolbarCount.textContent = checked > 0 ? `${checked} of ${total} selected` : `${total} file${total > 1 ? "s" : ""}`;
    if (checked === 0) {
      selectAllCb.checked = false;
      selectAllCb.indeterminate = false;
    } else if (checked === total) {
      selectAllCb.checked = true;
      selectAllCb.indeterminate = false;
    } else {
      selectAllCb.checked = false;
      selectAllCb.indeterminate = true;
    }
  };

  const render = () => {
    list.innerHTML = "";
    syncToolbar();
    entries.forEach((entry, index) => {
      const li = document.createElement("li");
      if (entry.checked) li.classList.add("is-checked");

      // ── Checkbox ──────────────────────────────────────────────
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "filelist__check";
      cb.checked = entry.checked;
      cb.setAttribute("aria-label", `Select ${entry.file.name}`);
      cb.addEventListener("change", () => {
        entries[index].checked = cb.checked;
        li.classList.toggle("is-checked", cb.checked);
        notify();
      });

      // ── Body: name row + label chips row ─────────────────────
      const body = document.createElement("div");
      body.className = "filelist__body";

      const nameEl = document.createElement("div");
      nameEl.className = "filelist__name";
      nameEl.textContent = `${entry.file.name} · ${formatBytes(entry.file.size)}`;
      body.appendChild(nameEl);

      if (entry.labels.length) {
        const tagsEl = document.createElement("div");
        tagsEl.className = "filelist__tags";
        entry.labels.forEach((label, labelIndex) => {
          const chip = document.createElement("span");
          chip.className = "tag tag--sm";

          const text = document.createElement("span");
          text.textContent = label;

          const del = document.createElement("button");
          del.type = "button";
          del.className = "tag__remove";
          del.setAttribute("aria-label", `Remove label ${label}`);
          del.textContent = "\u00d7";
          del.addEventListener("click", (e) => {
            e.stopPropagation();
            entries[index].labels.splice(labelIndex, 1);
            render();
          });

          chip.appendChild(text);
          chip.appendChild(del);
          tagsEl.appendChild(chip);
        });
        body.appendChild(tagsEl);
      }

      // ── Remove button ─────────────────────────────────────────
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "filelist__remove";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => {
        entries = entries.filter((_, i) => i !== index);
        render();
        notify();
      });

      li.appendChild(cb);
      li.appendChild(body);
      li.appendChild(remove);
      list.appendChild(li);
    });

    notify();
  };

  // Select-all checkbox handler
  selectAllCb.addEventListener("change", () => {
    const shouldCheck = selectAllCb.checked;
    entries.forEach((e) => { e.checked = shouldCheck; });
    render();
  });

  const addFiles = (picked) => {
    const next = picked.filter((f) => f && typeof f.name === "string");
    if (!next.length) return;

    const supported = next.filter(isSupportedUploadFile);
    if (!supported.length) {
      input.value = "";
      return;
    }

    const key = (f) => `${f.name}::${f.size}::${f.lastModified}`;
    const existing = new Set(entries.map((e) => key(e.file)));
    const deduped = supported.filter((f) => !existing.has(key(f)));

    entries = [...entries, ...deduped.map((f) => ({ file: f, labels: [], checked: false }))];
    render();

    input.value = "";
  };

  withDropzone(input, container, addFiles);

  return {
    /** Returns all entries with their associated labels */
    getFiles: () => entries.map((e) => ({ file: e.file, labels: [...e.labels] })),
    /** Returns the total number of files */
    getFileCount: () => entries.length,
    /** How many files are currently checked */
    getCheckedCount: () => entries.filter((e) => e.checked).length,
    /**
     * Attach a label to every currently-checked file.
     * Returns true if at least one file was updated.
     */
    addLabelToChecked: (rawLabel) => {
      const label = String(rawLabel || "").trim();
      if (!label) return false;
      let changed = false;
      entries.forEach((e) => {
        if (e.checked && !e.labels.includes(label)) {
          e.labels.push(label);
          changed = true;
        }
      });
      if (changed) render();
      return changed;
    },
    /** Marks all unlabeled files as invalid and re-renders. Returns count of files missing labels. */
    markInvalid: () => {
      showValidation = true;
      render();
      return entries.filter((e) => e.labels.length === 0).length;
    },
    /** Returns the union of all labels across all files */
    getAllLabels: () => {
      const set = new Set();
      entries.forEach((e) => e.labels.forEach((l) => set.add(l)));
      return Array.from(set);
    },
    clear: () => {
      entries = [];
      showValidation = false;
      render();
      input.value = "";
    },
  };
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

function inferUploadKind(file) {
  const type = (file?.type || "").toLowerCase();
  if (type === "video/mp4") return "video";
  if (type === "image/jpeg") return "image";

  const name = (file?.name || "").toLowerCase();
  const ext = fileExtension(name);
  if (ext === ".mp4") return "video";
  if (ext === ".jpg") return "image";
  const docExts = new Set([".pdf", ".ppt", ".docx", ".csv", ".txt"]);
  if (docExts.has(ext)) return "document";

  // Default to document for unknown types since most non-media uploads are docs.
  return "document";
}

function uploadCounts(files) {
  const counts = { video: 0, image: 0, document: 0 };
  files.forEach((f) => {
    const kind = inferUploadKind(f);
    counts[kind] += 1;
  });
  return counts;
}

function fakeUploadSummary(files) {
  if (!files.length) return "No files selected";
  const { video, image, document } = uploadCounts(files);
  const parts = [];
  if (video) parts.push(`Video: ${video}`);
  if (image) parts.push(`Image: ${image}`);
  if (document) parts.push(`Documents: ${document}`);
  return parts.join(" · ");
}

function formatTimestamp(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function fakeSearchResults({ types, topK, textQuery, hasImageQuery }) {
  const mode = hasImageQuery ? "image" : "text";
  const query = hasImageQuery ? "(image)" : textQuery.trim() || "(empty)";
  const normalized = Array.isArray(types) && types.length ? types : ["document", "image", "video"];
  const unique = Array.from(new Set(normalized));
  const displayTypes = unique.length ? unique : ["document", "image", "video"];
  const count = Math.max(1, Math.min(10, topK));

  const sampleLabels = [
    ["Math", "Grade1"], ["Lily"], ["Science", "Grade2"], [], ["History"], ["Grade1", "Lily"],
  ];
  const docSubtypes = ["pdf", "txt", "video_summary"];

  return Array.from({ length: count }, (_, i) => {
    const rank = i + 1;
    const t = displayTypes[i % displayTypes.length];
    const score = Math.max(0.01, Math.min(1, +(0.97 - i * 0.06 + (((rank * 17) % 7) * 0.005)).toFixed(3)));
    const labels = sampleLabels[i % sampleLabels.length];
    const base = { type: t, rank, score, labels, meta: `${mode} query: ${query}` };

    if (t === "video") {
      const startSec = i * 47 + 8;
      const endSec = startSec + 24 + i * 6;
      return { ...base, filename: `lecture_clip_${String(rank).padStart(2, "0")}.mp4`,
        start_time: formatTimestamp(startSec), end_time: formatTimestamp(endSec) };
    }
    if (t === "image") {
      return { ...base, filename: `image_${String(rank).padStart(3, "0")}.jpg` };
    }
    // document — alternate subtypes
    const subtype = docSubtypes[i % docSubtypes.length];
    if (subtype === "pdf") {
      const p = rank * 3 - 2;
      return { ...base, subtype: "pdf", filename: `document_${rank}.pdf`, page_range: `pp. ${p}–${p + 3}` };
    }
    if (subtype === "video_summary") {
      return { ...base, subtype: "video_summary", filename: `summary_${rank}.txt`,
        chunk_id: `chunk_${String(rank * 7).padStart(4, "0")}` };
    }
    return { ...base, subtype: "txt", filename: `notes_${rank}.txt` };
  });
}

function renderResults(listEl, metaEl, results, metaText) {
  metaEl.textContent = metaText;
  listEl.innerHTML = "";
  results.forEach((r) => {
    const li = document.createElement("li");
    li.className = "result-card";

    // ── Header: type badge · filename · score ──────────────────
    const header = document.createElement("div");
    header.className = "result-card__header";

    const typeBadge = document.createElement("span");
    const subtypeLabel = r.subtype ? ` / ${r.subtype.replace("_", " ")}` : "";
    typeBadge.className = `result-card__type result-card__type--${r.type}`;
    typeBadge.textContent = `${r.type}${subtypeLabel}`;

    const filename = document.createElement("span");
    filename.className = "result-card__filename";
    filename.textContent = r.filename || r.title || "—";

    const scoreEl = document.createElement("span");
    const sv = typeof r.score === "number" ? r.score : null;
    if (sv !== null) {
      scoreEl.className = "result-card__score" +
        (sv >= 0.85 ? " result-card__score--high" : sv >= 0.60 ? " result-card__score--mid" : " result-card__score--low");
      scoreEl.textContent = `Score\u00a0${sv.toFixed(3)}`;
    }

    header.append(typeBadge, filename, scoreEl);
    li.appendChild(header);

    // ── Type-specific metadata row ─────────────────────────────
    const metaItems = [];
    if (r.start_time !== undefined) metaItems.push(`Start: ${r.start_time}`);
    if (r.end_time !== undefined)   metaItems.push(`End: ${r.end_time}`);
    if (r.page_range)               metaItems.push(`Pages: ${r.page_range}`);
    if (r.chunk_id)                 metaItems.push(`Chunk ID: ${r.chunk_id}`);
    if (metaItems.length) {
      const metaRow = document.createElement("div");
      metaRow.className = "result-card__meta";
      metaItems.forEach((text, idx) => {
        if (idx > 0) {
          const sep = document.createElement("span");
          sep.className = "result-card__meta-sep";
          sep.textContent = "·";
          metaRow.appendChild(sep);
        }
        const span = document.createElement("span");
        span.textContent = text;
        metaRow.appendChild(span);
      });
      li.appendChild(metaRow);
    }

    // ── Labels row ─────────────────────────────────────────────
    if (r.labels && r.labels.length) {
      const labelsRow = document.createElement("div");
      labelsRow.className = "result-card__labels";
      r.labels.forEach((lbl) => {
        const chip = document.createElement("span");
        chip.className = "tag tag--sm";
        chip.textContent = lbl;
        labelsRow.appendChild(chip);
      });
      li.appendChild(labelsRow);
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
  const uploadStatus = el("upload-status");
  const searchStatus = el("search-status");
  const resultsMeta = el("results-meta");
  const resultsList = el("results-list");
  const resultsFilterEl = el("results-filter");
  const uploadStateEl = el("upload-state");
  const indexingSpinnerEl = el("indexing-spinner");
  const indexingStateTextEl = el("indexing-state-text");
  const asyncHintEl = el("async-hint");

  /** @type {ReturnType<typeof setTimeout> | null} */
  let indexingTimer = null;

  /** @type {{ type?: string, title: string, meta: string }[]} */
  let lastResults = [];
  /** @type {string} */
  let lastResultsMetaText = "";

  const setPipelineState = ({ uploadState, indexingState, showHint }) => {
    if (typeof uploadState === "string") uploadStateEl.textContent = uploadState;
    if (typeof indexingState === "string") indexingStateTextEl.textContent = indexingState;

    const inProgress = indexingState === "Indexing in progress…";
    indexingSpinnerEl.hidden = !inProgress;
    asyncHintEl.hidden = !showHint;
  };

  // ── Label assignment panel ─────────────────────────────────────
  const labelAssignEl = el("label-assign");
  const labelAssignHintEl = el("label-assign-hint");
  const labelInputEl = el("label-input");

  // Global pool of all labels ever committed (shown in search filter)
  /** @type {Set<string>} */
  const availableLabels = new Set();
  /** @type {Set<string>} */
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

  const onSelectionChange = () => {
    const total = uploads.getFileCount();
    const count = uploads.getCheckedCount();
    // Show panel whenever there are files; hide when list is empty
    labelAssignEl.hidden = total === 0;
    const idleEl = el("label-assign-idle");
    const inputRowEl = labelInputEl.closest(".label-input-row");
    if (count > 0) {
      // Active: files are selected, show input
      labelAssignEl.classList.remove("is-idle");
      labelAssignHintEl.textContent = `${count} file${count > 1 ? "s" : ""} selected`;
      labelInputEl.disabled = false;
      el("btn-add-label").disabled = false;
      if (idleEl) idleEl.hidden = true;
      if (inputRowEl) inputRowEl.hidden = false;
    } else {
      // Idle: files exist but none checked
      labelAssignEl.classList.add("is-idle");
      labelAssignHintEl.textContent = "";
      labelInputEl.disabled = true;
      el("btn-add-label").disabled = true;
      if (idleEl) idleEl.hidden = false;
      if (inputRowEl) inputRowEl.hidden = true;
    }
  };

  const uploads = createFileListController({
    inputId: "upload-files",
    listId: "list-files",
    onSelectionChange,
  });

  // Add labels to checked files — each non-empty line is a separate label
  const doAddLabel = () => {
    const lines = labelInputEl.value.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!lines.length) return;
    lines.forEach((label) => uploads.addLabelToChecked(label));
    labelInputEl.value = "";
    labelInputEl.focus();
  };
  el("btn-add-label").addEventListener("click", doAddLabel);

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
      // Keep focus in the active control for clarity.
      queryTextEl.focus();
    } else {
      queryTextEl.value = "";
      queryTextEl.blur();
      queryImageEl.focus();
    }

    enforceTypeRulesForMode(mode);
  };

  /**
   * Poll task status
   */
  async function pollTaskStatus(taskId) {
    try {
      const response = await fetch(`http://127.0.0.1:9011/api/v1/task/query/${taskId}`, {
        method: "GET",
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      parseApiResponse(data, "Query task failed");

      return data.data;
    } catch (error) {
      console.error("Poll task failed:", error);

      // Handle specific error codes
      if (error.code === 50002) {
        // Task not found - might have expired
        setStatus(uploadStatus, "Task not found. It may have expired.");
        if (indexingTimer) {
          clearInterval(indexingTimer);
          indexingTimer = null;
        }
        setPipelineState({ indexingState: "Idle", showHint: false });
      }

      return null;
    }
  }

  /**
   * Start polling a task until it completes or fails
   */
  function startTaskPolling(taskId) {
    if (indexingTimer) {
      clearInterval(indexingTimer);
      indexingTimer = null;
    }

    // Poll every 2 seconds
    indexingTimer = setInterval(async () => {
      const taskData = await pollTaskStatus(taskId);

      if (!taskData) {
        return;
      }

      const status = taskData.status;

      if (status === "PENDING") {
        setPipelineState({ indexingState: "Pending...", showHint: true });
      } else if (status === "QUEUED") {
        setPipelineState({ indexingState: "Queued...", showHint: true });
      } else if (status === "PROCESSING") {
        // Note: progress field is not yet implemented in backend, always shows 100%
        // So we just show "Processing..." without percentage
        setPipelineState({ indexingState: "Processing...", showHint: true });
      } else if (status === "COMPLETED") {
        clearInterval(indexingTimer);
        indexingTimer = null;
        setPipelineState({ indexingState: "Completed", showHint: false });

        // Show success message with summary if available
        const summary = taskData.result?.video_summary;
        let successMsg = "Upload and indexing completed successfully!";
        if (summary) {
          const chunks = summary.total_chunks || 0;
          const elapsed = Math.round(summary.elapsed_seconds || 0);
          successMsg += ` (${chunks} chunk${chunks > 1 ? 's' : ''} processed in ${elapsed}s)`;
        }
        setStatus(uploadStatus, successMsg);

        // Clear file list after successful completion
        setTimeout(() => {
          uploads.clear();
        }, 3000);
      } else if (status === "FAILED") {
        clearInterval(indexingTimer);
        indexingTimer = null;
        setPipelineState({ indexingState: "Failed", showHint: false });
        const errorMsg = taskData.result?.message || "Indexing failed";
        setStatus(uploadStatus, `Indexing failed: ${errorMsg}`);
      }
    }, 2000);
  }

  el("btn-upload").addEventListener("click", async () => {
    const entries = uploads.getFiles();
    const files = entries.map((e) => e.file);

    if (!files.length) {
      if (indexingTimer) { clearInterval(indexingTimer); indexingTimer = null; }
      setPipelineState({ uploadState: "Idle", indexingState: "Idle", showHint: false });
      setStatus(uploadStatus, "");
      return;
    }

    const summary = fakeUploadSummary(files);
    setStatus(uploadStatus, `Uploading: ${summary}…`);
    if (indexingTimer) { clearInterval(indexingTimer); indexingTimer = null; }
    setPipelineState({ uploadState: "Uploading…", indexingState: "Queued", showHint: true });

    // Build FormData - upload each file with its labels as meta
    const formData = new FormData();

    entries.forEach((entry) => {
      formData.append("file", entry.file);

      // Add labels as meta if present
      if (entry.labels.length > 0) {
        const meta = JSON.stringify({ tags: entry.labels });
        formData.append("meta", meta);
      }
    });

    try {
      const response = await fetch("http://127.0.0.1:9011/api/v1/object/upload-ingest", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || `HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      parseApiResponse(data, "Upload failed");

      // Commit all labels from uploaded files into available pool
      entries.forEach((e) => e.labels.forEach((l) => availableLabels.add(l)));
      renderSearchLabelFilter();

      const allLabels = uploads.getAllLabels();
      const labelNote = allLabels.length ? ` · Labels: [${allLabels.join(", ")}]` : "";
      const taskId = data?.data?.task_id || data?.task_id;
      const taskNote = taskId ? ` · Task: ${taskId}` : "";
      setStatus(uploadStatus, `Upload success${taskNote}${labelNote}`);

      setPipelineState({ uploadState: "Uploaded", indexingState: "Processing", showHint: true });

      // Start polling task status
      if (taskId) {
        startTaskPolling(taskId);
      } else {
        // No task ID returned, simulate completion
        setTimeout(() => {
          setPipelineState({ indexingState: "Completed", showHint: false });
        }, 3000);
      }
    } catch (error) {
      // Show user-friendly error message based on error code
      let errorMsg = error?.message || "Unknown error";

      // Add specific hints for common errors
      if (error.code === 50001) {
        errorMsg += " Supported formats: .mp4, .jpg, .png, .pdf, .docx, .txt, .html, .md";
      } else if (error.code === 40901) {
        errorMsg += " Try uploading a different file.";
      }

      setStatus(uploadStatus, `Upload failed: ${errorMsg}`);
      setPipelineState({ uploadState: "Failed", indexingState: "Idle", showHint: false });
    }
  });

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

    const response = await fetch("http://127.0.0.1:9011/api/v1/object/search", {
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

          const response = await fetch("http://127.0.0.1:9011/api/v1/object/search", {
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
    const distance = apiResult.distance || 0;

    // Convert distance to similarity score (lower distance = higher similarity)
    // Assuming distance is in range [0, 2], convert to score [0, 1]
    const score = Math.max(0, Math.min(1, 1 - distance / 2));

    const result = {
      type: type,
      score: score,
      labels: meta.tags || [],
      filename: meta.asset_id || meta.file_path || "Unknown",
    };

    // Type-specific fields
    if (type === "video" || (meta.start_time !== undefined && meta.end_time !== undefined)) {
      result.start_time = formatTimestamp(Math.floor(meta.start_time || 0));
      result.end_time = formatTimestamp(Math.floor(meta.end_time || 0));
    }

    if (type === "document") {
      // Check if it's a video summary
      if (meta.chunk_id || meta.chunk_text) {
        result.subtype = "video_summary";
        result.chunk_id = meta.chunk_id;
      } else if (meta.doc_filetype === "application/pdf") {
        result.subtype = "pdf";
        if (meta.page_range) {
          result.page_range = meta.page_range;
        }
      } else {
        result.subtype = "txt";
      }
    }

    return result;
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
    uploads.clear();
    labelInputEl.value = "";
    labelAssignEl.hidden = true;
    searchSelectedLabels.clear();
    labelDropdownPanel.hidden = true;
    labelDropdownBtn.setAttribute("aria-expanded", "false");
    renderSearchLabelFilter();

    el("query-text").value = "";
    queryImage.clear();

    setQueryMode("text");

    typeDocEl.checked = true;
    typeImgEl.checked = true;
    typeVidEl.checked = true;
    el("topk").value = "4";

    setStatus(uploadStatus, "");
    setStatus(searchStatus, "");
    resultsMeta.textContent = "";
    resultsList.innerHTML = "";
    if (resultsFilterEl) resultsFilterEl.value = "all";
    lastResults = [];
    lastResultsMetaText = "";

    if (indexingTimer) {
      clearTimeout(indexingTimer);
      indexingTimer = null;
    }
    setPipelineState({ uploadState: "Idle", indexingState: "Idle", showHint: false });
  });

  // Initialize UI state
  setQueryMode("text");
  setPipelineState({ uploadState: "Idle", indexingState: "Idle", showHint: false });
  renderSearchLabelFilter();
})();
