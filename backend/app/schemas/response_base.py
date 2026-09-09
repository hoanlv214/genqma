"""Shared base for response models that must preserve legacy extra fields."""

from pydantic import BaseModel, ConfigDict


class ResponseModel(BaseModel):
    """Document known fields without dropping runtime/provider extensions."""

    model_config = ConfigDict(extra="allow")
