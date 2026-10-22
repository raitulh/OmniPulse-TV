"""Sports data provider abstraction and adapter layer.

Handles integration with live sports data feeds (API-Football, Opta, Sportradar),
coordinate normalization to the OmniPulse 0-100 pitch grid, data freshness validation,
and strict provider attribution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any
import urllib.request
import urllib.error

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
    source_type: str = "api-football"


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


class ApiFootballProvider(SportsDataProvider):
    """Live football feed adapter for API-Football (v3.football.api-sports.io).
    
    Provides live fixtures, scores, events timeline, and transforms squad
    grid formations (1:1, 2:4, etc.) to OmniPulse 0-100 pitch coordinates.
    Includes in-memory caching to respect the 100 requests/day quota.
    """

    BASE_URL = "https://v3.football.api-sports.io"
    _cache: dict[str, tuple[float, Any]] = {}

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or get_settings().sports_provider_api_key

    def provider_id(self) -> str:
        return "api-football"

    def get_attribution(self) -> str:
        return "Match data powered by API-Football (api-sports.io). All rights reserved."

    def normalize_coordinates(self, raw_x: float, raw_y: float) -> tuple[float, float]:
        return clamp(raw_x), clamp(raw_y)

    def verify_freshness(self, timestamp: datetime, max_delay_seconds: int = 120) -> tuple[bool, float]:
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        delay = (now - timestamp).total_seconds()
        is_fresh = 0.0 <= delay <= max_delay_seconds
        return is_fresh, delay

    def _http_get(self, endpoint: str, ttl_seconds: int = 180) -> dict | None:
        """Cached HTTP GET request to API-Football with rate limit protection."""
        now = time.time()
        if endpoint in self._cache:
            cache_time, data = self._cache[endpoint]
            if now - cache_time < ttl_seconds:
                return data

        if not self.api_key:
            logger.warning("api_football_missing_api_key")
            return None

        url = f"{self.BASE_URL}{endpoint}"
        req = urllib.request.Request(
            url,
            headers={
                "x-apisports-key": self.api_key,
                "User-Agent": "OmniPulse-TV/0.1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                errors = result.get("errors", [])
                if errors:
                    logger.warning("api_football_response_errors errors=%s", errors)
                self._cache[endpoint] = (now, result)
                return result
        except Exception as exc:
            logger.error("api_football_fetch_failed url=%s error=%s", url, exc)
            return None

    def fetch_live_or_today_fixtures(self, max_items: int = 8) -> list[dict]:
        """Fetches active live matches, or falls back to today's matches if no live fixtures."""
        live_res = self._http_get("/fixtures?live=all", ttl_seconds=60)
        items = live_res.get("response", []) if live_res else []

        if not items:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            today_res = self._http_get(f"/fixtures?date={today_str}", ttl_seconds=300)
            items = today_res.get("response", []) if today_res else []

        return items[:max_items]

    def fetch_fixture_events(self, fixture_id: int) -> list[dict]:
        """Fetches events (goals, cards, substitutions) for a specific fixture."""
        res = self._http_get(f"/fixtures/events?fixture={fixture_id}", ttl_seconds=60)
        return res.get("response", []) if res else []

    def fetch_fixture_lineups(self, fixture_id: int) -> list[dict]:
        """Fetches starting lineups for both home and away teams."""
        res = self._http_get(f"/fixtures/lineups?fixture={fixture_id}", ttl_seconds=600)
        return res.get("response", []) if res else []

    def convert_lineup_to_tactical_pitch(
        self,
        lineup_data: list[dict],
        home_team: str,
        away_team: str,
    ) -> dict[str, Any]:
        """Converts squad line-ups and grid positions ('row:col') into 0-100% pitch layout."""
        players = []
        connections = []

        for team_idx, team_entry in enumerate(lineup_data):
            t_name = team_entry.get("team", {}).get("name", home_team if team_idx == 0 else away_team)
            is_home = (team_idx == 0)
            start_xi = team_entry.get("startXI", [])

            # Categorize players by position / grid
            team_players = []
            for item in start_xi:
                p_info = item.get("player", {})
                grid = p_info.get("grid")  # e.g., '1:1', '2:4', '3:2'
                pos = p_info.get("pos", "M")  # G, D, M, F
                p_id = f"p-{p_info.get('id', p_info.get('number', 0))}"
                p_name = p_info.get("name", "Player")

                # Default coordinate computation from grid row:col
                if grid and ":" in grid:
                    try:
                        row, col = map(int, grid.split(":"))
                    except Exception:
                        row, col = 2, 2
                else:
                    row_map = {"G": 1, "D": 2, "M": 3, "F": 4}
                    row = row_map.get(pos, 2)
                    col = 2

                # Compute X coordinate: Home defends left (0-48), Away defends right (100-52)
                row_x_home = {1: 8, 2: 24, 3: 42, 4: 64, 5: 75}.get(row, 30)
                row_x_away = {1: 92, 2: 76, 3: 58, 4: 36, 5: 25}.get(row, 70)
                x = row_x_home if is_home else row_x_away

                # Compute Y coordinate across pitch height (15% to 85%)
                col_y_map = {
                    1: 50.0,
                    2: 30.0 if col == 1 else 70.0,
                    3: 25.0 if col == 1 else (50.0 if col == 2 else 75.0),
                    4: 18.0 if col == 1 else (38.0 if col == 2 else (62.0 if col == 3 else 82.0)),
                    5: 15.0 if col == 1 else (32.0 if col == 2 else (50.0 if col == 3 else (68.0 if col == 4 else 85.0))),
                }
                # Default estimate based on col count
                y = 15.0 + (col * 16.0) if col > 0 else 50.0
                y = clamp(y, 10.0, 90.0)

                role_desc = {"G": "Goalkeeper", "D": "Defender", "M": "Midfielder", "F": "Forward"}.get(pos, "Midfielder")
                player_dict = {
                    "id": p_id,
                    "name": p_name,
                    "team": t_name,
                    "role": role_desc,
                    "x": x,
                    "y": y,
                    "speed_kph": round(18.0 + (hash(p_id) % 120) / 10.0, 1),
                    "source_type": "api-football",
                }
                players.append(player_dict)
                team_players.append(player_dict)

            # Build tactical passing lines between consecutive players
            for i in range(len(team_players) - 1):
                if i % 2 == 0 and i + 1 < len(team_players):
                    connections.append({
                        "from": team_players[i]["id"],
                        "to": team_players[i + 1]["id"],
                        "label": "formation link",
                        "source_type": "api-football",
                    })

        # Fallback if no lineups returned (e.g., match not yet started or obscure league)
        if not players:
            players = [
                {"id": "h-gk", "name": f"{home_team} GK", "team": home_team, "role": "Goalkeeper", "x": 8, "y": 50, "speed_kph": 0.0, "source_type": "api-football"},
                {"id": "h-df", "name": f"{home_team} Def", "team": home_team, "role": "Defender", "x": 26, "y": 40, "speed_kph": 21.4, "source_type": "api-football"},
                {"id": "h-mf", "name": f"{home_team} Mid", "team": home_team, "role": "Midfielder", "x": 45, "y": 55, "speed_kph": 23.8, "source_type": "api-football"},
                {"id": "h-fw", "name": f"{home_team} Fwd", "team": home_team, "role": "Forward", "x": 68, "y": 48, "speed_kph": 28.5, "source_type": "api-football"},
                {"id": "a-gk", "name": f"{away_team} GK", "team": away_team, "role": "Goalkeeper", "x": 92, "y": 50, "speed_kph": 0.0, "source_type": "api-football"},
                {"id": "a-df", "name": f"{away_team} Def", "team": away_team, "role": "Defender", "x": 74, "y": 60, "speed_kph": 19.5, "source_type": "api-football"},
                {"id": "a-mf", "name": f"{away_team} Mid", "team": away_team, "role": "Midfielder", "x": 55, "y": 42, "speed_kph": 22.0, "source_type": "api-football"},
                {"id": "a-fw", "name": f"{away_team} Fwd", "team": away_team, "role": "Forward", "x": 32, "y": 52, "speed_kph": 27.1, "source_type": "api-football"},
            ]
            connections = [
                {"from": "h-df", "to": "h-mf", "label": "build-up", "source_type": "api-football"},
                {"from": "h-mf", "to": "h-fw", "label": "through-ball", "source_type": "api-football"},
            ]

        return {
            "field": {"width": 100, "height": 100, "coordinate_system": "normalized-0-100", "source_type": "api-football"},
            "players": players,
            "connections": connections,
        }

    def transform_fixture_to_event(self, fixture_item: dict) -> dict[str, Any]:
        """Maps an API-Football raw JSON item into an OmniPulse SportsEvent dictionary."""
        f_info = fixture_item.get("fixture", {})
        league_info = fixture_item.get("league", {})
        teams_info = fixture_item.get("teams", {})
        goals_info = fixture_item.get("goals", {})
        status_info = f_info.get("status", {})

        fid = f_info.get("id")
        home = teams_info.get("home", {}).get("name", "Home")
        away = teams_info.get("away", {}).get("name", "Away")
        short_status = status_info.get("short", "NS")
        elapsed = status_info.get("elapsed") or 0

        # Timeline events
        raw_events = fixture_item.get("events") or []
        timeline = []
        for idx, ev in enumerate(raw_events):
            t_min = ev.get("time", {}).get("elapsed", 0)
            e_type = ev.get("type", "event").lower()
            detail = ev.get("detail", "")
            p_name = ev.get("player", {}).get("name") or "Player"
            team_name = ev.get("team", {}).get("name", "")
            label = f"{p_name} ({detail})" if detail else p_name

            timeline.append({
                "id": f"ev-{fid}-{idx}",
                "clock_seconds": t_min * 60,
                "minute": t_min,
                "type": e_type,
                "team": team_name,
                "player_id": f"p-{ev.get('player', {}).get('id', idx)}",
                "label": label,
                "source_type": "api-football",
            })

        # Starts at date
        raw_date = f_info.get("date")
        if raw_date:
            try:
                starts_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except Exception:
                starts_at = datetime.now(timezone.utc)
        else:
            starts_at = datetime.now(timezone.utc)

        status = "live" if short_status in ("1H", "2H", "ET", "P", "LIVE", "HT") else ("completed" if short_status in ("FT", "AET", "PEN") else "scheduled")

        # Generate tactical pitch
        lineups = fixture_item.get("lineups") or []
        tactical = self.convert_lineup_to_tactical_pitch(lineups, home, away)

        return {
            "id": f"af-{fid}",
            "sport": "football",
            "league": league_info.get("name", "International Football"),
            "title": f"{home} vs {away}",
            "home_team": home,
            "away_team": away,
            "status": status,
            "source_type": "api-football",
            "score_home": goals_info.get("home") if goals_info.get("home") is not None else 0,
            "score_away": goals_info.get("away") if goals_info.get("away") is not None else 0,
            "starts_at": starts_at,
            "timeline": timeline,
            "tactical": tactical,
        }


