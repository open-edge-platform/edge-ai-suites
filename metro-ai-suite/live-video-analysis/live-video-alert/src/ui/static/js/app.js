/**
 * Agentic Alert NVR Dashboard
 */

const timestamp = document.getElementById('timestamp');
const streamCount = document.getElementById('stream-count');

let activeStreams = [];
let cardStates = {};
let agentConfig = [];
let resultsCache = {};

let eventSource = null;
let pollingInterval = null;
let sseConnected = false;

function cssSafeId(str) {
    return str.replace(/[^a-zA-Z0-9-_]/g, '_');
}

function showToast(message, type = 'info') {
    const existing = document.getElementById('toast-notification');
    if (existing) existing.remove();
    
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        info: 'bg-blue-500'
    };
    
    const toast = document.createElement('div');
    toast.id = 'toast-notification';
    toast.className = `fixed bottom-4 right-4 ${colors[type] || colors.info} text-white px-4 py-2 rounded-lg shadow-lg z-50 text-sm font-medium`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

document.addEventListener('DOMContentLoaded', async () => {
    await loadAgentConfig();
    await loadStreams();
    
    initSSE();
    
    initResizer();
    
    window.addEventListener('beforeunload', () => {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
    });
});

function initSSE() {
    if (eventSource) {
        eventSource.close();
    }
    
    console.log('[SSE] Connecting to /events...');
    eventSource = new EventSource('/events');
    
    eventSource.onopen = () => {
        console.log('[SSE] Connected successfully');
        sseConnected = true;
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
            console.log('[SSE] Stopped polling - using SSE');
        }
    };
    
    eventSource.addEventListener('init', (e) => {
        try {
            const data = JSON.parse(e.data);
            console.log('[SSE] Received init:', data.streams?.length, 'streams');
            
            if (data.streams && JSON.stringify(data.streams.sort()) !== JSON.stringify(activeStreams.sort())) {
                activeStreams = data.streams;
                streamCount.textContent = activeStreams.length;
                renderGrid();
                renderStreamList();
            }
            
            if (data.results) {
                updateAllResults(data.results);
            }
        } catch (err) {
            console.error('[SSE] Init parse error:', err);
        }
    });
    
    eventSource.addEventListener('analysis', (e) => {
        try {
            const data = JSON.parse(e.data);
            const { stream_id, results } = data;
            
            timestamp.textContent = new Date().toLocaleTimeString();
            updateStreamResult(stream_id, results);
        } catch (err) {
            console.error('[SSE] Analysis parse error:', err);
        }
    });
    
    eventSource.addEventListener('keepalive', () => {
        console.log('[SSE] Keepalive received');
    });
    
    eventSource.onerror = (e) => {
        console.error('[SSE] Connection error');
        sseConnected = false;
        
        if (eventSource.readyState === EventSource.CLOSED) {
            console.log('[SSE] Connection closed, falling back to polling');
            eventSource.close();
            eventSource = null;
            startPollingFallback();
        }
    };
}

function startPollingFallback() {
    if (pollingInterval) return;
    console.log('[Polling] Starting fallback polling...');
    pollingInterval = setInterval(fetchData, 1000);
}

function updateStreamResult(streamId, results) {
    resultsCache[streamId] = results;
    
    const safeId = cssSafeId(streamId);
    const resultDiv = document.getElementById(`result-${safeId}`);
    if (!resultDiv) return;
    
    const selectedAgent = cardStates[streamId];
    renderResultDiv(resultDiv, selectedAgent, results);
}

function refreshAllResults() {
    activeStreams.forEach(id => {
        const safeId = cssSafeId(id);
        const resultDiv = document.getElementById(`result-${safeId}`);
        if (!resultDiv) return;
        
        const selectedAgent = cardStates[id];
        const cachedData = resultsCache[id];
        renderResultDiv(resultDiv, selectedAgent, cachedData);
    });
}

function updateAllResults(allResults) {
    timestamp.textContent = new Date().toLocaleTimeString();
    
    activeStreams.forEach(id => {
        const streamData = allResults[id];
        if (streamData) {
            updateStreamResult(id, streamData);
        }
    });
}

