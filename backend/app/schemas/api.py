from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    household_id: str
    profile_id: str
    demo: bool = True


class DeviceCodeRequest(StrictModel):
    client_id: str | None = Field(default="omnipulse-tv-client", max_length=80)


class DeviceCodeResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class DeviceTokenRequest(StrictModel):
    device_code: str = Field(min_length=10, max_length=120)


class DeviceAuthorizeRequest(StrictModel):
    user_code: str = Field(min_length=4, max_length=30)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    household_id: str
    profile_id: str


class RefreshTokenRequest(StrictModel):
    refresh_token: str = Field(min_length=10)


class ProfilePreferencesUpdate(StrictModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=80)
    favorite_sports: list[str] | None = Field(default=None, max_length=8)
    detail_level: Literal["simple", "balanced", "advanced"] | None = None
    spoiler_policy: Literal["allow", "avoid", "strict"] | None = None
    default_mode: Literal["family", "analyst", "catch_up"] | None = None


class SessionCreate(StrictModel):
    event_id: str | None = Field(default=None, max_length=100)
    mode: Literal["family", "analyst", "catch_up"] = "family"
    context: dict[str, Any] = Field(default_factory=dict, max_length=20)


class ExperienceResolveRequest(StrictModel):
    event_id: str | None = Field(default=None, max_length=100)
    override_mode: Literal["family", "analyst", "catch_up"] | None = None


class AICommandRequest(StrictModel):
    session_id: str | None = Field(default=None, max_length=80)
    event_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=2, max_length=500)
    selected_player_id: str | None = Field(default=None, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=120)


class CoachSessionCreate(StrictModel):
    exercise: Literal["squat", "stretch", "athletic_stance"]
    consent_recorded: bool


class CoachMetricCreate(StrictModel):
    metric_type: Literal["knee_angle", "hip_angle", "pose_confidence", "repetition_count"]
    value: float = Field(ge=0, le=360)
    unit: Literal["degrees", "fraction", "count"] = "degrees"
    confidence: float | None = Field(default=None, ge=0, le=1)


class FeedbackCreate(StrictModel):
    category: Literal["bug", "ux", "data_quality", "accessibility", "other"]
    message: str = Field(min_length=4, max_length=2000)
    context: dict[str, Any] = Field(default_factory=dict, max_length=20)


class APIError(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    retryable: bool = False


class APIErrorEnvelope(BaseModel):
    error: APIError
