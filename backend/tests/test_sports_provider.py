from datetime import datetime, timedelta, timezone
from app.services.sports_provider import (
    OptaSportsProvider,
    SportradarProvider,
    SampleSportsProvider,
    ApiFootballProvider,
    get_sports_provider,
    clamp,
)


def test_clamp_function():
    assert clamp(-5.0) == 0.0
    assert clamp(105.4) == 100.0
    assert clamp(55.234) == 55.23


def test_opta_provider():
    provider = OptaSportsProvider()
    assert provider.provider_id() == "opta"
    assert "Opta Sports" in provider.get_attribution()
    
    # Coordinate normalization
    x, y = provider.normalize_coordinates(45.5, 92.1)
    assert x == 45.5
    assert y == 92.1

    # Freshness
    now = datetime.now(timezone.utc)
    fresh, delay = provider.verify_freshness(now - timedelta(seconds=5), max_delay_seconds=30)
    assert fresh is True
    assert 4.0 <= delay <= 7.0

    stale, delay = provider.verify_freshness(now - timedelta(seconds=45), max_delay_seconds=30)
    assert stale is False
    assert delay >= 45.0


def test_sportradar_provider():
    provider = SportradarProvider()
    assert provider.provider_id() == "sportradar"
    assert "Sportradar" in provider.get_attribution()

    # Coordinates: 105m length, 68m width
    x, y = provider.normalize_coordinates(52.5, 34.0)
    assert round(x, 1) == 50.0
    assert round(y, 1) == 50.0


def test_api_football_provider():
    provider = ApiFootballProvider(api_key="dummy-test-key")
    assert provider.provider_id() == "api-football"
    assert "API-Football" in provider.get_attribution()

    # Test coordinate transformation for a dummy lineup
    sample_lineups = [
        {
            "team": {"name": "Real Madrid"},
            "startXI": [
                {"player": {"id": 1, "name": "Courtois", "pos": "G", "grid": "1:1"}},
                {"player": {"id": 2, "name": "Carvajal", "pos": "D", "grid": "2:1"}},
            ],
        },
        {
            "team": {"name": "Barcelona"},
            "startXI": [
                {"player": {"id": 10, "name": "Ter Stegen", "pos": "G", "grid": "1:1"}},
                {"player": {"id": 11, "name": "Kounde", "pos": "D", "grid": "2:1"}},
            ],
        },
    ]
    tactical = provider.convert_lineup_to_tactical_pitch(sample_lineups, "Real Madrid", "Barcelona")
    assert len(tactical["players"]) == 4
    # Goalkeeper of home team should be near x=8
    home_gk = next(p for p in tactical["players"] if p["name"] == "Courtois")
    assert home_gk["x"] == 8
    # Goalkeeper of away team should be near x=92
    away_gk = next(p for p in tactical["players"] if p["name"] == "Ter Stegen")
    assert away_gk["x"] == 92


def test_sports_provider_factory():
    provider = get_sports_provider()
    assert isinstance(provider, (SampleSportsProvider, OptaSportsProvider, SportradarProvider, ApiFootballProvider))
    assert provider.provider_id() in ("sample", "opta", "sportradar", "api-football")
