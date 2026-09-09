"""Chat request schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., examples=["user"])
    content: str = Field(..., examples=["Explain the historical analogs for this signal."])


class ChatRequest(BaseModel):
    invoice_id: str = Field(..., examples=["inv_79d896a28cd5"])
    message: str = Field(..., examples=["What are the main risks in this report?"])
    history: Optional[List[ChatMessage]] = Field(
        default_factory=list,
        examples=[[{"role": "user", "content": "Summarize the setup."}]],
    )
