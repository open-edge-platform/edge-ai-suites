# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import os
import gradio as gr
import threading
import tempfile
from datetime import datetime, timedelta
import time
import logging
from services.api_client import (
    fetch_cameras,
    fetch_events,
    add_rule,
    fetch_rule_responses,
    fetch_rules,
    delete_rule_by_id,
    fetch_search_responses,
    fetch_summary_status,
)
from services.video_processor import process_video
from services.event_utils import display_events
from config import logger
import json

camera_list = []
recent_events = []
# Global state
recent_events = []
event_update_thread = None
stop_event_thread = threading.Event()


def initialize_app():
    """Initialize application and fetch initial data."""
    global camera_list
    logger.info("Initializing app and fetching camera list...")
    camera_list = fetch_cameras()
    return camera_list


def stop_event_updates():
    """Stop any background event polling."""
    global event_update_thread, stop_event_thread
    logger.info("Stopping event update thread...")
    if event_update_thread and event_update_thread.is_alive():
        stop_event_thread.set()
        event_update_thread.join(timeout=2)
        logger.info("Event update thread stopped.")


def cleanup_temp_files():
    """Clean up temporary MP4 files older than 1 hour."""
    logger.info("Cleaning up temp .mp4 files...")
    try:
        temp_dir = tempfile.gettempdir()
        for file in os.listdir(temp_dir):
            if file.endswith(".mp4"):
                full_path = os.path.join(temp_dir, file)
                age = time.time() - os.path.getmtime(full_path)
                if age > 3600:
                    os.remove(full_path)
                    logger.info(f"Deleted: {full_path}")
    except Exception as e:
        logger.error(f"Failed to clean temp files: {e}")


def render_rule_rows(rules, response_output):
    """Render rows of rules with delete buttons."""
    with gr.Column() as rule_column:
        for rule in rules:
            rule_id_state = gr.State(rule["id"])  # Hold rule ID as state

            with gr.Row():
                gr.Textbox(
                    value=rule["id"], label="ID", interactive=False, show_label=False
                )
                gr.Textbox(
                    value=rule.get("camera", ""),
                    label="Camera",
                    interactive=False,
                    show_label=False,
                )
                gr.Textbox(
                    value=rule.get("label", ""),
                    label="Label",
                    interactive=False,
                    show_label=False,
                )
                gr.Textbox(
                    value=rule.get("action", ""),
                    label="Action",
                    interactive=False,
                    show_label=False,
                )

                delete_btn = gr.Button("❌ Delete")
                delete_btn.click(
                    fn=delete_rule_by_id,
                    inputs=[rule_id_state],  # 👈 Pass the rule ID
                    outputs=[response_output],
                )
    return rule_column


polling_threads = {}


def poll_summary_status(summary_id, status_output, stop_event):
    while not stop_event.is_set():
        try:
            raw_response = fetch_summary_status(summary_id)
            logger.info(f"raw_response : {raw_response}")
            if isinstance(raw_response, str):
                if not raw_response.strip():
                    logger.warning(f"Empty response for summary_id={summary_id}")
                    raise ValueError(
                        "Empty response received from fetch_summary_status."
                    )
                logger.info(f"raw_response : {raw_response}")
                response = json.loads(raw_response)
            elif isinstance(raw_response, dict):
                response = raw_response
            else:
                raise ValueError(f"Invalid response type: {type(raw_response)}")

            status = response.get("status", "unknown")
            logger.info(f"Polled summary {summary_id} status: {status}")

            # Format response as markdown
            markdown_output = f"## Summary Status (Auto-Polling)\n\n"
            markdown_output += f"**Summary ID:** `{summary_id}`\n\n"
            for key, value in response.items():
                if key == "status":
                    status_emoji = (
                        "✅"
                        if value == "completed"
                        else "❌" if value == "failed" else "⏳"
                    )
                    markdown_output += f"**Status:** {status_emoji} {value}\n\n"
                else:
                    markdown_output += (
                        f"**{key.replace('_', ' ').title()}:** {value}\n\n"
                    )

            # Safely update the status_output (Gradio Markdown)
            logger.info(f"status_output : {status_output} and markdown_output {markdown_output}")
            status_output=markdown_output

            if status in ("completed", "failed"):
                break

        except Exception as e:
            logger.error(f"Error polling summary status: {e}", exc_info=True)
            error_markdown = f"## Error\n\n❌ **Error fetching status:** {str(e)}"
            status_output =error_markdown
            break

        time.sleep(10)


