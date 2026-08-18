#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Edge AI Skills MCP Server

Dynamically loads tool definitions from mcp_tools.yaml files in each repository
and routes calls to the appropriate provider handler.

Each repo owns its tool definitions (mcp_tools.yaml).
This server discovers, loads, and serves them via MCP protocol.
"""

import asyncio
import functools
import sys
from pathlib import Path

import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from providers import PROVIDER_HANDLERS

# Tool configs live in expose-skill, not in the cloned repos
TOOL_CONFIGS_DIR = Path(__file__).parent / "tool_configs"


def discover_tools() -> tuple[list[Tool], dict]:
    """Discover tools from YAML configs in tool_configs/."""
    tools = []
    handler_map = {}

    for config_file in TOOL_CONFIGS_DIR.glob("*.yaml"):
        with open(config_file) as f:
            config = yaml.safe_load(f)

        namespace = config.get("namespace", config_file.stem)
        provider_handlers = PROVIDER_HANDLERS.get(namespace, {})

        for tool_def in config.get("tools", []):
            tool_id = tool_def["id"]
            full_name = f"{namespace}_{tool_id}"

            tool = Tool(
                name=full_name,
                description=tool_def["description"].strip(),
                inputSchema=tool_def.get("parameters", {"type": "object", "properties": {}}),
            )
            tools.append(tool)

            handler_name = tool_def.get("handler", tool_id)
            if handler_name in provider_handlers:
                handler_map[full_name] = provider_handlers[handler_name]

    return tools, handler_map


app = Server("edge-ai-skills")
TOOLS, HANDLER_MAP = discover_tools()


@app.list_tools()
async def list_tools():
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    handler = HANDLER_MAP.get(name)
    if not handler:
        raise ValueError(f"Unknown tool: {name}")

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, functools.partial(handler, arguments))
    return [TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
