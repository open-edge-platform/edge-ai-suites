style = """
    /* Modern Font Import */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global Font Styles */
    body, .gradio-container, .gradio-container *, .gradio-container label, .gradio-container input, .gradio-container textarea, .gradio-container select, .gradio-container button {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600;
    }

    .map-container {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        position: relative;
    }
    .map-container iframe {
        border-radius: 12px;
        box-shadow: 0 4px 8px rgba(192, 38, 38, 0.3);
    }

    .search-button {
        background: linear-gradient(135deg, #13B513 0%, #069106 100%);
    }

    .search-button:hover {
        background: linear-gradient(135deg, #13B513 0%, #069106 50%);
        transform: translateY(-2px);
    }
    .stop-button {
        background-color: #C02626;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: bold;
        margin-top: 10px;
        transition: all 0.2s ease;
        box-shadow: 0 2px 6px rgba(192, 38, 38, 0.25);
        letter-spacing: 0.5px;
    }
    .stop-button:hover {
        background-color: #d9342a;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(192, 38, 38, 0.3);
    }
    .main-content-row {
        min-height: 50vh;
        display: flex;
        flex-direction: row;
    }
    .horizontal-search {
        background: linear-gradient(135deg, #8a85e9 0%, #4a43ce 100%);
        padding: 24px;
        border-radius: 16px;
        margin-bottom: 24px;
        box-shadow: 0 8px 16px rgba(79, 70, 229, 0.15);
    }
    .horizontal-search .gr-dropdown {
        background: white;
        border-radius: 10px;
        border: none;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    .progress-container {
        z-index: 10 !important;
    }
    .traffic-slider {
        width: 100%;
    }
    .threshold-status {
        display: flex;
        width: 100%;
        overflow: hidden;
        word-wrap: break-word;
    }
    .settings-panel {
        display: flex;
        background-color: #E3F2F0;
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        overflow: visible;
    }
    .settings-panel .block {
        width: 100%;
    }

    /* Styling for the thinking output markdown component */
    .thinking-output {
        border-radius: 10px;
        border: solid 1px #EBE6E6;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        overflow-y: auto;
        max-height: 50vh;
        line-height: 1.6;
    }

    .thinking-output h1, .thinking-output h2, .thinking-output h3 {
        color: #b112cd;
        margin-top: 1em;
        margin-bottom: 0.5em;
    }
    .thinking-output h2 {
        color: #9230a4
    }

    .thinking-output h3 {
        color: #1073be;
    }

    .thinking-output h4 {
        color: #950d85
    }

    .thinking-output h5, .thinking-output h6 {
        color: #b942ab;
    }

    .thinking-output code {
        background-color: #f3f4f6;
        padding: 2px 5px;
        border-radius: 4px;
        font-family: 'Roboto Mono', monospace;
        font-size: 0.9em;
    }

    .thinking-output pre {
        background-color: #f8fafc;
        padding: 12px;
        border-radius: 8px;
        border-left: 3px solid #4f46e5;
        overflow-x: auto;
    }

    .thinking-output em, .thinking-output i {
        color: #8d3419;
    }

    .thinking-output strong, .thinking-output b {
        color: #262E9E;
    }

    .status-indicator {
        padding: 10px 16px;
        border-radius: 4px;
        font-weight: bold;
        text-align: center;
        letter-spacing: 0.3px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.2s ease;
        font-size: 18px;
    }
    .status-active {
        background-color: #8ccf9b;
        color: #155724;
        border: 1px solid #4b8257;
    }
    .status-inactive {
        background-color: #e7bcbf;
        color: #721c24;
        border: 1px solid #986b6e;
        font-weight: bold;
        font-size: 18px;
    }
    .no-map-style {
        text-align: center;
        padding: 50px;
        font-size: 18px;
        color: #666;
    }
    .error-while-thinking {
        text-align: center;
        padding: 20px;
        color: #C02626;
        font-weight: bold;
        font-size: 18px;
    }
    """
