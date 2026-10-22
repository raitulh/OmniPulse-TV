"""Sports data provider abstraction and adapter layer.

Handles integration with licensed sports data feeds (e.g., Opta, Sportradar, Stats Perform),
coordinate normalization to the OmniPulse 0-100 pitch grid, data freshness validation,
and strict provider attribution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class NormalizedPlayerCoord:
    player_id: str
    name: str
    team: str
    role: str
    x: float  # 0.0 - 100.0 percentage of pitch width
    y: float  # 0.0 - 100.0 percentage of pitch height
    speed_kph: float = 0.0
    source_type: str = "licensed_provider"


@dataclass
class NormalizedEventFrame:
    event_id: str
    timestamp_utc: datetime
    provider_name: str
    attribution: str
    is_live: bool
    is_fresh: bool
    delay_seconds: float
    players: list[dict[str, Any]] = field(default_factory=list)
    connections: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


def clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamps coordinates to the 0-100 pitch boundary."""
    return max(min_val, min(max_val, round(value, 2)))


class SportsDataProvider(ABC):
    """Abstract base provider for sports telemetry and match events."""

    @abstractmethod
    def provider_id(self) -> str:
        """Unique key identifying this provider implementation."""
        ...

    @abstractmethod
    def get_attribution(self) -> str:
        """Mandatory attribution string required by licensing agreements."""
        ...

    @abstractmethod
    def normalize_coordinates(self, raw_x: float, raw_y: float) -> tuple[float, float]:
        """Maps raw provider coordinates to standard 0-100% pitch space."""
        ...

    @abstractmethod
    def verify_freshness(self, timestamp: datetime, max_delay_seconds: int = 30) -> tuple[bool, float]:
        """Checks whether the incoming frame is within real-time latency thresholds."""
        ...


class OptaSportsProvider(SportsDataProvider):
    """Adapter for Opta / Stats Perform F9 & F24 feeds.
    
    Opta native pitch grid is already 0.0 - 100.0 from left to right, but can
    exceed bounds or have specific origin conventions depending on direction of play.
    """

    def provider_id(self) -> str:
        return "opta"

    def get_attribution(self) -> str:
        return "Data powered by Opta Sports. All rights reserved."

    def normalize_coordinates(self, raw_x: float, raw_y: float) -> tuple[float, float]:
        # Opta standard coordinates: 0.0 <= x <= 100.0, 0.0 <= y <= 100.0
        return clamp(raw_x), clamp(raw_y)

    def verify_freshness(self, timestamp: datetime, max_delay_seconds: int = 30) -> tuple[bool, float]:
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        delay = (now - timestamp).total_seconds()
        is_fresh = 0.0 <= delay <= max_delay_seconds
        return is_fresh, delay


class SportradarProvider(SportsDataProvider):
    """Adapter for Sportradar Soccer v4 API.
    
    Sportradar uses meter-based coordinates on standard 105m x 68m pitch dimensions.
    """

    PITCH_LENGTH_METERS = 105.0
    PITCH_WIDTH_METERS = 68.0

    def provider_id(self) -> str:
        return "sportradar"

    def get_attribution(self) -> str:
        return "Live match data provided by Sportradar. Official Telemetry."

    def normalize_coordinates(self, raw_x: float, raw_y: float) -> tuple[float, float]:
        # Convert meters to 0-100 scale
        norm_x = (raw_x / self.PITCH_LENGTH_METERS) * 100.0
        norm_y = (raw_y / self.PITCH_WIDTH_METERS) * 100.0
        return clamp(norm_x), clamp(norm_y)

    def verify_freshness(self, timestamp: datetime, max_delay_seconds: int = 30) -> tuple[bool, float]:
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        delay = (now - timestamp).total_seconds()
        is_fresh = 0.0 <= delay <= max_delay_seconds
        return is_fresh, delay


class SampleSportsProvider(SportsDataProvider):
    """Fallback provider when licensed feeds are unconfigured or in demo mode."""

    def provider_id(self) -> str:
        return "sample"

    def get_attribution(self) -> str:
        return "SAMPLE DATA ONLY - Simulated event data for testing & certification."

    def normalize_coordinates(self, raw_x: float, raw_y: float) -> tuple[float, float]:
        return clamp(raw_x), clamp(raw_y)

    def verify_freshness(self, timestamp: datetime, max_delay_seconds: int = 30) -> tuple[bool, float]:
        return True, 0.0


def get_sports_provider() -> SportsDataProvider:
    """Factory returning the active sports data provider based on environment configuration."""
    settings = get_settings()
    provider_name = getattr(settings, "sports_provider", "sample").lower()
    if provider_name == "opta":
        return OptaSportsProvider()
    elif provider_name == "sportradar":
        return SportradarProvider()
    return SampleSportsProvider()
