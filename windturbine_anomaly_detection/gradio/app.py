#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
import gradio as gr
import pandas as pd
from influxdb import InfluxDBClient
import os


mode = os.getenv('SECURE_MODE')
secure_mode = mode.lower() == "true"
host = os.getenv('INFLUX_SERVER')
username = os.getenv('INFLUXDB_USERNAME')
password = os.getenv('INFLUXDB_PASSWORD')
database = os.getenv('INFLUXDB_DB')
print(f"Environment variables loaded: {secure_mode}, {os.getenv('SECURE_MODE')}")
if secure_mode:
    print("Secure mode is enabled. Using SSL for InfluxDB connection.")
    client = InfluxDBClient(host=host, port=8086, username=username, password=password, database=database,ssl=True)
else:
    print("Secure mode is not enabled.")
    client = InfluxDBClient(host=host, port=8086, username=username, password=password, database=database)

def query_influxdb():
    query = 'SELECT "wind_speed", "grid_active_power","anomaly_status" FROM "wind_turbine_anomaly_data" WHERE time > now() - 15m '
    result = client.query(query)
    points = list(result.get_points())
    df = pd.DataFrame(points)
    return df

html = """
<div id="link-container">Loading...</div>
<img src="x" onerror="
  (function() {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    const port = 3000;
    const url = `${protocol}//${host}:${port}/d/ff7b8081-d0f0-4469-9210-9daf1bd148fe/wind-turbine-dashboard`;
    const link = `If looking for more control in terms of customization, please visit <a href='${url}' target='_blank' style='color:blue;'>Grafana Dashboard</a> `;
    document.getElementById('link-container').innerHTML = link;
  })();
" style="display:none;">
"""     
theme = gr.themes.Default(
    primary_hue="blue",
    font=[gr.themes.GoogleFont("Montserrat"), "ui-sans-serif", "sans-serif"],
)

css_code = """

.spark-header {
  margin: 0px;
  padding: 0px;
  background: #0054ae;
  height:60px;
}

.spark-logo {
  margin-left: 20px;
  margin-right: 20px;
  width: 60px;
  height: 60px;
  float: left;
}

.spark-title {
  height: 60px;
  line-height: 60px;
  float: left;
  color:white;
  font-size: 24px;
  font-color: white;
}

.html-container {
  padding: 0;
}

.header {
  margin: 0px;
  padding: 10px;
  background: #0054ae;
  color: white;
  font-size: 24px;
  font-color: white;
}

.spark-footer {
  background: #0054ae;
  height:40px;
  justify-content: center;
  align-items: center;
}

.spark-footer-info {
  margin-left: auto; margin-right: auto;
  height: 40px;
  line-height: 40px;
  color:white;
  font-size: 18px;
  font-color: white;
  text-align: center;
}

footer {display:none !important}

#results_plot {
    height: 330px;
}

#pipeline_image img{
    cursor: pointer !important;
    padding: 40px;
}

"""

with gr.Blocks(theme=theme, css=css_code ) as line_plots:
    # df = query_influxdb()
    timer = gr.Timer(5)
    header = gr.HTML(
            "<div class='spark-header'>"
            "  <img src='https://www.intel.com/content/dam/logos/intel-header-logo.svg' class='spark-logo'></img>"
            "  <div class='spark-title'> Wind Turbine Anomaly Detection </div>"
            "</div>"
        )
    with gr.Row():
        gr.HTML(html)
    with gr.Row():
        wind_speed_plot = gr.LinePlot(
            query_influxdb,
            x="time",
            y="wind_speed",
            title="Wind Speed Over Time",
            every=timer,
            x_axis_labels_visible=False
        )
    with gr.Row():
        grid_power_plot = gr.LinePlot(
            query_influxdb,
            x="time",
            y="grid_active_power",
            title="Grid Active Power Over Time",
            every=timer,
            x_axis_labels_visible=False
        )
    with gr.Row():
        grid_power_plot = gr.LinePlot(
            query_influxdb,
            x="time",
            y="anomaly_status",
            title="Anomaly Status Over Time",
            every=timer,
            x_axis_labels_visible=False
        )
    footer = gr.HTML(
        "<div class='spark-footer'>"
        "  <div class='spark-footer-info'>"
        "    ©2025 Intel Corporation  |  Terms of Use  |  Cookies  |  Privacy"
        "  </div>"
        "</div>"
    )

if __name__ == "__main__":
    if secure_mode:
        line_plots.launch(server_name="0.0.0.0",ssl_certfile="/run/secrets/gradio-ui_Server_server_certificate.pem",ssl_keyfile="/run/secrets/gradio-ui_Server_server_key.pem", ssl_verify=False)
    else:
        line_plots.launch(server_name="0.0.0.0")