function renderResultDiv(resultDiv, selectedAgent, streamData) {
    if (!streamData) {
        resultDiv.innerHTML = '<p class="text-xs text-gray-400 italic">Waiting for analysis...</p>';
        return;
    }
    
    const enabledAgentNames = agentConfig.filter(a => a.enabled).map(a => a.name);
    
    if (selectedAgent === '__ALL__') {
        if (enabledAgentNames.length === 0) {
            resultDiv.innerHTML = '<p class="text-xs text-gray-400 italic">No alerts enabled</p>';
            return;
        }
        let allHtml = '';
        enabledAgentNames.forEach(agentName => {
            const result = streamData[agentName];
            if (result && result.answer) {
                allHtml += renderResultCard(result, agentName);
            }
        });
        resultDiv.innerHTML = allHtml || '<p class="text-xs text-gray-400 italic">Waiting for analysis...</p>';
    } else if (selectedAgent && streamData[selectedAgent] && enabledAgentNames.includes(selectedAgent)) {
        resultDiv.innerHTML = renderResultCard(streamData[selectedAgent], selectedAgent);
    } else {
        resultDiv.innerHTML = '<p class="text-xs text-gray-400 italic">Waiting for analysis...</p>';
    }
}

function renderResultCard(result, agentName) {
    const isYes = result.answer === 'YES';
    const bgClass = isYes ? 'bg-red-50 border-red-300' : 'bg-green-50 border-green-300';
    const textClass = isYes ? 'text-red-800' : 'text-green-800';
    const badgeClass = isYes ? 'bg-red-200 text-red-800' : 'bg-green-200 text-green-800';
    const icon = isYes ? '⚠️' : '✓';
    
    return `
        <div class="rounded border p-2 ${bgClass} transition-colors duration-300">
            <div class="flex justify-between items-center mb-1">
                <span class="font-bold text-xs uppercase ${textClass}">${icon} ${result.answer}</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded font-medium ${badgeClass}">${escapeHtml(agentName)}</span>
            </div>
            <p class="text-xs ${textClass} opacity-80 leading-tight">${escapeHtml(result.reason || 'No details')}</p>
        </div>
    `;
}

// ============== RESIZER LOGIC ==============
function initResizer() {
    const sidebar = document.getElementById('sidebar');
    const resizer = document.getElementById('resizer');
    const container = document.getElementById('main-container');
    let isResizing = false;

    resizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        document.body.style.cursor = 'col-resize';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        const containerRect = container.getBoundingClientRect();
        const newWidth = e.clientX - containerRect.left;
        if (newWidth > 200 && newWidth < containerRect.width * 0.5) {
            sidebar.style.width = `${newWidth}px`;
        }
    });

    document.addEventListener('mouseup', () => {
        isResizing = false;
        document.body.style.cursor = 'default';
    });
}

async function loadAgentConfig() {
    try {
        const res = await fetch('/config/agents');
        agentConfig = await res.json();
        renderAgentConfig();
    } catch(e) { 
        console.error("Failed to load agent config:", e);
        agentConfig = [];
        renderAgentConfig();
    }
}

