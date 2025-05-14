#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
import zipfile
import gradio as gr
import os
import random

from spark_classic_blue import SparkTheme  # Import the custom theme
from influx_connector import query_influxdb, get_total_anomaly_pts, get_total_ingested_pts, get_total_processed_pts, get_live_barplot


# Instantiate the custom theme
theme = SparkTheme()

themecss = theme.load_css()

mode = os.getenv('SECURE_MODE', "false")
secure_mode = mode.lower() == "true"

print(f"Environment variables loaded: {secure_mode}, {os.getenv('SECURE_MODE', "false")}")



html = """
<div id="link-container">Loading...</div>
<img src="x" onerror="
  (function() {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    let port = window.location.port === '7860' ? 3000 : 30001;
    const url = `${protocol}//${host}:${port}/d/ff7b8081-d0f0-4469-9210-9daf1bd148fe/wind-turbine-dashboard`;
    const link = `If looking for more control in terms of customization, please visit <a href='${url}' target='_blank' style='color:blue;'>Grafana Dashboard</a> `;
    document.getElementById('link-container').innerHTML = link;
  })();
" style="display:none;">
"""     
import datetime
def update_text():
    now = datetime.datetime.now(datetime.timezone.utc).astimezone().strftime("%H:%M:%S %Z")
    return f"⏱ Last updated: {now}<br>Total Anomalies Found: {get_total_anomaly_pts()}<br>Total Data Points Ingested: {get_total_ingested_pts()}<br>Total Data Points Processed: {get_total_processed_pts()}"

