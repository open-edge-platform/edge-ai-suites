# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import re
import time
from typing import List, Optional, Tuple

import httpx
from pydantic import ValidationError

from config import (
    OVMS_BASE_URL,
    REASONING_ENABLED,
    REASONING_MAX_TOKENS,
    REASONING_MODEL_NAME,
    REASONING_TEMPERATURE,
    REASONING_TIMEOUT_SEC,
)
from controllers.threshold import ThresholdController
from schema import ReasoningDecision, RouteCandidate
from utils.logging_config import get_logger
from utils.reasoning_prompt import (
    build_response_format,
    build_system_prompt,
    build_user_prompt,
)

logger = get_logger(__name__)

# Reasoning distilled models (for example DeepSeek-R1-Distill) emit their chain of thought
# inside <think> tags before the answer. Instruct models often wrap JSON in markdown fences.
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
CODE_FENCE_PATTERN = re.compile(r"```(?:json)?|```")


class ReasoningModelController:
    """
    Client for the reasoning model served by OVMS over its OpenAI compatible API.
    """

    def __init__(self) -> None:
        self.chat_completions_url = f"{OVMS_BASE_URL}/chat/completions"

    @staticmethod
    def _sanitise_content(content: str) -> str:
        """Remove reasoning traces and markdown fences so that only the answer text remains."""

        without_thinking = THINK_BLOCK_PATTERN.sub("", content)
        return CODE_FENCE_PATTERN.sub("", without_thinking).strip()

    @staticmethod
    def _extract_json(content: str) -> Optional[dict]:
        """
        Extract the first balanced JSON object from the model response.
        """

        start_index = content.find("{")
        if start_index == -1:
            return None

        open_braces = 0
        for current_index in range(start_index, len(content)):
            if content[current_index] == "{":
                open_braces += 1
            elif content[current_index] == "}":
                open_braces -= 1
                if open_braces == 0:
                    candidate_json = content[start_index : current_index + 1]
                    try:
                        parsed = json.loads(candidate_json)
                    except json.JSONDecodeError as e:
                        logger.error(f"Reasoning model returned malformed JSON: {e}")
                        return None
                    return parsed if isinstance(parsed, dict) else None

        logger.error("Reasoning model response contained no complete JSON object.")
        return None

    @staticmethod
    def _is_route_sub_optimal(candidate: RouteCandidate) -> bool:
        """
        Decide whether a route breaches a hard safety rule.

        Used both to constrain what the model is allowed to choose from and to drive the
        sub-optimal banner in the UI.
        """

        return (
            candidate.has_severe_incident
            or candidate.has_hazardous_weather
            or candidate.max_traffic_density
            > ThresholdController.TRAFFIC_DENSITY_THRESHOLD
        )

    @classmethod
    def _select_eligible_candidates(
        cls, candidates: List[RouteCandidate]
    ) -> Tuple[List[RouteCandidate], bool]:
        """
        Narrow the candidate set to the routes the model may choose from.

        Returns the candidates to present, and whether every route was disqualified.
        """

        eligible = [
            candidate
            for candidate in candidates
            if candidate.has_live_data and not cls._is_route_sub_optimal(candidate)
        ]
        if eligible:
            return eligible, False

        # Every route breaches a rule. Narrow to the least severe tier still available so the
        # model cannot rank a roadblock above mere congestion, then let it choose within that.
        pool = [candidate for candidate in candidates if candidate.has_live_data]

        without_incident = [
            candidate for candidate in pool if not candidate.has_severe_incident
        ]
        if without_incident:
            pool = without_incident

        without_hazard = [
            candidate for candidate in pool if not candidate.has_hazardous_weather
        ]
        if without_hazard:
            pool = without_hazard

        return pool, True

    @staticmethod
    def _validate_against_candidates(
        decision: ReasoningDecision, candidates: List[RouteCandidate]
    ) -> Optional[RouteCandidate]:
        """
        Ensure the model selected a real, usable route and return it.
        """

        for candidate in candidates:
            if candidate.route_name == decision.selected_route:
                if not candidate.has_live_data:
                    logger.error(
                        f"Reasoning model selected '{decision.selected_route}' which has no live traffic data. "
                        "Rejecting the decision."
                    )
                    return None
                return candidate

        logger.error(
            f"Reasoning model selected unknown route '{decision.selected_route}'. "
            f"Valid routes were: {[candidate.route_name for candidate in candidates]}"
        )
        return None

    async def _request_completion(
        self, messages: List[dict], response_format: Optional[dict] = None
    ) -> Optional[str]:
        """Call the OVMS chat completions endpoint and return the raw assistant message content."""

        request_body = {
            "model": REASONING_MODEL_NAME,
            "messages": messages,
            "max_tokens": REASONING_MAX_TOKENS,
            "temperature": REASONING_TEMPERATURE,
        }

        if response_format:
            request_body["response_format"] = response_format

        try:
            started_at = time.monotonic()
            async with httpx.AsyncClient(timeout=REASONING_TIMEOUT_SEC) as client:
                response = await client.post(
                    self.chat_completions_url, json=request_body
                )
                response.raise_for_status()
                payload = response.json()

            logger.info(
                f"Reasoning model responded in {time.monotonic() - started_at:.2f}s"
            )
            logger.debug(f"Raw reasoning model payload: {payload}")

            return payload["choices"][0]["message"]["content"]

        except httpx.TimeoutException:
            logger.error(
                f"Reasoning model timed out after {REASONING_TIMEOUT_SEC}s at {self.chat_completions_url}. "
                "Falling back to rule based route planning."
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Reasoning model returned HTTP {e.response.status_code}: {e.response.text}"
            )
        except httpx.RequestError as e:
            logger.error(
                f"Could not reach the reasoning model at {self.chat_completions_url}: {e}"
            )
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Unexpected response structure from reasoning model: {e}")
        except Exception as e:
            logger.error(f"Error while querying the reasoning model: {e}")

        return None

    async def decide_route(
        self, source: str, destination: str, candidates: List[RouteCandidate]
    ) -> Optional[ReasoningDecision]:
        """
        Ask the reasoning model to pick the best route from the given candidates.

        Returns:
            ReasoningDecision when the model produced a valid, usable answer.
            None on any failure, which tells the caller to use the rule based fallback.
        """

        if not REASONING_ENABLED:
            logger.debug("Reasoning model is not configured. Skipping reasoning path.")
            return None

        if not candidates:
            logger.warning("No route candidates available for the reasoning model.")
            return None

        # Without live data on any route the model has nothing to reason about, so the
        # inference cost is skipped entirely and the fallback handles it.
        if not any(candidate.has_live_data for candidate in candidates):
            logger.warning(
                "No live traffic data on any candidate route. Skipping reasoning path."
            )
            return None

        # Hard safety constraints are applied before the model sees the options.
        eligible_candidates, all_disqualified = self._select_eligible_candidates(
            candidates
        )

        messages = [
            {"role": "system", "content": build_system_prompt(all_disqualified)},
            {
                "role": "user",
                "content": build_user_prompt(source, destination, eligible_candidates),
            },
        ]

        content = await self._request_completion(
            messages, build_response_format(eligible_candidates)
        )
        if not content:
            return None

        sanitised_content = self._sanitise_content(content)
        logger.debug(f"Sanitised reasoning model content: {sanitised_content}")

        decision_data = self._extract_json(sanitised_content)
        if not decision_data:
            logger.error(
                f"Could not extract a decision from the reasoning model response: {sanitised_content[:500]}"
            )
            return None

        try:
            decision = ReasoningDecision.model_validate(decision_data)
        except ValidationError as e:
            logger.error(f"Reasoning model decision failed validation: {e}")
            return None

        selected_candidate = self._validate_against_candidates(
            decision, eligible_candidates
        )
        if selected_candidate is None:
            return None

        decision.is_sub_optimal = self._is_route_sub_optimal(selected_candidate)
        logger.info(
            f"Reasoning model selected '{decision.selected_route}' "
            f"(sub-optimal: {decision.is_sub_optimal}). Reason: {decision.reason}"
        )
        return decision