function renderAgentConfig() {
    const container = document.getElementById('agents-container');
    const addBtn = document.getElementById('add-agent-btn');
    container.innerHTML = '';
    
    agentConfig.forEach((agent, index) => {
        const card = document.createElement('div');
        card.className = "bg-white border border-slate-200 rounded-lg p-3 shadow-sm hover:shadow-md transition-all group relative";
        card.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                     <input type="checkbox" 
                       class="w-3.5 h-3.5 rounded border-slate-300 text-blue-600 focus:ring-offset-0 focus:ring-1 focus:ring-blue-500 cursor-pointer" 
                       ${agent.enabled ? 'checked' : ''} 
                       onchange="toggleAgent(${index}, this.checked)">
                     <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Alert ${index + 1}</span>
                </div>
                <button onclick="removeAgent(${index})" class="text-slate-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100" title="Remove Alert">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="space-y-2">
                <input type="text" 
                       value="${escapeHtml(agent.name)}" 
                       class="w-full text-xs font-semibold text-slate-700 bg-slate-100 border-0 rounded px-2.5 py-1.5 focus:bg-white focus:ring-2 focus:ring-blue-500/20 placeholder:text-slate-400 transition-all outline-none"
                       placeholder="Alert Name"
                       onchange="updateAgentName(${index}, this.value)">
                <textarea class="w-full text-[11px] text-slate-600 bg-slate-100 border-0 rounded px-2.5 py-1.5 resize-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 placeholder:text-slate-400 transition-all outline-none leading-relaxed" 
                          rows="2" 
                          placeholder="Describe visual condition (e.g., Is there fire?)"
                          onchange="updateAgentPrompt(${index}, this.value)">${escapeHtml(agent.prompt)}</textarea>
            </div>
        `;
        container.appendChild(card);
    });
    
    addBtn.style.display = agentConfig.length >= 4 ? 'none' : 'flex';
    
    updateAllDropdowns();
    refreshAllResults();
}

function addAgent() {
    if (agentConfig.length >= 4) return;
    let num = 1;
    while (agentConfig.some(a => a.name === `Alert ${num}`)) {
        num++;
    }
    agentConfig.push({
        name: `Alert ${num}`,
        prompt: "",
        enabled: true
    });
    renderAgentConfig();
}

function removeAgent(index) {
    const name = agentConfig[index]?.name || `Alert ${index + 1}`;
    agentConfig.splice(index, 1);
    renderAgentConfig();
    showToast(`Removed ${name}`, "info");
}

function toggleAgent(index, enabled) {
    agentConfig[index].enabled = enabled;
    updateAllDropdowns();
    refreshAllResults();
}

function updateAgentName(index, name) {
    agentConfig[index].name = name;
    updateAllDropdowns();
}

function updateAgentPrompt(index, prompt) {
    agentConfig[index].prompt = prompt;
}

async function saveAgents() {
    const valid = agentConfig.every(a => a.name.trim() && a.prompt.trim());
    if (!valid && agentConfig.length > 0) {
        showToast("Please fill in all alert names and prompts", "error");
        return;
    }
    
    const names = agentConfig.map(a => a.name.trim().toLowerCase());
    if (new Set(names).size !== names.length) {
        showToast("Alert names must be unique", "error");
        return;
    }
    
    try {
        const res = await fetch('/config/agents', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(agentConfig)
        });
        if (res.ok) {
            showToast("Alerts saved!", "success");
        } else {
            showToast("Failed to save alerts", "error");
        }
    } catch(e) {
        console.error(e);
        showToast("Failed to save alerts", "error");
    }
}

function updateAllDropdowns() {
    const enabledAgents = agentConfig.filter(a => a.enabled);
    let optionsHtml = '<option value="__ALL__">All Alerts</option>';
    optionsHtml += enabledAgents.length > 0
        ? enabledAgents.map(a => `<option value="${escapeHtml(a.name)}">${escapeHtml(a.name)}</option>`).join('')
        : '';
    
    activeStreams.forEach(id => {
        const safeId = cssSafeId(id);
        const select = document.querySelector(`#card-${safeId} select`);
        if (select) {
            const currentVal = select.value;
            select.innerHTML = optionsHtml;
            if (currentVal === '__ALL__') {
                select.value = '__ALL__';
                cardStates[id] = '__ALL__';
            } else if (enabledAgents.some(a => a.name === currentVal)) {
                select.value = currentVal;
            } else {
                select.value = '__ALL__';
                cardStates[id] = '__ALL__';
            }
        }
    });
}

async function loadStreams() {
    try {
        const res = await fetch('/streams');
        const data = await res.json();
        activeStreams = data.streams || [];
        streamCount.textContent = activeStreams.length;
        renderGrid();
        renderStreamList();
    } catch(e) { console.error("Error loading streams", e); }
}

function renderStreamList() {
    const list = document.getElementById('stream-list');
    if (!list) return;
    list.innerHTML = '';
    if (activeStreams.length === 0) {
        list.innerHTML = '<li class="text-xs text-gray-400 italic">No streams active.</li>';
        return;
    }
    activeStreams.forEach(id => {
        const li = document.createElement('li');
        li.className = "flex justify-between items-center text-xs text-slate-600 bg-white p-2.5 rounded-md border border-slate-200 shadow-sm hover:border-blue-300 transition-all group";
        li.innerHTML = `
            <div class="flex items-center gap-2 overflow-hidden">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 shadow-[0_0_4px_rgba(16,185,129,0.4)]"></span>
                <span class="font-semibold truncate" title="${escapeHtml(id)}">${escapeHtml(id)}</span>
            </div>
            <button onclick="deleteStream('${escapeHtml(id)}')" class="text-slate-300 hover:text-red-500 transition p-1 opacity-0 group-hover:opacity-100" title="Delete Stream">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
        `;
        list.appendChild(li);
    });
}

async function deleteStream(id) {
    // Optimistic UI update - remove immediately
    const idx = activeStreams.indexOf(id);
    if (idx > -1) {
        activeStreams.splice(idx, 1);
        streamCount.textContent = activeStreams.length;
        renderGrid();
        renderStreamList();
    }
    
    try {
        const res = await fetch(`/streams/${id}`, { method: 'DELETE' });
        if(res.ok) {
            showToast(`Deleted stream '${id}'`, "success");
        } else {
            // Revert on failure
            await loadStreams();
            showToast("Failed to delete stream", "error");
        }
    } catch(e) { 
        console.error(e);
        await loadStreams();
        showToast("Error deleting stream", "error"); 
    }
}