def extract_summary_id(raw_id):
    if not raw_id:
        return None
    if isinstance(raw_id, dict):
        return list(raw_id.keys())[0]
    return raw_id


def process_and_poll(camera, start, duration, action, status_output):
    result = process_video(camera, start, duration, action)
    if action == "Add to Search":
        return result
    raw_id = result.get("summary_id")
    summary_id = extract_summary_id(raw_id)

    if result["status"] == "success" and summary_id:
        if summary_id in polling_threads:
            polling_threads[summary_id]["stop"].set()

        stop_event = threading.Event()
        thread = threading.Thread(
            target=poll_summary_status,
            args=(summary_id, status_output, stop_event),
            daemon=True,
        )
        thread.start()
        polling_threads[summary_id] = {"thread": thread, "stop": stop_event}

    return result
def wrapper_fn(
    camera,
    start,
    duration,
    action,
    status_output_box,
    previous_summary_id,
):
    now = datetime.now()
    min_time = now - timedelta(hours=24)

    # Ensure start is a datetime object
    if isinstance(start, float):
        start = datetime.fromtimestamp(start)
    elif isinstance(start, int):
        start = datetime.fromtimestamp(float(start))
    elif not isinstance(start, datetime):
        return (
            None,
            gr.update(value="❌ Error: Invalid start time format.", visible=True),
            gr.update(visible=True),
            previous_summary_id,
            gr.update(value=""),
            False
        )

    # Validate start time
    if start > now:
        return (
            None,
            gr.update(value="❌ Error: Start time cannot be in the future.", visible=True),
            gr.update(visible=True),
            previous_summary_id,
            gr.update(value=""),
            False
        )
    elif start < min_time:
        return (
            None,
            gr.update(value="❌ Error: Start time must be within the last 24 hours.", visible=True),
            gr.update(visible=True),
            previous_summary_id,
            gr.update(value=""),
            False
        )

    # Validate duration > 0
    try:
        duration_sec = int(duration)
        if duration_sec <= 0:
            raise ValueError
    except Exception:
        return (
            None,
            gr.update(value="❌ Error: Duration must be a number greater than 0 seconds.", visible=True),
            gr.update(visible=True),
            previous_summary_id,
            gr.update(value=""),
            False
        )

    # Validate that end time is not in the future
    end_time = start + timedelta(seconds=duration_sec)
    if end_time > now:
        return (
            None,
            gr.update(value="❌ Error: End time (start + duration) cannot be in the future.", visible=True),
            gr.update(visible=True),
            previous_summary_id,
            gr.update(value=""),
            False
        )
    # Call processing function
    result_dict = process_and_poll(camera, start, duration, action, status_output_box)

    message = result_dict.get("message", json.dumps(result_dict, indent=2))

    if action == "Summarize":
        raw_summary = result_dict.get("summary_id")
        summary_id = extract_summary_id(raw_summary)
        logger.info("Extracted Summary ID:", summary_id)

        return (
            result_dict,
            gr.update(value=message, visible=True),
            gr.update(visible=True),
            summary_id,
            gr.update(value="Processing..."),
            True
        )
    else:  # Search or other action
        return (
            result_dict,
            gr.update(value=message, visible=True),
            gr.update(visible=True),
            previous_summary_id,
            gr.update(value=""),
            False
        )
# Function to hide toast and close button
def dismiss_toast():
    return gr.update(visible=False), gr.update(visible=False)
