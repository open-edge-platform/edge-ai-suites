# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.config import settings
from src.schemas.monitor import AlertConfig
from src.agentic.mcp_client import get_tool_defaults
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from src.agentic.adk_common import create_adk_model, create_runner
from src.agentic.adk_common import run_agent_prompt

logger = logging.getLogger(__name__)


_CONTEXT_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

_TOOLS_CONFIG_FILE = Path("resources/tools.json")
_TOOL_TIMEOUT = 10.0  # Per-tool execution timeout in seconds


def _load_tools_config() -> Tuple[Dict[str, Callable], List[dict]]:
    """
    Load tool registry from external JSON config file.
    
    Returns (tool_map, tool_schemas) where:
      - tool_map: {name: async_callable}
      - tool_schemas: OpenAI-compatible function schemas for LLM dispatch
    """
    tool_map: Dict[str, Callable] = {}
    tool_schemas: List[dict] = []

    if not _TOOLS_CONFIG_FILE.exists():
        logger.warning(f"Tools config not found: {_TOOLS_CONFIG_FILE} — using defaults")
        return {}, []

    try:
        with open(_TOOLS_CONFIG_FILE) as f:
            config = json.load(f)
    except (json.JSONDecodeError, IOError) as exc:
        logger.error(f"Failed to load tools.json: {exc} — using defaults")
        return {}, []

    for tool in config:
        name = tool.get("name")
        if not name:
            continue

        # Check if tool is enabled
        if not tool.get("enabled", True):
            logger.info(f"Tool '{name}' is disabled in config — skipping")
            continue

        # Check required environment variables
        requires_env = tool.get("requires_env", [])
        missing = [e for e in requires_env if not os.getenv(e)]
        if missing:
            logger.debug(f"Tool '{name}' missing env vars {missing} — will skip at runtime")
            # Still register it; tool itself handles missing config gracefully

        # Dynamic import
        try:
            module_path = tool.get("module")
            func_name = tool.get("function")
            if not module_path or not func_name:
                logger.warning(f"Tool '{name}' missing module/function — skipping")
                continue

            module = importlib.import_module(module_path)
            fn = getattr(module, func_name)
            tool_map[name] = fn

            # Build OpenAI-compatible schema
            tool_schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description", f"Execute {name} action"),
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            })
            logger.debug(f"Loaded tool: {name} from {module_path}.{func_name}")

        except (ImportError, AttributeError) as exc:
            logger.error(f"Failed to load tool '{name}': {exc}")
            continue

    logger.info(f"Loaded {len(tool_map)} tools from {_TOOLS_CONFIG_FILE}")
    return tool_map, tool_schemas


_TOOL_MAP, _TOOL_SCHEMAS = _load_tools_config()

# MCP tools are merged in at runtime after MCP initialization
_MCP_TOOL_MAP: Dict[str, Callable] = {}
_MCP_TOOL_SCHEMAS: List[dict] = []
_MCP_TOOL_LOCK = threading.Lock()


def register_mcp_tools(tool_map: Dict[str, Callable], tool_schemas: List[dict]):
    """
    Register MCP tools with the alert agent.
    
    Called by main.py after MCP initialization.
    MCP tools are kept separate and merged during dispatch.
    """
    global _MCP_TOOL_MAP, _MCP_TOOL_SCHEMAS
    with _MCP_TOOL_LOCK:
        _MCP_TOOL_MAP = tool_map
        _MCP_TOOL_SCHEMAS = tool_schemas
    logger.info(f"Registered {len(tool_map)} MCP tools with AlertActionAgent")


def clear_mcp_tools():
    """Clear registered MCP tools (called during MCP shutdown/reload)."""
    global _MCP_TOOL_MAP, _MCP_TOOL_SCHEMAS
    with _MCP_TOOL_LOCK:
        _MCP_TOOL_MAP = {}
        _MCP_TOOL_SCHEMAS = []


