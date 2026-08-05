from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.models import ProgressSource, SourceType


class RewardIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    required_minutes: int = Field(ge=0, le=10000)


class RewardOut(RewardIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    earned: bool
    claimed: bool


class CampaignIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    starts_at: datetime
    ends_at: datetime
    required_minutes: int = Field(ge=0, le=10000)
    eligible_channels: list[str] = Field(default_factory=list, max_length=100)
    category_name: str = Field(default="World of Tanks", max_length=120)
    link_url: HttpUrl
    source_type: SourceType = SourceType.manual
    source_url: HttpUrl | None = None
    rewards: list[RewardIn] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def dates_valid(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("Koniec kampanii musi przypadać po jej rozpoczęciu")
        return self


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    starts_at: datetime
    ends_at: datetime
    required_minutes: int
    watched_minutes: int
    eligible_channels: list[str]
    category_name: str
    link_url: str
    source_type: SourceType
    source_url: str
    source_updated_at: datetime
    progress_source: ProgressSource
    last_progress_at: datetime | None
    rewards: list[RewardOut]


class ProgressIn(BaseModel):
    watched_minutes: int = Field(ge=0, le=10000)
    source: ProgressSource = ProgressSource.manual