# Function to manually refresh summary status
def refresh_summary_status(summary_id):
    if not summary_id:
        return "", gr.update(visible=False), gr.update(visible=False)

    try:
        response = fetch_summary_status(summary_id)
        if isinstance(response, dict):
            # Hide toast and return formatted markdown
            markdown_output = f"## Summary Status\n\n"
            markdown_output += f"**Summary ID:** `{summary_id}`\n\n"
            for key, value in response.items():
                markdown_output += f"**{key.replace('_', ' ').title()}:** {value}\n\n"
            return markdown_output, gr.update(visible=False), gr.update(visible=False)
        else:
            return f"## Summary Status\n\n```json\n{json.dumps(response, indent=2)}\n```", gr.update(visible=False), gr.update(visible=False)

    except Exception as e:
        return f"## Error\n\n❌ **Error fetching status:** {str(e)}", gr.update(visible=True), gr.update(visible=True)

def auto_refresh_summary_status(summary_id):
    if not summary_id:
        return "", gr.update(visible=False), gr.update(visible=False)

    try:
        response = fetch_summary_status(summary_id)
        if isinstance(response, dict):
            markdown_output = f"## Summary Status\n\n"
            markdown_output += f"**Summary ID:** `{summary_id}`\n\n"
            for key, value in response.items():
                markdown_output += f"**{key.replace('_', ' ').title()}:** {value}\n\n"
            # Hide toast on success
            return markdown_output, gr.update(visible=False), gr.update(visible=False)
        else:
            return f"## Summary Status\n\n```json\n{json.dumps(response, indent=2)}\n```", gr.update(visible=False), gr.update(visible=False)
    except Exception as e:
        return f"## Error\n\n❌ **Error fetching status:** {str(e)}", f"❌ Error: {str(e)}", gr.update(visible=True)

