# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys

import aiohttp
import gradio as gr
from fastapi import Request
from fastapi.responses import StreamingResponse

from config import Config
from data_loader import update_components, fetch_intersection_data


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_dashboard(debug_mode=False):
    """Update all dashboard components with fresh data"""
    try:
        # Load fresh data using API only
        data = load_monitoring_data(api_url=Config.get_api_url())
        
        if not data:
            # Return no-ops to preserve existing DOM (avoids flicker from metrics JS)
            return (gr.update(), gr.update(), gr.update(), gr.update(),
                    gr.update(), gr.update(), gr.update())
        
        # Generate UI components
        header = UIComponents.create_header(data)
        camera_gallery = UIComponents.create_camera_images(data)
        traffic = UIComponents.create_traffic_summary(data)
        environmental = UIComponents.create_environmental_panel(data)
        alerts = UIComponents.create_alerts_panel(data)
        system_info = UIComponents.create_system_info(data)
        debug_panel = UIComponents.create_debug_panel(data)

        return header, camera_gallery, traffic, environmental, alerts, system_info, gr.HTML(value=debug_panel, visible=debug_mode)

    except Exception as e:
        logging.exception("update_dashboard failed: %s", e)
        return (gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update())

def _metrics_panel_html():
    """HTML markup for the metrics panel — matches LVC chart-grid style."""
    return """
    <style>
      .metrics-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px;
        background: #fafafa;
        font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue";
      }
      .metrics-title { font-weight: 600; font-size: 14px; margin-bottom: 8px; }
      .chart-grid { display: flex; gap: 12px; flex-wrap: wrap; }
      .chart-card { flex: 1; min-width: 140px; }
      .chart-header { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 2px; }
      .chart-header span:first-child { font-weight: 600; color: #555; }
      .chart-value { font-weight: 700; font-size: 13px; }
      .chart-wrap { height: 80px; }
      .chart-wrap canvas { width: 100% !important; height: 100% !important; }
      .gpu-detail-row { font-size: 11px; color: #888; margin-top: 2px; display: none; }
      .metrics-status { margin-top: 6px; font-size: 12px; color: #444; }
      .metrics-status .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #ccc; margin-right: 4px; vertical-align: middle; }
      .metrics-status .dot.active { background: #10b981; }
    </style>
    <div class="metrics-card">
      <div class="metrics-title">System Telemetry</div>
      <div class="chart-grid">
        <div class="chart-card">
          <div class="chart-header"><span>CPU</span><span class="chart-value" id="cpuVal">—</span></div>
          <div class="chart-wrap"><canvas id="cpuChart"></canvas></div>
          <div class="gpu-detail-row" id="cpuFreq"></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><span>RAM</span><span class="chart-value" id="ramVal">—</span></div>
          <div class="chart-wrap"><canvas id="ramChart"></canvas></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><span>GPU</span><span class="chart-value" id="gpuVal">—</span></div>
          <div id="gpuError" style="font-size:0.7rem;color:#999;display:none;"></div>
          <div class="chart-wrap"><canvas id="gpuChart"></canvas></div>
          <div class="gpu-detail-row" id="gpuEngines"></div>
          <div class="gpu-detail-row" id="gpuFreq"></div>
          <div class="gpu-detail-row" id="gpuPower"></div>
          <div class="gpu-detail-row" id="gpuTemp"></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><span>NPU</span><span class="chart-value" id="npuVal">—</span></div>
          <div class="chart-wrap"><canvas id="npuChart"></canvas></div>
          <div class="gpu-detail-row" id="npuDetail"></div>
        </div>
      </div>
      <div class="metrics-status">
        <span class="dot" id="metricsManagerStatusDot"></span>
        Metrics Manager: <span id="metricsManagerStatus">Disconnected</span>
      </div>
    </div>
    """


