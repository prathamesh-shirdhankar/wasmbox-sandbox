from typing import Literal
from pydantic import BaseModel, Field

RunStatus = Literal["ok", "error", "denied", "timeout", "memory_exceeded"]


class HealthResponse(BaseModel):
    ok: bool = True


class RunRequest(BaseModel):
    code: str = Field(..., description="Python source code to execute")


class RunResponse(BaseModel):
    status: RunStatus = Field(..., description="Status of execution")
    stdout: str = Field(default="", description="Captured standard output")
    stderr: str = Field(default="", description="Captured standard error")
    exec_ms: float = Field(default=0.0, description="Execution duration in milliseconds")
    mem_bytes: int = Field(default=0, description="Memory used in bytes")
