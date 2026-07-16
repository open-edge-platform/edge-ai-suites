# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import logging
import requests
from fastapi import APIRouter
from config import VSS_SUMMARY_URL

logger = logging.getLogger(__name__)

vss_router = APIRouter()


@vss_router.get("/vss-features", summary="Detect which VSS features are enabled")
def get_vss_features():
    """Report which VSS features (summary/search) are active.

    Queries the VSS pipeline-manager /app/features endpoint. VSS_SUMMARY_URL
    is the base URL for the single VSS nginx proxy that serves both summary
    and search — the URL name is historical, not mode-specific.

    If VSS is unreachable or returns an unexpected payload, both features are
    reported as enabled so the UI shows all options rather than hiding a
    working feature.
    """
    fallback = {"summary_enabled": True, "search_enabled": True}

    if not VSS_SUMMARY_URL:
        logger.warning("VSS_SUMMARY_URL is not set; reporting all VSS features enabled.")
        return fallback

    try:
        response = requests.get(f"{VSS_SUMMARY_URL}/manager/app/features", timeout=3)
        response.raise_for_status()
        data = response.json()
        summary_on = data.get("summary") == "FEATURE_ON"
        search_on = data.get("search") == "FEATURE_ON"
        if summary_on and search_on:
            mode_label = "Dual (summary + search)"
        elif summary_on:
            mode_label = "Summary-only"
        elif search_on:
            mode_label = "Search-only"
        else:
            logger.warning("VSS reported no active features; falling back to all enabled.")
            return fallback
        logger.info(f"VSS mode detected: {mode_label}")
        return {
            "summary_enabled": summary_on,
            "search_enabled": search_on,
        }
    except Exception as e:
        logger.warning(
            f"Could not reach VSS /app/features ({e}); reporting all VSS features enabled."
        )
        return fallback