async function addNewStream() {
    if (activeStreams.length >= 3) {
        showToast("Limit reached. Delete an existing stream first", "error");
        return;
    }

    const id = document.getElementById('inp-stream-id').value.trim();
    const url = document.getElementById('inp-stream-url').value.trim();
    if(!id || !url) {
        showToast("Please enter both ID and URL", "error");
        return;
    }
    
    try {
        const res = await fetch('/streams', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id, url})
        });
        if(res.ok) {
            document.getElementById('inp-stream-id').value = '';
            document.getElementById('inp-stream-url').value = '';
            await loadStreams();
            showToast(`Added stream '${id}'`, "success");
        } else {
            showToast("Failed to add stream", "error");
        }
    } catch(e) { 
        console.error(e);
        showToast("Error adding stream", "error"); 
    }
}

function updateCardAgent(streamId, agentName) {
    cardStates[streamId] = agentName;
}

// ============== VIDEO GRID RENDERING ==============
function renderGrid() {
    const grid = document.getElementById('video-grid');
    
    // Re-render check shortcut (compare CSS-safe IDs)
    const existingIds = Array.from(grid.children).map(c => c.id.replace('card-', ''));
    const currentSafeIds = activeStreams.map(id => cssSafeId(id));
    const sameStreams = currentSafeIds.length === existingIds.length && currentSafeIds.every(id => existingIds.includes(id));
    if (sameStreams) {
        // Even if not re-rendering, update dropdowns
        updateAllDropdowns();
        return;
    }

    grid.innerHTML = '';
    
    if (activeStreams.length === 0) {
        grid.innerHTML = '<div class="col-span-2 text-gray-400 text-center mt-10">No active streams. Add one from the sidebar.</div>';
        return;
    }

    // Get enabled agents for dropdown
    const enabledAgents = agentConfig.filter(a => a.enabled);

    activeStreams.forEach(id => {
        // Default state - default to "All Agents"
        if (!cardStates[id]) {
            cardStates[id] = '__ALL__';
        }
        
        const safeId = cssSafeId(id);

        // Card Container
        const card = document.createElement('div');
        card.id = `card-${safeId}`;
        card.className = "bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden flex flex-col h-full";
        
        // Header (with Title + Live Badge)
        const header = document.createElement('div');
        header.className = "px-4 py-2 bg-gray-50 border-b border-gray-100 flex justify-between items-center";
        header.innerHTML = `<span class="font-bold text-gray-700 text-sm overflow-hidden text-ellipsis whitespace-nowrap mr-2" title="${escapeHtml(id)}">${escapeHtml(id)}</span><span class="text-xs text-green-600 font-mono shrink-0">LIVE</span>`;

        // Video Wrapper
        const videoWrapper = document.createElement('div');
        videoWrapper.className = "relative bg-black w-full aspect-video flex items-center justify-center";
        
        const img = document.createElement('img');
        img.src = `/video_feed?stream_id=${encodeURIComponent(id)}`;
        img.className = "w-full h-full object-contain";
        img.alt = id;
        videoWrapper.appendChild(img);

        // Control Bar (Agent Selector)
        const controlBar = document.createElement('div');
        controlBar.className = "px-2 py-2 bg-gray-50 border-b border-gray-100 flex items-center";
        const select = document.createElement('select');
        select.className = "w-full text-xs p-1 border border-gray-300 rounded bg-white focus:outline-none";
        
        // Build dropdown options from dynamic agents
        let selectOptions = '<option value="__ALL__">All Alerts</option>';
        if (enabledAgents.length > 0) {
            selectOptions += enabledAgents.map(a => `<option value="${escapeHtml(a.name)}">${escapeHtml(a.name)}</option>`).join('');
        }
        select.innerHTML = selectOptions;
        
        if (cardStates[id]) select.value = cardStates[id];
        select.onchange = (e) => updateCardAgent(id, e.target.value);
        controlBar.appendChild(select);

        // Results Area
        const stats = document.createElement('div');
        stats.id = `result-${safeId}`;
        stats.className = "flex-1 overflow-y-auto p-2 bg-white flex flex-col gap-2 min-h-[100px]";
        stats.innerHTML = '<p class="text-xs text-gray-400 italic">Waiting for analysis...</p>';

        card.appendChild(header);
        card.appendChild(videoWrapper);
        card.appendChild(controlBar);
        card.appendChild(stats);
        grid.appendChild(card);
    });
}

async function fetchData() {
    try {
        const response = await fetch('/data');
        const json = await response.json();

        timestamp.textContent = new Date().toLocaleTimeString();

        // Update each stream's result area using the shared render function
        activeStreams.forEach(id => {
            const safeId = cssSafeId(id);
            const resultDiv = document.getElementById(`result-${safeId}`);
            if (!resultDiv) return;
            
            const selectedAgent = cardStates[id];
            const streamData = json[id];
            renderResultDiv(resultDiv, selectedAgent, streamData);
        });

    } catch (e) {
        console.error("Error fetching data:", e);
    }
}


function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#039;');
}