def get_all_tools() -> Tuple[Dict[str, Callable], List[dict]]:
    """
    Get combined tool map and schemas (built-in + MCP).
    
    Returns (tool_map, tool_schemas) for all available tools.
    """
    with _MCP_TOOL_LOCK:
        combined_map = {**_TOOL_MAP, **_MCP_TOOL_MAP}
        combined_schemas = _TOOL_SCHEMAS + _MCP_TOOL_SCHEMAS
    return combined_map, combined_schemas


def reload_tools() -> int:
    """
    Reload built-in tools from tools.json at runtime.
    
    Returns the number of built-in tools loaded.
    Note: MCP tools are reloaded separately via /mcp/reload endpoint.
    """
    global _TOOL_MAP, _TOOL_SCHEMAS
    _TOOL_MAP, _TOOL_SCHEMAS = _load_tools_config()
    return len(_TOOL_MAP)


def get_available_tools() -> List[dict]:
    """
    Return list of all available tools with their metadata.
    
    Includes both built-in tools and MCP tools.
    Useful for API introspection (GET /tools endpoint).
    """
    result = []
    
    # Built-in tools
    for schema in _TOOL_SCHEMAS:
        func = schema.get("function", {})
        result.append({
            "name": func.get("name"),
            "description": func.get("description"),
            "enabled": func.get("name") in _TOOL_MAP,
            "source": "builtin",
        })
    
    # MCP tools
    for schema in _MCP_TOOL_SCHEMAS:
        func = schema.get("function", {})
        result.append({
            "name": func.get("name"),
            "description": func.get("description"),
            "enabled": func.get("name") in _MCP_TOOL_MAP,
            "source": "mcp",
        })
    
    return result