def _metrics_js():
    """Return JavaScript code for Chart.js + Metrics Manager SSE metrics.

    Executed on page load via the Gradio ``js`` parameter (evaluated by
    ``new Function()``, so raw JS — no ``<script>`` wrapper needed).
    """
    return """
    (function() {
      /* Prevent duplicate initialization */
      if (window.__metricsInitialized) return;
      window.__metricsInitialized = true;

      /* ── Chart.js loader ── */
      function loadChartJs(cb) {
        if (window.Chart) return cb();
        var s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js';
        s.onload = cb;
        document.head.appendChild(s);
      }

      function initMetrics(tries) {
        var el = document.getElementById('cpuVal');
        if (!el) {
          if ((tries||0) < 100) setTimeout(function(){ initMetrics((tries||0)+1); }, 300);
          return;
        }

        loadChartJs(function() {
          /* ── Chart manager (mirrors LVC ChartManager) ── */
          var statsCharts = {};
          var maxPoints = 60;

          function createStatChart(elId, label, color) {
            var canvas = document.getElementById(elId);
            if (!canvas) return;
            var ctx = canvas.getContext('2d');
            var gradient = ctx.createLinearGradient(0, 0, 0, 80);
            gradient.addColorStop(0, color + '55');
            gradient.addColorStop(1, color + '0f');
            var chart = new Chart(ctx, {
              type: 'line',
              data: { labels: [], datasets: [{ label: label, data: [], borderColor: color, backgroundColor: gradient, tension: 0.35, fill: true, pointRadius: 0, borderWidth: 2 }] },
              options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                scales: { x: { display: false }, y: { suggestedMin: 0, suggestedMax: 100, grid: { color: '#e5e7eb' }, ticks: { color: '#9ca3af', font: { size: 10 } } } },
                plugins: { legend: { display: false } }
              }
            });
            statsCharts[elId.replace('Chart', '')] = chart;
          }

          function pushSample(key, value) {
            var chart = statsCharts[key];
            if (!chart) return;
            chart.data.labels.push(new Date().toLocaleTimeString());
            if (chart.data.labels.length > maxPoints) chart.data.labels.shift();
            var ds = chart.data.datasets[0];
            ds.data.push(value);
            if (ds.data.length > maxPoints) ds.data.shift();
            chart.update('none');
          }

          createStatChart('cpuChart', 'CPU %', '#1ad0ff');
          createStatChart('ramChart', 'RAM %', '#8ca0c2');
          createStatChart('gpuChart', 'GPU %', '#ffb347');
          createStatChart('npuChart', 'NPU %', '#a78bfa');

          /* ── DOM refs ── */
          var cpuVal    = document.getElementById('cpuVal');
          var ramVal    = document.getElementById('ramVal');
          var gpuVal    = document.getElementById('gpuVal');
          var npuVal    = document.getElementById('npuVal');
          var cpuFreq   = document.getElementById('cpuFreq');
          var gpuEngines = document.getElementById('gpuEngines');
          var gpuFreq   = document.getElementById('gpuFreq');
          var gpuPower  = document.getElementById('gpuPower');
          var gpuTemp   = document.getElementById('gpuTemp');
          var npuDetail = document.getElementById('npuDetail');
          var gpuError  = document.getElementById('gpuError');
          var metricsManagerStatus    = document.getElementById('metricsManagerStatus');
          var metricsManagerStatusDot = document.getElementById('metricsManagerStatusDot');

          var gpuEngineData = {};
          var gpuPowerValue = null;
          var pkgPowerValue = null;

          function asNumber(value) {
            var parsed = Number(value);
            return Number.isFinite(parsed) ? parsed : null;
          }

          function setMetricValue(el, value, suffix, precision) {
            if (!el || value === null) return;
            el.textContent = value.toFixed(precision === undefined ? 1 : precision) + suffix;
          }

          function labelsOf(metric) {
            return metric.labels || metric.tags || {};
          }

          function isMetricName(name, candidates) {
            return candidates.indexOf(name) !== -1;
          }

          function processPrometheusSample(metric) {
            var name = metric.name || '';
            var labels = labelsOf(metric);
            var value = asNumber(metric.value);
            if (value === null) return;

            if (isMetricName(name, ['cpu_usage_user'])) {
              if (!labels.cpu || labels.cpu === 'cpu-total') {
                pushSample('cpu', value);
                setMetricValue(cpuVal, value, '%');
              }
              return;
            }

            if (isMetricName(name, ['mem_used_percent'])) {
              pushSample('ram', value);
              setMetricValue(ramVal, value, '%');
              return;
            }

            if (isMetricName(name, ['cpu_frequency_avg_frequency'])) {
              if (cpuFreq) {
                cpuFreq.textContent = 'Freq: ' + (value / 1000).toFixed(0) + ' MHz';
                cpuFreq.style.display = 'block';
              }
              return;
            }

            if (isMetricName(name, ['gpu_engine_usage_usage', 'gpu_engine_usage'])) {
              var engine = labels.engine || labels.type;
              if (engine) gpuEngineData[String(engine).toUpperCase()] = value;
              return;
            }

            if (isMetricName(name, ['gpu_frequency_value', 'gpu_frequency']) && labels.type === 'cur_freq') {
              if (gpuFreq) {
                gpuFreq.textContent = 'Freq: ' + value.toFixed(0) + ' MHz';
                gpuFreq.style.display = 'block';
              }
              return;
            }

            if (isMetricName(name, ['gpu_power_value', 'gpu_power'])) {
              if (labels.type === 'gpu_cur_power') gpuPowerValue = value;
              else if (labels.type === 'pkg_cur_power') pkgPowerValue = value;
              return;
            }

            if (isMetricName(name, ['temp_temp', 'temp'])) {
              var sensor = String(labels.sensor || '').toLowerCase();
              if (gpuTemp && sensor.indexOf('package') >= 0) {
                gpuTemp.textContent = 'Temp: ' + value.toFixed(1) + '°C';
                gpuTemp.style.display = 'block';
              }
              return;
            }

            if (isMetricName(name, ['npu_utilization'])) {
              pushSample('npu', value);
              setMetricValue(npuVal, value, '%');
              if (npuDetail) {
                npuDetail.textContent = 'Utilization: ' + value.toFixed(1) + '%';
                npuDetail.style.display = 'block';
              }
              return;
            }

            if (isMetricName(name, ['npu_power']) && npuDetail) {
              npuDetail.textContent = 'Power: ' + value.toFixed(1) + 'W';
              npuDetail.style.display = 'block';
            }
          }

          function processLegacyMetric(metric) {
            var name   = metric.name || '';
            var fields = metric.fields || {};
            var tags   = metric.tags || {};

            switch (name) {
              case 'cpu':
                if (fields.usage_user !== undefined) {
                  var cpu = asNumber(fields.usage_user);
                  if (cpu !== null) {
                    pushSample('cpu', cpu);
                    setMetricValue(cpuVal, cpu, '%');
                  }
                }
                break;

              case 'mem':
                if (fields.used_percent !== undefined) {
                  var mem = asNumber(fields.used_percent);
                  if (mem !== null) {
                    pushSample('ram', mem);
                    setMetricValue(ramVal, mem, '%');
                  }
                }
                break;

              case 'gpu_engine_usage':
                if (fields.usage !== undefined && tags.engine) {
                  var usage = asNumber(fields.usage);
                  if (usage !== null) gpuEngineData[tags.engine.toUpperCase()] = usage;
                }
                break;

              case 'gpu_frequency':
                if (fields.value !== undefined && tags.type === 'cur_freq') {
                  var legacyFreq = asNumber(fields.value);
                  if (legacyFreq !== null && gpuFreq) {
                    gpuFreq.textContent = 'Freq: ' + legacyFreq.toFixed(0) + ' MHz';
                    gpuFreq.style.display = 'block';
                  }
                }
                break;

              case 'gpu_power':
                if (fields.value !== undefined) {
                  var power = asNumber(fields.value);
                  if (power !== null && tags.type === 'gpu_cur_power') gpuPowerValue = power;
                  else if (power !== null && tags.type === 'pkg_cur_power') pkgPowerValue = power;
                }
                break;

              case 'temp':
                if (fields.temp !== undefined) {
                  var temp = asNumber(fields.temp);
                  var sensor = String(tags.sensor || '').toLowerCase();
                  if (temp !== null && gpuTemp && sensor.indexOf('package') >= 0) {
                    gpuTemp.textContent = 'Temp: ' + temp.toFixed(1) + '°C';
                    gpuTemp.style.display = 'block';
                  }
                }
                break;
            }
          }

          function processMetrics(metrics) {
            gpuPowerValue = null;
            pkgPowerValue = null;
            gpuEngineData = {};

            metrics.forEach(function(metric) {
              if (metric.fields) processLegacyMetric(metric);
              else processPrometheusSample(metric);
            });

            /* GPU power display */
            if (gpuPower && gpuPowerValue !== null) {
              var pwr = 'Power: ' + gpuPowerValue.toFixed(1) + 'W';
              if (pkgPowerValue !== null) pwr += ' (Pkg: ' + pkgPowerValue.toFixed(1) + 'W)';
              gpuPower.textContent = pwr;
              gpuPower.style.display = 'block';
            }

            /* GPU engines display */
            var engineNames = Object.keys(gpuEngineData);
            if (gpuEngines && engineNames.length > 0) {
              gpuEngines.textContent = engineNames.map(function(n){ return n + ': ' + gpuEngineData[n].toFixed(1) + '%'; }).join(' | ');
              gpuEngines.style.display = 'block';
            }

            /* Overall GPU usage = max engine */
            var engineValues = Object.keys(gpuEngineData).map(function(key){ return gpuEngineData[key] || 0; });
            if (engineValues.length > 0) {
              var maxGpu = Math.max.apply(null, engineValues);
              pushSample('gpu', maxGpu);
              setMetricValue(gpuVal, maxGpu, '%');
              if (gpuError) gpuError.style.display = 'none';
            }
          }

          /* ── Metrics Manager SSE ── */
          var source = null;
          var STREAM_URL = '/metrics/stream';

          function setConnectionState(connected, label) {
            if (metricsManagerStatus) {
              metricsManagerStatus.textContent = label;
              metricsManagerStatus.className = connected ? 'status-connected' : 'status-disconnected';
            }
            if (metricsManagerStatusDot) {
              if (connected) metricsManagerStatusDot.classList.add('active');
              else metricsManagerStatusDot.classList.remove('active');
            }
          }

          function connect() {
            if (source && source.readyState !== EventSource.CLOSED) return;
            console.log('[metrics] connecting to', STREAM_URL);
            source = new EventSource(STREAM_URL);

            source.onopen = function() {
              console.log('[metrics] connected');
              setConnectionState(true, 'Connected');
            };

            source.onmessage = function(ev) {
              try {
                var msg = JSON.parse(ev.data);
                if (msg.error) {
                  console.warn('[metrics] stream error:', msg.error);
                  setConnectionState(false, 'Stream error');
                  return;
                }
                if (msg.metrics && Array.isArray(msg.metrics)) {
                  processMetrics(msg.metrics);
                  setConnectionState(true, 'Connected');
                }
              } catch (e) { console.warn('[metrics] parse error:', e); }
            };

            source.onerror = function() {
              setConnectionState(false, 'Reconnecting');
            };
          }

          connect();

          window.addEventListener('beforeunload', function() {
            if (source) source.close();
          });
        });
      }
      initMetrics(0);
    })();
    """

