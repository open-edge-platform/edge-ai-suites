# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import sys
import time
import asyncio
from functools import partial
from typing import Any, Optional

import gradio as gr

from config import APP_DETAILS, INITIAL_MAP_HTML
from services.route_service import RouteService
from utils.logging_config import setup_logging
from schema import QueueItem
from css import style


logger = setup_logging(logger_name=__name__)

# Queue for  passing data between agent and UI
data_queue: asyncio.Queue = asyncio.Queue()
agent_is_not_stopped: bool = True  # Global flag to control agent execution


async def reset_route_optimizing_agent() -> None:
    """Function to stop the route optimizing agent by setting the global flag to False and clearing the data queue."""

    global agent_is_not_stopped
    agent_is_not_stopped = False
    logger.debug(
        "Resetting Route Optimizing Agent. Setting agent_is_not_stopped to False and clearing the data queue..."
    )
    while not data_queue.empty():
        try:
            data_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

    await data_queue.put(None)


async def agent_running_callback(
    custom_thinking_output: str = "",
) -> tuple[
    gr.Dropdown, gr.Dropdown, gr.Button, gr.Button, gr.Textbox, gr.Markdown, gr.HTML
]:
    """Callback to toggle UI components based on agent running state"""

    logger.debug("Updating UI components based on agent running state...")
    start_dropdown_state = gr.Dropdown(interactive=not agent_is_not_stopped)
    end_dropdown_state = gr.Dropdown(interactive=not agent_is_not_stopped)
    search_btn_state = gr.Button(interactive=not agent_is_not_stopped)
    stop_btn_state = gr.Button(interactive=agent_is_not_stopped)

    if agent_is_not_stopped:
        logger.debug(
            "Agent is running. Updating thinking output with custom message or default message..."
        )
        thinking_output_state = gr.Markdown(
            value="## Planning Route... \n\n  ### This may take a few moments ..."
        )
    else:
        logger.debug(
            "Agent is not running. Updating thinking output with custom message or default app details..."
        )
        thinking_output_state = (
            gr.Markdown(value=custom_thinking_output)
            if custom_thinking_output
            else gr.Markdown()
        )

    agent_status_state = gr.Textbox(
        value="Active - Planning Route..." if agent_is_not_stopped else "Inactive",
        elem_classes=[
            "status-indicator",
            "status-active" if agent_is_not_stopped else "status-inactive",
        ],
    )

    map_html = gr.HTML()

    return (
        start_dropdown_state,
        end_dropdown_state,
        search_btn_state,
        stop_btn_state,
        agent_status_state,
        thinking_output_state,
        map_html,
    )


async def get_direct_route(
    source: str, destination: str, route_service: RouteService
) -> Any:
    """
    Uses RouteService to trigger RoutePlanner agent and gets direct route between source and destination.
    """
    try:
        logger.debug(
            f"Getting direct route for Source: {source} and Destination: {destination}..."
        )
        yield (
            gr.Button(interactive=False),
            "# Loading direct route ...",
            INITIAL_MAP_HTML,
        )
        res, error = route_service.validate_route_request(source, destination)
        if not res:
            thinking_message = f"## ⚠️ {error}"
            yield (
                gr.Button(interactive=True),
                thinking_message,
                "<div class='no-map-style'>Please select valid source and destination to load the route.</div>",
            )
        else:
            # Get direct shortest route
            distance, main_route_map = await route_service.create_direct_route_map(
                source, destination
            )

            thinking_message = (
                f"## Route: {source} -> {destination}\n\n #### Direct route "
                + f"loaded by analyzing shortest route between {source} and {destination}."
                + f" \n\n ### Total Distance : {distance:.2f} Kms \n\n"
            )
            yield gr.Button(interactive=True), thinking_message, main_route_map

    except Exception as e:
        logger.error(f"Error getting direct route: {e}")
        error_message = (
            "<div class='error-while-thinking'>❌ Error loading route!</div>"
        )
        yield gr.Button(interactive=True), error_message, INITIAL_MAP_HTML