class AlertActionAgent:
    """
    Dispatches actions when an alert fires.

    When USE_ADK=true, uses the Google ADK framework backed by the local OVMS
    endpoint (LLM_URL).  When false, falls back to rule-based dispatch.
    """

    def __init__(self, use_adk: Optional[bool] = None):
        self._use_adk = use_adk if use_adk is not None else settings.USE_ADK
        self._adk_runner = None
        self._session_service = None
        self._known_sessions: set = set()
        # Per-stream call counters for periodic session reset
        self._stream_call_counts: Dict[str, int] = {}
        # Max calls per stream session before context is reset
        self._max_session_calls: int = 5

        if self._use_adk:
            self._init_adk()
        else:
            logger.info("AlertActionAgent initialised in rule-based mode")

    def _init_adk(self, preserve_sessions: bool = False):
        """Initialise the Google ADK runner backed by local OVMS via LiteLLM.

        When preserve_sessions=True the existing session service is reused so
        that in-flight sessions survive a tool-list refresh.
        """
        try:
            if not settings.LLM_URL:
                logger.warning(
                    "USE_ADK=true but LLM_URL is not set — "
                    "falling back to rule-based mode"
                )
                self._use_adk = False
                return

            adk_model = create_adk_model()
            logger.info(
                f"ADK using local OVMS (url={settings.LLM_URL} "
                f"model={settings.LLM_MODEL})"
            )

            all_tools, _ = get_all_tools()
            tool_names = ", ".join(all_tools.keys()) or "none loaded"

            instruction = (
                "You are an alert action agent for a live video surveillance system.\n\n"
                f"AVAILABLE TOOLS: {tool_names}\n\n"
                "RULES:\n"
                "1. ALWAYS invoke log_alert.\n"
                "2. Invoke the tools from configured_tools that fit the alert context.\n"
                "3. If escalated=true, invoke more tools (webhook, mqtt).\n"
                "4. Use MCP tools (mcp_ prefix) when they can enrich the response.\n"
                "Return a one-line summary of actions taken."
            )

            adk_tools = [FunctionTool(fn) for fn in all_tools.values()]

            agent = LlmAgent(
                name="alert_action_agent",
                model=adk_model,
                description="Processes video alert detections and dispatches actions",
                instruction=instruction,
                tools=adk_tools,
            )

            # Reuse existing session service when refreshing tools so that
            reuse_svc = self._session_service if preserve_sessions else None
            self._adk_runner, self._session_service = create_runner(
                agent, "live-video-alert-agent", session_service=reuse_svc,
            )
            if not preserve_sessions:
                self._known_sessions.clear()

            logger.info(f"AlertActionAgent initialised with ADK (model=local:{settings.LLM_MODEL})")

        except ImportError as exc:
            logger.warning(
                f"google-adk not installed or import failed ({exc}) — "
                "falling back to rule-based mode"
            )
            self._use_adk = False
        except Exception as exc:
            logger.error(f"ADK init error: {exc} — falling back to rule-based mode")
            self._use_adk = False

    def reinit_adk(self):
        """Re-initialise the ADK runner with the current tool set.

        Call after MCP tools are registered so the agent instruction and
        FunctionTool list include all available tools.  The existing session
        service is preserved so in-flight sessions are not disrupted.
        """
        if not self._use_adk:
            return
        logger.info("Re-initialising ADK agent with updated tool set ...")
        self._init_adk(preserve_sessions=True)

    def clear_sessions_for_streams(self, stream_ids: set) -> None:
        """Drop ADK session state for the given stream IDs
        """
        for stream_id in stream_ids:
            session_id = f"stream_{stream_id}".replace(" ", "_")
            self._known_sessions.discard(session_id)
            self._stream_call_counts.pop(stream_id, None)
        if stream_ids:
            logger.debug(
                f"Cleared ADK sessions for streams: {stream_ids}"
            )

    async def dispatch(
        self,
        stream_id: str,
        alert_cfg: AlertConfig,
        answer: str,
        reason: str,
        consecutive_count: int = 1,
        escalated: bool = False,
        snapshot_path: Optional[str] = None,
    ) -> List[str]:
        """
        Execute actions for a triggered alert.

        Returns a list of tool names that were successfully invoked.
        """
        if answer != "YES":
            return []

        if self._use_adk and self._adk_runner:
            logger.info(
                f"[DISPATCH] mode=adk-local stream={stream_id} alert={alert_cfg.name} "
                f"escalated={escalated}"
            )
            return await self._dispatch_adk(
                stream_id, alert_cfg, answer, reason,
                consecutive_count, escalated, snapshot_path,
            )
        else:
            logger.info(
                f"[DISPATCH] mode=rule_based stream={stream_id} alert={alert_cfg.name} "
                f"escalated={escalated}"
            )
            return await self._dispatch_rule_based(
                stream_id, alert_cfg, answer, reason,
                consecutive_count, escalated, snapshot_path,
            )

    async def _dispatch_rule_based(
        self,
        stream_id: str,
        alert_cfg: AlertConfig,
        answer: str,
        reason: str,
        consecutive_count: int,
        escalated: bool,
        snapshot_path: Optional[str],
    ) -> List[str]:
        """
        Directly invoke the tools listed in alert_cfg.tools (and escalation
        tools if applicable) without an LLM reasoning step.
        """
        tool_names: List[str] = list(alert_cfg.tools)
        if "log_alert" not in tool_names:
            tool_names.insert(0, "log_alert")
        if escalated and alert_cfg.escalation:
            for t in alert_cfg.escalation.additional_tools:
                if t not in tool_names:
                    tool_names.append(t)
        return await self._execute_tool_list(
            tool_names, stream_id, alert_cfg, answer, reason,
            consecutive_count, escalated, snapshot_path,
        )

    async def _execute_tool_list(
        self,
        tool_names: List[str],
        stream_id: str,
        alert_cfg: AlertConfig,
        answer: str,
        reason: str,
        consecutive_count: int,
        escalated: bool,
        snapshot_path: Optional[str],
    ) -> List[str]:
        """
        Execute a specific list of tools, building all kwargs automatically.
        Shared by rule-based and local-LLM dispatch modes.
        """
        names = list(tool_names)
        if "log_alert" not in names:
            names.insert(0, "log_alert")

        common_ctx = {
            "stream_id": stream_id,
            "alert_name": alert_cfg.name,
            "answer": answer,
            "reason": reason,
            "consecutive_count": consecutive_count,
            "escalated": escalated,
            "snapshot_path": snapshot_path,
        }

        # Get combined tool map (built-in + MCP)
        all_tools, _ = get_all_tools()

        # --- Prepare all tool calls (synchronous kwarg building) ---
        prepared: List[Tuple[str, Callable, dict]] = []
        for tool_name in names:
            fn = all_tools.get(tool_name)
            if fn is None:
                logger.warning(f"Unknown tool '{tool_name}' — skipped")
                continue
            try:
                if tool_name.startswith("mcp_"):
                    configured_args = alert_cfg.tool_arguments.get(tool_name, {})
                    if configured_args:
                        kwargs = _render_tool_arguments(configured_args, common_ctx)
                    else:
                        kwargs = _render_tool_arguments(
                            get_tool_defaults(tool_name), common_ctx,
                        )
                else:
                    kwargs = _build_tool_kwargs(
                        tool_name, common_ctx, consecutive_count, escalated, snapshot_path,
                    )
                    override_args = _render_tool_arguments(
                        alert_cfg.tool_arguments.get(tool_name, {}),
                        common_ctx,
                    )
                    if override_args:
                        kwargs.update(override_args)
                prepared.append((tool_name, fn, kwargs))
            except Exception as exc:
                logger.error(f"Failed to prepare tool '{tool_name}': {exc}")

        # --- Execute all tools in parallel with per-tool timeout ---
        async def _run_one(name: str, fn: Callable, kwargs: dict) -> Tuple[str, bool]:
            try:
                result = await asyncio.wait_for(fn(**kwargs), timeout=_TOOL_TIMEOUT)
                logger.debug(f"Tool '{name}' result: {result}")
                return name, result.get("status") != "error"
            except asyncio.TimeoutError:
                logger.error(f"Tool '{name}' timed out after {_TOOL_TIMEOUT}s")
                return name, False
            except Exception as exc:
                logger.error(f"Tool '{name}' raised: {exc}")
                return name, False

        results = await asyncio.gather(
            *[_run_one(n, f, k) for n, f, k in prepared]
        )
        return [name for name, ok in results if ok]

    async def _dispatch_adk(
        self,
        stream_id: str,
        alert_cfg: AlertConfig,
        answer: str,
        reason: str,
        consecutive_count: int,
        escalated: bool,
        snapshot_path: Optional[str],
    ) -> List[str]:
        """
        Feed alert context into the ADK agent and let it decide tool calls.
        """
        try:
            # --- per-stream session management ---
            session_id = f"stream_{stream_id}".replace(" ", "_")
            count = self._stream_call_counts.get(stream_id, 0) + 1
            self._stream_call_counts[stream_id] = count

            # Periodic reset: delete the session 
            if count > self._max_session_calls and session_id in self._known_sessions:
                try:
                    await self._session_service.delete_session(
                        app_name="live-video-alert-agent",
                        user_id="system",
                        session_id=session_id,
                    )
                except Exception:
                    pass  # best-effort; create_session below will overwrite
                self._known_sessions.discard(session_id)
                self._stream_call_counts[stream_id] = 1
                logger.debug(f"Reset ADK session for stream '{stream_id}'")

            logger.info(
                f"[ADK] Sending to ADK agent — stream={stream_id} "
                f"alert={alert_cfg.name} model={settings.LLM_MODEL} "
                f"session={session_id}"
            )

            prompt = (
                f"Alert detection result:\n"
                f"  stream_id: {stream_id}\n"
                f"  alert_name: {alert_cfg.name}\n"
                f"  answer: {answer}\n"
                f"  reason: {reason}\n"
                f"  consecutive_count: {consecutive_count}\n"
                f"  escalated: {escalated}\n"
                f"  snapshot_path: {snapshot_path or 'none'}\n"
                f"  configured_tools: {alert_cfg.tools}\n"
                f"\nPlease handle this alert appropriately."
            )

            text_response, invoked_tools = await run_agent_prompt(
                runner=self._adk_runner,
                session_service=self._session_service,
                session_id=session_id,
                prompt=prompt,
                timeout=settings.LLM_TIMEOUT,
                known_sessions=self._known_sessions,
            )

            if invoked_tools:
                logger.info(
                    f"ADK agent invoked tools for [{stream_id}][{alert_cfg.name}]: "
                    f"{invoked_tools}"
                )
                return invoked_tools

            all_tools, _ = get_all_tools()
            tool_names = list(alert_cfg.tools)
            if text_response:
                for name in all_tools:
                    if name not in tool_names and name in text_response:
                        tool_names.append(name)
            if escalated and alert_cfg.escalation:
                for t in alert_cfg.escalation.additional_tools:
                    if t not in tool_names:
                        tool_names.append(t)

            logger.info(
                f"ADK model returned no tool_calls for [{stream_id}][{alert_cfg.name}] "
                f"— executing configured tools: {tool_names}"
            )
            return await self._execute_tool_list(
                tool_names, stream_id, alert_cfg, answer, reason,
                consecutive_count, escalated, snapshot_path,
            )

        except asyncio.TimeoutError:
            logger.error(
                f"ADK dispatch timed out after {settings.LLM_TIMEOUT}s "
                f"for [{stream_id}][{alert_cfg.name}] — falling back to rule-based"
            )
            return await self._dispatch_rule_based(
                stream_id, alert_cfg, answer, reason,
                consecutive_count, escalated, snapshot_path,
            )
        except Exception as exc:
            logger.error(
                f"ADK dispatch failed for [{stream_id}][{alert_cfg.name}]: "
                f"{type(exc).__name__}: {exc} — falling back to rule-based"
            )
            return await self._dispatch_rule_based(
                stream_id, alert_cfg, answer, reason,
                consecutive_count, escalated, snapshot_path,
            )


