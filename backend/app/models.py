import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SourceType(str, enum.Enum):
    twitch = "twitch"
    wargaming = "wargaming"
    manual = "manual"


class ProgressSource(str, enum.Enum):
    official = "official"
    manual = "manual"
    estimated = "estimated"


class DetectionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    duplicate = "duplicate"


class QualificationDecision(str, enum.Enum):
    auto_approve = "auto_approve"
    manual_review = "manual_review"
    auto_ignore = "auto_ignore"


class RewardValue(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"
    unknown = "unknown"


class Confidence(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    session_version: Mapped[int] = mapped_column(Integer, default=1)


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    required_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eligible_channels: Mapped[list] = mapped_column(JSON, default=list)
    category_name: Mapped[str] = mapped_column(String(120), default="World of Tanks")
    link_url: Mapped[str] = mapped_column(String(500), default="https://www.twitch.tv/directory/category/world-of-tanks")
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), default=SourceType.manual)
    source_url: Mapped[str] = mapped_column(String(500), default="")
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    watched_minutes: Mapped[int] = mapped_column(Integer, default=0)
    progress_source: Mapped[ProgressSource] = mapped_column(Enum(ProgressSource), default=ProgressSource.manual)
    last_progress_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence_score: Mapped[int] = mapped_column(Integer, default=0)
    reward_value: Mapped[RewardValue] = mapped_column(Enum(RewardValue), default=RewardValue.unknown)
    auto_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_reason: Mapped[str] = mapped_column(Text, default="")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness_status: Mapped[str] = mapped_column(String(40), default="historical", index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    rewards: Mapped[list["Reward"]] = relationship(back_populates="campaign", cascade="all, delete-orphan", lazy="selectin")


class Reward(Base):
    __tablename__ = "rewards"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    required_minutes: Mapped[int] = mapped_column(Integer, default=0)
    earned: Mapped[bool] = mapped_column(Boolean, default=False)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    campaign: Mapped[Campaign] = relationship(back_populates="rewards")


class TwitchConnection(Base):
    __tablename__ = "twitch_connections"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    twitch_user_id: Mapped[str] = mapped_column(String(80))
    login: Mapped[str] = mapped_column(String(120))
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class EventLog(Base):
    __tablename__ = "event_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    level: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(String(500))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("dedupe_key", "channel"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(String(250))
    channel: Mapped[str] = mapped_column(String(30))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DetectedEvent(Base):
    __tablename__ = "detected_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stream_times: Mapped[list] = mapped_column(JSON, default=list)
    probable_rewards: Mapped[list] = mapped_column(JSON, default=list)
    required_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str] = mapped_column(String(600), unique=True)
    source_name: Mapped[str] = mapped_column(String(120), default="World of Tanks EU")
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    excerpt: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[Confidence] = mapped_column(Enum(Confidence), default=Confidence.low)
    event_type: Mapped[str] = mapped_column(String(50), default="event")
    status: Mapped[DetectionStatus] = mapped_column(Enum(DetectionStatus), default=DetectionStatus.pending)
    approved_campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    qualification_decision: Mapped[QualificationDecision] = mapped_column(
        Enum(QualificationDecision), default=QualificationDecision.manual_review
    )
    confidence_score: Mapped[int] = mapped_column(Integer, default=0)
    reward_value: Mapped[RewardValue] = mapped_column(Enum(RewardValue), default=RewardValue.unknown)
    matched_keywords: Mapped[list] = mapped_column(JSON, default=list)
    score_breakdown: Mapped[list] = mapped_column(JSON, default=list)
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[str] = mapped_column(String(30), default="automation")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_content_hash: Mapped[str] = mapped_column(String(64), default="")
    freshness_status: Mapped[str] = mapped_column(String(40), default="historical", index=True)
    detected_date_text: Mapped[str] = mapped_column(Text, default="")
    date_confidence: Mapped[str] = mapped_column(String(20), default="none")


class TrustedSource(Base):
    __tablename__ = "trusted_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    url_pattern: Mapped[str] = mapped_column(String(600), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=True)
    max_trust_score: Mapped[int] = mapped_column(Integer, default=100)
    ignored: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DecisionHistory(Base):
    __tablename__ = "decision_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    detected_event_id: Mapped[int] = mapped_column(ForeignKey("detected_events.id", ondelete="CASCADE"), index=True)
    decision: Mapped[QualificationDecision] = mapped_column(Enum(QualificationDecision))
    score: Mapped[int] = mapped_column(Integer)
    reward_value: Mapped[RewardValue] = mapped_column(Enum(RewardValue))
    reason: Mapped[str] = mapped_column(Text)
    score_breakdown: Mapped[list] = mapped_column(JSON, default=list)
    matched_keywords: Mapped[list] = mapped_column(JSON, default=list)
    actor: Mapped[str] = mapped_column(String(30), default="automation")
    action: Mapped[str] = mapped_column(String(60), default="decision")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class SourceCache(Base):
    __tablename__ = "source_cache"
    url: Mapped[str] = mapped_column(String(600), primary_key=True)
    etag: Mapped[str] = mapped_column(String(300), default="")
    last_modified: Mapped[str] = mapped_column(String(300), default="")
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_error: Mapped[str] = mapped_column(String(500), default="")


class WatchedChannel(Base):
    __tablename__ = "watched_channels"
    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(100), unique=True)
    drops_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    drops_source_url: Mapped[str] = mapped_column(String(600), default="")
    drops_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