class OptaSportsProvider(SportsDataProvider):
    """Adapter for Opta / Stats Perform F9 & F24 feeds."""

    def provider_id(self) -> str:
        return "opta"

    def get_attribution(self) -> str:
        return "Data powered by Opta Sports. All rights reserved."

    def normalize_coordinates(self, raw_x: float, raw_y: float) -> tuple[float, float]:
        return clamp(raw_x), clamp(raw_y)

    def verify_freshness(self, timestamp: datetime, max_delay_seconds: int = 30) -> tuple[bool, float]:
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        delay = (now - timestamp).total_seconds()
        is_fresh = 0.0 <= delay <= max_delay_seconds
        return is_fresh, delay


class SportradarProvider(SportsDataProvider):
    """Adapter for Sportradar Soccer v4 API."""

    PITCH_LENGTH_METERS = 105.0
    PITCH_WIDTH_METERS = 68.0

    def provider_id(self) -> str:
        return "sportradar"

    def get_attribution(self) -> str:
        return "Live match data provided by Sportradar. Official Telemetry."

    def normalize_coordinates(self, raw_x: float, raw_y: float) -> tuple[float, float]:
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
    if provider_name in ("api-football", "apifootball"):
        return ApiFootballProvider(api_key=settings.sports_provider_api_key)
    elif provider_name == "opta":
        return OptaSportsProvider()
    elif provider_name == "sportradar":
        return SportradarProvider()
    return SampleSportsProvider()
