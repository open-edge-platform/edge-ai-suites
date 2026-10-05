/* SPDX-FileCopyrightText: (C) 2026 Intel Corporation */
/* SPDX-License-Identifier: Apache-2.0 */

(() => {
  const $ = (id) => document.getElementById(id);
  const prevBtn = $("prevBtn");
  const nextBtn = $("nextBtn");
  const refreshBtn = $("refreshTopBtn");
  const refreshSelect = $("refreshIntervalSelect");
  const explainBtn = $("explainBtn");
  const tableHead = $("tableHead");
  const tableBody = $("tableBody");
  const status = $("status");
  const explainOutput = $("explainOutput");
  const explainBody = $("explainBody");
  const state = {
    page: 1,
    hasMore: false,
    loading: false,
    explaining: false,
    timer: null,
    intervalMs: 10000,
    explanationId: 0,
  };

  function apiUrl(path, params) {
    const url = new URL(`/insights-ui${path}`, window.location.origin);
    Object.entries(params || {}).forEach(([key, value]) => url.searchParams.set(key, value));
    return url.toString();
  }

  function selectedTimes() {
    return [...tableBody.querySelectorAll('input[data-row-select="true"]:checked')]
      .map((checkbox) => JSON.parse(checkbox.dataset.rowJson).time)
      .filter(Boolean);
  }

  function updateControls() {
    const selection = selectedTimes().length > 0;
    prevBtn.disabled = state.loading || state.page <= 1;
    nextBtn.disabled = state.loading || !state.hasMore;
    refreshBtn.disabled = state.loading || selection;
    refreshSelect.disabled = state.loading || selection;
    explainBtn.disabled = state.loading || state.explaining || !selection;
  }

  function renderTable(rows) {
    tableHead.replaceChildren();
    tableBody.replaceChildren();
    $("emptyMessage").hidden = rows.length !== 0;

    if (!rows.length) {
      updateControls();
      return;
    }

    const columns = Object.keys(rows[0]);
    const header = document.createElement("tr");
    const selectHeader = document.createElement("th");
    selectHeader.textContent = "Select";
    header.appendChild(selectHeader);
    columns.forEach((column) => {
      const th = document.createElement("th");
      th.textContent = column;
      header.appendChild(th);
    });
    tableHead.appendChild(header);

    rows.forEach((row, index) => {
      const tr = document.createElement("tr");
      const selectTd = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.dataset.rowSelect = "true";
      checkbox.dataset.rowJson = JSON.stringify(row);
      checkbox.setAttribute("aria-label", `Select row ${index + 1}`);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          tableBody.querySelectorAll('input[data-row-select="true"]').forEach((other) => {
            if (other !== checkbox) other.checked = false;
          });
        }
        updateControls();
      });
      selectTd.appendChild(checkbox);
      tr.appendChild(selectTd);

      columns.forEach((column) => {
        const td = document.createElement("td");
        td.textContent = row[column] == null ? "" : String(row[column]);
        tr.appendChild(td);
      });
      tableBody.appendChild(tr);
    });
    updateControls();
  }

  async function loadPage() {
    if (state.loading) return;
    state.loading = true;
    updateControls();
    status.textContent = `Loading page ${state.page}...`;

    try {
      const response = await fetch(apiUrl("/api/data", { page: state.page }));
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Failed to load data");

      state.hasMore = payload.has_more;
      renderTable(payload.rows);
      $("pageInfo").textContent = `Page ${state.page}`;
      status.textContent = `Loaded ${payload.rows.length} rows.`;
    } catch (error) {
      state.hasMore = false;
      renderTable([]);
      status.textContent = error.message;
    } finally {
      state.loading = false;
      updateControls();
    }
  }

  function startAutoRefresh() {
    if (state.timer !== null) window.clearInterval(state.timer);
    state.timer = window.setInterval(() => {
      if (!state.loading && selectedTimes().length === 0) loadPage();
    }, state.intervalMs);
  }

  prevBtn.addEventListener("click", () => {
    if (state.page > 1) {
      state.page -= 1;
      loadPage();
    }
  });
  nextBtn.addEventListener("click", () => {
    if (state.hasMore) {
      state.page += 1;
      loadPage();
    }
  });
  refreshBtn.addEventListener("click", loadPage);
  refreshSelect.addEventListener("change", () => {
    state.intervalMs = (Number(refreshSelect.value) || 10) * 1000;
    startAutoRefresh();
    loadPage();
  });
  $("resetBtn").addEventListener("click", () => window.location.reload());

  function showEvidence(payload) {
    const image = payload.resolved_images?.[0];
    const telemetry = payload.ts_data?.[0];
    if (!image && !telemetry) return;

    const table = document.createElement("table");
    table.className = "data-display-table";
    const row = table.insertRow();
    const imageCell = row.insertCell();
    const imageUrl = image?.image_load_url || image?.image_url;
    if (imageUrl) {
      const img = document.createElement("img");
      img.src = imageUrl;
      img.alt = `Weld inspection at ${image.selected_time}`;
      imageCell.appendChild(img);
    }
    row.insertCell().textContent = telemetry || "No sensor data available.";
    explainBody.appendChild(table);
  }

  function showMarkdown(markdown, explanationId) {
    if (!markdown) {
      const empty = document.createElement("p");
      empty.textContent = "No explanation available.";
      explainBody.appendChild(empty);
      return;
    }

    markdown.split("\n").forEach((line, index) => {
      window.setTimeout(() => {
        if (explanationId !== state.explanationId) return;
        const div = document.createElement("div");
        div.style.opacity = "0";
        div.style.transition = "opacity 0.3s ease-in";
        if (window.marked && window.DOMPurify) {
          div.innerHTML = window.DOMPurify.sanitize(window.marked.parse(line || " "));
        } else {
          div.textContent = line;
        }
        explainBody.appendChild(div);
        window.requestAnimationFrame(() => { div.style.opacity = "1"; });
      }, index * 50);
    });
  }

  explainBtn.addEventListener("click", async () => {
    const times = selectedTimes();
    if (!times.length) return;

    state.explaining = true;
    state.explanationId += 1;
    updateControls();
    explainOutput.hidden = false;
    $("explainHeader").textContent = "AI Assistant Output";
    explainBody.innerHTML = '<span class="explain-spinner" aria-hidden="true"></span>Generating analysis...';
    status.textContent = "Generating explanation...";

    try {
      const response = await fetch(apiUrl("/api/explain"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_times: times }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Failed to generate explanation");

      $("explainHeader").textContent = payload.title || "AI Assistant Output";
      explainBody.replaceChildren();
      showEvidence(payload);
      showMarkdown(payload.markdown, state.explanationId);
      status.textContent = `Explanation generated for ${times.length} selected time value(s).`;
    } catch (error) {
      explainBody.textContent = error.message;
      status.textContent = error.message;
    } finally {
      state.explaining = false;
      updateControls();
    }
  });

  const phaseLabels = ["Starting vLLM server…", "Loading model…", "Initializing…"];
  let phase = 0;
  async function checkVllmReady() {
    try {
      const response = await fetch(apiUrl("/api/vllm/health"));
      if (response.ok && (await response.json()).accessible === true) {
        $("vllmOverlay").hidden = true;
        await loadPage();
        startAutoRefresh();
        return;
      }
    } catch (_) {
      // vLLM is still starting; try again shortly.
    }
    phase = (phase + 1) % phaseLabels.length;
    $("vllmLabel").textContent = phaseLabels[phase];
    window.setTimeout(checkVllmReady, 30000);
  }

  updateControls();
  checkVllmReady();
})();