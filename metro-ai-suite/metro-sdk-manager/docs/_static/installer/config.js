// Self-contained, no fetch: CONFIG is embedded here.
const CONFIG = {
  title: "Install Selector",
  shareKeys: [
    "VERSION", 
    "OP_SYSTEM", 
    "SDK"
  ],
  
  categories: [
    {
      key: "OP_SYSTEM",
      label: "Operating System",
      type: "single",
      options: [
        { 
          label: "Ubuntu", 
          value: "UBUNTU" 
        }
      ]
    },
    {
      key: "SDK",
      label: "SDK",
      type: "single",
      options: [
        { 
          label: "Metro Vision AI SDK", 
          value: "METRO_VISION" 
        },
        { 
          label: "Metro Gen AI SDK", 
          value: "METRO_GENAI" 
        },
        { 
          label: "Visual AI Demo Kit", 
          value: "VISUAL_AI_DEMO" 
        }
      ]
    },
    {
      key: "VERSION",
      label: "Version",
      type: "single",
      options: [
        { 
          label: "2025.2", 
          value: "2025.2" 
        }
      ]
    }
  ],
  outputs: [
    {
      id: "components",
      label: "Installed Components",
      fallback: "Select options to see installed components…",
      rules: [
        { 
          when: { 
            SDK: "METRO_VISION",
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          components: [
            "DLStreamer",
            "DLStreamer Pipeline Server",
            "OpenVINO",
            "OpenVINO Model Server",
            "Edge AI Libraries - Repo",
            "Edge AI Suites - Repo"
          ]
        },
        { 
          when: { 
            SDK: "METRO_GENAI", 
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          components: [
            "Audio Analyzer Microservice",
            "Document Ingestion (pgvector)",
            "Multimodal Embedding Serving",
            "Visual Data Preparation For Retrieval",
            "VLM OpenVINO Serving",
            "Edge AI Libraries - Repo",
            "Edge AI Suites - Repo"
          ]
        },
        { 
          when: { 
            SDK: "VISUAL_AI_DEMO",
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          components: [
            "DLStreamer Pipeline Server",
            "Node Red",
            "Grafana",
            "MediaMTX",
            "MQTT Broker",
            "Edge AI Suites - Repo"
          ]
        }
      ]
    },
    {
      id: "install",
      label: "Install",
      fallback: "Select options to see a command…",
      rules: [
        { 
          when: { 
            SDK: "METRO_VISION",
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          text: `curl https://raw.githubusercontent.com/open-edge-platform/edge-ai-suites/refs/heads/main/metro-ai-suite/metro-sdk-manager/scripts/metro-vision-ai-sdk.sh | bash`
        },
        
        { 
          when: { 
            SDK: "METRO_GENAI", 
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          text: `curl https://raw.githubusercontent.com/open-edge-platform/edge-ai-suites/refs/heads/main/metro-ai-suite/metro-sdk-manager/scripts/metro-gen-ai-sdk.sh | bash`
        },

        { 
          when: { 
            SDK: "VISUAL_AI_DEMO",
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          text: `curl https://raw.githubusercontent.com/open-edge-platform/edge-ai-suites/refs/heads/main/metro-ai-suite/metro-sdk-manager/scripts/visual-ai-demo-kit.sh | bash`
        }
      ]
    },
    {
      id: "nextsteps",
      label: "Next Steps",
      fallback: "Select options to see next steps…",
      rules: [
        { 
          when: { 
            SDK: "METRO_VISION", 
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          text: `Get Started`,
          link: `../../user-guide/metro-vision-ai-sdk/get-started.html`
        },
        { 
          when: { 
            SDK: "METRO_GENAI", 
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          text: `Get Started`,
          link: `../../user-guide/metro-gen-ai-sdk/get-started.html`
        },
        { 
          when: { 
            SDK: "VISUAL_AI_DEMO", 
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          text: `Get Started`,
          link: `../../user-guide/visual-ai-demo-kit/get-started.html`
        }
      ]
    },
    {
      id: "resources",
      label: "Resources",
      fallback: "Select options to see resources…",
      rules: [
        { 
          when: { 
            SDK: "METRO_VISION", 
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          links: [
            { text: "DLStreamer", url: "http://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dl-streamer/index.html" },
            { text: "DLStreamer Pipeline Server", url: "https://docs.openedgeplatform.intel.com/edge-ai-libraries/dlstreamer-pipeline-server/main/user-guide/Overview.html" },
            { text: "OpenVINO", url: "https://docs.openvino.ai/2025/get-started.html" },
            { text: "OpenVINO Model Server", url: "https://docs.openvino.ai/2025/model-server/ovms_what_is_openvino_model_server.html" },
            { text: "Edge AI Libraries", url: "https://docs.openedgeplatform.intel.com/dev/ai-libraries.html"},
            { text: "Edge AI Suites", url: "https://docs.openedgeplatform.intel.com/dev/ai-suite-metro.html"}
          ]
        },
        { 
          when: { 
            SDK: "METRO_GENAI", 
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          links: [
            { text: "Audio Analyzer", url: "https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/audio-analyzer/index.html" },
            { text: "Document Ingestion - pgvector", url: "https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/document-ingestion/pgvector/docs/get-started.md" },
            { text: "Multimodal Embedding Serving", url: "https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/multimodal-embedding-serving/docs/user-guide/Overview.md" },
            { text: "Visual Data Preparation For Retrieval", url: "https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/visual-data-preparation-for-retrieval/vdms/docs/user-guide/Overview.md" },
            { text: "VLM OpenVINO Serving", url: "https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/vlm-openvino-serving/docs/user-guide/Overview.md" },
            { text: "Edge AI Libraries", url: "https://docs.openedgeplatform.intel.com/dev/ai-libraries.html"},
            { text: "Edge AI Suites", url: "https://docs.openedgeplatform.intel.com/dev/ai-suite-metro.html"}
          ]
        },
        { 
          when: { 
            SDK: "VISUAL_AI_DEMO", 
            OP_SYSTEM: "UBUNTU",
            VERSION: "2025.2" 
          }, 
          links: [
            { text: "DLStreamer", url: "http://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dl-streamer/index.html" },
            { text: "DLStreamer Pipeline Server", url: "https://docs.openedgeplatform.intel.com/edge-ai-libraries/dlstreamer-pipeline-server/main/user-guide/Overview.html" },
            { text: "Edge AI Libraries", url: "https://docs.openedgeplatform.intel.com/dev/ai-libraries.html"},
            { text: "Edge AI Suites", url: "https://docs.openedgeplatform.intel.com/dev/ai-suite-metro.html"}
          ]
        }
      ]
    }
  ]
};

// --- small helpers ---
const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls, txt) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (txt != null) n.textContent = txt;
  return n;
};

const parseQuery = (keys) => {
  const qs = new URLSearchParams(location.search);
  const out = {};
  for (const k of keys) {
    const v = qs.get(k);
    if (v) out[k] = v;
  }
  return out;
};

const writeQuery = (state, keys) => {
  const qs = new URLSearchParams();
  keys.forEach((k) => {
    const v = state[k];
    if (v != null && v !== "") qs.set(k, String(v));
  });
  const q = `?${qs.toString()}`;
  history.replaceState({}, "", q);
  return location.origin + location.pathname + q;
};

// {{KEY}} or {{KEY|dotver}}
const interpolate = (text, sel) =>
  text.replace(/\{\{\s*([A-Z0-9_]+)(?:\|([a-z]+))?\s*\}\}/g, (_, key, filter) => {
    let v = sel[key] ?? "";
    if (filter === "dotver") v = v.startsWith("v_") ? v.slice(2).replaceAll("_", ".") : v;
    return String(v);
  });

const firstMatch = (rules, sel) => {
  for (const r of rules || []) {
    const cond = r.when || {};
    const ok = Object.keys(cond).every((k) => String(sel[k] ?? "") === String(cond[k]));
    if (ok) return r;
  }
  return null;
};

// --- UI rendering ---
let STATE = {};

function init() {
  $("#app-title").textContent = CONFIG.title || "Selector";

  // defaults: first option per category
  const defaults = {};
  (CONFIG.categories || []).forEach((cat) => {
    const first = cat.options?.[0]?.value;
    if (first != null) defaults[cat.key] = first;
  });

  // state from URL (shareable)
  STATE = { ...defaults, ...parseQuery(CONFIG.shareKeys || []) };

  renderCategories();
  updateOutputsAndUrl();
  hookCopyButtons();
}

function renderCategories() {
  const host = $("#categories");
  host.innerHTML = "";

  (CONFIG.categories || []).forEach((cat) => {
    const sec = el("section", "st-section st-section-accent");
    const title = el("div", "st-section-title", cat.label);
    const content = el("div", "st-section-content");
    const row = el("div", "st-section-content-row");

    const group = el("div", "spark-button-group option-button-group");
    (cat.options || []).forEach((opt) => {
      const btn = el("button", "spark-button spark-button-size-l spark-button-ghost");
      const inner = el("span", "spark-button-content");
      inner.append(el("span", "", opt.label));
      if (opt.subtitle) inner.append(el("span", "subtitle", opt.subtitle));
      btn.append(inner);

      const isActive = STATE[cat.key] === opt.value;
      if (isActive) btn.classList.add("spark-toggle-button-clicked-ghost", "pill-active");

      btn.addEventListener("click", () => {
        STATE[cat.key] = opt.value;
        // update selected visuals
        Array.from(group.children).forEach((b) =>
          b.classList.remove("spark-toggle-button-clicked-ghost", "pill-active")
        );
        btn.classList.add("spark-toggle-button-clicked-ghost", "pill-active");
        updateOutputsAndUrl();
      });

      group.append(btn);
    });

    row.append(group);
    content.append(row);
    sec.append(title, content);
    host.append(sec);
  });
}

function updateOutputsAndUrl() {
  // keep URL in sync
  const shareUrl = writeQuery(STATE, CONFIG.shareKeys || []);

  // compute outputs
  (CONFIG.outputs || []).forEach((o) => {
    const matched = firstMatch(o.rules, STATE);
    
    if (o.id === "components") {
      const container = $("#componentsText");
      if (matched?.components && Array.isArray(matched.components)) {
        container.innerHTML = "";
        
        // Create a compact list container
        const list = document.createElement("ul");
        list.style.margin = "0.5rem 0 0 0";
        list.style.padding = "0";
        list.style.listStyle = "none";
        list.style.display = "flex";
        list.style.flexWrap = "wrap";
        list.style.gap = "0.5rem";
        
        matched.components.forEach((component) => {
          // Create small component badge
          const listItem = document.createElement("li");
          listItem.style.display = "inline-flex";
          listItem.style.alignItems = "center";
          listItem.style.padding = "0.25rem 0.5rem";
          listItem.style.backgroundColor = "var(--spark-color-theme-light-gray100, #f8f9fa)";
          listItem.style.border = "1px solid var(--spark-color-theme-light-gray300, #dee2e6)";
          listItem.style.borderRadius = "0.25rem";
          listItem.style.fontSize = "0.75rem";
          listItem.style.fontWeight = "500";
          listItem.style.color = "var(--spark-color-theme-light-gray700, #495057)";
          listItem.style.whiteSpace = "nowrap";
          
          // Add small checkmark icon
          const icon = document.createElement("span");
          icon.innerHTML = "✓";
          icon.style.color = "#28a745";
          icon.style.fontWeight = "bold";
          icon.style.marginRight = "0.375rem";
          icon.style.fontSize = "0.75rem";
          
          // Add component text
          const text = document.createElement("span");
          text.textContent = component;
          
          listItem.appendChild(icon);
          listItem.appendChild(text);
          list.appendChild(listItem);
        });
        
        container.appendChild(list);
      } else {
        container.textContent = o.fallback ?? "";
      }
    }
    
    if (o.id === "install") {
      const finalText = matched?.text ? interpolate(String(matched.text), STATE) : (o.fallback ?? "");
      $("#installText").textContent = finalText;
    }
    
    if (o.id === "nextsteps") {
      const container = $("#nextStepsText");
      if (matched?.text && matched?.link) {
        const link = document.createElement("a");
        link.href = matched.link;
        link.target = "_blank";
        link.className = "spark-hyperlink spark-hyperlink-primary";
        link.textContent = matched.text;
        container.innerHTML = "";
        container.appendChild(link);
      } else {
        container.textContent = o.fallback ?? "";
      }
    }
    
    if (o.id === "resources") {
      const container = $("#resourcesText");
      if (matched?.links && Array.isArray(matched.links)) {
        container.innerHTML = "";
        matched.links.forEach((linkObj, index) => {
          const link = document.createElement("a");
          link.href = linkObj.url;
          link.target = "_blank";
          link.className = "spark-hyperlink spark-hyperlink-primary";
          link.textContent = linkObj.text;
          container.appendChild(link);
          if (index < matched.links.length - 1) {
            container.appendChild(document.createElement("br"));
          }
        });
      } else {
        container.textContent = o.fallback ?? "";
      }
    }
  });
}

function copyToClipboard(text) {
  // Try modern clipboard API first if available and in secure context
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text).catch(err => {
      console.warn('Clipboard API failed, falling back to legacy method:', err);
      return copyToClipboardFallback(text);
    });
  }
  
  // Fallback for older browsers or non-secure contexts
  return copyToClipboardFallback(text);
}

function copyToClipboardFallback(text) {
  return new Promise((resolve, reject) => {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    
    // Ensure the textarea is visible and properly positioned
    textArea.style.position = 'absolute';
    textArea.style.left = '0';
    textArea.style.top = '0';
    textArea.style.opacity = '0';
    textArea.style.pointerEvents = 'none';
    textArea.style.zIndex = '-1';
    
    // Make it readable
    textArea.setAttribute('readonly', '');
    textArea.style.border = 'none';
    textArea.style.outline = 'none';
    textArea.style.boxShadow = 'none';
    textArea.style.background = 'transparent';
    
    document.body.appendChild(textArea);
    
    try {
      // Focus and select
      textArea.focus();
      textArea.select();
      textArea.setSelectionRange(0, textArea.value.length);
      
      // Try execCommand
      const successful = document.execCommand('copy');
      document.body.removeChild(textArea);
      
      if (successful) {
        resolve();
      } else {
        reject(new Error('Copy failed'));
      }
    } catch (err) {
      document.body.removeChild(textArea);
      reject(err);
    }
  });
}



function hookCopyButtons() {
  const copyCmd = $("#copyCmd");
  if (copyCmd) {
    copyCmd.addEventListener("click", async () => {
    const text = $("#installText").textContent.trim();
    if (!text || text === "Select options to see a command…") {
      alert("No command to copy. Please select your options first.");
      return;
    }
    
    const btn = $("#copyCmd");
    
    try {
      btn.disabled = true;
      await copyToClipboard(text);
      btn.disabled = false;
      flashCopied("#copyCmd");
    } catch (err) { 
      console.error('Copy failed:', err);
      btn.disabled = false;
      alert("Copy failed. Please try manually selecting the text and pressing Ctrl+C (or Cmd+C on Mac).");
    }
    });
  }






}

function flashCopied(sel) {
  const btn = document.querySelector(sel);
  if (!btn) return; // Guard against missing elements
  
  const old = btn.textContent;
  btn.textContent = "Copied!";
  setTimeout(() => {
    // Only reset if the button text hasn't changed (to avoid conflicts)
    if (btn.textContent === "Copied!") {
      btn.textContent = old;
    }
  }, 900);
}

document.addEventListener("DOMContentLoaded", init);