def validate_zip(file):
    try:
        with zipfile.ZipFile(file, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            if file_list:
                return f"ZIP file is valid and contains {len(file_list)} files."
            else:
                return "ZIP file is empty."
    except zipfile.BadZipFile:
        return "Not a valid ZIP file."

with gr.Blocks(theme=theme, css=themecss ) as line_plots:
    # df = query_influxdb()
    timer = gr.Timer(5)
    timer_sec_1 = gr.Timer(1)
    header = SparkTheme.header("Wind Turbine Anomaly Detection")        
    with gr.Tab("Dashboard"):
      with gr.Row():
        with gr.Column(scale=1):
            image = gr.Image("wind-turbines.jpg", label="Live view: Site 1", height=300)
        with gr.Column(scale=1):
          gr.Markdown("<div class='section-title'>Live Metrics</div>")
          gr.Markdown(update_text,every=timer) 
          gr.HTML(html)
        with gr.Column(scale=1):
          with gr.Blocks() as demo:
            plot = gr.Plot(
              get_live_barplot,
              every=timer
            )
            
      with gr.Row():
        with gr.Column(scale=1):
          grid_power_plot = gr.ScatterPlot(
              query_influxdb,
              x="time",
              y="grid_active_power",
              title="Grid Active Power Over Time",
              every=timer,
              x_axis_labels_visible=False,
              height=500
          )
        with gr.Column(scale=1):
          anomaly_status_plot = gr.LinePlot(
              query_influxdb,
              x="time",
              y="anomaly_status",
              title="Anomaly Status Over Time",
              every=timer,
              x_axis_labels_visible=False,
              height=500
          )
    # with gr.Tab("UDF Configurator"):
    #   block_descriptions = {
    #     "Ingestion": "### Ingestion Block\n- Collects data from wind turbine sensors.\n- Pushes raw telemetry to data lake.\n- Upload a .zip file to simulate data ingestion.",
    #     "InfluxDB": "### Processing Block\n- Cleans and preprocesses data.\n- Converts raw logs to structured formats.",
    #     "Telegraf": "### Detection Block\n- Applies anomaly detection models.\n- Classifies anomalies into low, medium, high.",
    #     "Dashboard": "### Dashboard Block\n- Visualizes live and historical data.\n- Displays metrics and alerts."
    #   }
    #   with gr.Blocks() as demo:
    #       gr.Markdown("Click a block below to view its details.")
    #       with gr.Row():
    #           b1 = gr.Button("Telegraf")
    #           b2 = gr.Button("InfluxDB")
    #           b3 = gr.Button("Time Series Analytics") 

    #       def show_block_ingestion():
    #           return (
    #               gr.Markdown("", visible=True),
    #               gr.File(file_types=[".zip"], label="Upload ZIP file", visible=True),
    #               gr.Textbox(label="Validation Status", visible=True, interactive=False),
    #               gr.Checkbox(label="Ingestion Status", visible=True, interactive=False)
    #           )
          
    #       def show_telegraf():
    #           return (
    #               gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
    #           )

    #       def show_influxdb():
    #           return (
    #               gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
    #           )

    #       def show_analytics():
    #           return (
    #               gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)
    #           )

    #       def show_block_generic(name):
    #           return (
    #               gr.update(value=block_descriptions[name], visible=True),
    #               gr.update(visible=False),
    #               gr.update(visible=False)
    #           )
    #       # Telegraf form
    #       with gr.Column(visible=False) as telegraf_form:
    #         gr.Checkbox(label="Enable CPU metrics")
    #         gr.Checkbox(label="Enable Disk I/O")
    #         gr.Textbox(label="Agent Interval (e.g. 10s)")
    #         gr.Button("Submit Telegraf")

    #       # InfluxDB form
    #       with gr.Column(visible=False) as influxdb_form:
    #         gr.Checkbox(label="Enable Authentication")
    #         gr.Textbox(label="Database Name")
    #         gr.Textbox(label="Retention Policy")
    #         gr.Button("Submit InfluxDB")
    #       with gr.Column(visible=False) as analytics_form:
    #         with gr.Row():
    #           with gr.Column(scale=1):
    #             gr.Markdown("### Time Series Analytics")
    #             gr.Checkbox(label="Enable Anomaly Detection")
    #             gr.Checkbox(label="Send Alerts")
    #             gr.Textbox(label="Threshold Value")
    #           with gr.Column(scale=2):
    #             with gr.Row():
    #               gr.Markdown("### Enable MQTT Alert")
    #               gr.Checkbox(label="Enable MQTT Alert")
    #               gr.Textbox(label="MQTT Broker URL")
    #               gr.Textbox(label="MQTT Broker Port")
    #               gr.Textbox(label="MQTT Topic")
    #             with gr.Row():
    #               gr.Markdown("### Enable OPC UA Alert")
    #               gr.Checkbox(label="Enable OPC UA Alert")
    #               gr.Textbox(label="OPC UA URL")
    #           with gr.Column(scale=3):
    #             file_status = gr.Textbox(label="Validation Status", visible=False, interactive=False)
    #             gr.File(file_types=[".zip"], label="Upload ZIP file", visible=True).change(fn=validate_zip, outputs=file_status)
    #         with gr.Row():
    #           gr.Button("Submit Analytics")
    #       block_display = gr.Markdown("", visible=False)
    #       file_upload = gr.File(file_types=[".zip"], label="Upload ZIP file", visible=False)
    #       # 
    #       b1.click(show_telegraf, outputs=[telegraf_form, influxdb_form, analytics_form])
    #       b2.click(show_influxdb, outputs=[telegraf_form, influxdb_form, analytics_form])
    #       b3.click(show_analytics, outputs=[telegraf_form, influxdb_form, analytics_form])
    #       # file_upload.change(fn=validate_zip, inputs=file_upload, outputs=file_status)
    # 
    footer = SparkTheme.footer()

if __name__ == "__main__":
    if secure_mode:
        line_plots.launch(server_name="0.0.0.0",ssl_certfile="/run/secrets/gradio-ui_Server_server_certificate.pem",ssl_keyfile="/run/secrets/gradio-ui_Server_server_key.pem", ssl_verify=False)
    else:
        line_plots.launch(server_name="0.0.0.0")
