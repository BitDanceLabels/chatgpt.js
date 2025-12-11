from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Prompt to send to ChatGPT")
    timeout: int | None = Field(
        60, ge=5, le=300, description="Timeout in seconds for chatgpt.ask"
    )


class AskResponse(BaseModel):
    reply: str
    duration_ms: int | None = None


class StatusResponse(BaseModel):
    ready: bool
    idle: bool
