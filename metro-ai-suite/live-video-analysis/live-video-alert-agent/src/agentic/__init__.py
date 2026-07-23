# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Agentic package — MCP client utilities only.
# Action dispatch is delegated to the external alert-agent-service.

from .mcp_client import (
    initialize_mcp_servers,
    shutdown_mcp_servers,
    get_mcp_server_status,
    get_mcp_tools,
    get_mcp_servers,
)

__all__ = [
    "initialize_mcp_servers",
    "shutdown_mcp_servers",
    "get_mcp_server_status",
    "get_mcp_tools",
    "get_mcp_servers",
]
