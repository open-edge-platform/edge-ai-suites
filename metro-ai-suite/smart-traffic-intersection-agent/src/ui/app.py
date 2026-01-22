# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
"""
RSU Monitoring System - Main Application
A Gradio-based web interface for monitoring RSU data
"""

import gradio as gr
import logging
import sys
import time

# Import our modules
from config import Config
from data_loader import load_monitoring_data
from ui_components import UIComponents
from auto_refresh import create_status_indicator_html

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_dashboard(debug_mode=False):
    """Update all dashboard components with fresh data"""
    try:
        # Load fresh data using API only
        data = load_monitoring_data(api_url=Config.API_URL)
        
        if not data:
            error_msg = "<div style='color: red; text-align: center; padding: 20px;'>❌ No data available</div>"
            return error_msg, [], error_msg, error_msg, error_msg, error_msg, gr.HTML(visible=False)
        
        # Generate UI components
        header = UIComponents.create_header(data)
        #camera_images_html = UIComponents.create_camera_grid_html(data)
        camera_gallery = UIComponents.create_camera_images(data)
        traffic = UIComponents.create_traffic_summary(data)
        environmental = UIComponents.create_environmental_panel(data)
        alerts = UIComponents.create_alerts_panel(data)
        system_info = UIComponents.create_system_info(data)
        debug_panel = UIComponents.create_debug_panel(data)

        return header, camera_gallery, traffic, environmental, alerts, system_info, gr.HTML(value=debug_panel, visible=debug_mode)

    except Exception as e:
        logger.error(f"Error updating dashboard: {e}")
        error_msg = f"<div style='color: red; text-align: center; padding: 20px;'>❌ Error: {str(e)}</div>"
        return error_msg, [], error_msg, error_msg, error_msg, error_msg, gr.HTML(visible=False)

def create_dashboard_interface():
    """Create the main dashboard interface"""
    
    # Custom CSS for better styling - theme-aware
    is_light_theme = Config.UI_THEME == "light"
    
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
        title=Config.APP_TITLE,
        theme=gr.themes.Base() if Config.UI_THEME == "light" else gr.themes.Monochrome()
    ) as interface:
        
        # Header component
        header_component = gr.HTML()

        # Main content grid
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
                debug_panel_component = gr.HTML(visible=False)


        # Alerts section
        alerts_component = gr.HTML()
        
        # System information footer
        system_info_component = gr.HTML()

        # Auto-refresh status indicator
        gr.HTML(create_status_indicator_html())
        
        # Refresh function for the interface
        def refresh_data(debug_mode_checked):
            """Refresh dashboard data"""
            return update_dashboard(debug_mode=debug_mode_checked)
        
        # Manual refresh button and debug toggle
        with gr.Row(elem_id="footer-actions"):
            with gr.Column(scale=3):
                pass  
            with gr.Column(scale=1):
                with gr.Row():                    
                    refresh_btn = gr.Button("🔄 Refresh Data", variant="primary", elem_id="refresh-data-btn")
                with gr.Row():
                    debug_mode = gr.Checkbox(label="🐞 Show Debug Info", value=False, container=False, visible=False)

        # Initial load of data
        interface.load(
            fn=refresh_data,
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
        # Set up manual refresh handler
        refresh_btn.click(
            fn=refresh_data,
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

        # Auto refresh using Gradio Timer (server side)
        try:
            auto_timer = gr.Timer(value=Config.REFRESH_INTERVAL_SECONDS)
            auto_timer.tick(
                fn=refresh_data,
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
            logger.info("Gradio Timer auto-refresh enabled (value=%ss)" % Config.REFRESH_INTERVAL_SECONDS)
        except Exception as e:
            logger.warning(f"Unable to initialize Gradio Timer auto-refresh: {e}")
    
    return interface

def main():
    """Main application entry point"""
    logger.info("Starting RSU Monitoring Dashboard...")
    logger.info(f"API URL: {Config.API_URL}")
    logger.info(f"Refresh interval: {Config.REFRESH_INTERVAL_SECONDS} seconds")
    logger.info(f"Server: {Config.APP_HOST}:{Config.APP_PORT}")
    logger.info("Configured to use API endpoint for data")
    
    try:
        # Create and launch the interface
        interface = create_dashboard_interface()
        
        interface.launch(
            server_name=Config.APP_HOST,
            server_port=Config.APP_PORT,
            share=False,
            show_error=True,
            show_api=False,
            quiet=False
        )
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()