def _device_security_panel_html():
    """Static Device Security State panel — hardcoded for now, configurable via CLI/env later."""
    # TODO: Replace hardcoded values with Config.get_device_security() or CLI input
    security_data = {
        "Secure Boot": {"status": "", "ok": True},
        "Full Disk Encryption": {"status": "", "ok": True},
        "Total Memory Encryption": {"status": "Enabled", "warn": True, "text_color": "#3b82f6"},
        "Trusted Compute": {"status": "", "ok": True}
        }

    rows_html = ""
    for label, info in security_data.items():
        if info.get("warn"):
            icon = '<span style="color:#3b82f6;">☑</span>'
            color = "#3b82f6"
        elif info.get("ok"):
            icon = "✅"
            color = "#10b981"
        else:
            icon = "❌"
            color = "#ef4444"
        text_color = info.get("text_color", color)
        rows_html += f"""
        <tr>
          <td style="padding:5px 8px;font-size:12px;color:#555;">{label}</td>
          <td style="padding:5px 8px;font-size:12px;font-weight:600;">{icon} <span style="color:{text_color};">{info["status"]}</span></td>
        </tr>"""

    return f"""
    <div style="border:1px solid #e0e0e0;border-radius:8px;padding:12px;background:#fafafa;
                font-family:ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue';margin-top:12px;">
      <div style="font-weight:600;font-size:14px;margin-bottom:8px;">🛡️ Device Security State</div>
      <table style="width:100%;border-collapse:collapse;">
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
    """


