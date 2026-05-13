#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from utils.database import get_db
import time
from utils.storage_service import storage_service
from utils.search_service import search_service

router = APIRouter()


@router.get("/config")
async def get_config():
    """Return Content Search model and database configuration."""
    vs_enabled = os.getenv("VIDEO_SUMMARIZATION_ENABLED", "true").lower() in ("true", "1", "yes")
    return {
        "vlm_model": os.getenv("VLM_MODEL_NAME", "Qwen/Qwen2.5-VL-3B-Instruct"),
        "visual_embedding_model": os.getenv("VISUAL_EMBEDDING_MODEL", "CLIP/clip-vit-b-16"),
        "doc_embedding_model": os.getenv("DOC_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
        "reranker_model": os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-large"),
        "vector_db": f"ChromaDB ({os.getenv('CHROMA_HOST', '127.0.0.1')}:{os.getenv('CHROMA_PORT', '9090')})",
        "video_summarization_enabled": vs_enabled,
    }


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok" if db_status == "healthy" else "error",
        "timestamp": time.time(),
        "services": {
            "database": db_status
        }
    }

@router.post("/reconcile")
async def reconcile_storage_data(
    dry_run: bool = True,
    cleanup_sqlite_orphans: bool = True,
    cleanup_storage_orphans: bool = True,
    cleanup_index_orphans: bool = True,
    auto_reindex: bool = False,
    report_detail: str = "summary",
    db: Session = Depends(get_db)
):
    import logging
    logger = logging.getLogger(__name__)

    stats = {
        "sqlite_total": 0,
        "storage_total": 0,
        "index_total": 0,
        "synced": 0,
        "sqlite_orphans": 0,
        "storage_orphans": 0,
        "index_orphans": 0,
        "missing_storage": 0,
        "missing_index": 0,
        "missing_both": 0,
    }

    actions = {
        "sqlite_deleted": [],
        "storage_deleted": [],
        "index_deleted": [],
        "reindex_triggered": [],
    }

    logger.info("Phase 1: Checking SQLite records against physical storage")

    sqlite_records = db.execute(
        text("SELECT file_hash, file_name, file_path, bucket_name FROM file_assets")
    ).fetchall()
    stats["sqlite_total"] = len(sqlite_records)

    sqlite_paths = set()

    for row in sqlite_records:
        f_hash, f_name, f_path, f_bucket = row
        sqlite_paths.add(f_path)

        local_exists = storage_service.file_exists(f_path)
        chroma_exists = await search_service.check_file_exists(f_path, bucket_name=f_bucket)

        if local_exists and chroma_exists:
            stats["synced"] += 1
        elif local_exists and not chroma_exists:
            stats["missing_index"] += 1
            if auto_reindex and not dry_run:
                actions["reindex_triggered"].append({
                    "file_path": f_path,
                    "file_name": f_name
                })
        elif not local_exists and chroma_exists:
            stats["missing_storage"] += 1
            if cleanup_sqlite_orphans and not dry_run:
                await search_service.delete_file_index(f_path, bucket_name=f_bucket)
                db.execute(text("DELETE FROM file_assets WHERE file_hash = :h"), {"h": f_hash})
                actions["sqlite_deleted"].append({
                    "file_hash": f_hash,
                    "file_name": f_name,
                    "file_path": f_path,
                    "reason": "file_missing_but_index_exists"
                })
                stats["sqlite_orphans"] += 1
        else:
            stats["missing_both"] += 1
            if cleanup_sqlite_orphans and not dry_run:
                db.execute(text("DELETE FROM file_assets WHERE file_hash = :h"), {"h": f_hash})
                actions["sqlite_deleted"].append({
                    "file_hash": f_hash,
                    "file_name": f_name,
                    "file_path": f_path,
                    "reason": "both_storage_and_index_missing"
                })
                stats["sqlite_orphans"] += 1

    if not dry_run and stats["sqlite_orphans"] > 0:
        db.commit()

    logger.info("Phase 2: Checking LocalStorage for orphaned files")

    all_storage_files = storage_service.list_all_files()
    stats["storage_total"] = len(all_storage_files)

    for file_path in all_storage_files:
        if file_path not in sqlite_paths:
            if cleanup_storage_orphans and not dry_run:
                storage_service.delete_file(file_path, missing_ok=True)
                actions["storage_deleted"].append({
                    "file_path": file_path,
                    "reason": "no_sqlite_record"
                })
            stats["storage_orphans"] += 1

    logger.info("Phase 3: Checking ChromaDB for orphaned indices")

    id_maps = await search_service.get_id_maps()
    all_indexed_paths = set()
    all_indexed_paths.update(id_maps.get("visual", {}).keys())
    all_indexed_paths.update(id_maps.get("document", {}).keys())
    all_indexed_paths.update(id_maps.get("video_summary", {}).keys())

    stats["index_total"] = len(all_indexed_paths)

    for indexed_path in all_indexed_paths:
        if indexed_path not in sqlite_paths:
            if cleanup_index_orphans and not dry_run:
                bucket = None
                if indexed_path.startswith("local://"):
                    parts = indexed_path.replace("local://", "").split("/", 1)
                    if len(parts) > 0:
                        bucket = parts[0]

                await search_service.delete_file_index(indexed_path, bucket_name=bucket)
                actions["index_deleted"].append({
                    "file_path": indexed_path,
                    "reason": "no_sqlite_record"
                })
            stats["index_orphans"] += 1

    response = {
        "status": "ok",
        "mode": "dry_run" if dry_run else "executed",
        "summary": {
            "total_files_in_sqlite": stats["sqlite_total"],
            "total_files_in_storage": stats["storage_total"],
            "total_indexed_paths": stats["index_total"],
            "synced_files": stats["synced"],
            "inconsistencies_found": {
                "sqlite_orphans": stats["sqlite_orphans"],
                "storage_orphans": stats["storage_orphans"],
                "index_orphans": stats["index_orphans"],
                "missing_storage": stats["missing_storage"],
                "missing_index": stats["missing_index"],
                "missing_both": stats["missing_both"],
            },
            "actions_taken": {
                "sqlite_records_deleted": len(actions["sqlite_deleted"]),
                "storage_files_deleted": len(actions["storage_deleted"]),
                "index_entries_deleted": len(actions["index_deleted"]),
                "reindex_triggered": len(actions["reindex_triggered"]),
            }
        }
    }

    if report_detail == "detailed":
        response["details"] = {
            "sqlite_deleted": actions["sqlite_deleted"][:50],
            "storage_deleted": actions["storage_deleted"][:50],
            "index_deleted": actions["index_deleted"][:50],
            "reindex_triggered": actions["reindex_triggered"][:50],
            "note": "Lists truncated to first 50 items for each category"
        }

    if dry_run:
        recommendations = []
        if stats["sqlite_orphans"] > 0:
            recommendations.append(
                f"Found {stats['sqlite_orphans']} SQLite orphans. "
                f"Run with dry_run=false and cleanup_sqlite_orphans=true to clean them."
            )
        if stats["storage_orphans"] > 0:
            recommendations.append(
                f"Found {stats['storage_orphans']} orphaned files in LocalStorage. "
                f"Run with dry_run=false and cleanup_storage_orphans=true to delete them."
            )
        if stats["index_orphans"] > 0:
            recommendations.append(
                f"Found {stats['index_orphans']} orphaned indices in ChromaDB. "
                f"Run with dry_run=false and cleanup_index_orphans=true to delete them."
            )
        if stats["missing_index"] > 0:
            recommendations.append(
                f"Found {stats['missing_index']} files without indices. "
                f"Consider running with auto_reindex=true to reindex them."
            )

        response["recommendations"] = recommendations if recommendations else ["No inconsistencies found"]

    logger.info(f"Reconciliation complete: {json.dumps(response['summary'], indent=2)}")
    return response
