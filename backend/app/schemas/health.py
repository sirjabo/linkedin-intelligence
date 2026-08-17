from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    database: Literal["ok", "error"]
    redis: Literal["ok", "error"]
    data_freshness: Literal["ok", "stale"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"] = Field(description="Overall health")
    version: str
    services: ServiceStatus
    checked_at: datetime
