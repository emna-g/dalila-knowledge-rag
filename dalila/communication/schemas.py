"""Stable HTTP request and response contracts for the Dalila API."""

import json
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatMessage(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le contenu du message ne peut pas être vide.")
        return value


class ChatContext(StrictModel):
    page: Optional[str] = Field(None, max_length=32)
    zone_id: Optional[str] = Field(None, max_length=24)
    lot_id: Optional[str] = Field(None, max_length=24)
    favorites: List[str] = Field(default_factory=list, max_length=5)

    @field_validator("favorites")
    @classmethod
    def favorites_must_be_bounded(cls, values: List[str]) -> List[str]:
        if any(not value.strip() or len(value) > 24 for value in values):
            raise ValueError("Chaque favori doit être un identifiant non vide de 24 caractères au plus.")
        return [value.strip() for value in values]

    def to_agent_context(self) -> Optional[str]:
        values = self.model_dump(exclude_none=True)
        if not values:
            return None
        return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=500)
    history: List[ChatMessage] = Field(default_factory=list, max_length=20)
    lang: Optional[str] = Field(None, min_length=2, max_length=16)
    context: Optional[ChatContext] = None

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le message ne peut pas être vide.")
        return value


class SourceReference(StrictModel):
    source_id: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    date: Optional[str] = None


class GeoJSONFeature(StrictModel):
    type: Literal["Feature"]
    id: Optional[Union[str, int]] = None
    geometry: Dict[str, Any]
    properties: Dict[str, Any] = Field(default_factory=dict)


class GeoJSONFeatureCollection(StrictModel):
    type: Literal["FeatureCollection"]
    features: List[GeoJSONFeature] = Field(default_factory=list)
    source_id: Optional[str] = None
    notice: Optional[str] = None
    truncated: bool = False
    next_cursor: Optional[int] = None
    rejected_geometry_count: int = 0


class MapZone(StrictModel):
    zone_id: str
    name_fr: Optional[str] = None
    name_ar: Optional[str] = None
    governorate_fr: Optional[str] = None
    governorate_code: Optional[str] = None
    development_regional: Optional[bool] = None
    development_regional_group: Optional[int] = Field(None, ge=1, le=2)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source_id: Literal["afi_sql"] = "afi_sql"


class MapZonesResponse(StrictModel):
    source_id: Literal["afi_sql"] = "afi_sql"
    zones: List[MapZone] = Field(default_factory=list)


class ApiError(StrictModel):
    code: str
    message: str


class ChatResponse(StrictModel):
    request_id: str
    status: Literal["answered", "abstained", "degraded"]
    answer: str
    sources: List[SourceReference] = Field(default_factory=list)
    map_data: Optional[GeoJSONFeatureCollection] = None
    error: Optional[ApiError] = None


class ErrorResponse(StrictModel):
    request_id: str
    error: ApiError
