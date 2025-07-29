# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from service.vms_service import VmsService
from service.redis_store import save_summary_id, save_summary_result, save_search
from api.endpoints.summarization_api import SummarizationService
from api.endpoints.frigate_api import FrigateService
import logging

logger = logging.getLogger(__name__)
frigate_service = FrigateService()
summarization_service = SummarizationService()
vms_service = VmsService(frigate_service, summarization_service)


async def dispatch_action(action: str, event: dict):
    if action == "summarize":
        try:
            camera_name = event.get("camera")
            start_time = event.get("start_time")
            end_time = event.get("end_time")

            # Validate required fields
            if not camera_name or start_time is None or end_time is None:
                raise ValueError(
                    "Missing required fields: camera, start_time, or end_time"
                )

            summary_response = await vms_service.summarize(
                camera_name=camera_name,
                start_time=start_time,
                end_time=end_time,
            )
            if summary_response["status"] != 200:
                logger.info(summary_response)
                return
            summary_id = summary_response["message"]
            # Save summary_id under the rule
            await save_summary_id(event["rule_id"], summary_id)

            # Retrieve actual summary result (synchronously)
            summary_result = vms_service.summary(summary_id)["summary"]

            logger.info(
                f"Saving summary result  {summary_result} for summary id {summary_id}"
            )
            # Store summary response
            await save_summary_result(summary_id, summary_result)

            return {
                "summary_id": summary_id,
                "result": summary_result,
            }

        except Exception as e:
            logger.error(f"❌ Summarize action failed: {e}")
            return {"error": str(e)}

    elif action == "add to search":
        try:
            camera_name = event.get("camera")
            start_time = event.get("start_time")
            end_time = event.get("end_time")

            # Validate required fields
            if not camera_name or start_time is None or end_time is None:
                raise ValueError(
                    "Missing required fields: camera, start_time, or end_time"
                )

            output = await vms_service.search_embeddings(
                camera_name=camera_name,
                start_time=start_time,
                end_time=end_time,
            )

            # Save summary_id under the rule
            if output["status"] != 200:
                return
            await save_search(event["rule_id"], output)
            return output

        except Exception as e:
            logger.error(f"❌ Search action failed: {e}")
            return {"error": str(e)}

    else:
        return {"error": f"Unknown action: {action}"}