def create_dashboard_interface():
    """Create the main dashboard interface"""
    
    # Custom CSS for better styling - theme-aware
    is_light_theme = Config.get_ui_theme() == "light"
    
    # Define theme colors
    bg_primary = "#ffffff" if is_light_theme else "#1f2937"
    bg_secondary = "#f8fafc" if is_light_theme else "#374151"
    border_color = "#e2e8f0" if is_light_theme else "#4b5563"
    text_primary = "#1f2937" if is_light_theme else "#f3f4f6"
    
    css = f"""
    .gradio-container {{
        max-width: 1400px !important;
        margin: auto !important;
        padding: 10px !important;
        background: {bg_primary} !important;
        font-family: Arial, sans-serif !important;
    }}
    
    .block {{
        border-radius: 12px !important;
        border: 1px solid {border_color} !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
        background: {bg_secondary} !important;
    }}
    
    .alert-urgent {{
        background: linear-gradient(135deg, #ff4444, #cc0000) !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 12px !important;
        margin: 4px !important;
        border-left: 4px solid #ff0000 !important;
    }}
    
    .alert-advisory {{
        background: linear-gradient(135deg, #ff8800, #cc6600) !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 12px !important;
        margin: 4px !important;
        border-left: 4px solid #ff6600 !important;
    }}
    
    .status-good {{
        color: #10b981 !important;
        font-weight: bold !important;
    }}
    
    .status-warning {{
        color: #f59e0b !important;
        font-weight: bold !important;
    }}
    
    .status-critical {{
        color: #ef4444 !important;
        font-weight: bold !important;
    }}
    
    .metric-card {{
        background: {bg_secondary} !important;
        border-radius: 12px !important;
        padding: 16px !important;
        margin: 8px !important;
        border: 1px solid {border_color} !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
    }}
    
    .metric-value {{
        font-size: 2em !important;
        font-weight: bold !important;
        margin: 8px 0 !important;
        color: {text_primary} !important;
    }}

    .debug {{
        padding: 5px;
        background: #4b5563;
        border-radius: 4px;
        margin-top: 5px;
        text-align: center;
    }}
       
    /* Gallery styling */
    .gallery {{
        border-radius: 12px !important;
        overflow: hidden !important;
    }}
    
    /* Button styling */
    .primary {{
        background: linear-gradient(135deg, #3b82f6, #1e40af) !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 10px 20px !important;
    }}
    """
    
    with gr.Blocks(
        css=css,
        title=Config.get_app_title(),
        theme=gr.themes.Base() if Config.get_ui_theme() == "light" else gr.themes.Monochrome(),
    ) as interface:

        # Header component (full width)
        header_component = gr.HTML()

        # Row 1: Camera Feeds (left) | Traffic (mid) | Weather/Environmental (right)
        with gr.Row():
            with gr.Column(scale=2):
                camera_gallery = gr.Gallery(
                    label="📹 Camera Feeds",
                    show_label=True,
                    columns=2,
                    rows=2,
                    height="450px",
                    container=True,
                    object_fit="cover"
                )

            with gr.Column(scale=1):
                traffic_component = gr.HTML()

            with gr.Column(scale=1):
                environmental_component = gr.HTML()

        # Row 2: Alerts (full width)
        alerts_component = gr.HTML()

        # Row 3: System Info / Summary (full width)
        system_info_component = gr.HTML()

        # Row 4: System Telemetry (full width)
        # NOTE: Device Security panel is available via _device_security_panel_html()
        # but hidden until data source is wired up.
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML(_metrics_panel_html())
        
        # Invisible Debug panel and debug mode toggle button at the bottom
        with gr.Row(elem_id="footer-actions"):
            with gr.Column(scale=3):
                pass  
            with gr.Column(scale=1):
                with gr.Row():
                    debug_mode = gr.Checkbox(label="🐞 Show Debug Info", value=False, container=False, visible=False)
                with gr.Row():
                    debug_panel_component = gr.HTML(visible=False)

        # Running data fetcher and UI updater concurrently, runs in main event loop
        interface.load(fn=fetch_intersection_data, outputs=[])
        interface.load(
            fn=update_components,
            inputs=[debug_mode],
            outputs=[
                header_component,
                camera_gallery,
                traffic_component, 
                environmental_component,
                alerts_component,
                system_info_component,
                debug_panel_component
            ]
        )
        # Show/hide debug panel
        debug_mode.change(
            fn=lambda x: gr.update(visible=x),
            inputs=debug_mode,
            outputs=debug_panel_component
        )

    return interface


