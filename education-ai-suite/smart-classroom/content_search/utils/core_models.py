#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

from sqlalchemy import Column, String, JSON, DateTime, Integer
from utils.database import Base
from datetime import datetime
import uuid

class AITask(Base):
    __tablename__ = "edu_ai_tasks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type = Column(String)
    status = Column(String, default="QUEUED")
    progress = Column(Integer, default=0, nullable=False)
    payload = Column(JSON)
    result = Column(JSON, nullable=True)
    user_id = Column(String, index=True, nullable=True, default="default_user")
    created_at = Column(DateTime, default=datetime.now)

class FileAsset(Base):
    __tablename__ = "minio_file_assets"

    file_hash = Column(String, primary_key=True, index=True) 
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    bucket_name = Column(String, nullable=False)
    content_type = Column(String)
    size_bytes = Column(Integer)
    meta = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)