def create_ui():
    show_genai_tab = os.getenv("NVR_GENAI", "false").lower() == "true"
    time.sleep(5)  # Ensure the environment is fully initialized
    camera_data = fetch_cameras()
    camera_list = list(camera_data.keys())
    recent_events = []
    def get_labels_for_camera(camera_name):
        # Dummy example mapping camera to labels
        camera_to_labels = {
            "Front Gate": ["person", "car", "dog"],
            "Backyard": ["cat", "person"],
        }

        labels = camera_data.get(camera_name, [])

        return gr.update(choices=labels, value=None)

    def format_summary_responses():
        data = fetch_rule_responses()
        rows = []

        # Check if the response contains an error (e.g., 502 error wrapped in a dict)
        if isinstance(data, dict) and "error" in data:
            return [
                ["-", "-", "❌ Failed to retrieve summary from summarization service"]
            ]

        for rule_id, summaries in data.items():
            if summaries:
                for summary_id, message in summaries.items():
                    rows.append(
                        [rule_id, summary_id, message.get("summary", "No summary text")]
                    )
            else:
                rows.append([rule_id, "", "No summaries available."])

        return rows

    def format_search_responses():
        data = fetch_search_responses()
        rows = []
        for rule_id, results in data.items():
            if results:
                for item in results:
                    video_id = item.get("video_id", "")
                    message = item.get("message", "")
                    if video_id or message:  # Only add if at least one is non-empty
                        rows.append([rule_id, video_id, message])
            else:
                rows.append([rule_id, "", "No search results available."])
        return rows

    with gr.Blocks() as ui:
        gr.Markdown("## NVR Event Router")
        gr.Markdown(
            "Monitor and process events from Frigate VMS using OEP Video Search and Summarization Application."
        )
        summary_id_state = gr.State(None)
        with gr.Tabs():
            # Tab 1: Summarize/Search
            with gr.TabItem("Summarize/Search Clips"):
                with gr.Row():
                    with gr.Column(scale=1):
                        cam_dropdown = gr.Dropdown(
                            choices=camera_list, label="Select Camera"
                        )
                    with gr.Column(scale=1):
                        action_dropdown = gr.Dropdown(
                            choices=["Summarize", "Add to Search"], value="Summarize"
                        )
                    with gr.Column(scale=1):
                        start_input = gr.DateTime(
                            label="Start Time",
                            value=datetime.now()
                        )
                    with gr.Column(scale=1):
                        duration_input = gr.Number(
                            label="Duration (seconds)", precision=0
                        )
                    with gr.Column():
                        with gr.Row():
                            process_btn = gr.Button("Process Video")
                        with gr.Row():
                            refresh_status_btn = gr.Button("🔄 Refresh Status")

                with gr.Row():
                    status_output = gr.Markdown(value="", label="Summary Status")
                polling_timer = gr.Timer(value=5.0, active=False)  # 5 seconds interval, initially inactive

                polling_enabled_state = gr.State(value=False)
                result = gr.JSON(visible=False)

                # Turn timer visibility ON or OFF based on state
                polling_enabled_state.change(
                    fn=lambda enabled: gr.update(active=enabled),
                    inputs=[polling_enabled_state],
                    outputs=[polling_timer],
                )

                with gr.Row():
                    toast_output = gr.Textbox(
                        visible=False,
                        interactive=False,
                        label="Status Message",
                        scale=5,
                    )
                    close_toast_btn = gr.Button("❌", visible=False, scale=1)
                
                # Register the tick event
                polling_timer.tick(
                    fn=auto_refresh_summary_status,
                    inputs=[summary_id_state],
                    outputs=[status_output, toast_output, close_toast_btn],
                )

                process_btn.click(
                    fn=wrapper_fn,
                    inputs=[
                        cam_dropdown,
                        start_input,
                        duration_input,
                        action_dropdown,
                        status_output,
                        summary_id_state,
                    ],
                    outputs=[
                        result,
                        toast_output,
                        close_toast_btn,
                        summary_id_state,
                        status_output,
                        polling_enabled_state
                    ],
                )

                close_toast_btn.click(
                    fn=dismiss_toast, inputs=[], outputs=[toast_output, close_toast_btn]
                )

                refresh_status_btn.click(
                    fn=refresh_summary_status,
                    inputs=[summary_id_state],
                    outputs=[status_output, toast_output, close_toast_btn],
                )

            if show_genai_tab:
                # Tab 2: AI-Powered Event Viewer
                with gr.TabItem("AI-Powered Event Viewer") as event_viewer_tab:

                    with gr.Row():
                        with gr.Column(scale=1):
                            cam_dropdown_view = gr.Dropdown(
                                choices=camera_list,
                                label="Select Camera",
                                interactive=True,
                                container=True,
                            )
                        with gr.Column(scale=2):
                            gr.HTML("")  # Placeholder for spacing or future use
                    with gr.Row():
                        with gr.Column(scale=2):
                            events_table = gr.Dataframe(
                                headers=[
                                    "Label",
                                    "Start Time",
                                    "End Time",
                                    "Top Score",
                                    "Description",
                                    "Thumbnail",
                                ],
                                datatype=["str", "str", "str", "str", "str", "html"],
                                label="Events",
                                interactive=False,
                                elem_id="events-table",
                                elem_classes="events-table",
                            )
                            gr.HTML(
                                """
                            <style>
                            .events-table table td:nth-child(5) {
                                white-space: normal !important;
                                word-wrap: break-word !important;
                                max-width: 300px;
                            }
                            .events-table table td:nth-child(6) {
                                text-align: center;
                                vertical-align: middle;
                            }
                            .events-table table td:nth-child(6) img {
                                border-radius: 4px;
                                border: 1px solid #ddd;
                            }
                            </style>
                            """
                            )
                    
                    def fetch_and_display_events(camera):
                        nonlocal recent_events
                        recent_events = fetch_events(camera)
                        return display_events(recent_events)

                    cam_dropdown_view.change(
                        fn=fetch_and_display_events,
                        inputs=[cam_dropdown_view],
                        outputs=[events_table],
                    )
                        # 👇 Trigger fetch when tab is opened
                    event_viewer_tab.select(
                        fn=fetch_and_display_events,
                        inputs=[cam_dropdown_view],
                        outputs=[events_table],
                    )

            # Tab 3: Auto-Route Rules
            with gr.TabItem("Auto-Route Events"):
                with gr.Row():
                    camera_dropdown = gr.Dropdown(
                        choices=camera_list,
                        value=camera_list[0] if camera_list else None,
                        label="Select Camera"
                    )

                    label_filter = gr.Dropdown(
                        choices=[],
                        value=None,
                        label="Detection Labels"
                    )

                    action_dropdown_auto = gr.Dropdown(
                        choices=["Summarize", "Add to Search"],
                        value="Summarize",
                        label="Select Action",
                    )
                    add_rule_btn = gr.Button("➕ Add Rule")

                # 🔄 Trigger label load when dropdown loads (first time)
                ui.load(
                    fn=get_labels_for_camera,
                    inputs=[camera_dropdown],
                    outputs=[label_filter]
                )

                # 🔄 Also update labels when dropdown changes
                camera_dropdown.change(
                    fn=get_labels_for_camera,
                    inputs=[camera_dropdown],
                    outputs=[label_filter]
                )


                with gr.Row():
                    add_rule_alert = gr.Textbox(label="Status", visible=False)

                # 🔘 Callback to add rule and show alert
                def add_rule_callback(camera, label, action):
                    resp = add_rule(camera, label, action)
                    message = resp
                    return gr.update(value=message, visible=True)

                # ⏳ Hide alert after delay
                def delayed_hide():
                    time.sleep(5)
                    return gr.update(visible=False)

                # 🚀 Show alert on rule add
                # 🔘 Combined logic: show message, sleep, hide
                def add_rule_with_auto_hide(camera, label, action):
                    resp = add_rule(camera, label, action)
                    message = (
                        resp.get("message") if isinstance(resp, dict) else str(resp)
                    )

                    # Show message
                    yield gr.update(value=message, visible=True)

                    # Keep it visible for 5 seconds
                    time.sleep(3)

                    # Hide message
                    yield gr.update(visible=False)

                add_rule_btn.click(
                    fn=add_rule_with_auto_hide,
                    inputs=[camera_dropdown, label_filter, action_dropdown_auto],
                    outputs=[add_rule_alert],
                )

                # ⏱️ Automatically hide after 5 seconds
                # add_rule_event.then(
                #     fn=delayed_hide,
                #     inputs=[],
                #     outputs=[add_rule_alert]
                # )

                # Rules Table Section
                gr.Markdown("### Current Rules")
                delete_status = gr.Textbox(label="Deletion Status", visible=False)
                rules_table = gr.Dataframe(
                    headers=["ID", "Camera", "Label", "Action", "Delete"],
                    datatype=["str", "str", "str", "str", "str"],
                    interactive=False,
                )
                refresh_rules_btn = gr.Button("🔄 Refresh Rules")

                def load_rules():
                    rules = fetch_rules()
                    return [
                        [r["id"], r["camera"], r["label"], r["action"], "🗑️ Delete"]
                        for r in rules
                    ]

                def delete_selected_rule(evt: gr.SelectData):

                    if evt.value == "🗑️ Delete":
                        try:
                            # Get the full row data from row_value
                            selected_row = evt.row_value

                            # Extract rule ID (first column)
                            rule_id = selected_row[0]

                            # Delete the rule
                            result = delete_rule_by_id(rule_id)
                            return result, load_rules()

                        except Exception as e:
                            logger.error(f"Error deleting rule: {str(e)}")
                            return f"❌ Error: {str(e)}", load_rules()

                    return "Click the delete icon (🗑️) to remove a rule", load_rules()

                # Event handlers
                refresh_rules_btn.click(fn=load_rules, outputs=[rules_table])

                rules_table.select(
                    fn=delete_selected_rule, outputs=[delete_status, rules_table]
                )

                # Initial load
                ui.load(fn=load_rules, outputs=[rules_table])
                gr.Markdown("### Rule Responses")

                summary_response_table = gr.Dataframe(
                    headers=["Rule ID", "Summary ID", "Message"],
                    datatype=["str", "str", "str"],
                    label="Summary Responses",
                    interactive=False,
                )

                gr.Button("🔄 Refresh Summary Responses").click(
                    fn=format_summary_responses, outputs=[summary_response_table]
                )

                search_response_table = gr.Dataframe(
                    headers=["Rule ID", "Video ID", "Message"],
                    datatype=["str", "str", "str"],
                    label="Search Responses",
                    interactive=False,
                )
                gr.Button("🔍 Refresh Search Responses").click(
                    fn=format_search_responses, outputs=[search_response_table]
                )

    return ui
