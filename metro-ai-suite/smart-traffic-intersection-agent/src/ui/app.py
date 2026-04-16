# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import sys

import gradio as gr

from config import Config
from data_loader import update_components, fetch_intersection_data


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        theme=gr.themes.Base() if Config.get_ui_theme() == "light" else gr.themes.Monochrome()
    ) as interface:
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

        alerts_component = gr.HTML()
        system_info_component = gr.HTML()
        
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
        interface.launch(
            server_name=Config.get_app_host(),
            server_port=Config.get_app_port(),
            share=False,
            show_error=True,
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