def _build_tool_kwargs(
    tool_name: str,
    ctx: Dict[str, Any],
    consecutive_count: int,
    escalated: bool,
    snapshot_path: Optional[str],
) -> Dict[str, Any]:
    """Map common alert context fields to per-tool keyword arguments."""
    base = {
        "stream_id": ctx["stream_id"],
        "alert_name": ctx["alert_name"],
    }
    if tool_name == "log_alert":
        return {
            **base,
            "answer": ctx["answer"],
            "reason": ctx["reason"],
            "consecutive_count": consecutive_count,
            "escalated": escalated,
            "snapshot_path": snapshot_path,
        }
    if tool_name == "trigger_webhook":
        return {
            "payload": {
                **ctx,
                "consecutive_count": consecutive_count,
                "escalated": escalated,
                "snapshot_path": snapshot_path,
            }
        }
    if tool_name == "capture_snapshot":
        return base
    if tool_name == "publish_mqtt":
        return {
            **base,
            "answer": ctx["answer"],
            "reason": ctx["reason"],
        }
    return {}


def _render_tool_arguments(value: Any, ctx: Dict[str, Any]) -> Any:
    """Render template placeholders in tool arguments from the alert context."""
    if isinstance(value, str):
        return _CONTEXT_TEMPLATE_PATTERN.sub(
            lambda m: "" if ctx.get(m.group(1)) is None else str(ctx.get(m.group(1))),
            value,
        )
    if isinstance(value, list):
        return [_render_tool_arguments(item, ctx) for item in value]
    if isinstance(value, dict):
        return {k: _render_tool_arguments(v, ctx) for k, v in value.items()}
    return value
