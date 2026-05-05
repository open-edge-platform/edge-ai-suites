# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
UI Components for the RSU Monitoring System
"""
import base64
import io
import os
from PIL import Image
from typing import Optional, List, Tuple

from models import MonitoringData
from config import Config


class ThemeColors:
    """Theme-aware color configuration"""
    
    @staticmethod
    def get_colors():
        """Get theme colors based on UI_THEME setting"""
        is_light = Config.get_ui_theme() == "light"
        
        return {
            'bg_primary': '#ffffff' if is_light else '#1f2937',
            'bg_secondary': '#f8fafc' if is_light else '#374151', 
            'bg_card': '#ffffff' if is_light else '#374151',
            'text_primary': '#1f2937' if is_light else '#f3f4f6',
            'text_secondary': '#64748b' if is_light else '#d1d5db',
            'border': '#e2e8f0' if is_light else '#4b5563',
            'header_bg': 'linear-gradient(135deg, #1e3a8a, #3b82f6)' if is_light else 'linear-gradient(135deg, #1e3a8a, #3b82f6)',
            'shadow': '0 2px 4px rgba(0,0,0,0.1)' if is_light else '0 2px 4px rgba(0,0,0,0.3)'
        }


class UIComponents:
    """UI component generator class"""

    @staticmethod
    async def _render_markdown(md_text: str) -> str:
        """Render markdown text to HTML. Falls back to simple replacements if markdown package not installed."""

        if not md_text:
            return ""

        md_text = "<span style='color:#000000;'>" + md_text + "</span>"

        try:
            import markdown 
            return markdown.markdown(md_text, extensions=["extra", "sane_lists", "tables"])
        except Exception:
            return "No VLM Analysis Available!"

    
    @staticmethod
    async def _get_traffic_density_color(density: int) -> str:
        """Get background color based on traffic density
        
        Args:
            density: Number of vehicles in the direction
            
        Returns:
            CSS background color string
        """
        if density >= Config.get_high_density_threshold():
            return "#ecb3b3"  # Light red for high density
        elif density >= Config.get_moderate_density_threshold():
            return "#ffff99"  # Yellow for moderate density
        else:
            return "#ffffff"  # Default white for low density
    
    @staticmethod
    async def create_header(monitoring_data: Optional[MonitoringData] = None) -> str:
        """Create the header section with system title and status"""
        colors = ThemeColors.get_colors()
        
        if not monitoring_data:
            intersection_label = os.getenv("INTERSECTION_NAME", "")
            title_text = f"{intersection_label} — Smart Traffic Intersection Agent" if intersection_label else "Smart Traffic Intersection Agent"
            return f"""
            <div style="text-align: center; background: {colors['header_bg']}; 
                        padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: {colors['shadow']};">
                <p style="color: white; margin: 0; font-size: 26px; font-weight: 600;">🚦 {title_text}</p>
                <p style="color: #fbbf24; margin: 8px 0 0 0; font-size: 16px; font-weight: 500;">⚠️ DATA UNAVAILABLE</p>
            </div>
            """
        
        intersection_label = monitoring_data.data.intersection_name or os.getenv("INTERSECTION_NAME", "")
        title_text = f"{intersection_label} — Smart Traffic Intersection Agent" if intersection_label else Config.get_app_title()
        return f"""
        <div style="text-align: center; background: {colors['header_bg']}; 
                    padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: {colors['shadow']};">
            <p style="color: white; margin: 0; font-size: 26px; font-weight: 600;">🚦 {title_text}</p> 
        </div>
        """

    @staticmethod
    async def create_traffic_summary(monitoring_data: Optional[MonitoringData]) -> str:
        """Create traffic summary cards"""
        if not monitoring_data:
            return "<p style='text-align: center; color: #ef4444;'>No traffic data available</p>"
        
        colors = ThemeColors.get_colors()
        data = monitoring_data.data
        total_pedestrians = monitoring_data.get_total_pedestrians()
        
        # Get background colors for each direction based on traffic density
        north_bg_color = await UIComponents._get_traffic_density_color(data.northbound_density)
        south_bg_color = await UIComponents._get_traffic_density_color(data.southbound_density)
        east_bg_color = await UIComponents._get_traffic_density_color(data.eastbound_density)
        west_bg_color = await UIComponents._get_traffic_density_color(data.westbound_density)
        
        return f"""
        <div style="background: {colors['bg_primary']}; border-radius: 12px; padding: 20px; margin: 10px 0; border: 1px solid {colors['border']}; box-shadow: {colors['shadow']};">
            <h3 style="color: {colors['text_primary']}; margin: 0 0 20px 0; text-align: center; font-size: 1.2em;">🚦 TRAFFIC SUMMARY</h3>
            
            <!-- Directional Traffic Grid -->
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 18px;">
                <div style="text-align: center; background: {east_bg_color}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #60a5fa; font-weight: bold; margin-bottom: 5px;">{data.eastbound_density}</div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9em; font-weight: 500;">→ EAST</div>
                </div>
                <div style="text-align: center; background: {north_bg_color}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #60a5fa; font-weight: bold; margin-bottom: 5px;">{data.northbound_density}</div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9em; font-weight: 500;">↑ NORTH</div>
                </div>
                <div style="text-align: center; background: {south_bg_color}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #60a5fa; font-weight: bold; margin-bottom: 5px;">{data.southbound_density}</div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9em; font-weight: 500;">↓ SOUTH</div>
                </div>
                <div style="text-align: center; background: {west_bg_color}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #60a5fa; font-weight: bold; margin-bottom: 5px;">{data.westbound_density}</div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9em; font-weight: 500;">← WEST</div>
                </div>
            </div>
            
            <!-- Total Summary Grid -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                <div style="text-align: center; background: {colors['bg_card']}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #60a5fa; font-weight: bold; margin-bottom: 6px;">{data.total_density}</div>
                    <div style="color: {colors['text_secondary']}; font-weight: 500; font-size: 0.9em;">TOTAL VEHICLES</div>
                </div>
                <div style="text-align: center; background: {colors['bg_card']}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #fbbf24; font-weight: bold; margin-bottom: 6px;">{total_pedestrians}</div>
                    <div style="color: {colors['text_secondary']}; font-weight: 500; font-size: 0.9em;">TOTAL PEDESTRIANS</div>
                </div>
            </div>
        </div>
        """
    
    @staticmethod
    async def create_debug_panel(monitoring_data: Optional[MonitoringData]) -> str:
        """
        Create a hidden debug panel which is shown only when the debug checkbox is enabled.
        Contains timestamp info about data and images for each direction.
        """

        if not monitoring_data:
            return "<p style='text-align: center; color: #ef4444;'>No traffic data available</p>"
        
        data = monitoring_data.data
        image = monitoring_data.camera_images

        return f"""
        <div class ="debug-panel" style="background: #1f2937; border-radius: 12px; padding: 20px; margin: 10px 0;font-family: Arial, sans-serif;">
            <h3 style="color: #f3f4f6; margin: 0 0 20px 0; text-align: center; font-size: 1.2em;"> Debug Timestamps </h3>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 5px; margin-bottom: 5px;">
                <div class="debug">
                    <div style="color: #d1d5db; font-size: 0.7em; font-weight: 500;">→ EAST</div>
                    <div style="color: #9ca3af; font-size: 0.9em; font-weight: 400;">Data: {data.east_timestamp}</div>
                    <div style="color: #9ca3af; font-size: 0.9em; font-weight: 400;">Image: {image.get("east_camera", {}).get("timestamp")}</div>
                </div>
                <div class="debug">
                    <div style="color: #d1d5db; font-size: 0.7em; font-weight: 500;">→ NORTH</div>
                    <div style="color: #9ca3af; font-size: 0.9em; font-weight: 400;">Data: {data.north_timestamp}</div>
                    <div style="color: #9ca3af; font-size: 0.9em; font-weight: 400;">Image: {image.get("north_camera", {}).get("timestamp")}</div>
                </div>
                <div class="debug">
                    <div style="color: #d1d5db; font-size: 0.7em; font-weight: 500;">→ SOUTH</div>
                    <div style="color: #9ca3af; font-size: 0.9em; font-weight: 400;">Data: {data.south_timestamp}</div>
                    <div style="color: #9ca3af; font-size: 0.9em; font-weight: 400;">Image: {image.get("south_camera", {}).get("timestamp")}</div>
                </div>
                <div class="debug">
                    <div style="color: #d1d5db; font-size: 0.7em; font-weight: 500;">→ WEST</div>
                    <div style="color: #9ca3af; font-size: 0.9em; font-weight: 400;">Data: {data.west_timestamp}</div>
                    <div style="color: #9ca3af; font-size: 0.9em; font-weight: 400;">Image: {image.get("west_camera", {}).get("timestamp")}</div>
                </div>
            </div>
        </div>
        """



    @staticmethod
    async def create_environmental_panel(monitoring_data: Optional[MonitoringData]) -> str:
        """Create environmental data panel"""
        if not monitoring_data:
            return "<p style='text-align: center; color: #ef4444;'>No environmental data available</p>"
        
        colors = ThemeColors.get_colors()
        weather = monitoring_data.weather_data
        
        # Determine air quality status (simulated)
        temp = weather.temperature_fahrenheit
        humidity = weather.humidity_percent
        
        if temp < 0 or temp > 35 or humidity > 80:
            air_quality = "POOR"
            air_color = "#ef4444"
        elif temp < 10 or temp > 30 or humidity > 60:
            air_quality = "MODERATE"
            air_color = "#f59e0b"
        else:
            air_quality = "GOOD"
            air_color = "#10b981"
        
        # Wind direction
        wind_dir = weather.wind_direction_degrees
        if wind_dir < 45 or wind_dir >= 315:
            wind_text = "N"
        elif wind_dir < 135:
            wind_text = "E"
        elif wind_dir < 225:
            wind_text = "S"
        else:
            wind_text = "W"
        
        # Format dewpoint for display
        dewpoint_display = "N/A"
        if weather.dewpoint is not None:
            # Convert from Celsius to Fahrenheit for consistency
            dewpoint_f = (weather.dewpoint * 9/5) + 32
            dewpoint_display = f"{dewpoint_f:.0f}°F"
        
        # Day/Night status
        daytime_status = "Unknown"
        daytime_icon = "🌅"
        if weather.is_daytime is not None:
            if weather.is_daytime:
                daytime_status = "Day time"
                daytime_icon = "☀️"
            else:
                daytime_status = "Night time"
                daytime_icon = "🌙"
        
        # Use relative humidity from API if available, otherwise use the estimated value
        display_humidity = weather.relative_humidity if weather.relative_humidity is not None else weather.humidity_percent
        
        return f"""
        <div style="background: {colors['bg_primary']}; border-radius: 12px; padding: 20px; margin: 10px 0; border: 1px solid {colors['border']}; box-shadow: {colors['shadow']};">
            <h3 style="color: {colors['text_primary']}; margin: 0 0 20px 0; text-align: center; font-size: 1.2em;">🌡️ ENVIRONMENTAL DATA</h3>
            
            <!-- Primary Weather Metrics -->
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 18px;">
                <div style="text-align: center; background: {colors['bg_card']}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #fbbf24; font-weight: bold; margin-bottom: 5px;">{weather.temperature_fahrenheit}°{weather.temperature_unit}</div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9em; font-weight: 500;">TEMPERATURE</div>
                </div>
                <div style="text-align: center; background: {colors['bg_card']}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #60a5fa; font-weight: bold; margin-bottom: 5px;">{display_humidity:.0f}%</div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9em; font-weight: 500;">HUMIDITY</div>
                </div>
                <div style="text-align: center; background: {colors['bg_card']}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #a78bfa; font-weight: bold; margin-bottom: 5px;">{weather.wind_speed_mph:.1f} mph</div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9em; font-weight: 500;">WIND {wind_text}</div>
                </div>
                <div style="text-align: center; background: {colors['bg_card']}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #34d399; font-weight: bold; margin-bottom: 5px;">{weather.precipitation_prob:.0f}%</div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9em; font-weight: 500;">RAINFALL (P)</div>
                </div>
            </div>
            
            <!-- Additional Environmental Info -->
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 18px;">
                <div style="text-align: center; background: {colors['bg_card']}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #f97316; font-weight: bold; margin-bottom: 5px;">{dewpoint_display}</div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9em; font-weight: 500;">DEWPOINT</div>
                </div>
                <div style="text-align: center; background: {colors['bg_card']}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1.5em; color: #8b5cf6; font-weight: bold; margin-bottom: 5px;">{daytime_icon}</div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9em; font-weight: 500;">{daytime_status.upper()}</div>
                </div>
            </div>
            
                <div style="text-align: center; background: {colors['bg_card']}; padding: 15px; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                    <div style="font-size: 1em; font-weight: bold; margin-bottom: 6px; color: {colors['text_primary']};">{weather.conditions}</div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9em; font-weight: 500;">CONDITIONS</div>
                </div>
        </div>
        """

    @staticmethod
    async def create_alerts_panel(monitoring_data: Optional[MonitoringData]) -> str:
        """Create alerts panel with structured alerts and recommendations"""
        if not monitoring_data:
            return "<p style='text-align: center; color: #ef4444;'>No alerts data available</p>"
        
        colors = ThemeColors.get_colors()
        alerts = monitoring_data.vlm_analysis.alerts
        recommendations = monitoring_data.vlm_analysis.recommendations or []
        
        if not alerts and not recommendations:
            return f"""
            <div style="background: {colors['bg_primary']}; border-radius: 12px; padding: 15px; margin: 10px 0; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                <h3 style="color: {colors['text_primary']}; margin: 0 0 15px 0; text-align: left;">🚨 Traffic Status and Alerts</h3>
                <div style="text-align: center; background: #065f46; padding: 20px; border-radius: 8px;">
                    <div style="font-size: 1.5em; color: #10b981;">✅ ALL SYSTEMS OPERATIONAL</div>
                    <div style="color: #d1fae5; margin-top: 10px;">No active alerts or recommendations</div>
                </div>
            </div>
            """
        
        # Process alerts with new structured format
        alerts_html = ""
        for alert in alerts:
            if isinstance(alert, dict):
                # New structured alert format
                alert_type = alert.get("alert_type", "general")
                level = alert.get("level", "info")
                description = alert.get("description", "")
                weather_related = alert.get("weather_related", False)
                
                # Determine styling based on level
                if level.lower() == "critical":
                    bg_color = "#c75959"  # Dark red
                    text_color = "#f6e4e4"
                    icon = "🚨"
                    border_color = "#dc2626"
                    alt_color = "#802222"
                elif level.lower() == "warning":
                    bg_color = "#b3724a"  # Dark orange
                    text_color = "#ffe7cc"
                    icon = "⚠️"
                    border_color = "#f59e0b"
                    alt_color = "#66361A"
                elif level.lower() == "advisory":
                    bg_color = "#3959BF"  # Dark blue
                    text_color = "#dde4ed"
                    icon = "ℹ️"
                    border_color = "#3b82f6"
                    alt_color = "#7EA8F1"
                else:
                    bg_color = "#D6DEEB"
                    text_color = "#25354E"
                    icon = "ℹ️"
                    border_color = "#6b7280"
                    alt_color = "#919CAD"

                # Add weather icon if weather-related
                if weather_related:
                    icon = "🌦️"
                
                alerts_html += f"""
                <div style="background: {bg_color}; !important; padding: 15px; 
                            border-radius: 8px; margin: 10px 0; border-left: 4px solid {border_color} !important;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <strong style="color: {text_color};">{icon} {level.upper()} ALERT</strong>
                        <span style="font-size: 0.8em; font-weight: bold; color: {alt_color};">{alert_type.replace('_', ' ').upper()}</span>
                    </div>
                    <div style="font-size: 1.0em; line-height: 1.4; color: {text_color}">{description}</div>
                </div>
                """
            else:
                # Fallback for string format (legacy)
                alerts_html += f"""
                <div style="background: #374151; color: #d1d5db; padding: 15px; 
                            border-radius: 8px; margin: 10px 0; border-left: 4px solid #6b7280;">
                    <strong>ℹ️ INFO:</strong> {alert}
                </div>
                """
        
        # Process recommendations
        recommendations_html = ""
        if recommendations:
            for idx, recommendation in enumerate(recommendations, 1):
                recommendations_html += f"""
                <div style="background: #67c2a8; color: #ebf0ee; padding: 12px; 
                            border-radius: 6px; margin: 8px 0; border-left: 3px solid #10b981;">
                    <div style="font-size: 1.0em; line-height: 1.4;">
                        <strong>💡 Recommendation {idx}:</strong> {recommendation}
                    </div>
                </div>
                """
        
        analysis_html = await UIComponents._render_markdown(monitoring_data.vlm_analysis.analysis)
        
        return f"""
        <div style="background: {colors['bg_primary']}; border-radius: 12px; padding: 20px; margin: 10px 0; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
            <h3 style="color: {colors['text_primary']}; margin: 0 0 20px 0; text-align: left; font-size: 1.3em;">🚨 Traffic Status and Alerts</h3>
            
            {alerts_html}
            
            {f'''
            <div style="margin-top: 20px;">
                <h4 style="color: {colors['text_primary']}; margin: 0 0 12px 0; font-size: 1.2em;">💡 Recommendations</h4>
                {recommendations_html}
            </div>
            ''' if recommendations_html else ''}
            
            <div style="margin-top: 20px; padding: 18px; background: {colors['bg_card']}; border-radius: 8px; box-shadow: {colors['shadow']}; border: 1px solid {colors['border']};">
                <h4 style="color: {colors['text_primary']}; margin: 0 0 12px 0; font-size: 1.2em;">🔎 Analysis Summary:</h4>
                <div style="color: #101010 !important; margin: 0; font-size: 1.0em; line-height: 1.5;">{analysis_html}</div>
            </div>
        </div>
        """

    @staticmethod
    async def create_camera_images(monitoring_data: Optional[MonitoringData]) -> List[Tuple[str, str]]:
        """Create camera images for display in Gradio Gallery"""
        if not monitoring_data or not monitoring_data.camera_images:
            return []
        
        image_list = []
        
        for camera_name, camera_data in monitoring_data.camera_images.items():
            # Handle both CameraData objects and dict structures from API
            if hasattr(camera_data, 'image_base64'):
                # CameraData object
                image_base64 = camera_data.image_base64
                direction = camera_data.direction
                camera_id = camera_data.camera_id
            elif isinstance(camera_data, dict):
                # Dict from API
                image_base64 = camera_data.get('image_base64')
                direction = camera_data.get('direction', 'unknown')
                camera_id = camera_data.get('camera_id', 'unknown')
            else:
                continue
                
            if image_base64:
                try:
                    # Decode base64 image
                    image_bytes = base64.b64decode(image_base64)
                    
                    # Create PIL Image from bytes
                    image = Image.open(io.BytesIO(image_bytes))
                    
                    # Create a caption with camera info
                    caption = f"{direction.upper()} - {camera_id}"
                    
                    # For Gradio Gallery, we need to save the image temporarily or use base64
                    # We'll return the image object and caption
                    image_list.append((image, caption))
                    
                except Exception as e:
                    print(f"Error processing image for {camera_name}: {e}")
                    continue
        
        return image_list
    
    @staticmethod
    async def create_system_info(monitoring_data: Optional[MonitoringData] = None) -> str:
        """Create system information footer with current status"""
        # Use UTC and consistent formatting for both current time and last update
        from datetime import datetime, timezone

        colors = ThemeColors.get_colors()

        # Current time in UTC with date and time (consistent format)
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Get system status information
        last_update = "N/A"
        system_status = "OFFLINE"
        
        if monitoring_data:
            # Prefer a nicely formatted last update using the data loader helper
            try:
                timestamp = datetime.fromisoformat(monitoring_data.timestamp.replace('Z', '+00:00'))
                last_update = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
                # TODO - Show time since last update in minutes/seconds for better understanding
            except Exception as e:
                # Fallback to raw timestamp or current time
                last_update = monitoring_data.timestamp or current_time
            system_status = "ONLINE"
        
        return f"""
        <div style="
            background: {colors['bg_primary']};
            border-radius: 10px;
            padding: 18px;
            margin: 10px 0;
            border: 1px solid {colors['border']};
            box-shadow: {colors['shadow']};
        ">
            <div style="
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                align-items: center;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 13px;
            ">
                <div>
                    <strong style="color: #60a5fa;">System Status:</strong>
                    <span style="color: {'#10b981' if system_status == 'ONLINE' else '#ef4444'};">
                        {'🟢' if system_status == 'ONLINE' else '🔴'} {system_status}
                    </span>
                </div>
                <div>
                    <strong style="color: #60a5fa;">Last Update:</strong>
                    <span style="color: {colors['text_primary']};">{last_update}</span>
                </div>
                <div>
                    <strong style="color: #60a5fa;">Current Time:</strong>
                    <span style="color: {colors['text_primary']};">{current_time}</span>
                </div>
                <div>
                    <strong style="color: #60a5fa;">Dashboard:</strong>
                    <span style="color: #10b981;">RSU Monitor v1.0</span>
                </div>
            </div>
        </div>
        """