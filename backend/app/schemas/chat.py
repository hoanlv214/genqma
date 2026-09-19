"""Chat request schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(
        ...,
        description="Role of the message participant: 'user' for human/agent questions, 'assistant' for AI responses.",
        examples=["user"],
    )
    content: str = Field(
        ...,
        description="Text content of the conversation message.",
        examples=["Explain the historical analogs for this signal."],
    )


class ChatRequest(BaseModel):
    invoice_id: str = Field(
        ...,
        description="Settled invoice ID or session reference granted for the quantitative report.",
        examples=["inv_79d896a28cd5"],
    )
    message: str = Field(
        ...,
        description="Interactive analysis question or inquiry regarding the report's signals and risk profile.",
        examples=["What are the main risks in this report?"],
    )
    history: Optional[List[ChatMessage]] = Field(
        default_factory=list,
        description="Chronological conversation turn history to provide ongoing context.",
        examples=[[{"role": "user", "content": "Summarize the setup."}]],
    )