async def start_route_optimizer_agent(
    source: str, destination: str, route_service: RouteService
) -> None:
    """
    Uses RouteService to trigger RoutePlanner agent and gets optimized route.
    """

    global agent_is_not_stopped
    try:
        is_valid, error_message = route_service.validate_route_request(
            source, destination
        )
        if not is_valid:
            raise ValueError(error_message)

        agent_is_not_stopped = True
        await data_queue.put(
            None
        )  # Start with None, so the check_updates function can make some UI updates based on it.
        while agent_is_not_stopped:
            logger.debug(
                "Route Optimizer Agent is running. Creating alternate route map..."
            )
            logger.debug("Value of agent_is_not_stopped" + str(agent_is_not_stopped))
            # Start planning the route
            (
                next_data_source,
                route_issue,
                distance,
                is_sub_optimal,
                optimized_route_map,
            ) = await route_service.create_alternate_route_map(source, destination)

            logger.debug(
                f"Next data source: {next_data_source}, Route issue: {route_issue}, Distance: {distance}, Is sub-optimal: {is_sub_optimal}"
            )

            thinking_message: str = f"\n #### Route: {source} -> {destination}\n\n"

            if is_sub_optimal:
                thinking_message += "## Sub-optimal Route Found. \n"

            if route_issue and distance:
                thinking_message += (
                    "### Route Updated due to "
                    + f"{route_issue} \n\n ##### Total Distance for Updated Route : {distance:.2f} Kms\n\n"
                )
            elif distance == 0.0 and route_issue:
                thinking_message += f"## {route_issue} \n\n"
            else:
                thinking_message = (
                    "### No traffic, weather issues or congestions found on current route."
                    + f"\n\n ##### Total Distance : {distance:.2f} Kms \n\n"
                )

            # Set message to show Real-time Agent actions
            agent_status_msg = f"Active - Analyzing {next_data_source} ..."

            await data_queue.put(
                QueueItem(
                    timestamp=time.time(),
                    agent_status=agent_status_msg,
                    thinking_output=thinking_message,
                    map_output=optimized_route_map,
                )
            )
            await asyncio.sleep(
                10
            )  # Sleep for some time before next update to simulate real-time monitoring and updating of route.

    except Exception as e:
        agent_is_not_stopped = False
        if isinstance(e, asyncio.CancelledError):
            logger.info("Route optimization task was cancelled.")
            return

        if isinstance(e, ValueError):
            logger.error(f"Validation error : {e}")
            error_message = (
                f"<span class='error-while-thinking'>❌ Error: {str(e)}</span>"
            )
        else:
            logger.error(f"Error in Route Optimization Agent: {e}")
            error_message = "<span class='error-while-thinking'>❌ Fatal Error! \n\n #### Route Planning Stopped! Please try again.</span>"

        await data_queue.put(
            QueueItem(
                timestamp=time.time(),
                agent_status="Error",
                thinking_output=error_message,
                map_output=route_service.get_fallback_map_html(
                    "Can not load route map due to some error!"
                ),
            )
        )


async def check_for_agent_updates() -> Any:
    """
    Checks the queue for updates from the agent.
    Yields updated components with new values whenever available.
    """

    # Initialize with agent not running state. This cleans the queue, resets the global flag and
    # updates the UI components based on no data in the queue.
    await reset_route_optimizing_agent()

    # async while loop to keep checking for updates without blocking the main thread
    while True:
        try:
            logger.info("Checking for agent updates...")
            update: Optional[QueueItem] = await data_queue.get()
            if update:
                if update.agent_status == "Error":
                    logger.warning(
                        "Agent encountered an error. It will be forcefully stopped!"
                    )
                    # Force stop the agent and update the UI accordingly- UI shows the error instead of just showing "Agent Stopped" message.
                    await reset_route_optimizing_agent()
                    yield await agent_running_callback(update.thinking_output)
                else:
                    yield (
                        gr.Dropdown(),  # no change to dropdowns
                        gr.Dropdown(),
                        gr.Button(),  # no change to buttons
                        gr.Button(),
                        gr.Textbox(value=update.agent_status),
                        gr.Markdown(value=update.thinking_output),
                        gr.HTML(value=update.map_output),
                    )
            else:
                # If update is None, it means the agent has been forcefully stopped or it has just started.
                logger.warning(
                    "Agent has been stopped or not running or have just started!"
                )
                yield await agent_running_callback()

        except Exception as e:
            logger.error(f"Error checking for agent updates: {e}")
            error_message = "<span class='error-while-thinking'> ⚠️ Some error occurred while loading route updates! \n\n #### Will continue re-trying to load updates...</span>"
            yield await agent_running_callback(error_message)
            await asyncio.sleep(3)  # wait for a few seconds before retrying
            continue