def _mount_metrics_stream_proxy(app):
    """Mount a same-origin SSE proxy for Metrics Manager live telemetry."""
    metrics_stream_url = Config.get_metrics_stream_url()

    @app.get("/metrics/stream")
    async def metrics_stream_proxy(request: Request):
        async def stream_metrics():
            timeout = aiohttp.ClientTimeout(total=None, connect=5, sock_read=30)
            headers = {"Accept": "text/event-stream"}
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(metrics_stream_url, headers=headers) as upstream:
                        upstream.raise_for_status()
                        async for chunk in upstream.content.iter_any():
                            if await request.is_disconnected():
                                break
                            yield chunk
            except Exception as e:
                logger.error("Metrics Manager stream proxy error: %s", e)
                yield b'data: {"error": "Metrics Manager stream unavailable"}\n\n'

        return StreamingResponse(
            stream_metrics(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )


def main():
    """Main application entry point"""
    logger.info("Starting Smart Traffic Intersection Agent Dashboard...")
    logger.info(f"API URL: {Config.get_api_url()}")
    logger.info(f"Refresh interval: {Config.get_refresh_interval()} seconds")
    logger.info(f"Server: {Config.get_app_host()}:{Config.get_app_port()}")
    logger.info("Configured to use API endpoint for data")
    
    try:
        # Create and launch the interface
        interface = create_dashboard_interface()
        
        # Enable request queuing for scaling
        interface.queue(default_concurrency_limit=5, max_size=20)

        # Launch without blocking so we can mount the metrics proxy on the
        # final FastAPI app that launch() creates (launch replaces self.app).
        _, local_url, _ = interface.launch(
            server_name=Config.get_app_host(),
            server_port=Config.get_app_port(),
            share=False,
            show_error=True,
            quiet=False,
            js=_metrics_js(),
            prevent_thread_lock=True,
        )

        # Mount the metrics stream proxy *after* launch() so we attach to the
        # actual FastAPI app instance that uvicorn is serving.
        _mount_metrics_stream_proxy(interface.server_app)
        logger.info("Metrics Manager stream proxy mounted at /metrics/stream")

        # Block the main thread so the server keeps running.
        interface.block_thread()
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        import sys
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()