def create_gradio_interface() -> gr.Blocks:
    """Create and configure the Gradio interface"""

    # Get default locations
    route_service = RouteService()
    location_choices = route_service.locations

    with gr.Blocks(
        title="Dynamic Route Updates with Agentic AI", theme=gr.themes.Soft(), css=style
    ) as app:
        gr.Markdown("# Route Planner - Agentic AI based Commuter Support System")
        gr.Markdown(
            "Get an optimal route using coordinated intersection agents that analyze **real GPX route data**, weather, live traffic, and road events."
        )

        gr.Markdown("### Quick Route Search")
        with gr.Row(elem_classes=["horizontal-search"]):
            with gr.Column(scale=3):
                start_dropdown = gr.Dropdown(
                    choices=[("Select Source", "")] + location_choices[:1],
                    label="From",
                    value="",
                    container=True,
                )
            with gr.Column(scale=3):
                end_dropdown = gr.Dropdown(
                    choices=[("Select Destination", "")] + location_choices[-1:],
                    label="To",
                    value="",
                    container=True,
                )

            with gr.Column(scale=1):
                with gr.Row():
                    with gr.Column(scale=1):
                        search_btn = gr.Button(
                            "Start Route Planning",
                            variant="primary",
                            size="lg",
                            elem_classes=["search-button"],
                            interactive=True,
                        )
                        stop_agent_btn = gr.Button(
                            "Stop Route Planning",
                            variant="stop",
                            elem_classes=["stop-button"],
                            interactive=False,
                        )

        # Thinking Output and Route Map side by side
        with gr.Row(elem_classes=["main-content-row"]):
            with gr.Column(scale=1):
                agent_status_tb = gr.Textbox(
                    label="AI Agent Planning Status",
                    value="Inactive",
                    elem_classes=["status-indicator", "status-inactive"],
                    interactive=False,
                )
                thinking_output_md = gr.Markdown(
                    label="AI Agent Thinking Process",
                    value=APP_DETAILS,
                    elem_classes=["thinking-output"],
                )

            with gr.Column(scale=2):
                with gr.Column():
                    map_output_html = gr.HTML(
                        label="Route Map",
                        value=INITIAL_MAP_HTML,
                        elem_id="route-map",
                        elem_classes=["map-container"],
                    )

        # Augment the functions with route_service dependency using partial, as gradio event handlers only accept UI components.
        get_direct_route_partial = partial(
            get_direct_route, route_service=route_service
        )
        start_route_optimizer_agent_partial = partial(
            start_route_optimizer_agent, route_service=route_service
        )

        # Trigger direct route display, once start and end locations are selected.
        start_dropdown.change(
            fn=get_direct_route_partial,
            inputs=[start_dropdown, end_dropdown],
            outputs=[search_btn, thinking_output_md, map_output_html],
        )
        end_dropdown.change(
            fn=get_direct_route_partial,
            inputs=[start_dropdown, end_dropdown],
            outputs=[search_btn, thinking_output_md, map_output_html],
        )

        # Connect the search button with initiating the Route Planner agent and update UI components accordingly
        search_btn.click(
            fn=start_route_optimizer_agent_partial,
            inputs=[start_dropdown, end_dropdown],
            outputs=[],
        )

        # Connect the stop button to stop the agent and update the UI accordingly
        stop_agent_btn.click(
            fn=reset_route_optimizing_agent,
            inputs=[],
            outputs=[],
        )

        # Look of agent updates forever without blocking
        app.load(
            fn=check_for_agent_updates,
            inputs=None,
            outputs=[
                start_dropdown,
                end_dropdown,
                search_btn,
                stop_agent_btn,
                agent_status_tb,
                thinking_output_md,
                map_output_html,
            ],
        )

    return app


def main():
    try:
        import os

        # Get configuration from environment variables
        server_name = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
        server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))

        server_config = {
            "server_name": server_name,
            "server_port": server_port,
            "share": False,
            "show_error": True,
            "quiet": False,
        }
        logger.info(
            f"Starting Route Planner application on {server_name}:{server_port}..."
        )
        app = create_gradio_interface()
        app.queue(default_concurrency_limit=9, max_size=20)
        app.launch(**server_config)
    except KeyboardInterrupt:
        logger.info("Application interrupted by user. Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error starting the application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
